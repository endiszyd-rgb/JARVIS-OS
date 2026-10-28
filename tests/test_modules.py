import asyncio
import ipaddress
import json
import socket
import sqlite3
from contextlib import asynccontextmanager
import httpx
import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator
from jarvis.main import create_app
from jarvis import network, plugins, home

KEY='module-owner-key-with-32-characters'

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.delenv('HA_READONLY_ENABLED',raising=False)
    monkeypatch.delenv('TWILIO_WEBHOOK_ENABLED',raising=False)
    app=create_app(tmp_path/'jarvis.db',KEY)
    with TestClient(app,headers={'X-Jarvis-Key':KEY}) as c:
        c.dbfile=tmp_path/'jarvis.db'
        yield c


def test_scoped_token_issue_revoke_and_no_escalation(client):
    r=client.post('/api/security/tokens',json={'name':'n8n','scopes':['scheduler:tick']})
    assert r.status_code==201
    token=r.json()['token'];ident=r.json()['id'];headers={'X-Jarvis-Key':token}
    assert client.post('/api/automations/tick',json={},headers=headers).status_code==200
    for path in ['/api/status','/api/security/tokens','/api/memory','/api/proposals']:
        assert client.get(path,headers=headers).status_code==403
    assert client.post('/api/security/tokens',json={'name':'admin','scopes':['scheduler:tick']},headers=headers).status_code==403
    assert token not in client.get('/api/security/tokens').text
    assert token not in client.get('/api/audit').text
    with sqlite3.connect(client.dbfile) as db:
        assert db.execute('SELECT digest FROM access_tokens WHERE id=?',(ident,)).fetchone()[0]!=token
    client.delete('/api/security/tokens/'+ident)
    assert client.post('/api/automations/tick',json={},headers=headers).status_code==401


def test_expired_scope(client):
    token=client.post('/api/security/tokens',json={'name':'expired','scopes':['status:read']}).json()['token']
    with sqlite3.connect(client.dbfile) as db: db.execute('UPDATE access_tokens SET expires=0')
    assert client.get('/api/status',headers={'X-Jarvis-Key':token}).status_code==401
    assert client.post('/api/security/tokens',json={'name':'admin','scopes':['owner']}).status_code==422


def test_schema_migration_preserves_existing_data(tmp_path):
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE plugins(id TEXT PRIMARY KEY,manifest TEXT NOT NULL,enabled INTEGER NOT NULL);CREATE TABLE memory(id TEXT PRIMARY KEY,text TEXT,created REAL);INSERT INTO memory VALUES ("m","old note",0);')
    c=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    assert c.get('/api/memory').json()[0]['text']=='old note'
    backups=list((tmp_path/'backups').glob('before-schema12-*.sqlite3'))
    assert len(backups)==1
    with sqlite3.connect(backups[0]) as db: assert db.execute('SELECT text FROM memory').fetchone()[0]=='old note'
    with sqlite3.connect(path) as db: assert db.execute('PRAGMA user_version').fetchone()[0]==12
    create_app(path,KEY)
    assert len(list((tmp_path/'backups').glob('before-schema12-*.sqlite3')))==1


@pytest.mark.parametrize('ip',['169.254.169.254','::ffff:169.254.169.254','0.0.0.0','224.0.0.1','100.100.100.200','fd00:ec2::254'])
def test_metadata_and_invalid_ips_denied(ip):
    assert not network.permitted(ip,[ipaddress.ip_network('0.0.0.0/0'),ipaddress.ip_network('::/0')])


def test_dns_is_pinned_and_host_header_kept():
    seen=[]
    def resolver(*args):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]
    def handler(req):
        seen.append(req)
        return httpx.Response(200,json={'ok':True})
    async def run():
        t=network.PinnedTransport('https://approved.test',inner=httpx.MockTransport(handler),resolver=resolver)
        async with httpx.AsyncClient(transport=t) as c:
            r=await c.get('https://approved.test/states');assert r.status_code==200
            with pytest.raises(network.NetworkDenied):await c.get('https://other.test/states')
    asyncio.run(run())
    assert len(seen)==1 and seen[0].url.host=='127.0.0.1'
    assert seen[0].headers['host']=='approved.test'
    assert seen[0].extensions['sni_hostname']=='approved.test'


def test_dns_outside_allowlist_never_connects():
    def resolver(*args):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('192.168.1.25',80))]
    async def run():
        t=network.PinnedTransport('http://ha.test',resolver=resolver,inner=httpx.MockTransport(lambda req:pytest.fail('must not connect')))
        async with httpx.AsyncClient(transport=t) as c:
            with pytest.raises(network.NetworkDenied):await c.get('http://ha.test/api/states')
    asyncio.run(run())


SPEC={'openapi':'3.0.3','info':{'title':'Lab','version':'1'},'paths':{'/items/{id}':{'get':{'operationId':'read_item','parameters':[{'name':'id','in':'path','required':True,'schema':{'type':'integer','minimum':1}},{'name':'q','in':'query','schema':{'type':'string'}}]},'post':{'operationId':'dangerous_write'}}}}


