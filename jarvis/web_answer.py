"""Workshop questions answered from the internet by an AI with server-side web search.

Used by the hands-free path (Siri shortcut → POST /api/v1/voice/ask): "jaki moment dokręcania śrub koła
Golf 7?" → the model searches the web, answers in two or three spoken Polish sentences and names its source.
Providers: ``groq`` (default; free plan without a card, ``groq/compound`` with built-in web search) or
``anthropic`` (paid, Claude with the ``web_search_20250305`` tool). The keys are the owner's own, stored
like the other secrets (masked in every response).
Answers are internet data, never verified manufacturer data — the prompt makes the model say where a value
comes from and when sources disagree, and the reply carries the source links for the phone.
"""
import json
import re
import time
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

API = 'https://api.anthropic.com'
GROQ_API = 'https://api.groq.com/openai/v1'
SECRET_MASK = '••••••••'
MODELS = ('claude-sonnet-5-5', 'claude-haiku-5-5', 'claude-opus-5-5')
GROQ_MODELS = ('groq/compound', 'groq/compound-mini')
SECRETS = ('api_key', 'groq_api_key')
MAX_BODY = 2 * 1024 * 1024
HISTORY_SECONDS = 15 * 60
HISTORY_TURNS = 3

SYSTEM = """Jesteś JARVIS — asystent mechanika w warsztacie samochodowym. Mechanik pyta głosem, ma brudne ręce i słucha odpowiedzi w słuchawce.
Zasady:
- Odpowiadasz po polsku, maksymalnie 3 krótkie zdania, bez list, tabel, nagłówków i adresów www (tekst zostanie przeczytany na głos).
- Dane techniczne (momenty dokręcania, kąty dociągania, pojemności i specyfikacje płynów, ciśnienia, luzy zaworowe, kolejność dokręcania, kody silników) ZAWSZE sprawdzaj wyszukiwarką. Najpierw podaj wartość z jednostką i warunkami (np. „plus 90 stopni”, „nowe śruby”, „na sucho/olejone”), potem nazwę źródła (np. „według forum TDIclub” albo „według katalogu Febi”).
- Jeśli źródła podają różne wartości albo nie dotyczą dokładnie tego silnika/modelu — powiedz to wprost i poleć sprawdzenie w danych producenta. Nigdy nie zgaduj i nie podawaj wartości z pamięci jako pewnej.
- Jeśli brakuje modelu auta, rocznika albo silnika, a od tego zależy odpowiedź — zapytaj krótko o brakującą informację.
- Przy pracach niebezpiecznych (układ hamulcowy, poduszki powietrzne, wysokie napięcie w hybrydach, układ paliwowy) dodaj jedno krótkie ostrzeżenie."""


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class WebAnswerConfig(Strict):
    enabled: bool = False
    provider: Literal['groq', 'anthropic'] = 'groq'
    groq_api_key: str = Field(default='', max_length=200)
    groq_model: Literal['groq/compound', 'groq/compound-mini'] = 'groq/compound'
    api_key: str = Field(default='', max_length=200, description='Anthropic (Claude) key')
    model: str = Field(default=MODELS[0], max_length=64, pattern=r'^claude-[a-z0-9.-]+$')
    max_searches: int = Field(default=3, ge=1, le=5)

    def key(self):
        return self.groq_api_key if self.provider == 'groq' else self.api_key

    def model_name(self):
        return self.groq_model if self.provider == 'groq' else self.model

    def masked(self):
        data = self.model_dump()
        for field in SECRETS:
            data[field + '_set'] = bool(data[field])
            data[field] = SECRET_MASK if data[field] else ''
        return data


def install(c):
    c.execute('INSERT OR IGNORE INTO device_config VALUES(?,?,?,?)', ('web_answer', WebAnswerConfig().model_dump_json(), 0, time.time()))


