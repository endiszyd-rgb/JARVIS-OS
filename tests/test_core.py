import sqlite3
import pytest
from fastapi.testclient import TestClient
from jarvis.main import create_app, DOMAINS

KEY = 'unit-test-key-32-characters-long'

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path/'test.db', KEY)
    with TestClient(app, headers={'X-Jarvis-Key': KEY}) as c:
        c.dbfile = tmp_path/'test.db'
        yield c


def test_fail_closed(tmp_path):
    c = TestClient(create_app(tmp_path/'x.db', ''))
    assert c.get('/health').status_code == 200
    assert c.get('/api/status').status_code == 503


def test_auth(client):
    assert client.get('/api/status', headers={'X-Jarvis-Key': 'wrong'}).status_code == 401
    assert client.get('/api/status').json()['live_devices'] is False
    assert client.get('/api/schema').status_code == 200
    assert client.get('/openapi.json').status_code == 404


def test_ui(client):
    assert 'Control Center' in client.get('/').text
    for path in ['/ui/app.js','/ui/style.css']:
        assert client.get(path).status_code == 200
    assert "frame-ancestors 'none'" in client.get('/').headers['Content-Security-Policy']


@pytest.mark.parametrize('domain', DOMAINS)
def test_autologika_synthetic(client, domain):
    r = client.post('/api/plugins/autologika/invoke',json={'operation':domain})
    assert r.status_code == 200
    assert r.json()['source'] == 'synthetic_fixture'


def test_plugin_lifecycle(client):
    manifest = {'id':'example','name':'Test','protocol':'openapi'}
    assert client.post('/api/plugins',json=manifest).status_code == 201
    assert client.post('/api/plugins',json=manifest).status_code == 409
    path = '/api/plugins/example'
    assert client.post(path+'/invoke',json={'operation':'x'}).status_code == 409
    assert client.put(path,json={'enabled':True}).status_code == 200
    assert client.post(path+'/invoke',json={'operation':'x'}).status_code == 501
    assert client.put('/api/plugins/missing',json={'enabled':True}).status_code == 404


@pytest.mark.parametrize('pid', ['home_assistant','mqtt','twilio','n8n','voice'])
def test_no_external_side_effects(client,pid):
    for args in [{'live':True},{'dry_run':False}]:
        r=client.post(f'/api/plugins/{pid}/invoke',json={'operation':'open_gate','arguments':args})
        assert r.json()['status']=='blocked'
    r=client.post(f'/api/plugins/{pid}/invoke',json={'operation':'status'})
    assert r.json()['external_request_sent'] is False


def test_disable_builtin(client):
    client.put('/api/plugins/home_assistant',json={'enabled':False})
    assert client.post('/api/plugins/home_assistant/invoke',json={'operation':'status'}).status_code==409


def test_memory_persistence_delete(client):
    ident=client.post('/api/memory',json={'text':'Touran AVQ'}).json()['id']
    assert len(client.get('/api/memory?q=avq').json())==1
    other=TestClient(create_app(client.dbfile,KEY),headers={'X-Jarvis-Key':KEY})
    assert len(other.get('/api/memory').json())==1
    assert client.delete('/api/memory/'+ident).status_code==200
    assert client.get('/api/memory').json()==[]


def test_chat_parser_and_demo(client):
    assert client.post('/api/chat',json={'message':'Cześć'}).json()['ai_generated'] is False
    client.post('/api/chat',json={'message':'zapamiętaj mój warsztat'})
    assert client.get('/api/memory').json()[0]['text']=='mój warsztat'
    p=client.post('/api/chat',json={'message':'ustaw imię Jan'}).json()['proposal']
    assert client.get('/api/status').json()['settings']['name']=='Andreas'
    assert p['payload']['name']=='Jan'


def propose(client,kind,payload):
    r=client.post('/api/proposals',json={'kind':kind,'payload':payload})
    assert r.status_code==201
    return r.json()['id']


def test_approve_rollback(client):
    pid=propose(client,'settings',{'name':'Jan','tone':'formal','model':'demo'})
    path='/api/proposals/'+pid
    assert client.post(path+'/decide',json={'approve':True}).json()['status']=='applied'
    assert client.get('/api/status').json()['settings']['name']=='Jan'
    assert client.post(path+'/decide',json={'approve':True}).status_code==409
    assert client.post(path+'/rollback',json={}).status_code==200
    assert client.get('/api/status').json()['settings']['name']=='Andreas'


