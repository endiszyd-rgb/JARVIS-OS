import asyncio
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi.testclient import TestClient
from jarvis.main import create_app
from jarvis import main

KEY='conversation-owner-test-key-32-chars'

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL','qwen2.5:3b')
    monkeypatch.setenv('OLLAMA_ALLOWED_MODELS','qwen2.5:3b,test-local:small')
    monkeypatch.setenv('JARVIS_ALLOW_CLOUD_MODELS','false')
    c=TestClient(create_app(tmp_path/'db.sqlite3',KEY),headers={'X-Jarvis-Key':KEY})
    c.path=tmp_path/'db.sqlite3'
    return c


def session(client,**values):
    r=client.post('/api/chat/sessions',json=values)
    assert r.status_code==201,r.text
    return r.json()['id']


def mock_model(monkeypatch,handler):
    original=httpx.AsyncClient
    monkeypatch.setattr(main.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))


def test_sessions_persist_rename_export_and_cascade_delete(client):
    ident=session(client,title='Warsztat')
    r=client.post('/api/chat',json={'session_id':ident,'message':'Cześć'})
    assert r.status_code==200 and r.json()['session_id']==ident
    messages=client.get(f'/api/chat/sessions/{ident}/messages').json()
    assert [m['role'] for m in messages]==['user','assistant']
    assert all(m['state']=='completed' for m in messages)
    restarted=TestClient(create_app(client.path,KEY),headers={'X-Jarvis-Key':KEY})
    assert len(restarted.get(f'/api/chat/sessions/{ident}/messages').json())==2
    assert restarted.patch(f'/api/chat/sessions/{ident}',json={'title':'Nowy tytuł'}).json()['title']=='Nowy tytuł'
    export=restarted.get(f'/api/chat/sessions/{ident}/export')
    assert export.status_code==200 and 'attachment' in export.headers['content-disposition']
    assert export.json()['messages'][0]['content']=='Cześć'
    assert 'Cześć' not in client.get('/api/audit').text
    assert client.delete(f'/api/chat/sessions/{ident}').status_code==200
    with sqlite3.connect(client.path) as db: assert db.execute('SELECT COUNT(*) FROM chat_messages').fetchone()[0]==0
    assert client.get(f'/api/chat/sessions/{ident}/messages').status_code==404


def test_context_sent_only_within_same_session_and_selected_model(client,monkeypatch):
    seen=[]
    def handler(req):
        seen.append(json.loads(req.content));return httpx.Response(200,json={'message':{'content':'Odpowiedź '+str(len(seen))}})
    mock_model(monkeypatch,handler)
    first=session(client,model='ollama',model_name='test-local:small')
    second=session(client,model='ollama',model_name='test-local:small')
    for ident,msg in [(first,'Prywatny temat A'),(first,'Kontynuuj A'),(second,'Temat B')]:
        assert client.post('/api/chat',json={'session_id':ident,'message':msg}).status_code==200
    assert seen[1]['model']=='test-local:small'
    assert [m['role'] for m in seen[1]['messages']]==['system','user','assistant','user']
    assert 'Prywatny temat A' in json.dumps(seen[1],ensure_ascii=False)
    assert 'Prywatny temat A' not in json.dumps(seen[2],ensure_ascii=False)


def test_model_allowlist_and_no_implicit_cloud(client,monkeypatch):
    monkeypatch.setenv('OLLAMA_ALLOWED_MODELS','qwen2.5:3b,remote:cloud')
    assert all(not m['cloud'] for m in client.get('/api/models').json()['models'])
    assert client.post('/api/chat',json={'message':'Test','model':'ollama','model_name':'unknown'}).status_code==403
    assert client.post('/api/chat/sessions',json={'model':'ollama','model_name':'remote:cloud'}).status_code==403
    monkeypatch.setenv('JARVIS_ALLOW_CLOUD_MODELS','true')
    assert client.post('/api/chat/sessions',json={'model':'ollama','model_name':'remote:cloud'}).status_code==201
    assert client.post('/api/chat/sessions',json={'model':'demo','model_name':'qwen2.5:3b'}).status_code==422


