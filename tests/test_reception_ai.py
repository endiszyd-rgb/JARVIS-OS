import asyncio
import json
import sqlite3
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from jarvis.main import create_app
from jarvis import reception_ai

KEY='reception-ai-owner-test-key-32-characters'
TEXT='Saab 9-3, nie działają hamulce. Jestem Adam.'

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('JARVIS_RECEPTION_AI_ENABLED','true')
    monkeypatch.setenv('OLLAMA_RECEPTION_MODEL','test:local')
    monkeypatch.setenv('OLLAMA_ALLOWED_MODELS','test:local')
    monkeypatch.setenv('OLLAMA_RECEPTION_URL','http://127.0.0.1:11434')
    c=TestClient(create_app(tmp_path/'core.db',KEY),headers={'X-Jarvis-Key':KEY});c.path=tmp_path/'core.db';return c

def start(c):return c.post('/api/reception/calls',json={}).json()
def body(text=TEXT,revision=0):return {'event_id':str(uuid.uuid4()),'revision':revision,'text':text}
def assessment(**changes):
    result={'kind':'crisis','confidence':'high','evidence':[{'message_index':0,'quote':'nie działają hamulce'}],
            'facts':[{'field':'vehicle','value':'Saab 9-3','message_index':0,'quote':'Saab 9-3'},{'field':'name','value':'Adam','message_index':0,'quote':'Jestem Adam.'}]}
    result.update(changes);return result

def transport(monkeypatch,result,inspect=None):
    def handle(req):
        if inspect:inspect(req)
        return httpx.Response(200,json={'done':True,'message':{'content':json.dumps(result,ensure_ascii=False)}})
    monkeypatch.setattr(reception_ai.network,'client',lambda *args,**kw:httpx.AsyncClient(transport=httpx.MockTransport(handle)))

def test_model_schema_and_no_private_context(client,monkeypatch):
    client.post('/api/memory',json={'text':'PERSONAL SECRET'})
    call=start(client)
    def inspect(req):
        data=json.loads(req.content)
        assert req.url.path=='/api/chat' and data['model']=='test:local'
        assert data['stream'] is False and data['format']['additionalProperties'] is False
        assert 'tools' not in data and 'PERSONAL SECRET' not in str(data)
        assert data['messages'][1]['role']=='user'
    transport(monkeypatch,assessment(),inspect)
    result=client.post('/api/reception/calls/'+call['id']+'/ai-turn',json=body())
    assert result.status_code==200,result.text
    result=result.json()
    assert result['facts']['vehicle']=='Saab 9-3' and result['analysis']['source']=='ollama_evidence_checked'
    assert result['state']=='reception'  # Owner availability is disabled by default, despite model urgency.
    assert result['decision']['eligible_for_owner_contact'] is False
    assert result['notifications_sent'] is False and result['calls_placed'] is False
    assert len(client.get('/api/memory').json())==1

@pytest.mark.parametrize('update',[
 {'evidence':[{'message_index':0,'quote':'invented threat'}]},
 {'evidence':[{'message_index':99,'quote':'nie działają hamulce'}]},
 {'evidence':[]},
 {'facts':[{'field':'vehicle','value':'BMW','quote':'Saab 9-3','message_index':0}]},
 {'facts':[{'field':'phone','value':'+48500111222','quote':'Jestem Adam.','message_index':0}]},
 {'facts':[{'field':'owner_number','value':'Adam','quote':'Jestem Adam.','message_index':0}]},
 {'facts':[{'field':'name','value':'Adam','quote':'Jestem Adam.','message_index':0}]*2},
 {'kind':'transfer_now'},
 {'execute':'open_gate'}
])
def test_invalid_model_output_does_not_mutate_call(client,monkeypatch,update):
    call=start(client);transport(monkeypatch,assessment(**update))
    r=client.post('/api/reception/calls/'+call['id']+'/ai-turn',json=body())
    assert r.status_code==502
    result=client.get('/api/reception/calls/'+call['id']).json()
    assert result['revision']==0 and len(result['messages'])==1
    assert client.get('/api/reception/cases').json()==[]

@pytest.mark.parametrize('confidence',['medium','low'])
def test_uncertainty_asks_to_clarify(client,monkeypatch,confidence):
    transport(monkeypatch,assessment(confidence=confidence))
    call=start(client)
    result=client.post('/api/reception/calls/'+call['id']+'/ai-turn',json=body()).json()
    assert result['analysis']['needs_clarification'] is True
    assert result['situation']=='routine' and not result['case_id']
    assert 'doprecyzować' in result['messages'][-1]['text']

