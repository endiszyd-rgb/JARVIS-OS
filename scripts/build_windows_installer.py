"""Build an offline per-user installer using an explicit Python 3.12 runtime."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or sys.platform != 'win32':
        raise SystemExit('Build with Windows Python 3.12')
    output = args.output.resolve()
    stage = output / 'payload'
    if stage.exists():
        raise SystemExit('Use a fresh output directory; existing builds are never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(['npm.cmd', '--prefix', str(ROOT / 'frontend'), 'run', 'build'], check=True, cwd=ROOT)
    runtime = stage / 'runtime'
    shutil.copytree(args.runtime, runtime, ignore=shutil.ignore_patterns('site-packages', '__pycache__', '*.pyc', 'include', 'libs', 'Scripts'))
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
    exe = output / 'JARVIS-OS-0.10.4-Setup-x64.exe'
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (output / (exe.name + '.sha256')).write_text(digest + '  ' + exe.name + '\n', encoding='ascii')
    print(json.dumps({'installer': str(exe), 'sha256': digest, 'bytes': exe.stat().st_size}))


if __name__ == '__main__':
    main()
