"""No-I/O owner gating and strict API input for optional PostgreSQL memory."""
from fastapi.testclient import TestClient
import pytest
from jarvis.main import create_app

KEY='synthetic-memory-api-owner-key-32chars'
OWNER={'X-Jarvis-Key':KEY}

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('JARVIS_POSTGRES_DSN','')
    monkeypatch.setenv('JARVIS_POSTGRES_MEMORY_ENABLED','false')
    with TestClient(create_app(tmp_path/'core.db',KEY),headers=OWNER) as c:yield c


def test_disabled_memory_status_avoids_pg_and_legacy_sqlite_remains_available(client,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('Disabled memory must not contact PostgreSQL')
    monkeypatch.setattr(client.app.state.postgres_memory,'status',forbidden)
    for prefix in ('/api','/api/v1'):
        assert client.get(prefix+'/storage/memory/status').json()=={'enabled':False,'status':'disabled','memory_schema_version':None}
        assert client.get(prefix+'/storage/memory').status_code==503
        assert client.post(prefix+'/storage/memory',json={'content':'Synthetic'}).status_code==503
        assert client.post(prefix+'/storage/memory/search',json={'query':'Synthetic'}).status_code==503
    assert client.post('/api/memory',json={'text':'Existing SQLite preserved'}).status_code==201
    assert client.get('/ready').status_code==200


@pytest.mark.parametrize('body',[{'content':'Note','owner_id':'forged'},{'content':'Note','subject':'forged'},
 {'content':'Note','embedding':[1,0]},{'content':'Note','category':'invalid category'},
 {'content':'Note','source':'generated_verified'}, {'content':'x'*8001}])
def test_owner_namespace_and_vectors_cannot_be_injected_in_create(client,body):
    assert client.post('/api/storage/memory',json=body).status_code==422


def test_service_and_unidentified_callers_cannot_use_memory_api(client):
    assert client.get('/api/storage/memory/status',headers={'X-Jarvis-Key':'invalid'}).status_code==401
    token=client.post('/api/security/tokens',json={'name':'Reader','scopes':['status:read']}).json()['token']
    assert client.get('/api/storage/memory/status',headers={'X-Jarvis-Key':token}).status_code==403


def test_invalid_activation_flag_returns_sanitized_error(client,monkeypatch):
    monkeypatch.setenv('JARVIS_POSTGRES_MEMORY_ENABLED','invalid-private-config')
    result=client.get('/api/storage/memory/status')
    assert result.status_code==503 and 'invalid-private-config' not in result.text


def test_conversation_routes_respect_disabled_flag_and_do_not_match_record_id(client):
    ident='00000000-0000-4000-8000-000000000001'
    for prefix in ('/api','/api/v1'):
        assert client.get(prefix+'/storage/memory/conversations').status_code==503
        assert client.post(prefix+'/storage/memory/conversations',json={'model':'ollama'}).status_code==503
        assert client.get(prefix+'/storage/memory/conversations/'+ident+'/messages').status_code==503
        assert client.post(prefix+'/storage/memory/conversations/'+ident+'/turns',json={'revision':0,'message':'Hello'}).status_code==503


@pytest.mark.parametrize('extra',[{'role':'owner'},{'input_mode':'voice'},{'workshop_id':'00000000-0000-4000-8000-000000000001'},
 {'model':'openai'},{'allow_cloud_context':'true'},{'memory_refs':[{'id':'invalid','revision':0}]}])
def test_conversation_turn_cannot_change_mode_scope_model_or_authority(client,extra):
    response=client.post('/api/storage/memory/conversations/00000000-0000-4000-8000-000000000001/turns',json={'revision':0,'message':'Hello',**extra})
    assert response.status_code==422
