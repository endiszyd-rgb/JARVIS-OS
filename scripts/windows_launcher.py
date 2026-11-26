"""Local Windows launcher. No credentials in URLs, shortcuts or command lines."""
from pathlib import Path
import argparse
import asyncio
import json
import logging
import re
from logging.handlers import RotatingFileHandler
import os
import secrets
import socket
import sys
import threading
import time
import subprocess
import urllib.request
import webbrowser


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 17321
PORT_FILE = 'desktop-port.txt'


# --------------------------------------------------------------------------- desktop window
# The desktop program is the same Control Center in its own window: Microsoft Edge (or Chrome) in
# app mode — no address bar or tabs, own taskbar entry and profile. Unlike an embedded WebView2,
# this keeps speech recognition, the microphone and Windows Hello passkeys working. The web page
# stays available in parallel (browser on this PC, phone through the tunnel).

def browser_candidates(environ=None):
    environ = os.environ if environ is None else environ
    roots = [environ.get(name) for name in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA')]
    for root in filter(None, roots):
        yield Path(root) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe'
    for root in filter(None, roots):
        yield Path(root) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe'


def find_app_browser(environ=None, exists=None):
    exists = exists or (lambda path: Path(path).is_file())
    return next((path for path in browser_candidates(environ) if exists(path)), None)


def desktop_url(port, view='kiosk'):
    # localhost (not 127.0.0.1): browsers allow passkeys / Windows Hello only on a host name.
    return f'http://localhost:{int(port)}/control/#/{view}'


def app_command(browser, port, data_dir, view='kiosk'):
    profile = Path(data_dir) / 'desktop-window'
    return [str(browser), '--app=' + desktop_url(port, view), '--user-data-dir=' + str(profile),
            '--window-size=1280,860', '--no-first-run', '--no-default-browser-check', '--disable-sync']


def open_desktop(port, data_dir, view='kiosk', environ=None, runner=None):
    """Open the app window; fall back to the default browser when Edge/Chrome is missing."""
    browser = find_app_browser(environ)
    if browser is None:
        webbrowser.open(desktop_url(port, view))
        return 'browser'
    (runner or subprocess.Popen)(app_command(browser, port, data_dir, view), close_fds=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 'app'


def remember_port(data_dir, port):
    (Path(data_dir) / PORT_FILE).write_text(str(int(port)), encoding='ascii')


def remembered_port(data_dir):
    try:
        value = int((Path(data_dir) / PORT_FILE).read_text(encoding='ascii').strip())
    except (OSError, ValueError):
        return None
    return value if 1024 <= value <= 65535 else None


def prepare(data_dir):
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    env = data_dir / '.env'
    try:
        with env.open('x', encoding='utf-8') as stream:
            stream.write('JARVIS_API_KEY=' + secrets.token_urlsafe(32) + '\n')
    except FileExistsError:
        pass
    from dotenv import dotenv_values
    values = dotenv_values(env, encoding='utf-8-sig')
    key = values.get('JARVIS_API_KEY', '')
    if not key or not key.isascii() or not 24 <= len(key) <= 256 or key.startswith('replace-'):
        raise ValueError('Nieprawidłowy klucz w pliku konfiguracji .env. Istniejący plik nie został zmieniony.')
    # Prevent unrelated environment variables from activating an integration.
    for name in list(os.environ):
        if name.startswith(('JARVIS_', 'OLLAMA_', 'OPENAI_', 'AUTOLOGIKA_', 'HA_', 'TWILIO_', 'WYOMING_')):
            del os.environ[name]
    os.environ.update({k: v for k, v in values.items() if v is not None})
    os.environ['JARVIS_DB'] = str(data_dir / 'jarvis.db')
    os.chdir(data_dir)
    sys.path.insert(0, str(APP_ROOT))
    return key


class LocalServer:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir).resolve()
        self.key = prepare(self.data_dir)
        self.server = None
        self.error = False
        self.thread = None
        self.stopping = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # A stable port keeps browser-side choices (remembered owner key, microphone permission)
        # valid between restarts; fall back to a free port when it is taken.
        preferred = os.environ.get('JARVIS_PORT', str(DEFAULT_PORT))
        try:
            self.sock.bind(('127.0.0.1', int(preferred)))
        except (OSError, ValueError):
            self.sock.bind(('127.0.0.1', 0))
        self.port = self.sock.getsockname()[1]
        self.url = f'http://127.0.0.1:{self.port}/control/'

    def start(self):
        def run():
            try:
                import uvicorn
                from jarvis.main import app
                config = uvicorn.Config(app, host='127.0.0.1', port=self.port,
                                        proxy_headers=False, access_log=False,
                                        log_config=None, timeout_graceful_shutdown=8)
                self.server = uvicorn.Server(config)
                if self.stopping.is_set():
                    return
                asyncio.run(self.server.serve(sockets=[self.sock]))
            except Exception:
                self.error = True
                logging.exception('Local server could not start')
            finally:
                self.sock.close()
        self.thread = threading.Thread(target=run, name='jarvis-local-server', daemon=True)
        self.thread.start()

    def ready(self):
        return self.server is not None and self.server.started and self.thread.is_alive()

    def stop(self):
        self.stopping.set()
        if self.server is not None:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=12)
        else:
            self.sock.close()


