"""Build an offline per-user Windows installer with an explicit Python 3.12 runtime.

Usage (Windows, Python 3.12):
  python scripts/build_windows_installer.py --runtime C:\\path\\to\\python-3.12-standalone --compiler "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" --output C:\\new-folder
  python scripts/build_windows_installer.py --download-runtime --compiler ... --output ...   # fetch the runtime from python-build-standalone

The GitHub Actions workflow .github/workflows/windows-installer.yml runs the same script on a Windows runner.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import os
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_RELEASES = 'https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest'
RUNTIME_ASSET = re.compile(r'^cpython-3\.12\.\d+\+\d+-x86_64-pc-windows-msvc-install_only\.tar\.gz$')
# Camera previews: go2rtc (MIT) pinned to a release; ffmpeg LGPL static build (BtbN) for JPEG frames.
GO2RTC_RELEASE = 'https://api.github.com/repos/AlexxIT/go2rtc/releases/tags/v1.9.14'
GO2RTC_ASSET = re.compile(r'^go2rtc_win64\.zip$')
FFMPEG_RELEASE = 'https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/latest'
FFMPEG_ASSET = re.compile(r'^ffmpeg-n(\d+)\.(\d+)-latest-win64-lgpl-\d+\.\d+\.zip$')


def github_json(url):
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'jarvis-installer-build'})
    if os.environ.get('GITHUB_TOKEN'):
        request.add_header('Authorization', 'Bearer ' + os.environ['GITHUB_TOKEN'])
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download_verified(asset, target: Path) -> Path:
    """Download a GitHub release asset and check it against the SHA-256 digest GitHub computed for it."""
    digest = str(asset.get('digest') or '')
    if not digest.startswith('sha256:'):
        raise SystemExit('No SHA-256 digest published for ' + asset['name'])
    path = target / asset['name']
    urllib.request.urlretrieve(asset['browser_download_url'], path)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest.split(':', 1)[1]:
        raise SystemExit('Checksum mismatch for ' + asset['name'])
    return path


def safe_member(name):
    return not (name.startswith(('/', '\\')) or '..' in Path(name).parts or ':' in name)


def download_camera_tools(work: Path, tools: Path) -> dict:
    """Put go2rtc.exe and ffmpeg.exe (+ licences) into <payload>/tools; returns what was bundled."""
    work.mkdir(parents=True, exist_ok=True)
    tools.mkdir(parents=True, exist_ok=True)
    bundled = {}
    release = github_json(GO2RTC_RELEASE)
    asset = next(a for a in release['assets'] if GO2RTC_ASSET.match(a['name']))
    archive = download_verified(asset, work)
    with zipfile.ZipFile(archive) as bundle:
        member = next(n for n in bundle.namelist() if n.lower().endswith('go2rtc.exe') and safe_member(n))
        (tools / 'go2rtc.exe').write_bytes(bundle.read(member))
    bundled['go2rtc'] = {'release': release['tag_name'], 'asset': asset['name'], 'sha256': asset['digest'], 'license': 'MIT'}
    release = github_json(FFMPEG_RELEASE)
    candidates = [a for a in release['assets'] if FFMPEG_ASSET.match(a['name'])]
    if not candidates:
        raise SystemExit('No LGPL win64 ffmpeg build in BtbN/FFmpeg-Builds latest')
    asset = max(candidates, key=lambda a: tuple(int(x) for x in FFMPEG_ASSET.match(a['name']).groups()))
    archive = download_verified(asset, work)
    with zipfile.ZipFile(archive) as bundle:
        names = [n for n in bundle.namelist() if safe_member(n)]
        exe = next(n for n in names if n.lower().endswith('/bin/ffmpeg.exe'))
        (tools / 'ffmpeg.exe').write_bytes(bundle.read(exe))
        licence = next((n for n in names if n.lower().endswith('/license.txt')), None)
        if licence:
            (tools / 'ffmpeg-LICENSE.txt').write_bytes(bundle.read(licence))
    bundled['ffmpeg'] = {'release': release['tag_name'], 'asset': asset['name'], 'sha256': asset['digest'], 'license': 'LGPL-2.1-or-later'}
    (tools / 'THIRD-PARTY.txt').write_text(
        'Narzędzia kamer dołączone do JARVIS OS (podgląd kamer):\n\n'
        f"- go2rtc {bundled['go2rtc']['release']} — licencja MIT — https://github.com/AlexxIT/go2rtc ({bundled['go2rtc']['sha256']})\n"
        f"- FFmpeg {bundled['ffmpeg']['asset']} — licencja LGPL (patrz ffmpeg-LICENSE.txt) — build https://github.com/BtbN/FFmpeg-Builds, "
        f"kod źródłowy https://ffmpeg.org/download.html ({bundled['ffmpeg']['sha256']})\n", encoding='utf-8')
    return bundled


def installer_name():
    text = (ROOT / 'packaging' / 'windows' / 'jarvis.iss').read_text(encoding='utf-8')
    match = re.search(r'^OutputBaseFilename=(.+)$', text, re.MULTILINE)
    if not match:
        raise SystemExit('OutputBaseFilename missing in jarvis.iss')
    return match.group(1).strip() + '.exe'


def download_runtime(target: Path) -> Path:
    """Fetch the latest python-build-standalone 3.12 Windows x64 'install_only' runtime and verify its SHA-256."""
    with urllib.request.urlopen(RUNTIME_RELEASES, timeout=60) as response:
        release = json.load(response)
    assets = {asset['name']: asset for asset in release['assets']}
    names = [name for name in assets if RUNTIME_ASSET.match(name)]
    if not names:
        raise SystemExit('No Python 3.12 Windows x64 install_only runtime in the latest python-build-standalone release')
    name = sorted(names)[-1]
    archive = target / name
    target.mkdir(parents=True, exist_ok=True)
    print('Downloading', name, 'from release', release['tag_name'])
    urllib.request.urlretrieve(assets[name]['browser_download_url'], archive)
    expected = assets.get(name + '.sha256')
    if expected:
        with urllib.request.urlopen(expected['browser_download_url'], timeout=60) as response:
            digest = response.read().decode().split()[0]
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise SystemExit('Runtime archive checksum mismatch')
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if member.name.startswith(('/', '..')) or '..' in Path(member.name).parts or member.issym() or member.islnk():
                raise SystemExit('Unsafe runtime archive member: ' + member.name)
        tar.extractall(target)
    runtime = target / 'python'
    if not (runtime / 'python.exe').exists():
        raise SystemExit('Extracted runtime does not contain python.exe')
    return runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, help='Existing standalone Python 3.12 (folder containing python.exe)')
    parser.add_argument('--download-runtime', action='store_true', help='Download the runtime from python-build-standalone into the output folder')
    parser.add_argument('--compiler', type=Path, required=True, help='Path to Inno Setup ISCC.exe')
    parser.add_argument('--output', type=Path, required=True, help='Fresh output folder')
    parser.add_argument('--no-camera-tools', action='store_true', help='Do not bundle go2rtc/ffmpeg (camera previews then need an external go2rtc)')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or sys.platform != 'win32':
        raise SystemExit('Build with Windows Python 3.12')
    if bool(args.runtime) == bool(args.download_runtime):
        raise SystemExit('Give exactly one of --runtime or --download-runtime')
    output = args.output.resolve()
    stage = output / 'payload'
    if stage.exists():
        raise SystemExit('Use a fresh output directory; existing builds are never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    source_runtime = download_runtime(output / 'runtime-download') if args.download_runtime else args.runtime
    if not (source_runtime / 'python.exe').exists():
        raise SystemExit('Runtime folder must contain python.exe')
    subprocess.run(['npm.cmd', '--prefix', str(ROOT / 'frontend'), 'run', 'build'], check=True, cwd=ROOT)
    runtime = stage / 'runtime'
    shutil.copytree(source_runtime, runtime, ignore=shutil.ignore_patterns('site-packages', '__pycache__', '*.pyc', 'include', 'libs', 'Scripts'))
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-compile', '--target', str(runtime / 'Lib' / 'site-packages'),
                    '-r', str(ROOT / 'requirements.txt')], check=True, cwd=ROOT)
    app = stage / 'app'
    for name in ('jarvis', 'migrations', 'third_party'):
        shutil.copytree(ROOT / name, app / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(ROOT / 'frontend' / 'dist', app / 'frontend' / 'dist')
    (app / 'scripts').mkdir()
    shutil.copy2(ROOT / 'scripts' / 'windows_launcher.py', app / 'scripts' / 'windows_launcher.py')
    for name in ('requirements.txt', 'requirements.lock'):
        shutil.copy2(ROOT / name, app / name)
    shutil.copy2(ROOT / 'docs' / 'WINDOWS-INSTALLER.md', stage / 'START-HERE.md')
    bundled = {} if args.no_camera_tools else download_camera_tools(output / 'tools-download', stage / 'tools')
    # Production payload: no source .env, DB, model, venv or developer tooling.
    for path in stage.rglob('*'):
        if path.is_file() and (path.name == '.env' or path.suffix in ('.db', '.sqlite3', '.gguf', '.safetensors')):
            raise SystemExit('Unexpected private/runtime payload: ' + str(path))
    subprocess.run([str(args.compiler), '/DPayloadDir=' + str(stage), '/DOutputDir=' + str(output),
                    str(ROOT / 'packaging' / 'windows' / 'jarvis.iss')], check=True, cwd=ROOT)
    exe = output / installer_name()
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (output / (exe.name + '.sha256')).write_text(digest + '  ' + exe.name + '\n', encoding='ascii')
    print(json.dumps({'installer': str(exe), 'sha256': digest, 'bytes': exe.stat().st_size, 'camera_tools': bundled}))


if __name__ == '__main__':
    main()