def load(c):
    row = c.execute("SELECT value,revision FROM device_config WHERE id='web_answer'").fetchone()
    if row is None:
        return WebAnswerConfig(), 0
    try:
        data = json.loads(row[0])
        if isinstance(data, dict) and 'provider' not in data and data.get('api_key'):
            data['provider'] = 'anthropic'  # saved before Groq existed with a Claude key: keep using Claude
        return WebAnswerConfig.model_validate(data), row[1]
    except (ValidationError, ValueError):
        return WebAnswerConfig(), row[1]


def save(c, incoming, expected_revision):
    stored, revision = load(c)
    if expected_revision != revision:
        raise HTTPException(409, 'Configuration changed; reload and retry')
    if isinstance(incoming, dict):
        incoming = {key: value for key, value in incoming.items() if not key.endswith('_set')}
        for field in SECRETS:
            if incoming.get(field) in (SECRET_MASK, None):
                incoming[field] = getattr(stored, field)
            elif isinstance(incoming.get(field), str):
                incoming[field] = incoming[field].strip()
    try:
        config = WebAnswerConfig.model_validate(incoming)
    except ValidationError as exc:
        detail = '; '.join('.'.join(str(x) for x in e['loc']) + ': ' + e['msg'] for e in exc.errors()[:4])
        raise HTTPException(422, 'Invalid configuration: ' + detail) from None
    if config.api_key and not re.fullmatch(r'sk-ant-[A-Za-z0-9_-]{20,190}', config.api_key):
        raise HTTPException(422, 'Invalid configuration: api_key: expected an Anthropic API key (sk-ant-…)')
    if config.groq_api_key and not re.fullmatch(r'gsk_[A-Za-z0-9]{20,190}', config.groq_api_key):
        raise HTTPException(422, 'Invalid configuration: groq_api_key: expected a Groq API key (gsk_…)')
    c.execute("UPDATE device_config SET value=?,revision=revision+1,updated=? WHERE id='web_answer'", (config.model_dump_json(), time.time()))
    return config, revision + 1


