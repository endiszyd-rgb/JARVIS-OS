"""Exercise the packaged server command over TCP: forwarded headers cannot reset quotas."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError,URLError
from urllib.request import ProxyHandler,Request,build_opener

ROOT=Path(__file__).resolve().parents[1]
KEY='security-server-test-owner-key-32-characters'


def test_packaged_uvicorn_command_limits_real_peer_despite_forwarded_headers(tmp_path):
    line=next(line for line in (ROOT/'Dockerfile').read_text().splitlines() if line.startswith('CMD '))
    command=json.loads(line[4:]);command[0]=sys.executable
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
    command[command.index('--host')+1]='127.0.0.1'
    command[command.index('--port')+1]=str(port)
    env=dict(os.environ,JARVIS_DB=str(tmp_path/'server.db'),JARVIS_API_KEY=KEY,
             JARVIS_API_REQUESTS_PER_MINUTE='2',JARVIS_LOGIN_ATTEMPTS_PER_MINUTE='2',JARVIS_CORS_ORIGINS='')
    for name in ('JARVIS_RECEPTION_AI_ENABLED','JARVIS_VOICE_ENABLED','JARVIS_EMBEDDINGS_ENABLED',
                 'TWILIO_WEBHOOK_ENABLED','HA_READONLY_ENABLED','AUTOLOGIKA_READONLY_ENABLED','AUTOLOGIKA_SNAPSHOT_ENABLED'):
        env[name]='false'
    opener=build_opener(ProxyHandler({}));origin=f'http://127.0.0.1:{port}'
    def request(path,headers=None):
        try:response=opener.open(Request(origin+path,headers=headers or {}),timeout=1)
        except HTTPError as exc:response=exc
        with response:return response.status,response.read()
    log=tmp_path/'server.log'
    with log.open('w') as output:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=output,stderr=output)
        try:
            deadline=time.monotonic()+12
            while True:
                try:
                    if request('/ready')[0]==200:break
                except (OSError,URLError):pass
                assert process.poll() is None,log.read_text()
                assert time.monotonic()<deadline,log.read_text()
                time.sleep(0.04)
            results=[request(path,{'X-Jarvis-Key':KEY,'X-Forwarded-For':f'203.0.113.{index}',
                                  'Forwarded':f'for=198.51.100.{index}'})[0]
                     for index,path in enumerate(('/api/status','/api/v1/status','/api/status'),1)]
            assert results==[200,200,429]
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=5)
