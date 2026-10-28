"""Transcribed voice text is owner-authenticated conversation data, never a command."""
import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from jarvis import main
from jarvis.main import create_app

KEY = 'voice-chat-owner-test-key-32-characters'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('OLLAMA_ALLOWED_MODELS', 'test:local')
    monkeypatch.setenv('JARVIS_ALLOW_CLOUD_MODELS', 'false')
    c = TestClient(create_app(tmp_path / 'voice-chat.db', KEY), headers={'X-Jarvis-Key': KEY})
    c.path = tmp_path / 'voice-chat.db'
    return c


def use_automatic_memory(c):
    saved = c.get('/api/memory/policy').json()
    saved['policy']['mode'] = 'auto'
    result = c.put('/api/memory/policy', json={
        'revision': saved['revision'], 'policy': saved['policy'],
    })
    assert result.status_code == 200, result.text


def mock_model(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kwargs: original(
        transport=httpx.MockTransport(handler), **kwargs,
    ))


def personal_state(c):
    with sqlite3.connect(c.path) as db:
        return {table: db.execute('SELECT * FROM ' + table).fetchall() for table in (
            'memory', 'memory_sources', 'memory_history', 'memory_origins',
            'memory_auto_keys', 'proposals', 'automations', 'settings',
        )}


@pytest.mark.parametrize('message', [
    'ustaw imię Robert',
    'przypominaj co 60 minut: Sprawdź części',
    'zapamiętaj moje prywatne hasło',
    'Preferuję krótkie odpowiedzi.',
])
def test_voice_never_runs_command_parsers_or_automatic_memory(client, message):
    use_automatic_memory(client)
    before = personal_state(client)
    result = client.post('/api/chat', json={
        'message': message, 'input_mode': 'voice', 'do_not_remember': False, 'model': 'demo',
    })
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['model'] == 'demo' and 'proposal' not in data
    assert data['memory_capture']['saved'] == 0
    assert personal_state(client) == before
    messages = client.get('/api/chat/sessions/' + data['session_id'] + '/messages').json()
    assert messages[0]['role'] == 'user' and messages[0]['content'] == message
    assert all(row['state'] == 'completed' for row in messages)


def test_text_mode_preserves_existing_explicit_parser_behavior(client):
    rename = client.post('/api/chat', json={'message': 'ustaw imię Robert'})
    assert rename.status_code == 200 and rename.json()['proposal']['kind'] == 'settings'
    reminder = client.post('/api/chat', json={
        'message': 'przypominaj co 60 minut: Sprawdź części', 'input_mode': 'text',
    })
    assert reminder.status_code == 200 and reminder.json()['proposal']['kind'] == 'automation'
    note = client.post('/api/chat', json={'message': 'zapamiętaj mój projekt Jarvis'})
    assert note.status_code == 200 and note.json()['model'] == 'parser'
    assert client.get('/api/memory').json()[0]['text'] == 'mój projekt Jarvis'


def test_voice_ollama_uses_model_without_personal_memory_context(client, monkeypatch):
    assert client.post('/api/memory', json={'text': 'PRIVATE MEMORY MUST STAY OUT'}).status_code == 201
    use_automatic_memory(client)
    before = personal_state(client)
    seen = []

    def reply(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={'message': {'content': 'Kontrolowana odpowiedź głosowa.'}})

    mock_model(monkeypatch, reply)
    result = client.post('/api/chat', json={
        'message': 'zapamiętaj Preferuję krótkie odpowiedzi.', 'input_mode': 'voice',
        'model': 'ollama', 'model_name': 'test:local',
    })
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['model'] == 'ollama' and data['reply'] == 'Kontrolowana odpowiedź głosowa.'
    assert data['memory_capture']['saved'] == 0
    assert len(seen) == 1 and seen[0]['model'] == 'test:local'
    assert seen[0]['messages'][-1]['content'] == 'zapamiętaj Preferuję krótkie odpowiedzi.'
    assert 'PRIVATE MEMORY MUST STAY OUT' not in json.dumps(seen)
    assert 'tools' not in seen[0]
    assert personal_state(client) == before


