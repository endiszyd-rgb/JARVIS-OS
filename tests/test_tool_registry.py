"""Trusted tool catalog and bounded dispatch policy, using controlled transports."""
import asyncio
from dataclasses import FrozenInstanceError
import json
import uuid

from fastapi import HTTPException
import pytest

from jarvis.identity import Principal
from jarvis import plugins
from jarvis.tool_registry import ToolGateway, demo_tools, mcp_tools, openapi_tools

OWNER=Principal(id='owner-key',kind='owner_key',role='owner',scopes=frozenset({'*'}))
READER=Principal(id=str(uuid.uuid4()),kind='service',role='service',scopes=frozenset({'plugins:read'}))
RUNNER=Principal(id=str(uuid.uuid4()),kind='service',role='service',scopes=frozenset({'plugins:invoke'}))
SCHEMA={'type':'object','properties':{'id':{'type':'integer','minimum':1}},'required':['id'],'additionalProperties':False}
SPEC={'openapi':'3.0.3','paths':{'/items/{id}':{'get':{'operationId':'read_item','summary':'Synthetic item','parameters':[
    {'name':'id','in':'path','required':True,'schema':{'type':'integer','minimum':1}},
    {'name':'query','in':'query','schema':{'type':'string','maxLength':20}}]},'post':{'operationId':'write_item'}}}}


def config(protocol='mcp',reviewed=None):
    return plugins.PluginConfig(endpoint='http://127.0.0.1:8999'+('/mcp' if protocol=='mcp' else ''),
                                reviewed_read_tools=['read_item'] if reviewed is None else reviewed,
                                openapi=SPEC if protocol=='openapi' else None)


def listed(name='read_item',schema=None,**extra):
    return {'name':name,'description':'Synthetic item','inputSchema':SCHEMA if schema is None else schema,**extra}


def run(awaitable):
    return asyncio.run(awaitable)


def denied(status,awaitable):
    with pytest.raises(HTTPException) as error:run(awaitable)
    assert error.value.status_code==status
    return error.value


def test_demo_catalog_is_explicit_and_has_no_external_operations():
    specs=demo_tools('autologika')
    assert isinstance(specs,tuple)
    assert {item.name for item in specs}=={'calendar','orders','vehicles','parts','customers','finances','reports','notifications'}
    for item in specs:
        public=item.public()
        assert public['id']=='autologika.'+item.name
        assert public['protocol']=='demo' and public['read_only_reviewed'] is True
        assert public['inputSchema']=={'type':'object','properties':{},'additionalProperties':False}
    assert [item.name for item in demo_tools('home_assistant')]==['status']
    assert [item.name for item in demo_tools('custom_demo')]==['status']


def test_openapi_catalog_normalizes_required_parameters_and_excludes_writes():
    specs=openapi_tools('lab',config('openapi'))
    assert isinstance(specs,tuple) and len(specs)==1
    public=specs[0].public()
    assert public['name']=='read_item' and public['plugin_id']=='lab'
    assert public['required_scope']=='plugins:invoke'
    schema=public['inputSchema']
    assert schema['type']=='object' and schema['additionalProperties'] is False
    assert schema['required']==['id']
    assert schema['properties']=={'id':{'type':'integer','minimum':1},'query':{'type':'string','maxLength':20}}
    assert openapi_tools('lab',config('openapi',reviewed=[]))==()


def test_specs_and_nested_schema_cannot_be_changed_by_consumer():
    item=mcp_tools('lab',config(),[listed()])[0]
    original=item.public()
    with pytest.raises((FrozenInstanceError,AttributeError)):item.name='write_item'
    exposed=item.public();exposed['inputSchema']['properties']['id']['type']='string'
    item.input_schema['properties'].clear()
    assert item.public()==original


def test_digest_is_canonical_and_changes_with_tool_identity_or_schema():
    first=mcp_tools('lab',config(),[listed()])[0]
    reordered={'additionalProperties':False,'required':['id'],'properties':{'id':{'minimum':1,'type':'integer'}},'type':'object'}
    same=mcp_tools('lab',config(),[listed(schema=reordered)])[0]
    changed=mcp_tools('lab',config(),[listed(schema={**SCHEMA,'required':[]})])[0]
    other=mcp_tools('other',config(),[listed()])[0]
    assert len(first.schema_digest)==64 and set(first.schema_digest)<=set('0123456789abcdef')
    assert first.schema_digest==same.schema_digest
    assert first.schema_digest!=changed.schema_digest and first.schema_digest!=other.schema_digest


def test_mcp_remote_hints_cannot_grant_local_review():
    assert mcp_tools('lab',config(reviewed=[]),[listed(readOnlyHint=True,read_only_reviewed=True)])==()
    items=mcp_tools('lab',config(),[listed(),listed('unreviewed',readOnlyHint=True)])
    assert [item.name for item in items]==['read_item']


@pytest.mark.parametrize('name',['','../read','read/item','read item','1read','a'*81])
def test_invalid_registered_names_are_rejected(name):
    with pytest.raises(ValueError):mcp_tools('lab',config(reviewed=[name]),[listed(name)])


