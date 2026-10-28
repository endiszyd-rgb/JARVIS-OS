"""Install/upgrade/run/uninstall in an isolated directory; preserve QA artifacts."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import winreg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('installer', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    # Never replace an already-installed user's registration during QA.
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{E66D7E5E-9928-4B46-B062-EF50F7B84341}_is1'):
            raise SystemExit('JARVIS is already installed: use a clean test Windows account')
    except FileNotFoundError:
        pass
    root = Path(tempfile.mkdtemp(prefix='jarvis-installer-qa-'))
    install = root / 'Program Files' / 'JARVIS OS'
    data = root / 'User Data'
    group = 'JARVIS OS QA ' + root.name

    def run(command):
        subprocess.run([str(x) for x in command], check=True, timeout=150,
                       creationflags=subprocess.CREATE_NO_WINDOW)

    command = [args.installer.resolve(), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
               '/SP-', '/DIR=' + str(install), '/GROUP=' + group, '/TASKS=', '/LOG=' + str(root / 'install.log')]
    run(command)
    python = install / 'runtime' / 'python.exe'
    launcher = install / 'app' / 'scripts' / 'windows_launcher.py'
    installed = False
    try:
        for index in range(2):
            run([python, '-I', launcher, '--smoke-test', '--data-dir', data,
                 '--report', root / f'run-{index}.json'])
            assert json.loads((root / f'run-{index}.json').read_text())['passed']
            if index == 0:
                key_hash = hashlib.sha256((data / '.env').read_bytes()).hexdigest()
                with sqlite3.connect(data / 'jarvis.db') as db:
                    db.execute('CREATE TABLE installer_qa(value TEXT)')
                    db.execute("INSERT INTO installer_qa VALUES ('preserve-me')")
                run(command)  # In-place reinstall/upgrade must not erase user data.
        assert hashlib.sha256((data / '.env').read_bytes()).hexdigest() == key_hash
        with sqlite3.connect(data / 'jarvis.db') as db:
            assert db.execute('SELECT value FROM installer_qa').fetchone() == ('preserve-me',)
        gui_test = root / 'gui_test.py'
        gui_test.write_text('''import runpy, sys, tkinter, webbrowser
module = runpy.run_path(sys.argv[1])
opened = []
webbrowser.open = lambda url: opened.append(url)
original = tkinter.Tk
for delay in (0, 4000):
    server = module['LocalServer'](sys.argv[2])
    def window():
        root = original()
        root.withdraw()
        root.after(delay, lambda: root.tk.call(root.protocol('WM_DELETE_WINDOW')))
        return root
    tkinter.Tk = window
    module['gui'](server)
    assert not server.thread.is_alive()
assert opened == [server.url], opened
''', encoding='utf-8')
        run([python, '-I', gui_test, launcher, data])
        installed = True
    finally:
        run([install / 'unins000.exe', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
             '/LOG=' + str(root / 'uninstall.log')])
    assert not python.exists()
    assert (data / '.env').exists() and (data / 'jarvis.db').exists()
    assert hashlib.sha256((data / '.env').read_bytes()).hexdigest() == key_hash
    report = {'passed': installed, 'installer_sha256': hashlib.sha256(args.installer.read_bytes()).hexdigest(),
              'installation': True, 'reinstall': True, 'installed_runtime_api_assets': True,
              'restart_preserves_key_database': True, 'tk_window_browser_handoff_shutdown': True,
              'uninstall_preserves_data': True, 'visual_inspection': 'not_run_tool_unavailable',
              'qa_artifacts': str(root), 'real_model_or_hardware': False}
    args.report.resolve().write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
