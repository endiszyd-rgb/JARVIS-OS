"""Canonical v1 and compatibility routes share policy/state; no live services."""
import uuid
from urllib.parse import urlencode

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest
from twilio.request_validator import RequestValidator

from jarvis import voice
from jarvis.main import create_app


KEY = 'versioning-owner-test-key-32-characters'
OWNER = {'X-Jarvis-Key': KEY}
PREFIXES = ('/api', '/api/v1')
READY_PATHS = ('/ready', '/api/ready', '/api/v1/ready')


@pytest.fixture
def client(tmp_path):
    path = tmp_path / 'versioning.db'
    with TestClient(create_app(path, KEY)) as c:
        c.dbfile = path
        yield c


def test_all_api_methods_have_exact_legacy_and_v1_counterparts(client):
    routes = [(route.path, method) for route in client.app.routes if isinstance(route, APIRoute)
              for method in route.methods if route.path.startswith('/api/')]
    assert len(routes) == len(set(routes)), 'Ambiguous duplicate API route/method'
    legacy = {(path[len('/api'):], method) for path, method in routes if not path.startswith('/api/v1/')}
    canonical = {(path[len('/api/v1'):], method) for path, method in routes if path.startswith('/api/v1/')}
    assert len(legacy) >= 60, 'Parity must cover the complete existing API, not a small replacement'
    assert canonical == legacy
    assert {('/voice/sessions', 'POST'), ('/memory/policy', 'PUT'),
            ('/telephony/transport/caller/{ident}/events', 'POST'),
            ('/telephony/transport/calls/{ident}', 'DELETE')} <= canonical


def test_auth_schema_scoped_token_and_revocation_work_across_prefixes(client):
    for prefix in PREFIXES:
        assert client.get(prefix + '/status').status_code == 401
        assert client.get(prefix + '/schema').status_code == 401
        assert client.get(prefix + '/status', headers={'X-Jarvis-Key': 'wrong'}).status_code == 401
    schema = client.get('/api/v1/schema', headers=OWNER)
    assert schema.status_code == 200
    assert {'/api/v1/status', '/api/status', '/api/v1/telephony/transport/caller/{ident}'} <= schema.json()['paths'].keys()
    issued = client.post('/api/v1/security/tokens', json={'name': 'status reader', 'scopes': ['status:read']}, headers=OWNER)
    assert issued.status_code == 201
    token = issued.json()
    scoped = {'X-Jarvis-Key': token['token']}
    for prefix in PREFIXES:
        assert client.get(prefix + '/status', headers=scoped).status_code == 200
        assert client.get(prefix + '/memory', headers=scoped).status_code == 403
        assert client.get(prefix + '/schema', headers=scoped).status_code == 403
    assert client.delete('/api/security/tokens/' + token['id'], headers=OWNER).status_code == 200
    for prefix in PREFIXES:
        assert client.get(prefix + '/status', headers=scoped).status_code == 401


def test_mutations_and_restart_share_one_database_across_prefixes(client):
    created = client.post('/api/v1/memory', json={'text': 'Versioned persistent note'}, headers=OWNER)
    assert created.status_code == 201
    ident = created.json()['id']
    legacy = client.get('/api/memory', headers=OWNER)
    assert any(row['id'] == ident and row['text'] == 'Versioned persistent note' for row in legacy.json())
    with TestClient(create_app(client.dbfile, KEY), headers=OWNER) as restarted:
        assert any(row['id'] == ident for row in restarted.get('/api/v1/memory').json())
        assert restarted.delete('/api/memory/' + ident).status_code == 200
    assert client.get('/api/v1/memory', headers=OWNER).json() == []


def test_mounted_audio_sessions_share_state_and_receipts_across_prefixes(client):
    response = client.post('/api/v1/voice/sessions', json={}, headers=OWNER)
    assert response.status_code == 201
    session = response.json()
    event = {'event_id': str(uuid.uuid4()), 'revision': session['revision'], 'action': 'activate'}
    path = '/voice/sessions/' + session['id']
    activated = client.post('/api' + path + '/events', json=event, headers=OWNER)
    assert activated.status_code == 200
    assert activated.json()['state'] == 'listening'
    assert client.get('/api/v1' + path, headers=OWNER).json()['revision'] == activated.json()['revision']
    replay = client.post('/api/v1' + path + '/events', json=event, headers=OWNER)
    assert replay.status_code == 200 and replay.json()['replayed'] is True
    assert replay.json()['revision'] == activated.json()['revision']


def test_transport_caller_token_is_shared_but_never_owner_authority(client):
    start = client.post('/api/v1/telephony/transport/calls', json={'event_id': str(uuid.uuid4())}, headers=OWNER)
    assert start.status_code == 201
    private = start.json()
    caller = {'X-Jarvis-Call-Token': private['caller_token']}
    public_path = '/telephony/transport/caller/' + private['id']
    owner_path = '/telephony/transport/calls/' + private['id']
    expected = {'id', 'revision', 'state', 'messages', 'mode', 'carrier_connected',
                'calls_placed', 'notifications_sent', 'replayed'}
    for prefix in PREFIXES:
        assert client.get(prefix + public_path, headers=OWNER).status_code == 401
        assert client.get(prefix + owner_path, headers=caller).status_code == 401
        assert client.get(prefix + owner_path, headers={'X-Jarvis-Key': private['caller_token']}).status_code == 401
        snapshot = client.get(prefix + public_path, headers=caller)
        assert snapshot.status_code == 200
        assert set(snapshot.json()) == expected
        assert snapshot.json()['carrier_connected'] is False
        assert snapshot.json()['calls_placed'] is False
        assert snapshot.json()['notifications_sent'] is False
        assert private['caller_token'] not in snapshot.text
    body = {'event_id': str(uuid.uuid4()), 'revision': private['revision'], 'action': 'hangup'}
    ended = client.post('/api/v1' + public_path + '/events', json=body, headers=caller)
    assert ended.status_code == 200 and ended.json()['state'] == 'ended'
    replay = client.post('/api' + public_path + '/events', json=body, headers=caller)
    assert replay.status_code == 200
    assert replay.json()['revision'] == ended.json()['revision']
    assert client.get('/api' + owner_path, headers=OWNER).json()['state'] == 'ended'


