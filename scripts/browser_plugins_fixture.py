"""Disposable Core and genuine loopback OpenAPI service for browser verification.

The remote counter excludes its fixture inspection route. No models, provider
accounts, physical devices, production data, or external hosts are used.
"""
import asyncio
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run(folder):
    key = secrets.token_urlsafe(36)
    plugin_secret = secrets.token_urlsafe(36)
    secret_env = 'JARVIS_PLUGIN_SECRET_BROWSER_FIXTURE'
    requests = []
    lock = threading.Lock()
    result_label = '<img src=x onerror="window.__pluginXss=true"> Synthetic read 7'

    class Remote(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status, payload):
            content = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.path == '/_fixture_status':
                with lock:
                    snapshot = list(requests)
                self.reply(200, {'requests': snapshot, 'count': len(snapshot)})
                return
            authorized = self.headers.get('Authorization') == 'Bearer ' + plugin_secret
            with lock:
                requests.append({'method': 'GET', 'path': self.path, 'authorized': authorized})
            if self.path != '/items/7':
                self.reply(404, {'error': 'Unknown synthetic fixture route'})
            elif not authorized:
                self.reply(401, {'error': 'Synthetic plugin credential missing'})
            else:
                self.reply(200, {'item': 7, 'label': result_label, 'source': 'genuine_loopback_http'})

        def do_POST(self):
            with lock:
                requests.append({'method': 'POST', 'path': self.path, 'authorized': False})
            self.reply(405, {'error': 'Fixture allows only an explicit GET'})

    remote = ThreadingHTTPServer(('127.0.0.1', 0), Remote)
    remote.daemon_threads = True
    remote_thread = threading.Thread(target=remote.serve_forever, daemon=True)
    remote_thread.start()
    os.environ.update(
        JARVIS_DB=str(Path(folder) / 'core.db'), JARVIS_API_KEY=key,
        JARVIS_POSTGRES_DSN='', JARVIS_SQLITE_TIMEOUT_SECONDS='15',
        JARVIS_POSTGRES_CONNECT_TIMEOUT_SECONDS='5',
        JARVIS_POSTGRES_STATEMENT_TIMEOUT_MS='5000',
        JARVIS_POSTGRES_LOCK_TIMEOUT_MS='1000', JARVIS_SESSION_MINUTES='60',
        JARVIS_API_REQUESTS_PER_MINUTE='1000',
        JARVIS_LOGIN_ATTEMPTS_PER_MINUTE='30', JARVIS_CORS_ORIGINS='',
        JARVIS_VOICE_ENABLED='false', JARVIS_RECEPTION_AI_ENABLED='false',
        JARVIS_EMBEDDINGS_ENABLED='false', TWILIO_WEBHOOK_ENABLED='false',
        HA_READONLY_ENABLED='false', AUTOLOGIKA_READONLY_ENABLED='false',
        AUTOLOGIKA_SNAPSHOT_ENABLED='false', JARVIS_ALLOW_CLOUD_MODELS='false',
        JARVIS_NETWORK_ALLOWLIST='127.0.0.0/8,::1/128',
    )
    os.environ[secret_env] = plugin_secret
    import uvicorn
    from jarvis.main import create_app

    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    sock.setblocking(False)
    server = uvicorn.Server(uvicorn.Config(create_app(Path(folder) / 'core.db', key),
        log_level='error', access_log=False, proxy_headers=False))
    server.capture_signals = lambda: nullcontext()
    done = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(signum, done.set)
        except (NotImplementedError, RuntimeError):
            pass
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(300):
            if server.started:
                break
            if task.done():
                raise RuntimeError('Plugin browser Core exited before startup')
            await asyncio.sleep(0.025)
        else:
            raise RuntimeError('Plugin browser Core startup timed out')
        print(json.dumps({
            'url': f'http://127.0.0.1:{sock.getsockname()[1]}', 'key': key,
            'plugin_origin': f'http://127.0.0.1:{remote.server_port}',
            'secret_env': secret_env, 'plugin_secret': plugin_secret,
            'source': 'temporary_core_genuine_loopback_openapi',
        }), flush=True)
        await done.wait()
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)
        sock.close()
        await asyncio.to_thread(remote.shutdown)
        remote.server_close()
        remote_thread.join(timeout=2)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='jarvis-plugins-browser-') as folder:
        asyncio.run(run(folder))