def test_settings_default_is_used_for_new_session(client,monkeypatch):
    p=client.post('/api/proposals',json={'kind':'settings','payload':{'name':'Andreas','model':'ollama'}}).json()['id']
    client.post(f'/api/proposals/{p}/decide',json={'approve':True})
    assert client.post('/api/chat/sessions',json={}).json()['provider']=='ollama'


def test_failed_reply_retained_as_failed_but_excluded_from_context(client,monkeypatch):
    ident=session(client,model='ollama')
    mock_model(monkeypatch,lambda req:httpx.Response(503))
    assert client.post('/api/chat',json={'session_id':ident,'message':'failed-private-turn'}).status_code==502
    messages=client.get(f'/api/chat/sessions/{ident}/messages').json()
    assert len(messages)==1 and messages[0]['state']=='failed'
    assert client.get(f'/api/chat/sessions/{ident}').json()['active_turn'] is None
    seen=[]
    def good(req):
        seen.append(json.loads(req.content));return httpx.Response(200,json={'message':{'content':'OK'}})
    # Reset to original class before replacing the factory again.
    monkeypatch.undo();mock_model(monkeypatch,good)
    assert client.post('/api/chat',json={'session_id':ident,'message':'Nowa próba'}).status_code==200
    assert 'failed-private-turn' not in json.dumps(seen)


def test_concurrent_turn_and_delete_are_blocked_until_finish(client,monkeypatch):
    ident=session(client,model='ollama')
    entered=threading.Event();release=threading.Event()
    async def handler(req):
        entered.set();await asyncio.to_thread(release.wait,5)
        return httpx.Response(200,json={'message':{'content':'OK'}})
    mock_model(monkeypatch,handler)
    with ThreadPoolExecutor(max_workers=1) as pool:
        running=pool.submit(client.post,'/api/chat',json={'session_id':ident,'message':'Pierwsza'})
        assert entered.wait(5)
        try:
            assert client.post('/api/chat',json={'session_id':ident,'message':'Druga'}).status_code==409
            assert client.delete(f'/api/chat/sessions/{ident}').status_code==409
        finally:release.set()
        assert running.result(timeout=10).status_code==200


def test_stale_turn_recovery_and_retention_preview(client):
    ident=session(client)
    with sqlite3.connect(client.path) as db:
        db.execute("UPDATE chat_sessions SET active_turn='old',active_since=0,updated=0 WHERE id=?",(ident,))
        db.execute("INSERT INTO chat_messages(session_id,turn_id,role,content,created,state) VALUES(?,'old','user','Interrupted',0,'pending')",(ident,))
    assert client.post('/api/chat',json={'session_id':ident,'message':'Odzyskaj sesję'}).status_code==200
    assert client.get(f'/api/chat/sessions/{ident}/messages').json()[0]['state']=='failed'
    with sqlite3.connect(client.path) as db:db.execute('UPDATE chat_sessions SET updated=0')
    assert client.post('/api/chat/retention',json={'days':1}).json()=={'dry_run':True,'sessions':1}
    assert len(client.get('/api/chat/sessions').json())==1
    assert client.post('/api/chat/retention',json={'days':1,'dry_run':False}).json()['sessions']==1
    assert client.get('/api/chat/sessions').json()==[]


def test_context_is_bounded(client,monkeypatch):
    ident=session(client,model='ollama');seen=[]
    def handler(req):
        seen.append(json.loads(req.content));return httpx.Response(200,json={'message':{'content':'x'*5000}})
    mock_model(monkeypatch,handler)
    for i in range(7):assert client.post('/api/chat',json={'session_id':ident,'message':'m'*5000}).status_code==200
    assert sum(len(m['content']) for m in seen[-1]['messages'][1:-1])<=24000
    assert len(client.get(f'/api/chat/sessions/{ident}/messages?limit=3&offset=2').json())==3


def test_scoped_services_cannot_read_chat_history(client):
    token=client.post('/api/security/tokens',json={'name':'n8n','scopes':['status:read']}).json()['token']
    assert client.get('/api/chat/sessions',headers={'X-Jarvis-Key':token}).status_code==403