@pytest.mark.parametrize('prefix', PREFIXES)
def test_body_limits_apply_to_json_and_allow_bounded_wav_in_both_prefixes(client, monkeypatch, prefix):
    seen = []

    async def transcribe(raw):
        seen.append(len(raw))
        return {'text': 'Controlled transcription', 'review_required': True, 'executed': False}

    monkeypatch.setattr(voice, 'transcribe', transcribe)
    too_large_json = b'{"text":"' + b'x' * 65536 + b'"}'
    assert client.post(prefix + '/memory', content=too_large_json,
                       headers={**OWNER, 'Content-Type': 'application/json'}).status_code == 413
    for size in (65537, 2 * 1024 * 1024):
        accepted = client.post(prefix + '/voice/transcribe', content=b'x' * size,
                               headers={**OWNER, 'Content-Type': 'audio/wav'})
        assert accepted.status_code == 200
        assert accepted.json()['executed'] is False
    refused = client.post(prefix + '/voice/transcribe', content=iter([b'x' * 1048576, b'x' * 1048577]),
                          headers={**OWNER, 'Content-Type': 'audio/wav'})
    assert refused.status_code == 413
    assert seen == [65537, 2 * 1024 * 1024]
    assert client.get('/api/v1/memory', headers=OWNER).json() == []


def test_readiness_is_public_safe_and_liveness_survives_unready_database(client, monkeypatch):
    monkeypatch.setenv('HA_TOKEN', 'private-home-token-sentinel')
    for path in READY_PATHS:
        ready = client.get(path)
        assert ready.status_code == 200
        assert ready.json()['status'] == 'ready'
        assert KEY not in ready.text
        assert str(client.dbfile) not in ready.text
        assert 'private-home-token-sentinel' not in ready.text
    client.dbfile.unlink()
    for path in READY_PATHS:
        failed = client.get(path)
        assert failed.status_code == 503
        assert failed.json()['status'] == 'not_ready'
        assert KEY not in failed.text and str(client.dbfile) not in failed.text
    assert not client.dbfile.exists(), 'Readiness must not silently create an empty database'
    assert client.get('/health').status_code == 200


def test_missing_owner_key_is_unready_but_liveness_and_ui_remain_available(tmp_path):
    with TestClient(create_app(tmp_path / 'unconfigured.db', '')) as c:
        assert c.get('/health').status_code == 200
        assert c.get('/').status_code == 200
        for path in READY_PATHS:
            response = c.get(path)
            assert response.status_code == 503
            assert response.json()['status'] == 'not_ready'
            assert str(tmp_path) not in response.text
        for prefix in PREFIXES:
            assert c.get(prefix + '/status', headers=OWNER).status_code == 503


@pytest.mark.parametrize('path', ['/api/v0/status', '/api/v2/status', '/api/v11/schema', '/api/v1/webhooks/twilio/whatsapp'])
def test_unknown_versions_and_invented_webhook_aliases_are_not_routes(client, path):
    assert client.get(path, headers=OWNER).status_code == 404


def test_twilio_keeps_its_signed_root_path_and_versioned_inbox(client, monkeypatch):
    secret = 'versioning-twilio-synthetic-secret'
    origin = 'https://versioning.example.test'
    values = {'TWILIO_WEBHOOK_ENABLED': 'true', 'TWILIO_AUTH_TOKEN': secret,
              'TWILIO_PUBLIC_ORIGIN': origin, 'TWILIO_ACCOUNT_SID': 'AC' + 'a' * 32,
              'TWILIO_WHATSAPP_FROM': 'whatsapp:+48123456789',
              'WHATSAPP_ALLOWED_SENDERS': 'whatsapp:+48987654321'}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    params = {'MessageSid': 'SM' + 'c' * 32, 'AccountSid': values['TWILIO_ACCOUNT_SID'],
              'From': values['WHATSAPP_ALLOWED_SENDERS'], 'To': values['TWILIO_WHATSAPP_FROM'],
              'Body': 'Synthetic inbound fixture'}
    path = '/webhooks/twilio/whatsapp'
    headers = {**OWNER, 'Content-Type': 'application/x-www-form-urlencoded'}
    assert client.post(path, content=urlencode(params), headers={**headers, 'X-Twilio-Signature': 'invalid'}).status_code == 403
    signature = RequestValidator(secret).compute_signature(origin + path, params)
    accepted = client.post(path, content=urlencode(params), headers={**headers, 'X-Twilio-Signature': signature,
                           'X-Forwarded-Host': 'untrusted.example.test'})
    assert accepted.status_code == 200
    for prefix in PREFIXES:
        inbox = client.get(prefix + '/whatsapp/inbox', headers=OWNER)
        assert inbox.status_code == 200
        assert len(inbox.json()) == 1 and inbox.json()[0]['sid'] == params['MessageSid']
    assert client.get('/api/v1/proposals', headers=OWNER).json() == []