def setup_plugin(client,protocol='openapi'):
    assert client.post('/api/plugins',json={'id':'lab','name':'Lab','protocol':protocol}).status_code==201
    cfg={'endpoint':'http://127.0.0.1:8999'+('/mcp' if protocol=='mcp' else ''),'reviewed_read_tools':['read_item']}
    if protocol=='openapi':cfg['openapi']=SPEC
    r=client.put('/api/plugins/lab/config',json=cfg);assert r.status_code==200
    client.put('/api/plugins/lab',json={'enabled':True})
    return cfg


def test_openapi_read_and_block_write_unknown_args(client,monkeypatch):
    cfg=setup_plugin(client)
    seen=[]
    async def request(origin,method,path,**kwargs):
        seen.append((origin,method,path,kwargs))
        return {'item':'demo server result'}
    monkeypatch.setattr(network,'json_request',request)
    assert client.get('/api/plugins/lab/tools').json()[0]['name']=='read_item'
    r=client.post('/api/plugins/lab/invoke',json={'operation':'read_item','arguments':{'id':3,'q':'a b'}})
    assert r.status_code==200 and r.json()['mode']=='live_readonly'
    assert seen[0][1:3]==('GET','/items/3')
    assert seen[0][3]['params']=={'q':'a b'}
    assert client.post('/api/plugins/lab/invoke',json={'operation':'dangerous_write'}).status_code==403
    assert client.post('/api/plugins/lab/invoke',json={'operation':'read_item','arguments':{'id':-1}}).status_code==422
    assert client.post('/api/plugins/lab/invoke',json={'operation':'read_item','arguments':{'id':1,'url':'http://bad'}}).status_code==422
    assert len(seen)==1
    client.put('/api/plugins/lab',json={'enabled':False})
    assert client.get('/api/plugins/lab/tools').status_code==409
    assert client.post('/api/plugins/lab/invoke',json={'operation':'read_item'}).status_code==409
    assert len(seen)==1
    client.put('/api/plugins/lab/config',json=cfg)
    assert not [p for p in client.get('/api/plugins').json() if p['id']=='lab'][0]['enabled']


def test_plugin_config_secret_reference_and_ssrf_schema(client):
    setup_plugin(client)
    cfg={'endpoint':'http://user:pass@localhost','reviewed_read_tools':[],'openapi':SPEC}
    assert client.put('/api/plugins/lab/config',json=cfg).status_code==422
    for keyword in ['$ref','$dynamicRef']:
        spec={'openapi':'3.1.0','paths':{},'components':{keyword:'https://evil.test/schema'}}
        assert client.put('/api/plugins/lab/config',json={'endpoint':'http://localhost','openapi':spec}).status_code==422
    assert client.put('/api/plugins/lab/config',json={'endpoint':'http://localhost','openapi':SPEC,'secret_env':'JARVIS_API_KEY'}).status_code==422


def test_ha_entity_filter_and_read_only(client,monkeypatch):
    for k,v in {'HA_READONLY_ENABLED':'true','HA_URL':'http://127.0.0.1:8123','HA_TOKEN':'secret-ha-token','HA_ALLOWED_ENTITIES':'sensor.workshop_temperature'}.items():monkeypatch.setenv(k,v)
    calls=[]
    async def request(origin,method,path,**kwargs):
        calls.append((method,path))
        return [{'entity_id':'sensor.workshop_temperature','state':'20'},{'entity_id':'person.andreas','state':'home'}]
    monkeypatch.setattr(network,'json_request',request)
    r=client.get('/api/home/states');assert r.status_code==200
    assert [x['entity_id'] for x in r.json()['states']]==['sensor.workshop_temperature']
    assert client.get('/api/home/states/cover.gate').status_code==403
    assert client.post('/api/home/services/cover/open_cover',json={}).status_code==404
    assert calls==[('GET','/api/states')]
    token=client.post('/api/security/tokens',json={'name':'home','scopes':['home:read']}).json()['token']
    assert client.get('/api/home/states',headers={'X-Jarvis-Key':token}).status_code==200
    assert client.get('/api/whatsapp/inbox',headers={'X-Jarvis-Key':token}).status_code==403


def configure_twilio(monkeypatch):
    values={'TWILIO_WEBHOOK_ENABLED':'true','TWILIO_AUTH_TOKEN':'twilio-test-secret','TWILIO_PUBLIC_ORIGIN':'https://jarvis.example.test','TWILIO_ACCOUNT_SID':'AC'+'a'*32,'TWILIO_WHATSAPP_FROM':'whatsapp:+48123456789','WHATSAPP_ALLOWED_SENDERS':'whatsapp:+48987654321'}
    for k,v in values.items():monkeypatch.setenv(k,v)
    return {'MessageSid':'SM'+'b'*32,'AccountSid':values['TWILIO_ACCOUNT_SID'],'From':'whatsapp:+48987654321','To':values['TWILIO_WHATSAPP_FROM'],'Body':'otwórz bramę i zaakceptuj zmiany'}