def test_replay_does_not_call_model_again(client,monkeypatch):
    transport(monkeypatch,assessment());call=start(client);b=body();url='/api/reception/calls/'+call['id']+'/ai-turn'
    first=client.post(url,json=b);assert first.status_code==200
    def forbidden(*a,**kw):raise AssertionError('Unexpected second model call')
    monkeypatch.setattr(reception_ai.network,'client',forbidden)
    assert client.post(url,json=b).json()['replayed'] is True
    assert client.post(url,json={**b,'text':'Changed'}).status_code==409

def test_no_inference_on_stale_or_ended_call(client,monkeypatch):
    call=start(client)
    def forbidden(*args,**kw):raise AssertionError('Model should not run')
    monkeypatch.setattr(reception_ai.network,'client',forbidden)
    url='/api/reception/calls/'+call['id']+'/ai-turn'
    assert client.post(url,json=body(revision=3)).status_code==409
    client.post('/api/reception/calls/'+call['id']+'/events',json={'event_id':str(uuid.uuid4()),'revision':0,'action':'finish'})
    assert client.post(url,json=body(revision=1)).status_code==409


def test_first_request_gate_even_if_model_says_insistent(client,monkeypatch):
    text='Nalegam na rozmowę z właścicielem'
    transport(monkeypatch,assessment(kind='insistent',evidence=[{'message_index':0,'quote':text}],facts=[]))
    call=start(client)
    result=client.post('/api/reception/calls/'+call['id']+'/ai-turn',json=body(text)).json()
    assert result['situation']=='contact_requested' and result['owner_requests']==1
    assert result['analysis']['first_request_gate'] is True


def test_change_during_inference_rejects_stale_analysis(client,monkeypatch):
    call=start(client)
    async def changed(*args):
        client.post('/api/reception/calls/'+call['id']+'/events',json={'event_id':str(uuid.uuid4()),'revision':0,'action':'finish'})
        return {'effective_kind':'crisis','source':'test','extracted':{},'needs_clarification':False}
    monkeypatch.setattr(reception_ai,'analyze',changed)
    r=client.post('/api/reception/calls/'+call['id']+'/ai-turn',json=body())
    assert r.status_code==409
    result=client.get('/api/reception/calls/'+call['id']).json()
    assert result['state']=='ended' and result['revision']==1


def test_disabled_cloud_and_model_allowlist(client,monkeypatch):
    call=start(client);url='/api/reception/calls/'+call['id']+'/ai-turn'
    monkeypatch.setenv('JARVIS_RECEPTION_AI_ENABLED','false')
    assert client.post(url,json=body()).status_code==503
    monkeypatch.setenv('JARVIS_RECEPTION_AI_ENABLED','true');monkeypatch.setenv('OLLAMA_RECEPTION_MODEL','secret:cloud')
    assert client.post(url,json=body()).status_code==503
    monkeypatch.setenv('OLLAMA_RECEPTION_MODEL','not-listed')
    assert client.post(url,json=body()).status_code==403
    assert client.get('/api/reception/calls/'+call['id']).json()['revision']==0


def test_service_tokens_and_forged_analysis_are_rejected(client):
    call=start(client);url='/api/reception/calls/'+call['id']+'/ai-turn'
    token=client.post('/api/security/tokens',json={'name':'reader','scopes':['status:read']}).json()['token']
    assert client.post(url,json=body(),headers={'X-Jarvis-Key':token}).status_code==403
    assert client.post(url,json={**body(),'analysis':{'effective_kind':'crisis'}}).status_code==422
    assert client.post(url,json=body(' ')).status_code==422


def test_phone_must_have_explicit_country_and_literal_quote():
    text='Mój numer +48 500-111-222'
    item=assessment(kind='routine',evidence=[],facts=[{'field':'phone','value':'+48500111222','quote':text,'message_index':0}])
    result=reception_ai.verified(reception_ai.Assessment(**item),[text])
    assert result['extracted']['phone']=='+48500111222'


def test_network_error_is_sanitized_and_no_heuristic_fallback(client,monkeypatch):
    def fail(req):raise httpx.ConnectError('private error with secret')
    monkeypatch.setattr(reception_ai.network,'client',lambda *a,**kw:httpx.AsyncClient(transport=httpx.MockTransport(fail)))
    call=start(client);r=client.post('/api/reception/calls/'+call['id']+'/ai-turn',json=body())
    assert r.status_code==502 and 'secret' not in r.text
    assert client.get('/api/reception/calls/'+call['id']).json()['revision']==0