@pytest.mark.parametrize('body', [
    {'message': 'Cześć', 'input_mode': 'administrator'},
    {'message': 'Cześć', 'input_mode': 'voice', 'include_workshop_summary': True},
])
def test_invalid_voice_source_or_workshop_context_is_rejected_before_history(client, body):
    assert client.get('/api/chat/sessions').json() == []
    response = client.post('/api/chat', json=body)
    assert response.status_code == 422, response.text
    assert client.get('/api/chat/sessions').json() == []
    assert client.get('/api/memory').json() == []


def test_voice_requires_owner_not_service_token(client):
    service = client.post('/api/security/tokens', json={
        'name': 'status-reader', 'scopes': ['status:read'],
    }).json()['token']
    response = client.post('/api/chat', headers={'X-Jarvis-Key': service}, json={
        'message': 'ustaw imię Robert', 'input_mode': 'voice',
    })
    assert response.status_code == 403
    assert client.get('/api/chat/sessions').json() == []
    assert client.get('/api/proposals').json() == []


def test_failed_voice_model_leaves_no_personal_writes_and_failed_history(client, monkeypatch):
    use_automatic_memory(client)
    before = personal_state(client)
    mock_model(monkeypatch, lambda request: httpx.Response(503))
    response = client.post('/api/chat', json={
        'message': 'Preferuję krótkie odpowiedzi.', 'input_mode': 'voice',
        'model': 'ollama', 'model_name': 'test:local', 'do_not_remember': False,
    })
    assert response.status_code == 502, response.text
    assert personal_state(client) == before
    sessions = client.get('/api/chat/sessions').json()
    assert len(sessions) == 1 and sessions[0]['active_turn'] is None
    messages = client.get('/api/chat/sessions/' + sessions[0]['id'] + '/messages').json()
    assert len(messages) == 1 and messages[0]['role'] == 'user' and messages[0]['state'] == 'failed'


def test_voice_cannot_attach_prior_text_session_or_receive_its_private_history(client, monkeypatch):
    first = client.post('/api/chat', json={'message': 'PRIVATE TEXT HISTORY MUST STAY OUT'}).json()
    ident = first['session_id']
    before = client.get('/api/chat/sessions/' + ident + '/messages').json()
    seen = []
    mock_model(monkeypatch, lambda request: seen.append(request) or httpx.Response(
        200, json={'message': {'content': 'This model must never be invoked.'}},
    ))
    response = client.post('/api/chat', json={
        'session_id': ident, 'message': 'Cześć', 'input_mode': 'voice',
        'model': 'ollama', 'model_name': 'test:local',
    })
    assert response.status_code == 422, response.text
    assert seen == []
    assert client.get('/api/chat/sessions/' + ident + '/messages').json() == before
    assert client.get('/api/chat/sessions/' + ident).json()['input_mode'] == 'text'


def test_voice_session_continuation_keeps_mode_and_rejects_default_text(client):
    first = client.post('/api/chat', json={'message': 'Cześć', 'input_mode': 'voice'}).json()
    ident = first['session_id']
    assert client.get('/api/chat/sessions/' + ident).json()['input_mode'] == 'voice'
    assert next(row for row in client.get('/api/chat/sessions').json() if row['id'] == ident)['input_mode'] == 'voice'
    before = client.get('/api/chat/sessions/' + ident + '/messages').json()
    # The default text origin cannot reuse the safer voice-origin session.
    rejected = client.post('/api/chat', json={'session_id': ident, 'message': 'ustaw imię Robert'})
    assert rejected.status_code == 422, rejected.text
    assert client.get('/api/chat/sessions/' + ident + '/messages').json() == before
    continuation = client.post('/api/chat', json={
        'session_id': ident, 'message': 'Jak się masz?', 'input_mode': 'voice',
    })
    assert continuation.status_code == 200, continuation.text
    assert continuation.json()['session_id'] == ident
    assert continuation.json()['context_messages'] == 2
    assert len(client.get('/api/chat/sessions/' + ident + '/messages').json()) == 4
    assert client.get('/api/proposals').json() == []
