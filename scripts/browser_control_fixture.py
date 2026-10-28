"""Loopback Core fixture for the React browser check; no providers or devices."""
import asyncio
from contextlib import nullcontext
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run(folder):
    key = secrets.token_urlsafe(36)
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
    )
    import uvicorn
    from jarvis.main import create_app

    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    sock.setblocking(False)
    port = sock.getsockname()[1]
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
                raise RuntimeError('Core browser fixture exited before startup')
            await asyncio.sleep(0.025)
        else:
            raise RuntimeError('Core browser fixture startup timed out')
        print(json.dumps({'url': f'http://127.0.0.1:{port}', 'key': key,
                          'source': 'temporary_core_integrations_disabled'}), flush=True)
        await done.wait()
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)
        sock.close()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='jarvis-control-browser-') as folder:
        asyncio.run(run(folder))
