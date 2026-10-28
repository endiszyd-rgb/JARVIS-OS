"""A real localhost MCP/OpenAPI server, with no provider keys or devices."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from fastapi.testclient import TestClient
from jarvis.main import create_app


def test_full_core_to_local_lab_mcp_and_openapi(tmp_path,monkeypatch):
    monkeypatch.setenv('JARVIS_NETWORK_ALLOWLIST','127.0.0.0/8,::1/128')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    process=subprocess.Popen([sys.executable,'-m','uvicorn','examples.lab_server:app','--host','127.0.0.1','--port',str(port),'--log-level','error'],cwd=Path(__file__).resolve().parents[1],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            if process.poll() is not None:raise AssertionError(process.stderr.read().decode())
            try:
                with urllib.request.urlopen(origin+'/lab/temperature',timeout=.5) as r:
                    if r.status==200:break
            except Exception:time.sleep(.1)
        else:raise AssertionError('Local lab failed to start')
        key='test-lab-owner-key-32-characters'
        client=TestClient(create_app(tmp_path/'core.db',key),headers={'X-Jarvis-Key':key})
        for protocol in ['openapi','mcp']:
            pid='lab_'+protocol
            assert client.post('/api/plugins',json={'id':pid,'name':pid,'protocol':protocol}).status_code==201
            config={'endpoint':origin+('/mcp' if protocol=='mcp' else ''),'reviewed_read_tools':['read_temperature']}
            if protocol=='openapi':config['openapi']=json.loads((Path(__file__).resolve().parents[1]/'examples/lab.openapi.json').read_text())
            assert client.put(f'/api/plugins/{pid}/config',json=config).status_code==200
            client.put(f'/api/plugins/{pid}',json={'enabled':True})
            r=client.get(f'/api/plugins/{pid}/tools')
            assert r.status_code==200, r.text
            assert [t['name'] for t in r.json()]==['read_temperature']
            r=client.post(f'/api/plugins/{pid}/invoke',json={'operation':'read_temperature','arguments':{}})
            assert r.status_code==200,r.text
            assert 'synthetic_fixture' in r.text
            assert r.json()['mode']=='live_readonly'
    finally:
        process.terminate()
        process.wait(timeout=10)
        process.stderr.close()
