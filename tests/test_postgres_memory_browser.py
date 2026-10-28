"""Optional actual Chromium -> Core TCP -> guarded PG -> synthetic LLM.

Only collected by --memory --browser in the isolated database runner.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import pytest
import uvicorn
from test_postgres_memory_integration import database,memory_client,owner
from test_postgres_context_integration import llm_server
pytestmark=pytest.mark.skipif(os.environ.get('JARVIS_TEST_MEMORY_BROWSER')!='true',reason='Use scripts/check_postgres.py --memory --browser')


def test_real_chromium_memory_profile_crud_context_and_mobile(memory_client,monkeypatch):
    c=memory_client;_,headers=owner(c,'browser.pg')
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128);sock.setblocking(False)
    origin=f'http://127.0.0.1:{sock.getsockname()[1]}'
    server=uvicorn.Server(uvicorn.Config(c.app,log_level='warning',access_log=False,proxy_headers=False))
    thread=threading.Thread(target=lambda:asyncio.run(server.serve(sockets=[sock])),daemon=True);thread.start()
    try:
        deadline=time.monotonic()+10
        while not server.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(0.01)
        assert server.started
        with llm_server(monkeypatch) as seen:
            result=subprocess.run(['node','scripts/check_postgres_memory_browser.cjs'],cwd=Path(__file__).resolve().parents[1],
                input=json.dumps({'url':origin,'token':headers['X-Jarvis-Key']}),text=True,capture_output=True,timeout=90)
            # Never print credentials or the subprocess's DOM/request data on failure.
            assert result.returncode==0,'Browser check failed: '+result.stderr[-1800:].replace(headers['X-Jarvis-Key'],'[REDACTED]')
            assert len(seen)==2
            assert 'PROFILE BROWSER STYLE' in seen[0]['messages'][0]['content']
            assert 'BROWSER PG NOTE' in seen[0]['messages'][0]['content']
            assert 'tools' not in seen[0]
    finally:
        server.should_exit=True;thread.join(timeout=10)
        if thread.is_alive():server.force_exit=True;thread.join(timeout=3)
        sock.close();assert not thread.is_alive()
