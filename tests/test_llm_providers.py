import json
from decimal import Decimal
import pytest
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jarvis.main import create_app
from jarvis import llm_providers as llm
from jarvis.llm import Message, CostPolicy
from pydantic import SecretStr

KEY='synthetic-llm-owner-key-32-chars'
SECRET='synthetic-cloud-provider-key-private'
MODEL=llm.OPENAI_MODELS[0]

def activate(monkeypatch):
    values={'JARVIS_ALLOW_CLOUD_MODELS':'true','JARVIS_OPENAI_ENABLED':'true',
      'JARVIS_OPENAI_API_KEY':SECRET,'JARVIS_OPENAI_MODEL':MODEL,
      'JARVIS_OPENAI_INPUT_USD_PER_MILLION':'0.75','JARVIS_OPENAI_OUTPUT_USD_PER_MILLION':'4.5',
      'JARVIS_OPENAI_MAX_REQUEST_USD':'1','JARVIS_OPENAI_URL':'http://127.0.0.1:12345'}
    for key,value in values.items():monkeypatch.setenv(key,value)

def success():
    return {'model':MODEL,'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'Synthetic provider reply'}}],
            'usage':{'prompt_tokens':12,'completion_tokens':8}}

def mock(monkeypatch,handler):
    original=httpx.AsyncClient
    monkeypatch.setattr(llm.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))

@pytest.fixture
def client(tmp_path,monkeypatch):
    activate(monkeypatch)
    return TestClient(create_app(tmp_path/'core.db',KEY),headers={'X-Jarvis-Key':KEY})

@pytest.mark.parametrize('name,value', [('JARVIS_OPENAI_ENABLED','false'),('JARVIS_ALLOW_CLOUD_MODELS','false'),
 ('JARVIS_OPENAI_MAX_REQUEST_USD','0.001'),('JARVIS_OPENAI_API_KEY',''),
 ('JARVIS_OPENAI_INPUT_USD_PER_MILLION','NaN'),('JARVIS_OPENAI_OUTPUT_USD_PER_MILLION','0'),
 ('JARVIS_OPENAI_MODEL','unknown'),('JARVIS_OPENAI_URL','https://evil.example'),
 ('JARVIS_OPENAI_URL','http://10.0.0.1'),('JARVIS_OPENAI_ENABLED','maybe')])
def test_cloud_refusal_precedes_transport(client,monkeypatch,name,value):
    monkeypatch.setenv(name,value);seen=[]
    mock(monkeypatch,lambda req:seen.append(req))
    response=client.post('/api/v1/chat',json={'message':'Hello','model':'openai'})
    assert response.status_code in (403,503)
    assert seen==[] and SECRET not in response.text and (not value or value not in response.json().get('detail',''))


def test_chat_catalog_sessions_cost_and_private_audit(client,monkeypatch):
    seen=[]
    def handler(req):seen.append(req);return httpx.Response(200,json=success())
    mock(monkeypatch,handler)
    catalog=client.get('/api/v1/models');assert catalog.status_code==200 and SECRET not in catalog.text
    assert {'provider':'openai','name':MODEL,'cloud':True} in catalog.json()['models'] and seen==[]
    client.post('/api/v1/memory',json={'text':'PRIVATE OWNER MEMORY'})
    session=client.post('/api/v1/chat/sessions',json={'model':'openai'}).json()['id']
    result=client.post('/api/v1/chat',json={'message':'Private input','session_id':session})
    assert result.status_code==200,result.text
    body=json.loads(seen[0].content);assert body['store'] is False and body['stream'] is False and body['n']==1
    assert body['max_completion_tokens']==1024 and 'tools' not in body
    assert seen[0].url.path=='/v1/chat/completions' and seen[0].headers['Authorization']=='Bearer '+SECRET
    assert 'PRIVATE OWNER MEMORY' in body['messages'][0]['content']
    assert result.json()['usage']['estimated_cost_usd']=='0.000045'
    assert Decimal(result.json()['usage']['reserved_cost_usd'])==Decimal('0.304608')
    audit=client.get('/api/v1/audit').text
    assert 'llm.completed' in audit and all(x not in audit for x in (SECRET,'Private input','PRIVATE OWNER MEMORY'))
    assert [m['state'] for m in client.get(f'/api/v1/chat/sessions/{session}/messages').json()]==['completed','completed']