def test_duplicate_names_are_rejected_instead_of_last_definition_winning():
    with pytest.raises(ValueError):mcp_tools('lab',config(),[listed(),listed(schema={'type':'object'})])


@pytest.mark.parametrize('schema',[
    {'type':'array','items':{'type':'string'}},
    {'type':'object','properties':{'id':{'$ref':'https://untrusted.invalid/schema'}}},
    {'type':'object','$dynamicRef':'https://untrusted.invalid/schema'},
    {'type':'object','properties':{'id':{'type':'not-a-json-schema-type'}}},
])
def test_non_object_or_referenced_or_invalid_schemas_are_rejected(schema):
    with pytest.raises(ValueError):mcp_tools('lab',config(),[listed(schema=schema)])


def test_tool_count_and_schema_size_are_bounded():
    names=['read_'+str(i) for i in range(101)]
    with pytest.raises(ValueError):mcp_tools('lab',config(reviewed=names[:100]),[listed(name) for name in names])
    huge={'type':'object','description':'x'*65537}
    with pytest.raises(ValueError):mcp_tools('lab',config(),[listed(schema=huge)])


@pytest.mark.parametrize('principal',[
    None,{'role':'owner','scopes':['*']},
    Principal(id='caller',kind='caller',role='owner',scopes=frozenset({'*'})),
    Principal(id='forged-service',kind='service',role='owner',scopes=frozenset({'*'})),
    Principal(id='observer',kind='session',role='observer',scopes=frozenset({'status:read'})),
])
def test_untrusted_or_insufficient_identity_cannot_dispatch(monkeypatch,principal):
    async def forbidden(*args):pytest.fail('Unauthorized operation reached transport')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    gateway=ToolGateway()
    denied(403,gateway.discover(principal,'lab','mcp',True,config()))
    denied(403,gateway.execute(principal,'lab','mcp',True,config(),'read_item',{'id':1}))


def test_read_and_invoke_scopes_are_distinct(monkeypatch):
    calls=[]
    async def discover(protocol,cfg):calls.append('discover');return [listed()]
    async def execute(protocol,cfg,name,args):calls.append((name,args));return {'mode':'live_readonly','ok':True}
    monkeypatch.setattr(plugins,'tools',discover);monkeypatch.setattr(plugins,'call',execute)
    gateway=ToolGateway()
    assert run(gateway.discover(READER,'lab','mcp',True,config()))[0]['id']=='lab.read_item'
    denied(403,gateway.execute(READER,'lab','mcp',True,config(),'read_item',{'id':1}))
    denied(403,gateway.discover(RUNNER,'lab','mcp',True,config()))
    assert run(gateway.execute(RUNNER,'lab','mcp',True,config(),'read_item',{'id':1}))['ok'] is True
    assert calls.count(('read_item',{'id':1}))==1


def test_disabled_unconfigured_and_unreviewed_fail_before_transport(monkeypatch):
    async def forbidden(*args):pytest.fail('Rejected request reached transport')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    gateway=ToolGateway()
    denied(409,gateway.discover(OWNER,'lab','mcp',False,config()))
    denied(409,gateway.execute(OWNER,'lab','mcp',False,config(),'read_item',{'id':1}))
    denied(409,gateway.discover(OWNER,'lab','mcp',True,None))
    denied(501,gateway.execute(OWNER,'lab','mcp',True,None,'read_item',{'id':1}))
    denied(403,gateway.execute(OWNER,'lab','mcp',True,config(),'write_item',{}))


@pytest.mark.parametrize('arguments',[{'live':True},{'dry_run':False},{'live':'yes'}])
def test_explicit_live_flags_block_even_an_unknown_operation(monkeypatch,arguments):
    async def forbidden(*args):pytest.fail('Blocked flag reached transport')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    result=run(ToolGateway().execute(OWNER,'home_assistant','demo',True,None,'open_gate',arguments))
    assert result['status']=='blocked'


def test_demo_operations_and_arguments_are_checked_without_network(monkeypatch):
    async def forbidden(*args):pytest.fail('Demo must not call a network transport')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    gateway=ToolGateway()
    denied(422,gateway.execute(OWNER,'home_assistant','demo',True,None,'open_gate',{}))
    denied(422,gateway.execute(OWNER,'home_assistant','demo',True,None,'status',{'unexpected':1}))
    result=run(gateway.execute(OWNER,'home_assistant','demo',True,None,'status',{}))
    assert result['mode']=='demo' and result['external_request_sent'] is False
    assert result['plugin']=='home_assistant' and result['operation']=='status'
    result=run(gateway.execute(OWNER,'autologika','demo',True,None,'orders',{}))
    assert result['source']=='synthetic_fixture' and result['domain']=='orders'


@pytest.mark.parametrize('arguments',[{}, {'id':0},{'id':'1'},{'id':1,'extra':'unapproved'}])
def test_invalid_openapi_arguments_fail_before_dispatch(monkeypatch,arguments):
    async def forbidden(*args):pytest.fail('Invalid arguments reached transport')
    monkeypatch.setattr(plugins,'call',forbidden)
    denied(422,ToolGateway().execute(OWNER,'lab','openapi',True,config('openapi'),'read_item',arguments))


