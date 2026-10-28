"""Validate an untrusted tool-call batch before any dispatch.

Bindings are server-owned aliases of selected ToolSpecs. Validation grants no
permissions: callers must still execute through ToolGateway with a verified
Principal and current configuration for each call. tool_loop owns the bounded
conversation; this module performs validation only.
"""
from dataclasses import dataclass
import json
import re
from collections.abc import Mapping
from jsonschema import Draft202012Validator
from .tool_registry import ToolSpec, _bounded_argument_tree

_ALIAS = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
_ID = re.compile(r'[A-Za-z0-9_-]{1,80}\Z')
MAX_CALLS = 8


@dataclass(frozen=True)
class PlannedCall:
    id: str
    tool: ToolSpec
    arguments_json: str

    @property
    def arguments(self):
        return json.loads(self.arguments_json)


def validate_calls(raw, bindings: Mapping[str, ToolSpec], *, previous_ids=frozenset(), remaining=MAX_CALLS):
    if type(remaining) is not int or not 0 <= remaining <= MAX_CALLS:
        raise ValueError('Invalid remaining call budget')
    if not isinstance(raw, list) or len(raw) > remaining or len(bindings) > 100:
        raise ValueError('Tool-call budget exceeded')
    if any(not isinstance(name, str) or not _ALIAS.fullmatch(name) or not isinstance(spec, ToolSpec)
           for name, spec in bindings.items()):
        raise ValueError('Invalid server tool bindings')
    seen = set(previous_ids)
    result = []
    for call in raw:
        if not isinstance(call, dict) or set(call) != {'id', 'name', 'arguments'}:
            raise ValueError('Invalid tool-call structure')
        ident, name, arguments = call['id'], call['name'], call['arguments']
        if not isinstance(ident, str) or not _ID.fullmatch(ident) or ident in seen:
            raise ValueError('Duplicate or invalid tool-call ID')
        if not isinstance(name, str) or name not in bindings:
            raise ValueError('Tool is outside the server-selected catalog')
        try:
            if isinstance(arguments, str):
                if len(arguments.encode('utf-8')) > 65536:
                    raise ValueError()
                arguments = json.loads(arguments)
            if not isinstance(arguments, dict):
                raise ValueError()
            _bounded_argument_tree(arguments)
            encoded = json.dumps(arguments, ensure_ascii=False, allow_nan=False, sort_keys=True)
            if len(encoded.encode('utf-8')) > 65536 or not Draft202012Validator(bindings[name].input_schema).is_valid(arguments):
                raise ValueError()
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise ValueError('Tool arguments violate the supported schema or limits') from None
        result.append(PlannedCall(ident, bindings[name], encoded))
        seen.add(ident)
    return tuple(result)