def smoke(server):
    """Exercise installed runtime without opening a browser or showing secrets."""
    server.start()
    deadline = time.monotonic() + 40
    try:
        while not server.ready():
            if server.error or time.monotonic() > deadline:
                raise RuntimeError('Server readiness timeout')
            time.sleep(0.1)
        base = server.url.removesuffix('/control/')
        for route in ('/ready', '/control/'):
            with urllib.request.urlopen(base + route, timeout=5) as response:
                assert response.status == 200
                if route == '/control/':
                    html = response.read().decode('utf-8')
        assets = re.findall(r'(?:src|href)="(/control/assets/[^"]+)"', html)
        assert any(item.endswith('.js') for item in assets)
        assert any(item.endswith('.css') for item in assets)
        for asset in assets:
            with urllib.request.urlopen(base + asset, timeout=5) as response:
                assert response.status == 200 and len(response.read()) > 0
        request = urllib.request.Request(base + '/api/v1/status', headers={'X-Jarvis-Key': server.key})
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
        return {'passed': True, 'host': '127.0.0.1', 'runtime': sys.version.split()[0],
                'control_ui': True, 'authenticated_api': True, 'data_directory': str(server.data_dir)}
    finally:
        server.stop()


def gui(server, minimized=False):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.title('JARVIS OS — serwer')
    root.geometry('620x470')
    root.resizable(False, False)
    root.configure(bg='#10151e')
    font = ('Segoe UI', 11)
    tk.Label(root, text='JARVIS OS', font=('Segoe UI', 25, 'bold'), bg='#10151e', fg='#f0f5ff').pack(pady=(25, 4))
    status = tk.StringVar(value='Uruchamianie lokalnego panelu…')
    tk.Label(root, textvariable=status, font=font, bg='#10151e', fg='#9eb7d5').pack(pady=8)
    tk.Label(root, text='JARVIS otwiera się w osobnym oknie programu. Ta sama strona działa równolegle\n'
                        'w przeglądarce i na telefonie. Pierwsze logowanie: „Klucz właściciela” → skopiuj klucz poniżej.',
             font=font, bg='#10151e', fg='#d3deed').pack(pady=12)
    def copy_key():
        root.clipboard_clear()
        root.clipboard_append(server.key)
        status.set('Klucz skopiowany. Wklej go wyłącznie w lokalnym panelu JARVIS.')
    def button(text, command):
        item = tk.Button(root, text=text, command=command, font=font, bg='#26364c', fg='white',
                         activebackground='#395674', activeforeground='white', relief='flat', padx=18, pady=7)
        item.pack(pady=4)
        return item
    open_button = button('Otwórz program JARVIS', lambda: open_desktop(server.port, server.data_dir))
    voice_button = button('Otwórz w przeglądarce', lambda: webbrowser.open(desktop_url(server.port, 'dashboard')))
    voice_button.configure(state='disabled')
    open_button.configure(state='disabled')
    button('Kopiuj klucz dostępu', copy_key)
    button('Otwórz folder danych', lambda: os.startfile(server.data_dir))
    tk.Label(root, text='Zamknięcie okna programu nie wyłącza JARVIS. Zamknięcie TEGO okna zatrzyma serwer.',
             font=('Segoe UI', 9), bg='#10151e', fg='#8196b0').pack(pady=12)
    def close():
        status.set('Zatrzymywanie…')
        root.update_idletasks()
        server.stop()
        try:
            if root.clipboard_get() == server.key:
                root.clipboard_clear()
        except tk.TclError:
            pass
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    deadline = time.monotonic() + 40
    def poll():
        if server.ready():
            status.set('Działa • ' + desktop_url(server.port, '').removesuffix('#/'))
            open_button.configure(state='normal')
            voice_button.configure(state='normal')
            try:
                remember_port(server.data_dir, server.port)
            except OSError:
                logging.warning('Cannot store the desktop port')
            if minimized:
                root.iconify()
            else:
                open_desktop(server.port, server.data_dir)
        elif server.error or time.monotonic() > deadline:
            status.set('Nie udało się uruchomić. Sprawdź launcher.log w folderze danych.')
            messagebox.showerror('JARVIS OS', 'Uruchomienie nie powiodło się. Szczegóły: launcher.log.', parent=root)
        else:
            root.after(150, poll)
    server.start()
    root.after(150, poll)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=Path(os.getenv('LOCALAPPDATA', Path.home())) / 'JARVIS OS' / 'data')
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--minimized', action='store_true', help='Start the server only (autostart); the window opens from the shortcut')
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.WARNING, handlers=[RotatingFileHandler(
        args.data_dir / 'launcher.log', maxBytes=1_000_000, backupCount=2, encoding='utf-8')])
    # Per-data-directory OS mutex prevents concurrent launchers using the same DB.
    mutex = None
    if os.name == 'nt':
        import ctypes
        import hashlib
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        name = 'Local\\JarvisOS-' + hashlib.sha256(str(args.data_dir.resolve()).lower().encode()).hexdigest()
        mutex = kernel.CreateMutexW(None, False, name)
        if not mutex:
            raise OSError('Cannot create launcher mutex')
        if ctypes.get_last_error() == 183:
            # Already running: the shortcut simply opens another program window.
            port = remembered_port(args.data_dir)
            if not args.smoke_test and not args.minimized:
                if port:
                    open_desktop(port, args.data_dir)
                else:
                    from tkinter import messagebox
                    messagebox.showinfo('JARVIS OS', 'JARVIS jest już uruchomiony. Otwórz jego okno na pasku zadań.')
            return 2
    try:
        server = LocalServer(args.data_dir)
        if args.smoke_test:
            result = smoke(server)
            if args.report:
                args.report.resolve().write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        else:
            gui(server, minimized=args.minimized)
    except Exception:
        logging.exception('Launcher failed')
        if not args.smoke_test:
            from tkinter import messagebox
            messagebox.showerror('JARVIS OS', 'Nie można uruchomić JARVIS. Sprawdź konfigurację i launcher.log w folderze danych.')
        return 1
    finally:
        if mutex:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(mutex)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