def test_input_size_and_non_json_values_fail_before_transport(monkeypatch):
    async def forbidden(*args):pytest.fail('Invalid input reached transport')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    gateway=ToolGateway(max_input_bytes=30)
    denied(422,gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1,'data':'x'*100}))
    denied(422,gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':float('nan')}))


def test_transport_errors_and_oversized_results_do_not_expose_secrets(monkeypatch):
    secret='synthetic-transport-secret-sentinel'
    async def discover(protocol,cfg):return [listed()]
    async def broken(*args):raise RuntimeError(secret)
    monkeypatch.setattr(plugins,'tools',discover);monkeypatch.setattr(plugins,'call',broken)
    gateway=ToolGateway()
    error=denied(502,gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1}))
    assert secret not in str(error.detail)
    async def too_large(*args):return {'result':secret+'x'*100}
    monkeypatch.setattr(plugins,'call',too_large)
    error=denied(502,ToolGateway(max_result_bytes=32).execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1}))
    assert secret not in str(error.detail)


def test_deadline_cancels_transport_and_releases_gateway_slot(monkeypatch):
    async def scenario():
        cancelled=asyncio.Event()
        async def discover(protocol,cfg):return [listed()]
        async def hanging(*args):
            try:await asyncio.Event().wait()
            finally:cancelled.set()
        monkeypatch.setattr(plugins,'tools',discover);monkeypatch.setattr(plugins,'call',hanging)
        gateway=ToolGateway(timeout_seconds=.02,max_concurrent=1)
        with pytest.raises(HTTPException) as caught:
            await gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1})
        assert caught.value.status_code==504 and cancelled.is_set()
        async def succeeds(*args):return {'ok':True}
        monkeypatch.setattr(plugins,'call',succeeds)
        assert await gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1})=={'ok':True}
    run(scenario())


def test_capacity_rejects_extra_work_and_cancel_releases_slot(monkeypatch):
    async def scenario():
        started=asyncio.Event()
        async def discover(protocol,cfg):return [listed()]
        async def hanging(*args):started.set();await asyncio.Event().wait()
        monkeypatch.setattr(plugins,'tools',discover);monkeypatch.setattr(plugins,'call',hanging)
        gateway=ToolGateway(max_concurrent=1)
        task=asyncio.create_task(gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1}))
        await asyncio.wait_for(started.wait(),1)
        with pytest.raises(HTTPException) as caught:
            await gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1})
        assert caught.value.status_code==429
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        async def succeeds(*args):return {'ok':True}
        monkeypatch.setattr(plugins,'call',succeeds)
        assert await gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1})=={'ok':True}
    run(scenario())


def test_discovery_obeys_the_same_result_size_cap(monkeypatch):
    async def discover(protocol,cfg):return [listed()]
    monkeypatch.setattr(plugins,'tools',discover)
    error=denied(502,ToolGateway(max_result_bytes=100).discover(OWNER,'lab','mcp',True,config()))
    assert 'size' in error.detail.lower() or 'limit' in error.detail.lower()


def test_remote_regex_schema_is_rejected_before_validation_can_run():
    schema={'type':'object','properties':{'value':{'type':'string','pattern':'(a+)+$'}}}
    with pytest.raises(ValueError):mcp_tools('lab',config(),[listed(schema=schema)])


def test_deep_remote_schema_is_rejected_before_recursive_validation():
    schema={'type':'object','properties':{}}
    node=schema
    for _ in range(20):
        child={'type':'object','properties':{}}
        node['properties']['nested']=child;node=child
    with pytest.raises(ValueError):mcp_tools('lab',config(),[listed(schema=schema)])


def test_argument_tree_depth_and_node_caps_apply_before_discovery(monkeypatch):
    async def forbidden(*args):pytest.fail('Oversized argument tree reached transport discovery')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    gateway=ToolGateway()
    deep={'id':1};node=deep
    for _ in range(20):node['nested']={};node=node['nested']
    denied(422,gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',deep))
    denied(422,gateway.execute(OWNER,'lab','mcp',True,config(),'read_item',{'id':1,'data':list(range(512))}))


def test_local_catalog_publication_is_scoped_bounded_and_sends_no_network(monkeypatch):
    def forbidden(*args):pytest.fail('Local catalog publication must not use transport')
    monkeypatch.setattr(plugins,'tools',forbidden);monkeypatch.setattr(plugins,'call',forbidden)
    tools=[item.public() for item in demo_tools('home_assistant')]
    gateway=ToolGateway()
    result=gateway.publish_catalog(READER,tools,['lab'])
    assert result=={'tools':tools,'discovery_required':['lab'],'network_requests_sent':False}
    with pytest.raises(HTTPException) as caught:gateway.publish_catalog(RUNNER,tools,[])
    assert caught.value.status_code==403
    with pytest.raises(HTTPException) as caught:gateway.publish_catalog({'role':'owner'},tools,[])
    assert caught.value.status_code==403
    with pytest.raises(HTTPException) as caught:ToolGateway(max_result_bytes=100).publish_catalog(OWNER,tools,[])
    assert caught.value.status_code==502
