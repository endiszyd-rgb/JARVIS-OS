"""Configured read-only plugin transports. No local process spawning."""
import asyncio
import copy
import json
import os
import re
from typing import Literal
from urllib.parse import quote
from pydantic import BaseModel, ConfigDict, Field, model_validator
from jsonschema import Draft202012Validator
from . import network

TOOL_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,79}\Z')
MAX_TOOLS = 100
MAX_SCHEMA_BYTES = 65536
MAX_SCHEMA_NODES = 512
MAX_SCHEMA_DEPTH = 16
MAX_SCHEMA_BRANCH_PRODUCT = 64

class PluginResultError(ValueError):
    """The remote reply violates its result contract, not the caller's input."""

class PluginStateChanged(ValueError):
    """The last observed input schema differs from the server-selected schema."""

class PluginConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    endpoint: str = Field(max_length=500)
    secret_env: str | None = Field(default=None, pattern=r'^JARVIS_PLUGIN_SECRET_[A-Z0-9_]{1,60}$')
    # These operations are reviewed locally by the owner, never granted by remote annotations.
    reviewed_read_tools: list[str] = Field(default_factory=list,max_length=100)
    openapi: dict | None = None

    @model_validator(mode='after')
    def safe(self):
        if (len(set(self.reviewed_read_tools)) != len(self.reviewed_read_tools) or
                any(not TOOL_NAME.fullmatch(name) for name in self.reviewed_read_tools)):
            raise ValueError('Reviewed tool names must be valid and unique')
        network.validate_origin(self.endpoint,allow_path=True)
        if self.openapi is not None:
            network.validate_origin(self.endpoint)
            try:
                inspect_openapi(self.openapi)
            except Exception as exc:
                raise ValueError('Invalid or unsupported OpenAPI schema') from exc
        return self


def inspect_openapi(spec):
    """OpenAPI 3.x safe subset: GET, operationId, scalar path/query params; no $ref."""
    if not str(spec.get('openapi','')).startswith('3.') or not isinstance(spec.get('paths'),dict):
        raise ValueError('OpenAPI 3.x with paths required')
    def refs(value):
        if isinstance(value,dict):
            return any(k in value for k in ('$ref','$dynamicRef','$recursiveRef')) or any(refs(v) for v in value.values())
        if isinstance(value,list): return any(refs(v) for v in value)
        return False
    if refs(spec):
        raise ValueError('$ref is not supported; supply a bundled scalar schema')
    found={}
    for path,item in spec['paths'].items():
        if not re.fullmatch(r'/[A-Za-z0-9_/{}/.\-]*',path) or '..' in path or path.startswith('//') or not isinstance(item,dict):
            raise ValueError('Invalid OpenAPI path')
        for method,op in item.items():
            if method=='parameters': continue
            if method not in ('get','post','put','patch','delete','head','options','trace'):
                continue
            if method!='get': continue
            if not isinstance(op,dict) or op.get('requestBody'):
                raise ValueError('GET bodies are unsupported')
            name=op.get('operationId')
            if not name or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,79}',name) or name in found:
                raise ValueError('GET operationId must be unique and valid')
            params=item.get('parameters',[])+op.get('parameters',[])
            names=set()
            for param in params:
                if not isinstance(param,dict) or param.get('in') not in ('path','query') or param.get('schema',{}).get('type') not in ('string','integer','number','boolean'):
                    raise ValueError('Only scalar path/query parameters are supported')
                key=param.get('name','')
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,60}',key) or key in names:
                    raise ValueError('Duplicate or invalid parameter name')
                names.add(key)
                if param['in']=='path' and not param.get('required'):
                    raise ValueError('Path parameters must be required')
            placeholders=set(re.findall(r'{([^}]+)}',path))
            if placeholders!={p['name'] for p in params if p['in']=='path'}:
                raise ValueError('Path placeholders do not match parameters')
            operation={'path':path,'parameters':params,'description':op.get('summary','')}
            openapi_input_schema(operation)
            found[name]=operation
    return found