@pytest.mark.parametrize('malformed', ['usage','content','tool','length','count'])
def test_malformed_cloud_result_fails_without_fallback(client,monkeypatch,malformed):
    data=success()
    if malformed=='usage':data.pop('usage')
    if malformed=='content':data['choices'][0]['message']['content']=''
    if malformed=='tool':data['choices'][0]['message']['tool_calls']=[{'name':'never_execute'}]
    if malformed=='length':data['choices'][0]['finish_reason']='length'
    if malformed=='count':data['usage']['completion_tokens']=True
    seen=[]
    def handler(req):seen.append(req);return httpx.Response(200,json=data)
    mock(monkeypatch,handler)
    response=client.post('/api/v1/chat',json={'message':'Hello','model':'openai'})
    assert response.status_code==502 and len(seen)==1 and SECRET not in response.text

@pytest.mark.parametrize('status',[302,401,429,500])
def test_remote_errors_are_sanitized_not_retried(client,monkeypatch,status):
    seen=[]
    def handler(req):seen.append(req);return httpx.Response(status,json={'secret':SECRET},headers={'location':'https://evil.example'})
    mock(monkeypatch,handler)
    response=client.post('/api/v1/chat',json={'message':'Hello','model':'openai'})
    assert response.status_code==502 and len(seen)==1 and SECRET not in response.text


def test_cloud_voice_does_not_send_private_memory(client,monkeypatch):
    client.post('/api/v1/memory',json={'text':'PRIVATE OWNER MEMORY'})
    seen=[]
    def handler(req):seen.append(json.loads(req.content));return httpx.Response(200,json=success())
    mock(monkeypatch,handler)
    result=client.post('/api/v1/chat',json={'message':'Voice input','model':'openai','input_mode':'voice'})
    assert result.status_code==200 and result.json()['memory_capture']['saved']==0
    assert 'PRIVATE OWNER MEMORY' not in json.dumps(seen)


def test_ollama_cloud_cannot_bypass_priced_adapter(client,monkeypatch):
    monkeypatch.setenv('OLLAMA_ALLOWED_MODELS','remote:cloud');seen=[]
    mock(monkeypatch,lambda req:seen.append(req))
    assert client.post('/api/v1/chat',json={'message':'Hello','model':'ollama','model_name':'remote:cloud'}).status_code==403
    assert seen==[]


def test_actual_loopback_protocols_and_persistence(tmp_path,monkeypatch):
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    import threading
    activate(monkeypatch); seen=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append((self.path,payload,self.headers.get('Authorization')==('Bearer '+SECRET)))
            data=success() if self.path=='/v1/chat/completions' else {'message':{'content':'Synthetic Ollama reply'},'prompt_eval_count':10,'eval_count':7}
            raw=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}'
        monkeypatch.setenv('OLLAMA_URL',url);monkeypatch.setenv('JARVIS_OPENAI_URL',url)
        monkeypatch.setenv('OLLAMA_ALLOWED_MODELS','synthetic:local')
        with TestClient(create_app(tmp_path/'core.db',KEY),headers={'X-Jarvis-Key':KEY}) as client:
            for provider,model in [('ollama','synthetic:local'),('openai',MODEL)]:
                response=client.post('/api/v1/chat',json={'message':'Synthetic localhost test','model':provider,'model_name':model})
                assert response.status_code==200,response.text
                session=response.json()['session_id']
                assert len(client.get(f'/api/v1/chat/sessions/{session}/messages').json())==2
                assert response.json()['usage']['input_tokens'] in (10,12)
        assert [item[0] for item in seen]==['/api/chat','/v1/chat/completions']
        assert seen[0][1]['options']['num_predict']==1024 and not seen[0][2] and seen[1][2]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def test_cancellation_is_propagated(monkeypatch):
    import asyncio
    async def handler(req):raise asyncio.CancelledError()
    mock(monkeypatch,handler)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(llm.OllamaProvider().complete([Message('user','Hello')],'synthetic:local',10))


def test_secret_is_not_in_configuration_representation(monkeypatch):
    activate(monkeypatch)
    assert SECRET not in repr(llm.OpenAIConfig.from_env())


@pytest.mark.parametrize('data', [None, [], 1, {'model': MODEL, 'choices': [1]}, {'model': MODEL, 'choices': [{'message': None}]}])
def test_invalid_json_structure_is_sanitized(client,monkeypatch,data):
    mock(monkeypatch,lambda req:httpx.Response(200,json=data))
    assert client.post('/api/v1/chat',json={'message':'Hello','model':'openai'}).status_code==502