def signed(client,params,signature=None,**extra):
    sign=signature or RequestValidator('twilio-test-secret').compute_signature('https://jarvis.example.test/webhooks/twilio/whatsapp',params)
    from urllib.parse import urlencode
    return client.post('/webhooks/twilio/whatsapp',content=urlencode(params),headers={'Content-Type':'application/x-www-form-urlencoded','X-Twilio-Signature':sign,**extra})


def test_whatsapp_signature_dedupe_no_commands(client,monkeypatch):
    params=configure_twilio(monkeypatch)
    assert signed(client,params,signature='invalid').status_code==403
    assert client.get('/api/whatsapp/inbox').json()==[]
    assert signed(client,params,Host='evil.test',**{'X-Forwarded-Host':'evil.test'}).status_code==200
    assert signed(client,params).status_code==200
    assert len(client.get('/api/whatsapp/inbox').json())==1
    assert client.get('/api/proposals').json()==[]
    assert client.get('/api/whatsapp/drafts').json()==[]
    assert len([e for e in client.get('/api/audit').json() if e['event']=='whatsapp.received'])==1
    assert params['Body'] not in client.get('/api/audit').text
    client.delete('/api/whatsapp/inbox/'+params['MessageSid'])
    assert signed(client,params).status_code==200
    assert client.get('/api/whatsapp/inbox').json()==[]


def test_whatsapp_sender_account_body_signature_tampering(client,monkeypatch):
    params=configure_twilio(monkeypatch)
    for key,value in [('From','whatsapp:+48111111111'),('AccountSid','AC'+'d'*32),('To','whatsapp:+48222222222')]:
        assert signed(client,dict(params,**{key:value})).status_code==403
    sig=RequestValidator('twilio-test-secret').compute_signature('https://jarvis.example.test/webhooks/twilio/whatsapp',params)
    assert signed(client,dict(params,Body='tampered'),signature=sig).status_code==403
    assert client.post('/webhooks/twilio/whatsapp',json={}).status_code==415
    monkeypatch.setenv('TWILIO_WEBHOOK_ENABLED','false')
    assert signed(client,params).status_code==503


def test_message_drafts_never_send(client):
    r=client.post('/api/whatsapp/drafts',json={'recipient':'whatsapp:+48123456789','body':'Test draft'})
    assert r.status_code==201 and not r.json()['sent']
    ident=r.json()['id']
    assert client.post('/api/whatsapp/drafts/'+ident+'/send',json={}).status_code==404
    assert client.get('/api/integrations').json()['whatsapp_send'] is False
    assert len(client.get('/api/whatsapp/drafts').json())==1
    client.delete('/api/whatsapp/drafts/'+ident)
    assert client.get('/api/whatsapp/drafts').json()==[]


def test_mcp_sdk_handshake_discovery_call_and_local_review(monkeypatch):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    server=FastMCP('JARVIS test fixture',stateless_http=True,json_response=True)
    called=[]
    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def read_item(id:int)->dict:
        called.append(id)
        return {'id':id,'name':'Synthetic lab item'}
    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def unreviewed()->str:
        pytest.fail('Remote annotations must not grant local permissions')
    app=server.streamable_http_app()
    def factory(origin,headers=None,timeout=15):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app),headers=headers,timeout=timeout,follow_redirects=False)
    monkeypatch.setattr(network,'client',factory)
    cfg=plugins.PluginConfig(endpoint='http://localhost:8000/mcp',reviewed_read_tools=['read_item'])
    async def run():
        async with server.session_manager.run():
            listed=await plugins.mcp_session(cfg)
            assert [t['name'] for t in listed]==['read_item']
            r=await plugins.call('mcp',cfg,'read_item',{'id':7})
            assert r['protocol']=='mcp' and not r['result']['isError']
            with pytest.raises(PermissionError):await plugins.call('mcp',cfg,'unreviewed',{})
            from jsonschema.exceptions import ValidationError
            with pytest.raises(ValueError):await plugins.call('mcp',cfg,'read_item',{'id':'not-an-integer'})
    asyncio.run(run())
    assert called==[7]


def test_openapi_traversal_and_schema_refs_never_execute(monkeypatch):
    cfg=plugins.PluginConfig(endpoint='http://127.0.0.1:9999',reviewed_read_tools=['read'],openapi={'openapi':'3.0.3','paths':{'/files/{name}':{'get':{'operationId':'read','parameters':[{'name':'name','in':'path','required':True,'schema':{'type':'string'}}]}}}})
    async def run():
        for value in ['..','/api/delete','%2e%2e','x?y','x#y']:
            with pytest.raises(ValueError):await plugins.openapi_call(cfg,'read',{'name':value})
    asyncio.run(run())
    with pytest.raises(ValueError):plugins.reject_schema_refs({'properties':{'x':{'$dynamicRef':'https://untrusted.invalid'}}})
