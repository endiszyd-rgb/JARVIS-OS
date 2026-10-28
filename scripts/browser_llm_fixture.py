"""Disposable Core and genuine loopback synthetic cloud protocol; no inference."""
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
    provider_secret = secrets.token_urlsafe(36)
    requests = []
    lock = threading.Lock()
    result_label = '<img src=x onerror="window.__jarvisXss=true"> Odpowiedź syntetycznej chmury.'
    class Remote(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def reply(self,status,payload):
            content=json.dumps(payload).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        def do_GET(self):
            if self.path=='/_fixture_status':
                with lock: data=list(requests)
                self.reply(200,{'count':len(data),'requests':data});return
            self.reply(404,{})
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            authorized=self.headers.get('Authorization')=='Bearer '+provider_secret
            with lock: requests.append({'path':self.path,'authorized':authorized,'model':body.get('model'),'max_output':body.get('max_completion_tokens'),'store':body.get('store'),'stream':body.get('stream'),'tools_sent':'tools' in body})
            if self.path!='/v1/chat/completions' or not authorized: self.reply(403,{});return
            self.reply(200,{'model':'gpt-5.4-mini-2026-03-17','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':result_label}}],'usage':{'prompt_tokens':12,'completion_tokens':8}})

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
        AUTOLOGIKA_SNAPSHOT_ENABLED='false', JARVIS_ALLOW_CLOUD_MODELS='true', JARVIS_OPENAI_ENABLED='true',
        JARVIS_OPENAI_API_KEY=provider_secret, JARVIS_OPENAI_MODEL='gpt-5.4-mini-2026-03-17',
        JARVIS_OPENAI_URL=f'http://127.0.0.1:{remote.server_port}',
        JARVIS_OPENAI_INPUT_USD_PER_MILLION='0.75', JARVIS_OPENAI_OUTPUT_USD_PER_MILLION='4.5',
        JARVIS_OPENAI_MAX_REQUEST_USD='1', JARVIS_LLM_MAX_OUTPUT_TOKENS='1024',
        JARVIS_NETWORK_ALLOWLIST='127.0.0.0/8,::1/128',
    )
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
            'provider_origin': f'http://127.0.0.1:{remote.server_port}',
            'provider_secret': provider_secret,
            'source': 'temporary_core_synthetic_cloud_no_inference',
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
    with tempfile.TemporaryDirectory(prefix='jarvis-llm-browser-') as folder:
        asyncio.run(run(folder))