def reject_schema_refs(value):
    if isinstance(value,dict):
        if any(k in value for k in ('$ref','$dynamicRef','$recursiveRef')):
            raise ValueError('Schema references are disabled')
        for item in value.values(): reject_schema_refs(item)
    elif isinstance(value,list):
        for item in value: reject_schema_refs(item)


def validated_input_schema(schema):
    """Return a detached, bounded object schema without reference resolution."""
    if not isinstance(schema, dict) or schema.get('type') != 'object':
        raise ValueError('Tool input schema must describe an object')
    try:
        stack, nodes = [(schema, 0)], 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            if nodes > MAX_SCHEMA_NODES or depth > MAX_SCHEMA_DEPTH:
                raise ValueError('Tool input schema is too complex')
            if isinstance(value, dict):
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)
        # JSON Schema regular expressions use a backtracking implementation;
        # untrusted remote patterns cannot be bounded by an async I/O deadline.
        # Inspect schema locations rather than property names such as 'pattern'.
        schemas = [(schema, 1)]
        while schemas:
            current, branch_product = schemas.pop()
            if not isinstance(current, dict):
                continue
            if 'pattern' in current or 'patternProperties' in current:
                raise ValueError('Regular expression schema keywords are disabled')
            for keyword in ('properties', '$defs', 'definitions', 'dependentSchemas'):
                mapping = current.get(keyword)
                if isinstance(mapping, dict):
                    schemas.extend((item, branch_product) for item in mapping.values())
            for keyword in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
                choices = current.get(keyword)
                if isinstance(choices, list):
                    cost = branch_product if keyword == 'prefixItems' else branch_product * max(1, len(choices))
                    if cost > MAX_SCHEMA_BRANCH_PRODUCT:
                        raise ValueError('Tool schema branches exceed their supported limit')
                    schemas.extend((item, cost) for item in choices)
            for keyword in ('items', 'contains', 'not', 'if', 'then', 'else',
                            'additionalProperties', 'unevaluatedProperties',
                            'unevaluatedItems', 'propertyNames', 'contentSchema'):
                schemas.append((current.get(keyword), branch_product))
        encoded = json.dumps(schema, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(encoded) > MAX_SCHEMA_BYTES:
            raise ValueError('Tool input schema exceeds 64 KiB')
        reject_schema_refs(schema)
        Draft202012Validator.check_schema(schema)
        return copy.deepcopy(schema)
    except Exception:
        raise ValueError('Invalid or unsupported tool input schema') from None


def openapi_input_schema(operation):
    """Describe the same scalar arguments accepted by the GET transport."""
    parameters = operation['parameters']
    return validated_input_schema({
        'type': 'object',
        'properties': {param['name']: copy.deepcopy(param['schema']) for param in parameters},
        'required': [param['name'] for param in parameters if param.get('required')],
        'additionalProperties': False,
    })


def _mcp_tools(listed, config):
    if not isinstance(listed, list) or len(listed) > MAX_TOOLS:
        raise ValueError('MCP tool listing exceeds its supported limit')
    names, reviewed = set(), {}
    for tool in listed:
        name = getattr(tool, 'name', None)
        if not isinstance(name, str) or not TOOL_NAME.fullmatch(name) or name in names:
            raise ValueError('MCP tool names must be valid and unique')
        names.add(name)
        if name in config.reviewed_read_tools:
            schema = validated_input_schema(tool.inputSchema)
            reviewed[name] = {
                'name': name, 'description': tool.description,
                'inputSchema': schema, 'read_only_reviewed': True,
            }
    return reviewed


def bearer(config):
    if not config.secret_env: return {}
    secret=os.getenv(config.secret_env,'')
    if not secret or '\r' in secret or '\n' in secret:
        raise ValueError('Configured plugin secret is missing or invalid')
    return {'Authorization':'Bearer '+secret}


async def openapi_tools(config):
    if config.openapi is None: raise ValueError('OpenAPI schema not configured')
    operations=inspect_openapi(config.openapi)
    return [{'name':name,'description':op['description'],'read_only':True,
             'inputSchema':openapi_input_schema(op)}
            for name,op in operations.items() if name in config.reviewed_read_tools]


async def openapi_call(config,name,arguments,*,expected_schema=None,before_dispatch=None):
    if name not in config.reviewed_read_tools:
        raise PermissionError('Operation not reviewed for read-only use')
    operations=inspect_openapi(config.openapi or {})
    if name not in operations: raise ValueError('GET operation missing')
    op=operations[name]
    schema=openapi_input_schema(op)
    if expected_schema is not None and schema!=expected_schema:
        raise PluginStateChanged('Tool schema changed')
    Draft202012Validator(schema).validate(arguments)
    if set(arguments)-{p['name'] for p in op['parameters']}:
        raise ValueError('Unknown argument')
    path=op['path'];query={}
    for p in op['parameters']:
        key=p['name']
        if key not in arguments:
            if p.get('required'): raise ValueError('Required argument missing')
            continue
        value=arguments[key]
        Draft202012Validator(p['schema']).validate(value)
        text=str(value).lower() if isinstance(value,bool) else str(value)
        if p['in']=='path':
            if text in ('.','..') or '/' in text or '\\' in text or '%' in text or '?' in text or '#' in text or not text:
                raise ValueError('Unsafe path argument')
            path=path.replace('{'+key+'}',quote(text,safe=''))
        else: query[key]=text
    if before_dispatch is not None:before_dispatch()
    data=await network.json_request(config.endpoint,'GET',path,headers=bearer(config),params=query)
    return {'mode':'live_readonly','protocol':'openapi','data':data}


async def mcp_session(config,operation=None,arguments=None,*,expected_schema=None,before_dispatch=None):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    error=None
    result=None
    call_arguments = {} if arguments is None else arguments
    async with asyncio.timeout(25):
        async with network.client(config.endpoint,headers=bearer(config),timeout=15) as client:
            async with streamable_http_client(config.endpoint,http_client=client,terminate_on_close=True) as streams:
                async with ClientSession(streams[0],streams[1]) as session:
                    await session.initialize()
                    listed=await session.list_tools()
                    try:
                        tools = _mcp_tools(listed.tools, config)
                    except ValueError:
                        error = ValueError('Invalid or unsupported MCP tool listing/schema')
                    if error is None and operation is None:
                        result = list(tools.values())
                    elif error is None and operation not in tools:
                        error = PermissionError('Tool not reviewed for read-only use')
                    elif error is None:
                        try:
                            schema=tools[operation]['inputSchema']
                            Draft202012Validator(schema).validate(call_arguments)
                        except Exception:
                            error=ValueError('Invalid or unsupported MCP arguments/schema')
                        if error is None:
                            try:
                                if expected_schema is not None and schema!=expected_schema:
                                    raise PluginStateChanged('Tool schema changed')
                                if before_dispatch is not None:before_dispatch()
                            except Exception as exc:
                                # Raise after SDK context cleanup rather than wrapping
                                # a controlled authorization failure in a task group.
                                error=exc
                        if error is None:
                            response=await session.call_tool(operation,call_arguments)
                            result={'mode':'live_readonly','protocol':'mcp','result':response.model_dump(mode='json',exclude_none=True)}
    if error: raise error
    if len(json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8'))>1024*1024:
        raise PluginResultError('MCP result exceeds 1 MiB')
    return result


async def tools(protocol,config):
    return await (openapi_tools(config) if protocol=='openapi' else mcp_session(config))


async def call(protocol,config,name,arguments,*,expected_schema=None,before_dispatch=None):
    # No call is attempted for unreviewed tools, even to a remote MCP endpoint.
    if name not in config.reviewed_read_tools:
        raise PermissionError('Operation not reviewed for read-only use')
    checks={'expected_schema':expected_schema,'before_dispatch':before_dispatch}
    return await (openapi_call(config,name,arguments,**checks) if protocol=='openapi' else mcp_session(config,name,arguments,**checks))
