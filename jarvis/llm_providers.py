"""Explicit text-only providers. No retries, discovery, downloads or tool execution."""
from dataclasses import dataclass, field
from decimal import Decimal
import ipaddress
import json
import os
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from pydantic import SecretStr
from .llm import Completion, CostPolicy, BudgetExceeded, Message
from .network import validate_origin

OPENAI_MODELS = ('gpt-5.4-mini-2026-03-17', 'gpt-5.4-mini')
OPENAI_CONTEXT = 400_000  # Official model contract, reviewed 2026-10-26.
MAX_BODY = 1_048_576


def enabled(name):
    value = os.getenv(name, 'false').lower()
    if value not in ('true', 'false'):
        raise ValueError('Provider activation must be true or false')
    return value == 'true'


def loopback(url):
    host = urlsplit(url).hostname
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def output_limit(value=None):
    text = os.getenv('JARVIS_LLM_MAX_OUTPUT_TOKENS', '1024') if value is None else str(value)
    if not text.isascii() or not text.isdigit() or not 1 <= int(text) <= 32768:
        raise ValueError('Output token limit must be 1..32768')
    return int(text)


@dataclass(frozen=True)
class OpenAIConfig:
    model: str
    cost: CostPolicy
    key: SecretStr = field(repr=False)
    endpoint: str = 'https://api.openai.com'

    def __post_init__(self):
        validate_origin(self.endpoint)
        if self.model not in OPENAI_MODELS:
            raise ValueError('Unsupported priced model')
        if self.endpoint.rstrip('/') != 'https://api.openai.com' and not (loopback(self.endpoint) and urlsplit(self.endpoint).scheme == 'http'):
            raise ValueError('Only the official origin or an explicit loopback laboratory is supported')
        if not isinstance(self.key, SecretStr):
            raise ValueError('Key must use SecretStr')
        key = self.key.get_secret_value()
        if not 16 <= len(key) <= 512 or not key.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise ValueError('Provider key missing or invalid')
        if self.cost.input_usd_per_million <= 0 or self.cost.output_usd_per_million <= 0:
            raise ValueError('Cloud prices must be explicitly positive')

    @classmethod
    def from_env(cls):
        try:
            active = enabled('JARVIS_ALLOW_CLOUD_MODELS') and enabled('JARVIS_OPENAI_ENABLED')
        except ValueError:
            raise HTTPException(503, 'Cloud provider configuration is invalid') from None
        if not active:
            raise HTTPException(403, 'Cloud provider is disabled')
        try:
            cost = CostPolicy(Decimal(os.environ['JARVIS_OPENAI_INPUT_USD_PER_MILLION']),
                              Decimal(os.environ['JARVIS_OPENAI_OUTPUT_USD_PER_MILLION']),
                              Decimal(os.environ['JARVIS_OPENAI_MAX_REQUEST_USD']))
            output_limit()
            return cls(os.getenv('JARVIS_OPENAI_MODEL', OPENAI_MODELS[0]), cost,
                       SecretStr(os.getenv('JARVIS_OPENAI_API_KEY', '')),
                       os.getenv('JARVIS_OPENAI_URL', 'https://api.openai.com'))
        except (ValueError, KeyError, ArithmeticError):
            raise HTTPException(503, 'Cloud provider configuration is invalid') from None


def cloud_models():
    try:
        if not enabled('JARVIS_ALLOW_CLOUD_MODELS') or not enabled('JARVIS_OPENAI_ENABLED'):
            return []
        config = OpenAIConfig.from_env()
        return [{'provider': 'openai', 'name': config.model, 'cloud': True}]
    except ValueError:
        raise HTTPException(503, 'Cloud provider configuration is invalid') from None


