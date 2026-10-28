"""Generated browser WAV and actual local HTTP/TCP adapters; no model inference."""
import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import threading
import uuid

import httpx
import pytest
from wyoming.event import async_read_event,async_write_event
from wyoming.asr import Transcript
from wyoming.audio import AudioStart,AudioChunk,AudioStop
from jarvis.main import create_app
from jarvis.voice import pcm_from_wav

KEY='voice-chain-owner-key-32-characters'


def browser_wav():
    node=shutil.which('node')
    if not node:pytest.skip('Node required to verify browser WAV encoder')
    root=Path(__file__).resolve().parents[1]
    return subprocess.check_output([node,'-e',"const {pcmWav}=require('./jarvis/pcm_capture.js');process.stdout.write(Buffer.from(pcmWav(new Float32Array(1600).fill(0.1))));"],cwd=root,timeout=10)


def test_javascript_encoded_wav_is_accepted_by_python_voice_adapter():
    pcm=pcm_from_wav(browser_wav())
    assert len(pcm)==3200
    assert int.from_bytes(pcm[:2],'little',signed=True)==3277


@contextmanager
def model_server():
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(request)
            result={'message':{'content':'To kontrolowana odpowiedź laboratoryjna.'}}
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(result).encode())
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',requests
    finally:server.shutdown();server.server_close();thread.join(timeout=5)


def test_two_voice_turns_through_real_local_wyoming_http_and_core(tmp_path,monkeypatch):
    raw=browser_wav()
    monkeypatch.setenv('JARVIS_VOICE_ENABLED','true')
    monkeypatch.setenv('JARVIS_NETWORK_ALLOWLIST','127.0.0.1/32')
    monkeypatch.setenv('OLLAMA_ALLOWED_MODELS','test:local')
    with model_server() as (origin,model_requests):
        monkeypatch.setenv('OLLAMA_URL',origin)
        async def run():
            stt_inputs=[];tts_inputs=[];failures=[]
            async def handler(reader,writer):
                try:
                    first=await async_read_event(reader)
                    if first.type=='transcribe':
                        audio=bytearray()
                        for _ in range(1024):
                            event=await async_read_event(reader)
                            if event.type=='audio-chunk':audio.extend(AudioChunk.from_event(event).audio)
                            if event.type=='audio-stop':break
                        stt_inputs.append(bytes(audio))
                        text='ustaw imię Robert' if len(stt_inputs)==1 else 'Jak się masz?'
                        await async_write_event(Transcript(text=text).event(),writer)
                    else:
                        assert first.type=='synthesize'
                        tts_inputs.append(first.data['text'])
                        for event in (AudioStart(rate=16000,width=2,channels=1),AudioChunk(rate=16000,width=2,channels=1,audio=b'\x01\x00'*160),AudioStop()):
                            await async_write_event(event.event(),writer)
                except Exception as exc:failures.append(exc)
                finally:writer.close();await writer.wait_closed()
            async with await asyncio.start_server(handler,'127.0.0.1',0) as server:
                port=server.sockets[0].getsockname()[1]
                monkeypatch.setenv('WYOMING_STT_URI',f'tcp://127.0.0.1:{port}')
                monkeypatch.setenv('WYOMING_TTS_URI',f'tcp://127.0.0.1:{port}')
                app=create_app(tmp_path/'chain.db',KEY)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://core',headers={'X-Jarvis-Key':KEY}) as c:
                    async def json_post(path,body):
                        r=await c.post(path,json=body);assert r.status_code in (200,201),r.text;return r.json()
                    audio_state=await json_post('/api/voice/sessions',{})
                    async def event(action):
                        nonlocal audio_state
                        audio_state=await json_post('/api/voice/sessions/'+audio_state['id']+'/events',{'event_id':str(uuid.uuid4()),'revision':audio_state['revision'],'action':action})
                    await event('activate')
                    chat_id=None
                    for _ in range(2):
                        await event('process')
                        transcript=await c.post('/api/voice/transcribe',content=raw,headers={'Content-Type':'audio/wav'})
                        assert transcript.status_code==200,transcript.text
                        assert transcript.json()['review_required'] is True and transcript.json()['executed'] is False
                        reply=await json_post('/api/chat',{'message':transcript.json()['text'],'input_mode':'voice','model':'ollama','model_name':'test:local',**({'session_id':chat_id} if chat_id else {})})
                        chat_id=reply['session_id']
                        assert reply['memory_capture']['saved']==0 and reply['model']=='ollama'
                        speech=await c.post('/api/voice/synthesize',json={'text':reply['reply']})
                        assert speech.status_code==200,speech.text
                        assert pcm_from_wav(speech.content)==b'\x01\x00'*160
                        await event('speak');await event('complete')
                        assert audio_state['state']=='listening'
                    assert (await c.get('/api/memory')).json()==[]
                    assert (await c.get('/api/proposals')).json()==[]
                    assert (await c.get('/api/status')).json()['settings']['name']=='Andreas'
                    assert (await c.get('/api/chat/sessions/'+chat_id)).json()['input_mode']=='voice'
                    assert len((await c.get('/api/chat/sessions/'+chat_id+'/messages')).json())==4
                    await event('end')
                    assert audio_state['state']=='idle'
                assert not failures
                assert stt_inputs==[pcm_from_wav(raw)]*2
                assert tts_inputs==['To kontrolowana odpowiedź laboratoryjna.']*2
        asyncio.run(run())
    assert len(model_requests)==2
    assert len(model_requests[0]['messages'])==2 and len(model_requests[1]['messages'])==4
    assert all('tools' not in request for request in model_requests)
