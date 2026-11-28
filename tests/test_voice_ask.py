"""Hands-free questions (Siri shortcut): device keys, remote policy, web-search answers and gate commands by voice."""
import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from jarvis import identity, remote_access, totp, web_answer
from jarvis.main import create_app

KEY = 'voice-ask-owner-key-32-characters-xx'
OWNER = {'X-Jarvis-Key': KEY}
PASSWORD = 'Synthetic-password-for-voice-tests'
TAILSCALE = {'Tailscale-User-Login': 'endi@example.com', 'Host': 'warsztat.tail1234.ts.net'}
API_KEY = 'sk-ant-api03-' + 'x' * 40


def anthropic_reply(text='**Śruby koła** Golfa 7 dokręca się momentem 120 Nm według forum vwgolf.pl.'):
    return {'id': 'msg_1', 'type': 'message', 'role': 'assistant', 'stop_reason': 'end_turn', 'content': [
        {'type': 'server_tool_use', 'id': 'srvtoolu_1', 'name': 'web_search', 'input': {'query': 'Golf 7 moment dokręcania kół'}},
        {'type': 'web_search_tool_result', 'tool_use_id': 'srvtoolu_1', 'content': []},
        {'type': 'text', 'text': text, 'citations': [
            {'type': 'web_search_result_location', 'url': 'https://vwgolf.pl/forum/kola', 'title': 'Momenty kół — vwgolf.pl', 'cited_text': '120 Nm'}]},
        {'type': 'text', 'text': ' Zobacz https://vwgolf.pl/forum/kola [1]'}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('JARVIS_REMOTE_ACCESS', 'true')
    app = create_app(tmp_path / 'ask.db', KEY)
    calls = []

    def handler(request):
        calls.append(request)
        reply = calls_reply.pop(0) if calls_reply else anthropic_reply()
        if isinstance(reply, int):
            return httpx.Response(reply, json={'type': 'error'})
        return httpx.Response(200, json=reply)
    calls_reply = []
    app.state.web_answer_transport = httpx.MockTransport(handler)
    with TestClient(app, base_url='http://127.0.0.1:17321') as c:
        c.calls, c.replies, c.path = calls, calls_reply, tmp_path / 'ask.db'
        yield c


def account_with_2fa(c, username='endi', role='owner'):
    assert c.post('/api/v1/security/users', headers=OWNER, json={'username': username, 'password': PASSWORD, 'role': role}).status_code == 201
    token = c.post('/api/v1/auth/login', json={'username': username, 'password': PASSWORD}).json()['token']
    auth = {'X-Jarvis-Key': token}
    secret = c.post('/api/v1/auth/mfa/setup', headers=auth).json()['secret']
    step = totp.step_at()
    assert c.post('/api/v1/auth/mfa/enable', headers=auth, json={'code': totp.code_at(secret, step)}).status_code == 200
    fresh = c.post('/api/v1/auth/login', json={'username': username, 'password': PASSWORD, 'otp': totp.code_at(secret, step + 1)})
    assert fresh.status_code == 200 and fresh.json()['mfa'] is True
    return {'X-Jarvis-Key': fresh.json()['token']}


def configure(c, **changes):
    revision = c.get('/api/v1/config/web-answer', headers=OWNER).json()['revision']
    return c.put('/api/v1/config/web-answer', headers=OWNER, json={'revision': revision, 'config': {
        'enabled': True, 'api_key': API_KEY, 'model': 'claude-sonnet-5-5', 'max_searches': 3, **changes}})


def phone_key(c, auth, name='iPhone Endi'):
    created = c.post('/api/v1/auth/device-keys', headers=auth, json={'name': name})
    assert created.status_code == 200, created.text
    return created.json()


def test_web_answer_config_masks_the_key_and_validates_it(client):
    assert configure(client).status_code == 200
    shown = client.get('/api/v1/config/web-answer', headers=OWNER)
    assert API_KEY not in shown.text and shown.json()['config']['api_key'] == web_answer.SECRET_MASK
    assert shown.json()['config']['api_key_set'] is True
    assert configure(client, api_key=web_answer.SECRET_MASK, max_searches=2).status_code == 200  # mask keeps the key
    with sqlite3.connect(client.path) as db:
        stored = json.loads(db.execute("SELECT value FROM device_config WHERE id='web_answer'").fetchone()[0])
    assert stored['api_key'] == API_KEY and stored['max_searches'] == 2
    assert configure(client, api_key='not-a-key').status_code == 422
    assert configure(client, max_searches=9).status_code == 422


def test_question_is_answered_from_the_web_with_sources_and_follow_up_context(client):
    configure(client)
    first = client.post('/api/v1/voice/ask', headers=OWNER, json={'text': 'Jaki moment dokręcania kół w Golfie 7?'})
    body = first.json()
    assert first.status_code == 200 and body['kind'] == 'answer' and body['ai_generated'] is True
    assert body['speech'] == 'Śruby koła Golfa 7 dokręca się momentem 120 Nm według forum vwgolf.pl. Zobacz'
    assert body['sources'] == [{'title': 'Momenty kół — vwgolf.pl', 'url': 'https://vwgolf.pl/forum/kola'}]
    sent = json.loads(client.calls[0].content)
    assert client.calls[0].url == 'https://api.anthropic.com/v1/messages' and client.calls[0].headers['x-api-key'] == API_KEY
    assert sent['tools'][0]['type'] == 'web_search_20250305' and sent['tools'][0]['max_uses'] == 3
    assert 'momenty dokręcania' in sent['system'] and 'Nigdy nie zgaduj' in sent['system']
    client.post('/api/v1/voice/ask', headers=OWNER, json={'text': 'A dla Passata B8?'})
    follow = json.loads(client.calls[1].content)['messages']
    assert [m['role'] for m in follow] == ['user', 'assistant', 'user'] and follow[0]['content'].startswith('Jaki moment')
    with sqlite3.connect(client.path) as db:
        events = [json.loads(row[0]) for row in db.execute("SELECT detail FROM audit WHERE event='voice.ask'")]
    assert events[0]['chars'] == len('Jaki moment dokręcania kół w Golfie 7?') and 'Golf' not in json.dumps(events)


def test_failures_are_spoken_not_thrown(client):
    off = client.post('/api/v1/voice/ask', headers=OWNER, json={'text': 'Pojemność oleju 1.9 TDI?'}).json()
    assert off['kind'] == 'error' and 'Ustawienia' in off['speech'] and client.calls == []
    configure(client)
    client.replies.append(401)
    rejected = client.post('/api/v1/voice/ask', headers=OWNER, json={'text': 'Pojemność oleju 1.9 TDI?'}).json()
    assert rejected['kind'] == 'error' and 'Klucz Claude został odrzucony' in rejected['speech']


def test_long_search_pause_is_continued(client):
    configure(client)
    client.replies.append({'stop_reason': 'pause_turn', 'content': [{'type': 'server_tool_use', 'id': 's1', 'name': 'web_search', 'input': {}}]})
    client.replies.append(anthropic_reply('Luz zaworowy wynosi 0,2 mm według instrukcji Hondy.'))
    body = client.post('/api/v1/voice/ask', headers=OWNER, json={'text': 'Luz zaworowy Honda D16?'}).json()
    assert body['kind'] == 'answer' and body['speech'].startswith('Luz zaworowy wynosi 0,2 mm')
    second = json.loads(client.calls[1].content)['messages']
    assert second[-1]['role'] == 'assistant' and second[-1]['content'][0]['type'] == 'server_tool_use'


def test_phone_key_works_through_the_tunnel_only_for_questions_and_the_gate(client):
    configure(client)
    auth = account_with_2fa(client)
    created = phone_key(client, auth)
    assert created['scopes'] == ['gate:control', 'voice:ask'] and len(created['token']) >= 40
    phone = {'X-Jarvis-Key': created['token'], **TAILSCALE}
    answer = client.post('/api/v1/voice/ask', headers=phone, json={'text': 'Moment dokręcania świec Astra H?'})
    assert answer.status_code == 200 and answer.json()['kind'] == 'answer'
    gate = client.post('/api/v1/voice/ask', headers=phone, json={'text': 'Jarvis, otwórz bramę'})
    assert gate.json()['kind'] == 'command' and len(client.calls) == 1  # commands never reach the AI
    assert client.post('/api/v1/devices/gate/command', headers=phone, json={'action': 'status'}).status_code == 200
    for path in ('/api/v1/config/web-answer', '/api/v1/cameras', '/api/v1/auth/device-keys', '/api/v1/devices/gate/config'):
        refused = client.get(path, headers=phone)
        assert refused.status_code == 403, path
    assert client.get('/api/v1/devices/gate/config', headers={'X-Jarvis-Key': created['token']}).status_code == 403  # no owner bypass locally
    listed = client.get('/api/v1/auth/device-keys', headers=auth).json()['keys']
    assert [item['name'] for item in listed] == ['iPhone Endi'] and 'token' not in listed[0]
    with sqlite3.connect(client.path) as db:
        assert created['token'] not in '\n'.join(db.iterdump())
    assert client.delete('/api/v1/auth/device-keys/' + created['id'], headers=auth).json() == {'revoked': True}
    assert client.post('/api/v1/voice/ask', headers=phone, json={'text': 'test'}).status_code == 401


def test_phone_keys_need_an_account_with_2fa_and_die_with_the_second_factor(client):
    assert client.post('/api/v1/auth/device-keys', headers=OWNER, json={'name': 'x'}).status_code == 403  # owner key: no account
    assert client.post('/api/v1/security/users', headers=OWNER, json={'username': 'bez2fa', 'password': PASSWORD, 'role': 'owner'}).status_code == 201
    plain = {'X-Jarvis-Key': client.post('/api/v1/auth/login', json={'username': 'bez2fa', 'password': PASSWORD}).json()['token']}
    assert client.post('/api/v1/auth/device-keys', headers=plain, json={'name': 'Telefon'}).status_code == 403
    auth = account_with_2fa(client)
    assert client.post('/api/v1/auth/device-keys', headers=auth, json={'name': '<script>'}).status_code == 422
    created = phone_key(client, auth)
    users = client.get('/api/v1/security/users', headers=OWNER).json()
    endi = next(user for user in users if user['username'] == 'endi')
    assert client.delete('/api/v1/security/users/' + endi['id'] + '/mfa', headers=OWNER).status_code == 200
    assert client.post('/api/v1/voice/ask', headers={'X-Jarvis-Key': created['token']}, json={'text': 'test'}).status_code == 401


def test_operator_phone_key_gets_the_same_narrow_scopes(client):
    account_with_2fa(client, 'owner2')
    auth = account_with_2fa(client, 'mechanik', 'operator')
    assert phone_key(client, auth, 'Telefon mechanika')['scopes'] == ['gate:control', 'voice:ask']


def test_remote_policy_for_device_principals():
    config = remote_access.RemoteConfig(enabled=True)
    device = identity.Principal(id='d', kind='device', role='device', scopes=identity.DEVICE_SCOPES)
    assert remote_access.decide('/api/v1/voice/ask', device, config) is None
    assert remote_access.decide('/api/v1/devices/gate/command', device, config) is None
    assert remote_access.decide('/api/v1/chat', device, config)[0] == 403
    assert device.is_owner is False


def test_speakable_and_history_helpers():
    assert web_answer.speakable('**120 Nm** [2] — https://example.com/x\n# nagłówek') == '120 Nm — nagłówek'
    history = web_answer.History()
    history.add('k', 'pytanie', 'odpowiedź', now=1000)
    assert history.get('k', now=1000 + 60) == [{'role': 'user', 'content': 'pytanie'}, {'role': 'assistant', 'content': 'odpowiedź'}]
    assert history.get('k', now=1000 + web_answer.HISTORY_SECONDS + 1) == []


def test_schema_15_migration_adds_device_keys_and_web_answer_with_a_backup(tmp_path):
    path = tmp_path / 'old.db'
    with TestClient(create_app(path, KEY)):
        pass
    with sqlite3.connect(path) as db:  # simulate a 0.18.0 database (schema 14)
        db.execute('DROP TABLE identity_device_keys')
        db.execute("DELETE FROM device_config WHERE id='web_answer'")
        db.execute('PRAGMA user_version=14')
    with TestClient(create_app(path, KEY)) as c:
        assert c.get('/api/v1/config/web-answer', headers=OWNER).json()['config']['enabled'] is False
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 15
        assert db.execute("SELECT name FROM sqlite_master WHERE name='identity_device_keys'").fetchone()
    backups = list((tmp_path / 'backups').glob('before-schema15-*.sqlite3'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 14
