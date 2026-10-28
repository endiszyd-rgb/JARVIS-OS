"""Tool transport contracts tested with controlled SDK sessions and no network."""
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace

import mcp
import mcp.client.streamable_http
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from jarvis import plugins


SPEC = {
    'openapi': '3.0.3',
    'paths': {
        '/items/{id}': {
            'get': {
                'operationId': 'read_item',
                'summary': 'Read a synthetic item',
                'parameters': [
                    {'name': 'id', 'in': 'path', 'required': True,
                     'schema': {'type': 'integer', 'minimum': 1}},
                    {'name': 'format', 'in': 'query', 'required': True,
                     'schema': {'type': 'string', 'enum': ['short', 'full']}},
                    {'name': 'include_details', 'in': 'query',
                     'schema': {'type': 'boolean'}},
                ],
            },
        },
        '/unreviewed': {'get': {'operationId': 'read_unreviewed'}},
    },
}


def openapi_config():
    return plugins.PluginConfig(
        endpoint='http://127.0.0.1:8765', reviewed_read_tools=['read_item'],
        openapi=deepcopy(SPEC),
    )


def mcp_config(names=('read_item',)):
    return plugins.PluginConfig(
        endpoint='http://127.0.0.1:8765/mcp', reviewed_read_tools=list(names),
    )


def tool(name='read_item', schema=None, **extra):
    return SimpleNamespace(
        name=name, description='Synthetic tool',
        inputSchema=deepcopy(schema if schema is not None else {
            'type': 'object', 'properties': {'id': {'type': 'integer', 'minimum': 1}},
            'required': ['id'], 'additionalProperties': False,
        }), **extra,
    )


@pytest.fixture
def sdk(monkeypatch):
    """Replace only SDK/network boundaries; execute real transport validation."""
    state = SimpleNamespace(tools=[tool()], calls=[], contexts=[], initialized=0)

    @asynccontextmanager
    async def client(*args, **kwargs):
        state.contexts.append('network_enter')
        try:
            yield object()
        finally:
            state.contexts.append('network_exit')

    @asynccontextmanager
    async def stream(*args, **kwargs):
        state.contexts.append('stream_enter')
        try:
            yield object(), object(), lambda: None
        finally:
            state.contexts.append('stream_exit')

    class Session:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            state.contexts.append('session_enter')
            return self

        async def __aexit__(self, *args):
            state.contexts.append('session_exit')

        async def initialize(self):
            state.initialized += 1

        async def list_tools(self):
            return SimpleNamespace(tools=state.tools)

        async def call_tool(self, name, arguments):
            state.calls.append((name, arguments))
            return SimpleNamespace(model_dump=lambda **kwargs: {'content': [{'type': 'text', 'text': 'Synthetic reply'}]})

    monkeypatch.setattr(plugins.network, 'client', client)
    monkeypatch.setattr(mcp.client.streamable_http, 'streamable_http_client', stream)
    monkeypatch.setattr(mcp, 'ClientSession', Session)
    return state