def speakable(text):
    """Plain sentences for text-to-speech: no markdown, links or citation markers."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S)
    text = re.sub(r'\[([^\]]+)\]\((?:https?://[^)]*)\)', r'\1', text)  # [label](url) → label
    text = re.sub(r'【[^】]*】', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[*_#`>|]+', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:700]


def parse(content):
    """Join the answer text and collect cited sources (title + URL, max 3, de-duplicated)."""
    parts, sources, seen = [], [], set()
    searches = 0
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get('type') == 'server_tool_use':
            searches += 1
        if block.get('type') != 'text':
            continue
        parts.append(str(block.get('text') or ''))
        for citation in block.get('citations') or []:
            url = str(citation.get('url') or '')
            if url.startswith('https://') or url.startswith('http://'):
                if url not in seen and len(sources) < 3:
                    seen.add(url)
                    sources.append({'title': str(citation.get('title') or url)[:120], 'url': url[:500]})
    return speakable(''.join(parts)), sources, searches


class History:
    """Short per-device memory so follow-ups work ("a dla tylnej osi?"); forgotten after 15 minutes."""

    def __init__(self):
        self.items = {}

    def get(self, key, now=None):
        now = now or time.time()
        turns = [turn for turn in self.items.get(key, []) if now - turn[0] < HISTORY_SECONDS]
        self.items[key] = turns
        messages = []
        for _, question, answer in turns[-HISTORY_TURNS:]:
            messages += [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer}]
        return messages

    def add(self, key, question, answer, now=None):
        self.items.setdefault(key, []).append((now or time.time(), question, answer))
        self.items[key] = self.items[key][-HISTORY_TURNS:]
        if len(self.items) > 64:
            oldest = min(self.items, key=lambda item: self.items[item][-1][0] if self.items[item] else 0)
            self.items.pop(oldest, None)


def parse_groq(message):
    """Groq Compound: answer in message.content, searches in message.executed_tools[].search_results."""
    sources, seen, searches = [], set(), 0
    for tool in message.get('executed_tools') or [] if isinstance(message, dict) else []:
        if not isinstance(tool, dict):
            continue
        found = tool.get('search_results')
        results = found.get('results') if isinstance(found, dict) else found if isinstance(found, list) else None
        if results is None:
            continue
        searches += 1
        for item in results:
            url = str(item.get('url') or '') if isinstance(item, dict) else ''
            if (url.startswith('https://') or url.startswith('http://')) and url not in seen and len(sources) < 3:
                seen.add(url)
                sources.append({'title': str(item.get('title') or url)[:120], 'url': url[:500]})
    content = message.get('content') if isinstance(message, dict) else ''
    return speakable(content if isinstance(content, str) else ''), sources, searches


def failure(response, provider):
    if response.status_code in (401, 403):
        return HTTPException(502, 'AI provider rejected the API key')
    if response.status_code == 429:
        return HTTPException(503, 'Groq free limit reached' if provider == 'groq' else 'AI rate limit reached; try again shortly')
    return HTTPException(502, 'AI provider error ' + str(response.status_code))


async def ask(config: WebAnswerConfig, question: str, history=(), transport=None):
    """One question → {'speech', 'sources', 'searches', 'model'}; raises HTTPException with a Polish-friendly detail."""
    if not config.enabled or not config.key():
        raise HTTPException(503, 'Web answers are not configured')
    if config.provider == 'groq':
        return await ask_groq(config, question, history, transport)
    messages = [*history, {'role': 'user', 'content': question}]
    payload = {
        'model': config.model, 'max_tokens': 700, 'system': SYSTEM, 'messages': messages,
        'tools': [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': config.max_searches,
                   'user_location': {'type': 'approximate', 'country': 'PL', 'timezone': 'Europe/Warsaw'}}],
    }
    headers = {'x-api-key': config.api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
    content = []
    try:
        async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(70, connect=10), follow_redirects=False,
                                     trust_env=transport is None) as client:
            for _ in range(3):  # long searches may pause the turn; continue at most twice
                response = await client.post(API + '/v1/messages', json=payload, headers=headers)
                if len(response.content) > MAX_BODY:
                    raise HTTPException(502, 'AI answer too large')
                if response.status_code >= 400:
                    raise failure(response, 'anthropic')
                data = response.json()
                content += data.get('content') or []
                if data.get('stop_reason') != 'pause_turn':
                    break
                payload = {**payload, 'messages': [*messages, {'role': 'assistant', 'content': content}]}
    except httpx.TimeoutException:
        raise HTTPException(504, 'AI answer timed out') from None
    except (httpx.HTTPError, json.JSONDecodeError):
        raise HTTPException(502, 'Cannot reach the AI service') from None
    speech, sources, searches = parse(content)
    if not speech:
        raise HTTPException(502, 'The AI returned no answer')
    return {'speech': speech, 'sources': sources, 'searches': searches, 'model': config.model}


async def ask_groq(config, question, history=(), transport=None):
    payload = {'model': config.groq_model, 'max_tokens': 700, 'temperature': 0.2,
               'messages': [{'role': 'system', 'content': SYSTEM}, *history, {'role': 'user', 'content': question}]}
    headers = {'authorization': 'Bearer ' + config.groq_api_key, 'content-type': 'application/json'}
    try:
        async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(70, connect=10), follow_redirects=False,
                                     trust_env=transport is None) as client:
            response = await client.post(GROQ_API + '/chat/completions', json=payload, headers=headers)
            if len(response.content) > MAX_BODY:
                raise HTTPException(502, 'AI answer too large')
            if response.status_code >= 400:
                raise failure(response, 'groq')
            data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(504, 'AI answer timed out') from None
    except (httpx.HTTPError, json.JSONDecodeError):
        raise HTTPException(502, 'Cannot reach the AI service') from None
    choices = data.get('choices') if isinstance(data, dict) else None
    message = choices[0].get('message') if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    speech, sources, searches = parse_groq(message or {})
    if not speech:
        raise HTTPException(502, 'The AI returned no answer')
    return {'speech': speech, 'sources': sources, 'searches': searches, 'model': config.groq_model}

