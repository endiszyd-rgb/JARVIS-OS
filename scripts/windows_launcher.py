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
import urllib.request
import webbrowser


APP_ROOT = Path(__file__).resolve().parents[1]


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


def gui(server):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.title('JARVIS OS')
    root.geometry('580x360')
    root.resizable(False, False)
    root.configure(bg='#10151e')
    font = ('Segoe UI', 11)
    tk.Label(root, text='JARVIS OS', font=('Segoe UI', 25, 'bold'), bg='#10151e', fg='#f0f5ff').pack(pady=(25, 4))
    status = tk.StringVar(value='Uruchamianie lokalnego panelu…')
    tk.Label(root, textvariable=status, font=font, bg='#10151e', fg='#9eb7d5').pack(pady=8)
    tk.Label(root, text='W panelu wybierz „Klucz właściciela”.\nSkopiuj klucz przyciskiem poniżej i wklej go w pole logowania.',
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
    open_button = button('Otwórz panel', lambda: webbrowser.open(server.url))
    open_button.configure(state='disabled')
    button('Kopiuj klucz dostępu', copy_key)
    button('Otwórz folder danych', lambda: os.startfile(server.data_dir))
    tk.Label(root, text='Zamknięcie tego okna zatrzyma JARVIS. Dane pozostaną zapisane.',
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
            status.set('Działa lokalnie • ' + server.url)
            open_button.configure(state='normal')
            webbrowser.open(server.url)
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
            if not args.smoke_test:
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
            gui(server)
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
