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
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_RELEASES = 'https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest'
RUNTIME_ASSET = re.compile(r'^cpython-3\.12\.\d+\+\d+-x86_64-pc-windows-msvc-install_only\.tar\.gz$')


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
    # Production payload: no source .env, DB, model, venv or developer tooling.
    for path in stage.rglob('*'):
        if path.is_file() and (path.name == '.env' or path.suffix in ('.db', '.sqlite3', '.gguf', '.safetensors')):
            raise SystemExit('Unexpected private/runtime payload: ' + str(path))
    subprocess.run([str(args.compiler), '/DPayloadDir=' + str(stage), '/DOutputDir=' + str(output),
                    str(ROOT / 'packaging' / 'windows' / 'jarvis.iss')], check=True, cwd=ROOT)
    exe = output / installer_name()
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (output / (exe.name + '.sha256')).write_text(digest + '  ' + exe.name + '\n', encoding='ascii')
    print(json.dumps({'installer': str(exe), 'sha256': digest, 'bytes': exe.stat().st_size}))


if __name__ == '__main__':
    main()