def messages_payload(messages):
    if not 1 <= len(messages) <= 64:
        raise HTTPException(422, 'Unsupported conversation size')
    rows = []
    for message in messages:
        if not isinstance(message, Message) or message.role not in ('system', 'user', 'assistant') or not isinstance(message.content, str):
            raise HTTPException(422, 'Invalid provider message')
        rows.append({'role': message.role, 'content': message.content})
    if len(json.dumps(rows, ensure_ascii=False).encode('utf-8')) > 262144:
        raise HTTPException(413, 'Provider input exceeds supported size')
    return rows


async def post_json(origin, path, payload, headers=None):
    # Loopback laboratories remain local; public HTTPS preserves the session proxy/CA.
    async with httpx.AsyncClient(timeout=60, trust_env=not loopback(origin), follow_redirects=False) as client:
        async with client.stream('POST', origin.rstrip('/') + path, json=payload, headers=headers) as response:
            response.raise_for_status()
            body = bytearray()
            async for block in response.aiter_bytes():
                body.extend(block)
                if len(body) > MAX_BODY:
                    raise ValueError('Provider response too large')
            return json.loads(body)


def reply(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 32000:
        raise ValueError('Invalid provider text')
    return value


def count(value, bound):
    if type(value) is not int or not 0 <= value <= bound:
        raise ValueError('Invalid provider usage')
    return value


class OllamaProvider:
    async def complete(self, messages, model, max_output_tokens):
        try:
            if model.lower().endswith(':cloud'):
                raise HTTPException(403, 'Use the explicitly priced cloud provider; Ollama cloud execution is disabled')
            origin = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
            validate_origin(origin)
            limit = output_limit(max_output_tokens)
            value = await post_json(origin, '/api/chat', {'model': model, 'stream': False,
                'messages': messages_payload(messages), 'options': {'num_predict': limit}})
            return Completion(reply(value['message']['content']), 'ollama', model,
                count(value['prompt_eval_count'], 10_000_000) if 'prompt_eval_count' in value else None,
                count(value['eval_count'], limit) if 'eval_count' in value else None)
        except HTTPException:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, UnicodeError):
            raise HTTPException(502, 'Ollama unavailable or invalid response') from None


class OpenAIProvider:
    async def complete(self, messages, model, max_output_tokens):
        config = OpenAIConfig.from_env()  # Activation is checked again for every request.
        if model != config.model:
            raise HTTPException(403, 'Cloud model is not configured')
        try:
            limit = output_limit(max_output_tokens)
            rows = messages_payload(messages)
            # Reserve the entire supported context, not a guessed tokenization of text.
            reserved = config.cost.authorize(OPENAI_CONTEXT, limit)
            value = await post_json(config.endpoint, '/v1/chat/completions', {
                'model': model, 'messages': rows, 'max_completion_tokens': limit,
                'stream': False, 'store': False, 'n': 1, 'service_tier': 'default',
            }, {'Authorization': 'Bearer ' + config.key.get_secret_value()})
            if not isinstance(value, dict) or value.get('model') not in OPENAI_MODELS:
                raise ValueError('Unexpected cloud model')
            choice = value['choices'][0]
            if not isinstance(choice, dict) or not isinstance(choice.get('message'), dict):
                raise ValueError('Invalid completion structure')
            if choice.get('finish_reason') != 'stop' or choice['message'].get('tool_calls') or choice['message'].get('refusal'):
                raise ValueError('Incomplete or non-text completion')
            usage = value['usage']
            inputs, outputs = count(usage['prompt_tokens'], OPENAI_CONTEXT), count(usage['completion_tokens'], limit)
            cost = config.cost.estimate(inputs, outputs)
            return Completion(reply(choice['message']['content']), 'openai', model, inputs, outputs,
                              str(cost), str(reserved))
        except BudgetExceeded:
            raise HTTPException(403, 'Configured per-request cloud cost limit exceeded') from None
        except HTTPException:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, UnicodeError):
            raise HTTPException(502, 'Cloud provider unavailable or invalid response') from None


def provider(name):
    if name == 'ollama':
        return OllamaProvider()
    if name == 'openai':
        return OpenAIProvider()
    raise HTTPException(422, 'Unsupported LLM provider')