def test_openapi_catalog_exposes_a_complete_strict_argument_contract_without_network(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail('Building a local OpenAPI catalog must not perform a request')
    monkeypatch.setattr(plugins.network, 'json_request', forbidden)
    listed = asyncio.run(plugins.openapi_tools(openapi_config()))
    assert [item['name'] for item in listed] == ['read_item']
    definition = listed[0]
    assert definition['read_only'] is True
    assert definition['description'] == 'Read a synthetic item'
    schema = definition['inputSchema']
    assert schema['type'] == 'object'
    assert schema['additionalProperties'] is False
    assert set(schema['required']) == {'id', 'format'}
    validator = Draft202012Validator(schema)
    validator.validate({'id': 1, 'format': 'short'})
    validator.validate({'id': 2, 'format': 'full', 'include_details': True})
    for invalid in ({'id': 0, 'format': 'short'}, {'id': 1},
                    {'id': 1, 'format': 'other'}, {'id': 1, 'format': 'short', 'extra': 'rejected'}):
        with pytest.raises(ValidationError):
            validator.validate(invalid)


def test_mutating_openapi_discovery_result_does_not_rewrite_configured_validation(monkeypatch):
    config = openapi_config()
    listed = asyncio.run(plugins.openapi_tools(config))
    listed[0]['inputSchema']['properties']['id']['minimum'] = 100
    seen = []
    async def request(origin, method, path, **kwargs):
        seen.append(path)
        return {'source': 'synthetic'}
    monkeypatch.setattr(plugins.network, 'json_request', request)
    result = asyncio.run(plugins.openapi_call(config, 'read_item', {'id': 1, 'format': 'short'}))
    assert result['mode'] == 'live_readonly' and seen == ['/items/1']


def test_mcp_discovery_returns_only_locally_reviewed_tools_and_ignores_remote_permissions(sdk):
    sdk.tools = [tool(), tool('remote_granted', annotations={'readOnlyHint': True})]
    listed = asyncio.run(plugins.mcp_session(mcp_config()))
    assert [item['name'] for item in listed] == ['read_item']
    assert listed[0]['read_only_reviewed'] is True
    assert listed[0]['inputSchema']['required'] == ['id']
    assert sdk.calls == []
    assert sdk.contexts[-3:] == ['session_exit', 'stream_exit', 'network_exit']


def test_mcp_advertised_extra_argument_policy_is_preserved(sdk):
    sdk.tools = [tool(schema={'type': 'object', 'additionalProperties': {'type': 'string'}})]
    listed = asyncio.run(plugins.mcp_session(mcp_config()))
    assert listed[0]['inputSchema']['additionalProperties'] == {'type': 'string'}
    result = asyncio.run(plugins.mcp_session(mcp_config(), 'read_item', {'label': 'synthetic'}))
    assert result['mode'] == 'live_readonly'
    assert sdk.calls == [('read_item', {'label': 'synthetic'})]


@pytest.mark.parametrize('malformed', [
    True,
    [],
    {},
    {'type': 'array', 'items': {'type': 'string'}},
    {'type': 'object', 'properties': {'item': {'$ref': 'https://invalid.example/schema'}}},
    {'type': 'object', '$dynamicRef': '#recursive'},
    {'type': 'object', '$recursiveRef': '#'},
    {'type': 'object', 'properties': {'id': {'type': 'not-a-json-type'}}},
    {'type': 'object', 'description': 'ą' * 40000},
])
def test_mcp_malformed_reviewed_schema_is_rejected_before_tool_call(sdk, malformed):
    sdk.tools = [tool(schema=malformed)]
    for operation, arguments in ((None, None), ('read_item', {'id': 1})):
        with pytest.raises(ValueError):
            asyncio.run(plugins.mcp_session(mcp_config(), operation, arguments))
        assert sdk.calls == []
        assert sdk.contexts[-3:] == ['session_exit', 'stream_exit', 'network_exit']


@pytest.mark.parametrize('duplicate_name', ['read_item', 'unreviewed'])
def test_mcp_duplicate_tool_names_are_rejected_instead_of_silently_overwritten(sdk, duplicate_name):
    sdk.tools = [tool(), tool(duplicate_name), tool(duplicate_name)]
    with pytest.raises(ValueError):
        asyncio.run(plugins.mcp_session(mcp_config()))
    assert sdk.calls == []


@pytest.mark.parametrize('name', ['bad name', '1starts_with_digit', 'x' * 81, '../unsafe'])
def test_mcp_invalid_names_are_rejected_before_dispatch(sdk, name):
    sdk.tools = [tool(name)]
    # A configuration object avoids coupling this transport check to a future
    # configuration validator that may independently reject the same name.
    config = SimpleNamespace(endpoint='http://127.0.0.1:8765/mcp', secret_env=None,
                             reviewed_read_tools=[name])
    with pytest.raises(ValueError):
        asyncio.run(plugins.mcp_session(config, name, {'id': 1}))
    assert sdk.calls == []


def test_mcp_overlarge_listing_is_rejected_even_if_few_tools_are_reviewed(sdk):
    sdk.tools = [tool('read_'+str(index)) for index in range(101)]
    with pytest.raises(ValueError):
        asyncio.run(plugins.mcp_session(mcp_config(('read_0',))))
    assert sdk.calls == []


@pytest.mark.parametrize('arguments', [{}, {'id': -1}, {'id': True}, {'id': 1, 'extra': 'no'}])
def test_mcp_schema_rejects_invalid_arguments_before_call(sdk, arguments):
    with pytest.raises(ValueError):
        asyncio.run(plugins.mcp_session(mcp_config(), 'read_item', arguments))
    assert sdk.calls == []


def test_unreviewed_mcp_operation_never_enters_network_or_sdk_context(sdk):
    with pytest.raises(PermissionError):
        asyncio.run(plugins.call('mcp', mcp_config(), 'remote_granted', {}))
    assert sdk.contexts == [] and sdk.initialized == 0 and sdk.calls == []


def test_mutating_mcp_discovery_metadata_does_not_rewrite_next_call_contract(sdk):
    listed = asyncio.run(plugins.mcp_session(mcp_config()))
    listed[0]['inputSchema']['properties']['id']['minimum'] = 100
    result = asyncio.run(plugins.mcp_session(mcp_config(), 'read_item', {'id': 1}))
    assert result['mode'] == 'live_readonly'
    assert sdk.calls == [('read_item', {'id': 1})]


def test_nullable_nested_schema_remains_valid_without_regular_expressions():
    schema = {
        'type': 'object', 'properties': {
            'label': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
        }, 'required': ['label'], 'additionalProperties': False,
    }
    validator = Draft202012Validator(plugins.validated_input_schema(schema))
    validator.validate({'label': None})
    validator.validate({'label': 'synthetic'})
    with pytest.raises(ValidationError):
        validator.validate({'label': 42})


@pytest.mark.parametrize('keyword_schema', [
    {'type': 'string', 'pattern': '^[a-z]+$'},
    {'type': 'object', 'patternProperties': {'^item': {'type': 'string'}}},
])
def test_regex_schema_keywords_are_rejected_at_nested_schema_locations(keyword_schema):
    schema = {'type': 'object', 'properties': {'value': keyword_schema}}
    with pytest.raises(ValueError):
        plugins.validated_input_schema(schema)


def test_property_names_pattern_and_pattern_properties_are_ordinary_data_names():
    schema = {
        'type': 'object', 'properties': {
            'pattern': {'type': 'string'},
            'patternProperties': {'type': 'object', 'additionalProperties': {'type': 'string'}},
        }, 'required': ['pattern', 'patternProperties'], 'additionalProperties': False,
    }
    validator = Draft202012Validator(plugins.validated_input_schema(schema))
    validator.validate({'pattern': 'ordinary data', 'patternProperties': {'item': 'value'}})
    with pytest.raises(ValidationError):
        validator.validate({'pattern': 12, 'patternProperties': {}})


def test_schema_raw_node_budget_includes_annotation_metadata():
    # The limit also applies to raw metadata that Draft202012Validator ignores.
    within = {'type': 'object', 'examples': [None] * 509}
    assert plugins.validated_input_schema(within)['examples'] == [None] * 509
    with pytest.raises(ValueError):
        plugins.validated_input_schema({'type': 'object', 'examples': [None] * 510})


def test_deeply_nested_property_schemas_are_rejected_but_normal_nesting_works():
    shallow = {'type': 'string'}
    for _ in range(3):
        shallow = {'type': 'object', 'properties': {'child': shallow}}
    Draft202012Validator(plugins.validated_input_schema(shallow)).validate({
        'child': {'child': {'child': 'synthetic'}},
    })
    deep = {'type': 'string'}
    for _ in range(9):
        deep = {'type': 'object', 'properties': {'child': deep}}
    with pytest.raises(ValueError):
        plugins.validated_input_schema(deep)


@pytest.mark.parametrize('outer_keyword', ['allOf', 'anyOf', 'oneOf'])
def test_schema_branch_product_is_carried_through_nested_properties(outer_keyword):
    def schema(outer_count):
        choices = [{'type': 'string'} for _ in range(8)]
        return {
            'type': 'object', outer_keyword: [
                {'properties': {'value': {'anyOf': deepcopy(choices)}}}
                for _ in range(outer_count)
            ],
        }
    assert plugins.validated_input_schema(schema(8))['type'] == 'object'
    with pytest.raises(ValueError):
        plugins.validated_input_schema(schema(9))


@pytest.mark.parametrize('arguments', [[], False])
def test_falsey_nonobject_mcp_arguments_are_not_coerced_into_an_empty_object(sdk, arguments):
    sdk.tools = [tool(schema={'type': 'object', 'properties': {}, 'additionalProperties': False})]
    with pytest.raises(ValueError):
        asyncio.run(plugins.mcp_session(mcp_config(), 'read_item', arguments))
    assert sdk.calls == []
    assert sdk.contexts[-3:] == ['session_exit', 'stream_exit', 'network_exit']


def test_last_mcp_schema_is_pinned_before_call_and_contexts_close(sdk):
    config=mcp_config()
    pinned={'type':'object','properties':{'id':{'type':'integer','minimum':2}},'required':['id'],'additionalProperties':False}
    with pytest.raises(plugins.PluginStateChanged):
        asyncio.run(plugins.mcp_session(config,'read_item',{'id':2},expected_schema=pinned))
    assert sdk.calls==[]
    assert sdk.contexts.count('network_enter')==sdk.contexts.count('network_exit')==1
    assert sdk.contexts.count('session_enter')==sdk.contexts.count('session_exit')==1


def test_last_mcp_authorization_is_rechecked_after_listing(sdk):
    from fastapi import HTTPException
    checked=[]
    def revoked():
        checked.append(sdk.initialized)
        raise HTTPException(401,'Session revoked')
    with pytest.raises(HTTPException) as denied:
        asyncio.run(plugins.mcp_session(mcp_config(),'read_item',{'id':1},before_dispatch=revoked))
    assert denied.value.status_code==401 and checked==[1] and sdk.calls==[]
    assert sdk.contexts.count('network_enter')==sdk.contexts.count('network_exit')==1


def test_openapi_pin_and_last_authority_precede_network(monkeypatch):
    from fastapi import HTTPException
    async def forbidden(*args,**kwargs):pytest.fail('Denied request must not reach the network')
    monkeypatch.setattr(plugins.network,'json_request',forbidden)
    config=openapi_config()
    with pytest.raises(plugins.PluginStateChanged):
        asyncio.run(plugins.openapi_call(config,'read_item',{'id':1,'format':'short'},expected_schema={'type':'object'}))
    def revoked():raise HTTPException(401,'Session revoked')
    with pytest.raises(HTTPException) as denied:
        asyncio.run(plugins.openapi_call(config,'read_item',{'id':1,'format':'short'},before_dispatch=revoked))
    assert denied.value.status_code==401
