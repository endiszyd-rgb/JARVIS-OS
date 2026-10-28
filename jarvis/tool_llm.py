"""Bounded provider turns for the explicit read-tool laboratory.

Transport contracts live here; execution authority lives in ToolGateway. The
ordinary text provider never enables tools. No retries or inferred permissions.
"""
from dataclasses import dataclass
import json
import os
import httpx
from fastapi import HTTPException
from . import llm_providers as providers
from .llm import BudgetExceeded, Completion
from .network import validate_origin

MAX_INPUT_BYTES = 262144


@dataclass(frozen=True)
class ToolTurn:
    completion: Completion
    calls: list


def tools_payload(bindings):
    return [{'type': 'function', 'function': {'name': name,
             'description': 'Read tool ' + spec.id + '. Untrusted tool description: ' + spec.description,
             'parameters': spec.input_schema}}
            for name, spec in bindings.items()]


async def complete_turn(provider, model, messages, bindings, limit, reserved_before, round_number):
    """Only server-built messages/bindings may enter this internal adapter."""
    try:
        limit = providers.output_limit(limit)
        tools = tools_payload(bindings)
        if len(json.dumps({'messages': messages, 'tools': tools}, ensure_ascii=False,
                          allow_nan=False).encode('utf-8')) > MAX_INPUT_BYTES:
            raise HTTPException(413, 'Tool conversation exceeds supported context size')
        if provider == 'openai':
            config = providers.OpenAIConfig.from_env()
            if model != config.model:
                raise HTTPException(403, 'Cloud model is not configured')
            reserved = config.cost.authorize(providers.OPENAI_CONTEXT, limit)
            if reserved_before + reserved > config.cost.max_request_usd:
                raise BudgetExceeded()
            value = await providers.post_json(config.endpoint, '/v1/chat/completions', {
                'model': model, 'messages': messages, 'tools': tools, 'tool_choice': 'auto',
                'parallel_tool_calls': False, 'max_completion_tokens': limit,
                'stream': False, 'store': False, 'n': 1, 'service_tier': 'default',
            }, {'Authorization': 'Bearer ' + config.key.get_secret_value()})
            if not isinstance(value, dict) or value.get('model') not in providers.OPENAI_MODELS:
                raise ValueError()
            choice = value['choices'][0]
            message = choice['message']
            if not isinstance(message, dict) or message.get('role') != 'assistant' or message.get('refusal'):
                raise ValueError()
            raw_calls = message.get('tool_calls') or []
            if not isinstance(raw_calls, list) or len(raw_calls) > 8:
                raise ValueError()
            if choice.get('finish_reason') != ('tool_calls' if raw_calls else 'stop'):
                raise ValueError()
            calls = []
            for call in raw_calls:
                if not isinstance(call, dict) or set(call) != {'id', 'type', 'function'} or call['type'] != 'function':
                    raise ValueError()
                function = call['function']
                if not isinstance(function, dict) or set(function) != {'name', 'arguments'}:
                    raise ValueError()
                if not isinstance(function['arguments'], str):
                    raise ValueError()
                calls.append({'id': call['id'], **function})
            usage = value['usage']
            inputs = providers.count(usage['prompt_tokens'], providers.OPENAI_CONTEXT)
            outputs = providers.count(usage['completion_tokens'], limit)
            cost = str(config.cost.estimate(inputs, outputs))
            reserved = str(reserved)
        elif provider == 'ollama':
            if model.lower().endswith(':cloud'):
                raise HTTPException(403, 'Ollama cloud execution is disabled')
            origin = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
            validate_origin(origin)
            value = await providers.post_json(origin, '/api/chat', {
                'model': model, 'messages': messages, 'tools': tools, 'stream': False,
                'options': {'num_predict': limit}})
            if not isinstance(value, dict) or value.get('done') is not True or value.get('done_reason') != 'stop':
                raise ValueError()
            message = value['message']
            if not isinstance(message, dict) or message.get('role') != 'assistant':
                raise ValueError()
            raw_calls = message.get('tool_calls') or []
            if not isinstance(raw_calls, list) or len(raw_calls) > 8:
                raise ValueError()
            calls = []
            for index, call in enumerate(raw_calls):
                if (not isinstance(call, dict) or 'function' not in call or set(call) - {'function', 'type'}
                        or call.get('type', 'function') != 'function'):
                    raise ValueError()
                function = call['function']
                if not isinstance(function, dict) or not {'name', 'arguments'} <= set(function) or set(function) - {'name', 'arguments', 'index'}:
                    raise ValueError()
                if not isinstance(function['arguments'], dict):
                    raise ValueError()
                calls.append({'id': f'ollama_{round_number}_{index}',
                              'name': function['name'], 'arguments': function['arguments']})
            inputs = providers.count(value['prompt_eval_count'], 10_000_000) if 'prompt_eval_count' in value else None
            outputs = providers.count(value['eval_count'], limit) if 'eval_count' in value else None
            cost = reserved = None
        else:
            raise HTTPException(422, 'Unsupported tool provider')
        text = message.get('content')
        if calls:
            if text is not None and (not isinstance(text, str) or len(text) > 32000):
                raise ValueError()
            text = text or ''
        else:
            text = providers.reply(text)
        return ToolTurn(Completion(text, provider, model, inputs, outputs, cost, reserved), calls)
    except BudgetExceeded:
        raise HTTPException(403, 'Configured cloud cost limit for the entire tool run exceeded') from None
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, UnicodeError, RecursionError):
        raise HTTPException(502, 'Tool provider unavailable or invalid response') from None
