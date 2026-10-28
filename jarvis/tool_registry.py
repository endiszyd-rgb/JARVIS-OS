"""Server-owned tool descriptions and one bounded, read-only execution gateway.

Remote descriptions and readOnlyHint annotations are data. Only the locally
configured reviewed operation names grant eligibility; a digest describes the
schema currently observed and is not a pinned approval of server behavior.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import threading

from fastapi import HTTPException
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .identity import Principal, ROLES
from . import plugins


_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,79}\Z')
_PLUGIN = re.compile(r'[a-z][a-z0-9_]{1,40}\Z')
_PROTOCOLS = ('demo', 'openapi', 'mcp')
_DOMAINS = ('calendar', 'orders', 'vehicles', 'parts', 'customers', 'finances', 'reports', 'notifications')
_EMPTY_ARGUMENTS = {'type': 'object', 'properties': {}, 'additionalProperties': False}
_BLOCKED = {'status': 'blocked', 'reason': 'Physical and write side effects disabled in this release'}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _schema(value):
    try:
        return plugins.validated_input_schema(value)
    except (ValueError, TypeError, UnicodeError, RecursionError, SchemaError):
        raise ValueError('Invalid or unsupported tool input schema') from None


def _plugin(value):
    if not isinstance(value, str) or not _PLUGIN.fullmatch(value):
        raise ValueError('Invalid plugin identifier')
    return value


def _name(value):
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError('Invalid tool operation name')
    return value


def _bounded_argument_tree(value):
    # Bound work before canonical serialization and schema evaluation. A byte
    # limit alone still permits very deep trees or many tiny array elements.
    pending, visited = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        visited += 1
        if visited > 512 or depth > 16:
            raise ValueError('Tool argument structure exceeds its supported limit')
        children = item.values() if isinstance(item, dict) else item if isinstance(item, (list, tuple)) else ()
        if visited + len(pending) + len(children) > 512:
            raise ValueError('Tool argument structure exceeds its supported limit')
        pending.extend((child, depth + 1) for child in children)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    plugin_id: str
    name: str
    protocol: str
    description: str
    schema_json: str = field(repr=False)
    schema_digest: str = field(init=False)

    def __post_init__(self):
        _plugin(self.plugin_id)
        _name(self.name)
        if self.protocol not in _PROTOCOLS:
            raise ValueError('Unsupported tool protocol')
        if not isinstance(self.description, str) or len(self.description) > 4000:
            raise ValueError('Invalid tool description')
        try:
            schema = _schema(json.loads(self.schema_json))
            canonical = _canonical(schema)
        except (ValueError, TypeError, RecursionError):
            raise ValueError('Invalid or unsupported tool input schema') from None
        object.__setattr__(self, 'schema_json', canonical)
        identity = {'plugin_id': self.plugin_id, 'name': self.name,
                    'protocol': self.protocol, 'inputSchema': schema}
        object.__setattr__(self, 'schema_digest', hashlib.sha256(_canonical(identity).encode('utf-8')).hexdigest())

    @property
    def id(self):
        return self.plugin_id + '.' + self.name

    @property
    def operation(self):
        return self.name

    @property
    def required_scope(self):
        return 'plugins:invoke'

    @property
    def input_schema(self):
        # An immutable spec never exposes its internal schema as a mutable dict.
        return json.loads(self.schema_json)

    def public(self):
        return {'id': self.id, 'plugin_id': self.plugin_id, 'name': self.name,
                'description': self.description, 'protocol': self.protocol,
                'inputSchema': self.input_schema, 'schema_digest': self.schema_digest,
                'read_only_reviewed': True, 'read_only': True,
                'required_scope': self.required_scope}


def _tool(pid, name, protocol, description, schema):
    return ToolSpec(_plugin(pid), _name(name), protocol, description or '', _canonical(_schema(schema)))


def demo_tools(pid):
    _plugin(pid)
    names = _DOMAINS if pid == 'autologika' else ('status',)
    return tuple(_tool(pid, name, 'demo', 'Synthetic demonstration; no external request', _EMPTY_ARGUMENTS)
                 for name in names)


def openapi_tools(pid, config):
    _plugin(pid)
    if not isinstance(config, plugins.PluginConfig) or config.openapi is None:
        raise ValueError('OpenAPI schema is not configured')
    operations = plugins.inspect_openapi(config.openapi)
    if len(operations) > 100:
        raise ValueError('Tool catalog exceeds 100 operations')
    found = []
    for name, operation in operations.items():
        _name(name)
        if name not in config.reviewed_read_tools:
            continue
        schema = plugins.openapi_input_schema(operation)
        found.append(_tool(pid, name, 'openapi', operation['description'], schema))
    return tuple(found)


def mcp_tools(pid, config, listed):
    _plugin(pid)
    if not isinstance(config, plugins.PluginConfig) or not isinstance(listed, (list, tuple)) or len(listed) > 100:
        raise ValueError('Invalid or oversized MCP catalog')
    seen, found = set(), []
    for item in listed:
        if not isinstance(item, dict):
            raise ValueError('Invalid MCP tool entry')
        name = _name(item.get('name'))
        if name in seen:
            raise ValueError('Duplicate MCP tool operation')
        seen.add(name)
        # Unreviewed remote annotations do not grant eligibility.
        if name in config.reviewed_read_tools:
            found.append(_tool(pid, name, 'mcp', item.get('description'), item.get('inputSchema')))
    return tuple(found)


class ToolGateway:
    def __init__(self, timeout_seconds=30, max_concurrent=4, max_input_bytes=65536, max_result_bytes=1048576):
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120):
            raise ValueError('Tool deadline must be finite and between 0 and 120 seconds')
        for value in (max_concurrent, max_input_bytes, max_result_bytes):
            if type(value) is not int or value < 1:
                raise ValueError('Tool limits must be positive integers')
        self.timeout_seconds = timeout_seconds
        self.max_concurrent = max_concurrent
        self.max_input_bytes = max_input_bytes
        self.max_result_bytes = max_result_bytes
        self._active = 0
        self._lock = threading.Lock()

    @staticmethod
    def _authorize(principal, scope):
        # Only the authentication layer constructs these objects. A caller/model
        # dict or a caller-channel identity must never become execution authority.
        if not isinstance(principal, Principal) or principal.kind not in ('owner_key', 'session', 'service'):
            raise HTTPException(403, 'Verified tool identity required')
        if principal.kind == 'owner_key':
            if principal.id != 'owner-key' or principal.role != 'owner':
                raise HTTPException(403, 'Invalid tool identity')
            return
        if principal.kind == 'session':
            if principal.role not in ROLES or principal.scopes != ROLES[principal.role]:
                raise HTTPException(403, 'Invalid tool identity')
            if principal.is_owner:
                return
        elif principal.role != 'service':
            raise HTTPException(403, 'Invalid tool identity')
        if scope not in principal.scopes:
            raise HTTPException(403, 'Insufficient tool scope')

    @staticmethod
    def _configuration(pid, protocol, enabled, config, discover=False):
        try:
            _plugin(pid)
        except ValueError:
            raise HTTPException(422, 'Invalid plugin identifier') from None
        if not enabled:
            raise HTTPException(409, 'Plugin disabled')
        if protocol not in _PROTOCOLS:
            raise HTTPException(422, 'Unsupported tool protocol')
        if protocol != 'demo' and not isinstance(config, plugins.PluginConfig):
            raise HTTPException(409 if discover else 501, 'Plugin endpoint is not configured')

    @asynccontextmanager
    async def _bounded(self):
        with self._lock:
            if self._active >= self.max_concurrent:
                raise HTTPException(429, 'Tool execution capacity exceeded')
            self._active += 1
        try:
            async with asyncio.timeout(self.timeout_seconds):
                yield
        except TimeoutError:
            raise HTTPException(504, 'Tool request timed out') from None
        finally:
            with self._lock:
                self._active -= 1

    def _arguments(self, value):
        try:
            if not isinstance(value, dict):
                raise ValueError()
            _bounded_argument_tree(value)
            encoded = _canonical(value)
            if len(encoded.encode('utf-8')) > self.max_input_bytes:
                raise ValueError()
            return json.loads(encoded)
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise HTTPException(422, 'Invalid or oversized tool arguments') from None

    def _result(self, result):
        try:
            encoded = _canonical(result)
            if len(encoded.encode('utf-8')) > self.max_result_bytes:
                raise ValueError()
            return json.loads(encoded)
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise HTTPException(502, 'Tool result is invalid or exceeds its size limit') from None

    @staticmethod
    async def _remote(awaitable):
        try:
            return await awaitable
        except HTTPException:
            raise
        except plugins.PluginStateChanged:
            raise HTTPException(409, 'Tool schema changed; start a new reviewed conversation') from None
        except PermissionError:
            raise HTTPException(403, 'Operation not reviewed for read-only use') from None
        except plugins.PluginResultError:
            raise HTTPException(502, 'Tool result is invalid or exceeds its size limit') from None
        except (ValueError, ValidationError, SchemaError):
            raise HTTPException(422, 'Invalid tool request, schema or network configuration') from None
        except TimeoutError:
            raise HTTPException(504, 'Tool request timed out') from None
        except Exception:
            raise HTTPException(502, 'Tool transport failed') from None

    async def _catalog(self, pid, protocol, config):
        try:
            if protocol == 'demo':
                return demo_tools(pid)
            if protocol == 'openapi':
                return openapi_tools(pid, config)
            listed = await self._remote(plugins.tools(protocol, config))
            return mcp_tools(pid, config, listed)
        except ValueError:
            raise HTTPException(422, 'Invalid or unsupported tool catalog') from None

    async def discover(self, principal, pid, protocol, enabled, config):
        self._authorize(principal, 'plugins:read')
        self._configuration(pid, protocol, enabled, config, discover=True)
        async with self._bounded():
            catalog = await self._catalog(pid, protocol, config)
            return self._result([tool.public() for tool in catalog])

    def publish_catalog(self, principal, tools, discovery_required):
        """Bound a local aggregate without starting discovery or any transport."""
        self._authorize(principal, 'plugins:read')
        if (not isinstance(tools, list) or any(not isinstance(item, dict) for item in tools)
                or not isinstance(discovery_required, list)
                or any(not isinstance(item, str) for item in discovery_required)):
            raise HTTPException(422, 'Invalid local tool catalog')
        return self._result({'tools': tools, 'discovery_required': discovery_required,
                             'network_requests_sent': False})

    async def execute(self, principal, pid, protocol, enabled, config, operation, arguments, *, expected_digest=None, before_dispatch=None):
        self._authorize(principal, 'plugins:invoke')
        self._configuration(pid, protocol, enabled, config)
        arguments = self._arguments(arguments)
        # Keep the legacy explicit side-effect guard ahead of operation lookup.
        if arguments.get('live') or arguments.get('dry_run') is False:
            return dict(_BLOCKED)
        try:
            _name(operation)
        except ValueError:
            raise HTTPException(422, 'Invalid tool operation name') from None
        if protocol != 'demo' and operation not in config.reviewed_read_tools:
            raise HTTPException(403, 'Operation not reviewed for read-only use')
        async with self._bounded():
            catalog = await self._catalog(pid, protocol, config)
            tool = next((entry for entry in catalog if entry.name == operation), None)
            if tool is None:
                raise HTTPException(422 if protocol == 'demo' else 403, 'Tool operation is not registered')
            if expected_digest is not None and tool.schema_digest != expected_digest:
                raise HTTPException(409, 'Tool schema changed; start a new reviewed conversation')
            try:
                Draft202012Validator(tool.input_schema).validate(arguments)
            except (ValidationError, SchemaError, ValueError, TypeError, RecursionError):
                raise HTTPException(422, 'Invalid tool arguments') from None
            # A tool conversation can wait for MCP discovery. Recheck current
            # server authority/configuration after that await, immediately before I/O.
            if before_dispatch is not None:
                self._authorize(before_dispatch(), 'plugins:invoke')
            if protocol == 'demo':
                if pid == 'autologika':
                    result = {'mode': 'demo', 'domain': operation, 'source': 'synthetic_fixture',
                              'items': [{'id': 'DEMO-001', 'label': 'Dane demonstracyjne: ' + operation, 'status': 'example'}]}
                else:
                    result = {'mode': 'demo', 'status': 'simulated', 'plugin': pid,
                              'operation': operation, 'external_request_sent': False}
            else:
                if expected_digest is not None or before_dispatch is not None:
                    def recheck():
                        if before_dispatch is not None:
                            self._authorize(before_dispatch(), 'plugins:invoke')
                    result = await self._remote(plugins.call(protocol, config, operation, arguments,
                        expected_schema=tool.input_schema, before_dispatch=recheck))
                else:
                    result = await self._remote(plugins.call(protocol, config, operation, arguments))
            return self._result(result)
