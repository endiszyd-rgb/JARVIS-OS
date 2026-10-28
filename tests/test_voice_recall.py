import asyncio
import io
import json
import sqlite3
import wave
import pytest
from fastapi.testclient import TestClient
from wyoming.event import async_read_event,async_write_event
from wyoming.asr import Transcript
from wyoming.audio import AudioStart,AudioChunk,AudioStop
from jarvis.main import create_app
from jarvis import voice,recall

KEY='voice-recall-owner-key-32-characters'
@pytest.fixture
def client(tmp_path):
    c=TestClient(create_app(tmp_path/'db',KEY),headers={'X-Jarvis-Key':KEY});c.path=tmp_path/'db';return c

def wav(rate=16000):
    out=io.BytesIO()
    with wave.open(out,'wb') as w:w.setparams((1,2,rate,0,'NONE','NONE'));w.writeframes(b'\0\0'*1600)
    return out.getvalue()

def test_voice_disabled_and_no_auto_execution(client,monkeypatch):
    monkeypatch.setenv('JARVIS_VOICE_ENABLED','false')
    assert client.get('/api/voice/status').json()['automatic_execution'] is False
    assert client.post('/api/voice/transcribe',content=wav(),headers={'content-type':'audio/wav'}).status_code==503
    assert client.post('/api/voice/synthesize',json={'text':'Cześć'}).status_code==503
    assert client.post('/api/voice/transcribe',content=b'x').status_code==415

@pytest.mark.parametrize('data',[b'bad',wav(8000),wav()[:-4]])
def test_invalid_audio(data):
    with pytest.raises(Exception) as e:voice.pcm_from_wav(data)
    assert e.value.status_code==422

def test_request_limits(client):
    assert client.post('/api/voice/transcribe',content=b'x'*(2*1024*1024+1),headers={'content-type':'audio/wav'}).status_code==413
    assert client.post('/api/memory',content=b'x'*65537).status_code==413

def test_wyoming_real_tcp_roundtrip(monkeypatch):
    monkeypatch.setenv('JARVIS_VOICE_ENABLED','true')
    async def run():
        async def handler(reader,writer):
            try:
                first=await async_read_event(reader)
                if first.type=='transcribe':
                    while (await async_read_event(reader)).type!='audio-stop':pass
                    await async_write_event(Transcript(text='Otwórz bramę').event(),writer)
                else:
                    assert first.type=='synthesize'
                    for event in [AudioStart(rate=16000,width=2,channels=1),AudioChunk(rate=16000,width=2,channels=1,audio=b'\0\0'*100),AudioStop()]:await async_write_event(event.event(),writer)
            finally:writer.close();await writer.wait_closed()
        async with await asyncio.start_server(handler,'127.0.0.1',0) as server:
            uri='tcp://127.0.0.1:'+str(server.sockets[0].getsockname()[1])
            monkeypatch.setenv('WYOMING_STT_URI',uri);monkeypatch.setenv('WYOMING_TTS_URI',uri)
            result=await voice.transcribe(wav())
            assert result['text']=='Otwórz bramę' and result['executed'] is False
            assert voice.pcm_from_wav(await voice.synthesize('Cześć'))==b'\0\0'*100
    asyncio.run(run())

def test_wyoming_rejects_public_and_huge_payload(monkeypatch):
    monkeypatch.setenv('WYOMING_STT_URI','tcp://8.8.8.8:10300')
    async def run():
        with pytest.raises(Exception) as e:await voice.target('WYOMING_STT_URI')
        assert e.value.status_code==403
        reader=voice.LimitedReader(None)
        with pytest.raises(ValueError):await reader.readexactly(1024*1024+1)
    asyncio.run(run())

def test_memory_fts_migration_and_delete(client):
    a=client.post('/api/memory',json={'text':'Warsztat: wymiana oleju silnika'}).json()['id']
    client.post('/api/memory',json={'text':'Kolacja w domu'})
    result=client.post('/api/memory/search',json={'query':'oleju OR " ()'}).json()
    assert result['results'][0]['id']==a and result['lexical_engine']=='fts5'
    client.delete('/api/memory/'+a)
    assert not client.post('/api/memory/search',json={'query':'oleju'}).json()['results']
    assert client.post('/api/memory/search',json={'query':'x','mode':'invalid'}).status_code==422

def test_hybrid_index_and_model_namespace(client,monkeypatch):
    monkeypatch.setenv('JARVIS_EMBEDDINGS_ENABLED','true');monkeypatch.setenv('OLLAMA_EMBED_MODEL','local-embed')
    async def fake(texts,config):return [[1.,0.] for _ in texts]
    monkeypatch.setattr(recall,'embed',fake)
    ident=client.post('/api/memory',json={'text':'Potrzebuję naprawy samochodu'}).json()['id']
    assert client.post('/api/memory/index',json={}).json()['indexed']==1
    assert client.post('/api/memory/index',json={}).json()['indexed']==0
    result=client.post('/api/memory/search',json={'query':'auto','mode':'hybrid'}).json()
    assert result['results'][0]['id']==ident and result['results'][0]['sources']==['semantic']
    monkeypatch.setenv('MEMORY_EMBEDDING_REVISION','2')
    assert not client.post('/api/memory/search',json={'query':'auto','mode':'hybrid'}).json()['results']
    client.delete('/api/memory/'+ident)
    with sqlite3.connect(client.path) as db:assert db.execute('SELECT COUNT(*) FROM memory_vectors').fetchone()[0]==0

def test_semantic_explicit_disabled_and_failed(client,monkeypatch):
    monkeypatch.setenv('JARVIS_EMBEDDINGS_ENABLED','false')
    assert client.post('/api/memory/index',json={}).status_code==503
    monkeypatch.setenv('JARVIS_EMBEDDINGS_ENABLED','true');monkeypatch.setenv('OLLAMA_EMBED_MODEL','test')
    client.post('/api/memory',json={'text':'notatka'})
    async def fail(*args):raise RuntimeError('secret service error')
    monkeypatch.setattr(recall,'embed',fail)
    response=client.post('/api/memory/index',json={})
    assert response.status_code==502 and 'secret' not in response.text
    assert len(client.get('/api/memory').json())==1
