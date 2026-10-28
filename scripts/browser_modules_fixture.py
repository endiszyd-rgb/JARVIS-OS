"""Isolated Core with a synthetic snapshot and guarded outbound transports.

Fixture-only controls expose counters and move one approved local reminder due.
They are registered only in this temporary test application, never in Core.
"""
import asyncio
from contextlib import nullcontext
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sqlite3
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run(folder):
    key = secrets.token_urlsafe(36)
    dbfile = Path(folder) / 'core.db'
    os.environ.update(
        JARVIS_DB=str(dbfile), JARVIS_API_KEY=key,
        JARVIS_POSTGRES_DSN='', JARVIS_SQLITE_TIMEOUT_SECONDS='15',
        JARVIS_POSTGRES_CONNECT_TIMEOUT_SECONDS='5',
        JARVIS_POSTGRES_STATEMENT_TIMEOUT_MS='5000',
        JARVIS_POSTGRES_LOCK_TIMEOUT_MS='1000', JARVIS_SESSION_MINUTES='60',
        JARVIS_API_REQUESTS_PER_MINUTE='1000',
        JARVIS_LOGIN_ATTEMPTS_PER_MINUTE='40', JARVIS_CORS_ORIGINS='',
        JARVIS_VOICE_ENABLED='false', JARVIS_RECEPTION_AI_ENABLED='false',
        JARVIS_EMBEDDINGS_ENABLED='false', TWILIO_WEBHOOK_ENABLED='false',
        HA_READONLY_ENABLED='false', AUTOLOGIKA_READONLY_ENABLED='false',
        JARVIS_ALLOW_CLOUD_MODELS='false',
    )
    from examples.workshop_fixture import create_fixture
    from jarvis import network
    from jarvis.workshop import build_snapshot, digest
    source = create_fixture(Path(folder) / 'synthetic-source.db')
    source_hash = digest(source)
    snapshot = Path(folder) / 'synthetic.snapshot.sqlite3'
    build_snapshot(source, snapshot)
    snapshot_hash = digest(snapshot)
    os.environ.update(AUTOLOGIKA_SNAPSHOT_ENABLED='true', AUTOLOGIKA_SNAPSHOT_PATH=str(snapshot))
    outbound_attempts = []

    def guarded_transport(*_args, **_kwargs):
        outbound_attempts.append('network.client')
        raise network.NetworkDenied('Outbound transport is disabled in the modules browser fixture')

    network.client = guarded_transport
    import uvicorn
    from fastapi import Header, HTTPException
    from jarvis.main import create_app
    app = create_app(dbfile, key)

    def fixture_auth(value):
        if not value or not secrets.compare_digest(value, key):
            raise HTTPException(401, 'Fixture control requires its synthetic owner key')

    @app.get('/_fixture_status')
    def fixture_status(x_jarvis_key: str | None = Header(default=None)):
        fixture_auth(x_jarvis_key)
        return {'network_attempts': len(outbound_attempts),
                'source_unchanged': digest(source) == source_hash,
                'snapshot_unchanged': digest(snapshot) == snapshot_hash,
                'synthetic_snapshot': True}

    @app.post('/_fixture_make_due/{ident}')
    def make_due(ident: uuid.UUID, x_jarvis_key: str | None = Header(default=None)):
        fixture_auth(x_jarvis_key)
        with sqlite3.connect(dbfile, timeout=15) as connection:
            changed = connection.execute('UPDATE automations SET next_run=0 WHERE id=?', (str(ident),)).rowcount
        if changed != 1:
            raise HTTPException(404, 'Approved synthetic reminder not found')
        return {'id': str(ident), 'due': True, 'fixture_clock_control': True}

    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    sock.setblocking(False)
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False, proxy_headers=False))
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
                raise RuntimeError('Modules browser Core exited before startup')
            await asyncio.sleep(0.025)
        else:
            raise RuntimeError('Modules browser Core startup timed out')
        print(json.dumps({'url': f'http://127.0.0.1:{sock.getsockname()[1]}', 'key': key,
                          'source': 'temporary_core_synthetic_snapshot_outbound_guard'}), flush=True)
        await done.wait()
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)
        sock.close()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='jarvis-modules-browser-') as folder:
        asyncio.run(run(folder))