def test_old_rollback_cannot_overwrite_new_settings(client):
    ids=[]
    for name in ['Jan','Oskar']:
        pid=propose(client,'settings',{'name':name})
        ids.append(pid)
        client.post(f'/api/proposals/{pid}/decide',json={'approve':True})
    assert client.post(f'/api/proposals/{ids[0]}/rollback',json={}).status_code==409


def test_code_never_executes(client):
    pid=propose(client,'code',{'description':'delete files'})
    r=client.post(f'/api/proposals/{pid}/decide',json={'approve':True})
    assert r.json()['status']=='review_required'


def test_automation_and_no_duplicate_tick(client):
    pid=propose(client,'automation',{'title':'Test','message':'Przypomnienie','interval_minutes':1})
    client.post(f'/api/proposals/{pid}/decide',json={'approve':True})
    with sqlite3.connect(client.dbfile) as db:
        db.execute('UPDATE automations SET next_run=0')
    assert client.post('/api/automations/tick',json={}).json()['fired']==[pid]
    assert client.post('/api/automations/tick',json={}).json()['fired']==[]
    assert len(client.get('/api/notifications').json())==1
    client.post(f'/api/proposals/{pid}/rollback',json={})
    assert client.get('/api/automations').json()==[]


def test_reject(client):
    pid=propose(client,'settings',{'name':'Jan'})
    assert client.post(f'/api/proposals/{pid}/decide',json={'approve':False}).json()['status']=='rejected'
    assert client.get('/api/status').json()['settings']['name']=='Andreas'


def test_backup_integrity(client):
    client.post('/api/memory',json={'text':'backup me'})
    result=client.post('/api/backups',json={}).json()
    file=client.dbfile.parent/'backups'/result['filename']
    import hashlib
    assert hashlib.sha256(file.read_bytes()).hexdigest()==result['sha256']
    with sqlite3.connect(file) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT text FROM memory').fetchone()[0]=='backup me'


def test_validation(client):
    assert client.post('/api/plugins',json={'id':'../../bad','name':'x'}).status_code==422
    assert client.post('/api/chat',json={'message':'','extra':1}).status_code==422
    assert client.post('/api/proposals',json={'kind':'code','payload':{'shell':'rm'}}).status_code==422
    assert client.post('/api/memory',json={'text':'a'*70000}).status_code==413


def test_audit_has_no_memory_text(client):
    client.post('/api/memory',json={'text':'private-unique-content'})
    assert 'private-unique-content' not in client.get('/api/audit').text


def test_conversation_automation_requires_approval(client):
    r=client.post('/api/chat',json={'message':'przypominaj co 15 minut: Sprawdź części'})
    assert r.status_code==200
    assert r.json()['proposal']['payload']['interval_minutes']==15
    assert client.get('/api/automations').json()==[]


def test_invalid_nested_proposal_returns_422(client):
    assert client.post('/api/proposals',json={'kind':'automation','payload':{'interval_minutes':0}}).status_code==422
    assert client.post('/api/proposals',json={'kind':'settings','payload':{'tone':'invalid'}}).status_code==422
    assert client.post('/api/chat',json={'message':'ustaw imię '+'a'*90}).status_code==422


def test_ollama_request_and_response(client, monkeypatch):
    import httpx
    import json
    from jarvis import main
    original=httpx.AsyncClient
    seen=[]
    def handler(req):
        seen.append(json.loads(req.content))
        return httpx.Response(200,json={'message':{'content':'Gotowe, Andreas.'}})
    monkeypatch.setattr(main.httpx,'AsyncClient',lambda **kwargs: original(transport=httpx.MockTransport(handler),**kwargs))
    client.post('/api/memory',json={'text':'Warsztat w Policach'})
    r=client.post('/api/chat',json={'message':'Gdzie warsztat?','model':'ollama'})
    assert r.status_code==200
    assert r.json()['reply']=='Gotowe, Andreas.'
    assert 'Warsztat w Policach' in seen[0]['messages'][0]['content']
    assert 'tools' not in seen[0]


def test_ollama_error_is_not_silent_demo_fallback(client,monkeypatch):
    import httpx
    from jarvis import main
    original=httpx.AsyncClient
    monkeypatch.setattr(main.httpx,'AsyncClient',lambda **kwargs: original(transport=httpx.MockTransport(lambda req:httpx.Response(503)),**kwargs))
    assert client.post('/api/chat',json={'message':'Test','model':'ollama'}).status_code==502
