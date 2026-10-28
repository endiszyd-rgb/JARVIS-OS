"""Versioned catalog/invocation share server policies without external effects."""
import json
import sqlite3
from fastapi.testclient import TestClient
import pytest
from jarvis import plugins
from jarvis.main import create_app

KEY='tool-api-owner-synthetic-key-32-characters'
OWNER={'X-Jarvis-Key':KEY}
SPEC={'openapi':'3.0.3','paths':{'/read':{'get':{'operationId':'read_item','parameters':[
    {'name':'item','in':'query','required':True,'schema':{'type':'integer','minimum':1}}]}}}}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'tool-api.db',KEY),headers=OWNER) as c:yield c


def configured(c,protocol='openapi',pid='catalog_lab'):
    assert c.post('/api/plugins',json={'id':pid,'name':'Synthetic lab','protocol':protocol}).status_code==201
    cfg={'endpoint':'http://127.0.0.1:8765'+('/mcp' if protocol=='mcp' else ''),
         'reviewed_read_tools':['read_item'],'secret_env':'JARVIS_PLUGIN_SECRET_TOOL_TEST'}
    if protocol=='openapi':cfg['openapi']=SPEC
    assert c.put('/api/plugins/'+pid+'/config',json=cfg).status_code==200
    assert c.put('/api/plugins/'+pid,json={'enabled':True}).status_code==200
    return pid


def test_local_catalog_is_normalized_and_sends_no_network_requests(client,monkeypatch):
    c=client;configured(c);configured(c,'mcp','remote_catalog')
    secret='Synthetic-tool-credential-absent-from-catalog'
    monkeypatch.setenv('JARVIS_PLUGIN_SECRET_TOOL_TEST',secret)
    async def forbidden(*args,**kwargs):pytest.fail('Local catalog must not discover or invoke network tools')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    for prefix in ('/api','/api/v1'):
        response=c.get(prefix+'/tools');assert response.status_code==200,response.text
        catalog=response.json();assert catalog['network_requests_sent'] is False
        assert catalog['discovery_required']==['remote_catalog']
        found={tool['id']:tool for tool in catalog['tools']}
        assert {'autologika.orders','home_assistant.status','catalog_lab.read_item'} <= found.keys()
        tool=found['catalog_lab.read_item']
        assert tool['name']=='read_item' and tool['protocol']=='openapi'
        assert tool['inputSchema']['required']==['item']
        assert tool['inputSchema']['additionalProperties'] is False
        assert tool['required_scope']=='plugins:invoke' and len(tool['schema_digest'])==64
        for forbidden_value in (secret,'http://127.0.0.1:8765','JARVIS_PLUGIN_SECRET_TOOL_TEST'):
            assert forbidden_value not in response.text
    assert c.put('/api/plugins/catalog_lab',json={'enabled':False}).status_code==200
    assert all(t['id']!='catalog_lab.read_item' for t in c.get('/api/tools').json()['tools'])


def test_both_aliases_enforce_review_schema_and_audit_privacy_before_dispatch(client,monkeypatch):
    c=client;pid=configured(c);seen=[]
    async def call(protocol,config,operation,arguments):
        seen.append((protocol,operation,arguments))
        return {'mode':'live_readonly','data':{'secret':'Synthetic private result'}}
    monkeypatch.setattr(plugins,'call',call)
    for prefix in ('/api','/api/v1'):
        route=prefix+'/plugins/'+pid+'/invoke'
        assert c.post(route,json={'operation':'unreviewed_secret_name','arguments':{}}).status_code==403
        assert c.post(route,json={'operation':'read_item','arguments':{'item':False}}).status_code==422
        assert c.post(route,json={'operation':'read_item','arguments':{'item':1,'extra':'Synthetic private argument'}}).status_code==422
        assert c.post(route,json={'operation':'read_item','arguments':{'item':1}}).status_code==200
    assert seen==[('openapi','read_item',{'item':1})]*2
    events=c.get('/api/audit').text
    for private in ('Synthetic private argument','Synthetic private result','unreviewed_secret_name'):
        assert private not in events
    assert c.put('/api/plugins/'+pid,json={'enabled':False}).status_code==200
    assert c.post('/api/plugins/'+pid+'/invoke',json={'operation':'read_item','arguments':{'item':1}}).status_code==409
    assert len(seen)==2


def test_catalog_and_invoke_have_distinct_service_permissions(client):
    c=client
    def token(scope):
        result=c.post('/api/security/tokens',json={'name':scope,'scopes':[scope]}).json()
        return {'X-Jarvis-Key':result['token']}
    read,invoke=token('plugins:read'),token('plugins:invoke')
    assert c.get('/api/v1/tools',headers=read).status_code==200
    assert c.post('/api/plugins/mqtt/invoke',headers=read,json={'operation':'status'}).status_code==403
    assert c.get('/api/tools',headers=invoke).status_code==403
    result=c.post('/api/v1/plugins/mqtt/invoke',headers=invoke,json={'operation':'status'})
    assert result.status_code==200 and result.json()['external_request_sent'] is False
    assert c.post('/api/plugins/mqtt/invoke',json={'operation':'open_gate'}).status_code==422
    assert c.post('/api/plugins/mqtt/invoke',json={'operation':'open_gate','arguments':{'live':True}}).json()['status']=='blocked'


def test_discovered_demo_and_openapi_specs_have_identical_catalog_schema(client):
    c=client;configured(c)
    local={tool['id']:tool for tool in c.get('/api/tools').json()['tools']}
    for pid in ('home_assistant','autologika','catalog_lab'):
        tools=c.get('/api/v1/plugins/'+pid+'/tools')
        assert tools.status_code==200,tools.text
        assert tools.json() and all(tool==local[tool['id']] for tool in tools.json())


def test_invalid_remote_result_is_a_sanitized_gateway_error(client,monkeypatch):
    c=client;pid=configured(c,'mcp')
    async def listing(*args):
        return [{'name':'read_item','inputSchema':{'type':'object','properties':{},'additionalProperties':False}}]
    async def oversized(*args):
        raise plugins.PluginResultError('Synthetic remote secret must not escape')
    monkeypatch.setattr(plugins,'tools',listing);monkeypatch.setattr(plugins,'call',oversized)
    response=c.post('/api/v1/plugins/'+pid+'/invoke',json={'operation':'read_item','arguments':{}})
    assert response.status_code==502
    assert 'Synthetic remote secret' not in response.text


def test_preexisting_schema_outside_supported_subset_requires_review_without_500(client,monkeypatch):
    c=client;pid=configured(c)
    path=c.app.state.runtime_config.database_path
    with sqlite3.connect(path) as db:
        cfg=json.loads(db.execute('SELECT config FROM plugin_configs WHERE id=?',(pid,)).fetchone()[0])
        cfg['openapi']['paths']['/read']['get']['parameters'][0]['schema']={'type':'string','pattern':'^[a-z]+$'}
        db.execute('UPDATE plugin_configs SET config=? WHERE id=?',(json.dumps(cfg),pid))
    async def forbidden(*args,**kwargs):pytest.fail('Legacy schema must be reviewed before transport')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    for route in ('/api/tools','/api/v1/plugins/'+pid+'/tools'):
        response=c.get(route)
        assert response.status_code==422 and 'review' in response.json()['detail']
    assert c.post('/api/plugins/'+pid+'/invoke',json={'operation':'read_item','arguments':{'item':'abc'}}).status_code==422
    # The owner can still retrieve the original configuration to correct it.
    assert c.get('/api/plugins/'+pid+'/config').json()['openapi']==cfg['openapi']
