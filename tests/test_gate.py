"""Gate control: simulator, confirmation, cooldown, configuration masking, local HTTP driver and chat/voice intents."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from jarvis import gate, intents
from jarvis.main import create_app

KEY = 'unit-test-key-32-characters-long'


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'gate.db', KEY)
    with TestClient(app, headers={'X-Jarvis-Key': KEY}) as c:
        c.app_state = app.state
        yield c


def put_config(client, config, revision=None):
    if revision is None:
        revision = client.get('/api/v1/devices/gate/config').json()['revision']
    return client.put('/api/v1/devices/gate/config', json={'revision': revision, 'config': config})


# ---------------------------------------------------------------- intents

@pytest.mark.parametrize('text,action', [
    ('Jarvis, otwórz bramę', 'open'), ('otworz brame', 'open'), ('jarvis zamknij bramę!', 'close'),
    ('brama stop', 'stop'), ('Jaki jest stan bramy?', 'status'), ('czy brama jest otwarta', 'status'), ('zamknij garaż', 'close'),
])
def test_gate_intents(text, action):
    intent = intents.parse(text)
    assert intent is not None and intent.kind == 'gate' and intent.action == action


@pytest.mark.parametrize('text', ['opowiedz o bramie brandenburskiej i jej historii w berlinie proszę dokładnie', 'jaka jest pogoda', 'zapamiętaj że brama jest zielona i trzeba ją pomalować wiosną tego roku', ''])
def test_non_gate_text_goes_to_model(text):
    assert intents.parse(text) is None


def test_confirm_and_cancel_words():
    assert intents.parse('tak').kind == 'confirm'
    assert intents.parse('Jarvis, nie').kind == 'cancel'


# ---------------------------------------------------------------- simulator and API

def test_default_configuration_is_simulator(client):
    data = client.get('/api/v1/devices/gate').json()
    assert data['config']['driver'] == 'simulator' and data['gate']['live'] is False and data['events'] == []
    assert client.get('/api/v1/status').json()['live_devices'] is False
    assert client.get('/api/v1/integrations').json()['physical_controls'] is False


def test_simulator_open_close_stop_cycle(client):
    r = client.post('/api/v1/devices/gate/command', json={'action': 'open'})
    assert r.status_code == 200
    body = r.json()
    assert body['status'] == 'executed' and body['external_request_sent'] is False and body['gate']['state'] == 'opening'
    assert client.post('/api/v1/devices/gate/command', json={'action': 'close'}).status_code == 429, 'cooldown applies'
    client.app_state.gate.last_command = 0
    assert client.post('/api/v1/devices/gate/command', json={'action': 'stop'}).json()['gate']['state'] == 'stopped'
    events = client.get('/api/v1/devices/gate').json()['events']
    assert [e['action'] for e in events] == ['stop', 'open'] and all(e['result'] == 'ok' for e in events)
    audit = [a for a in client.get('/api/v1/audit').json() if a['event'] == 'gate.command']
    assert len(audit) == 2


def test_travel_time_settles_state(client):
    put_config(client, {'driver': 'simulator', 'travel_seconds': 1})
    client.post('/api/v1/devices/gate/command', json={'action': 'open'})
    client.app_state.gate.state['changed'] -= 2
    assert client.get('/api/v1/devices/gate').json()['gate']['state'] == 'open'


def test_confirmation_token_flow(client):
    put_config(client, {'driver': 'simulator', 'require_confirmation': True, 'cooldown_seconds': 0})
    first = client.post('/api/v1/devices/gate/command', json={'action': 'open', 'source': 'voice'}).json()
    assert first['status'] == 'confirmation_required' and first['prompt'] == 'Otworzyć bramę?'
    wrong = client.post('/api/v1/devices/gate/command', json={'action': 'open', 'source': 'voice', 'confirm_token': 'nope'}).json()
    assert wrong['status'] == 'confirmation_required', 'a wrong token issues a new question instead of acting'
    # different action with the right token must not pass
    token = wrong['confirm_token']
    other = client.post('/api/v1/devices/gate/command', json={'action': 'close', 'source': 'voice', 'confirm_token': token}).json()
    assert other['status'] == 'confirmation_required'
    token = other['confirm_token']
    done = client.post('/api/v1/devices/gate/command', json={'action': 'close', 'source': 'voice', 'confirm_token': token}).json()
    assert done['status'] == 'executed' and done['gate']['state'] == 'closing'
    again = client.post('/api/v1/devices/gate/command', json={'action': 'close', 'source': 'voice', 'confirm_token': token}).json()
    assert again['status'] == 'confirmation_required', 'tokens are single-use'


def test_disabled_driver(client):
    put_config(client, {'driver': 'disabled'})
    assert client.post('/api/v1/devices/gate/command', json={'action': 'open'}).status_code == 503
    assert client.post('/api/v1/devices/gate/test').status_code == 503


def test_requires_owner(client, tmp_path):
    anonymous = TestClient(client.app)
    assert anonymous.get('/api/v1/devices/gate').status_code == 401
    assert anonymous.post('/api/v1/devices/gate/command', json={'action': 'open'}).status_code == 401


# ---------------------------------------------------------------- configuration

def test_config_validation_and_secret_masking(client):
    bad = put_config(client, {'driver': 'tuya_cloud'})
    assert bad.status_code == 422
    bad = put_config(client, {'driver': 'http', 'http': {'open_url': 'ftp://x'}})
    assert bad.status_code == 422
    stale = put_config(client, {'driver': 'simulator'}, revision=99)
    assert stale.status_code == 409
    ok = put_config(client, {'driver': 'tuya_cloud', 'tuya': {'access_id': 'abc', 'access_secret': 'topsecret', 'device_id': 'dev1'}})
    assert ok.status_code == 200
    masked = ok.json()['config']['tuya']
    assert masked['access_secret'] == gate.SECRET_MASK and masked['access_secret_set'] is True
    # Sending the mask back keeps the stored secret; nothing in any response reveals it.
    again = put_config(client, {'driver': 'tuya_cloud', 'tuya': dict(masked, device_id='dev2')})
    assert again.status_code == 200
    assert 'topsecret' not in json.dumps(client.get('/api/v1/devices/gate').json())
    assert 'topsecret' not in json.dumps(client.get('/api/v1/audit').json())
    with client.app_state.gate.lock if False else _db(client) as c:
        stored, _ = gate.load(c)
    assert stored.tuya.access_secret == 'topsecret' and stored.tuya.device_id == 'dev2'
    assert client.get('/api/v1/status').json()['live_devices'] is True


class _db:
    def __init__(self, client):
        import sqlite3
        self.c = sqlite3.connect(client.app_state.runtime_config.database_path)

    def __enter__(self):
        return self.c

    def __exit__(self, *a):
        self.c.close()


def test_tuya_signature_shape():
    config = gate.GateConfig(driver='tuya_cloud', tuya={'access_id': 'id', 'access_secret': 'secret', 'device_id': 'd'})
    headers = gate.TuyaCloud(config)._sign('GET', '/v1.0/token?grant_type=1', '')
    assert set(headers) == {'client_id', 'sign', 't', 'sign_method', 'nonce', 'Content-Type'}
    assert len(headers['sign']) == 64 and headers['sign'] == headers['sign'].upper() and headers['sign_method'] == 'HMAC-SHA256'
    with_token = gate.TuyaCloud(config)._sign('POST', '/v1.0/iot-03/devices/d/commands', '{}', 'tok')
    assert with_token['access_token'] == 'tok'


# ---------------------------------------------------------------- local HTTP driver (Shelly/Tasmota style)

class Relay(BaseHTTPRequestHandler):
    calls = []
    state = 'off'

    def do_GET(self):
        Relay.calls.append(('GET', self.path))
        if self.path.startswith('/relay/0?turn='):
            Relay.state = self.path.split('=')[1]
            payload = {'ison': Relay.state == 'on'}
        elif self.path == '/status':
            payload = {'ison': Relay.state == 'on'}
        else:
            self.send_response(404); self.end_headers(); return
        data = json.dumps(payload).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data))); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def relay():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Relay)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    Relay.calls.clear(); Relay.state = 'off'
    yield 'http://127.0.0.1:%d' % server.server_port
    server.shutdown(); server.server_close()


def test_http_driver_against_local_relay(client, relay):
    put_config(client, {'driver': 'http', 'cooldown_seconds': 0, 'http': {
        'open_url': relay + '/relay/0?turn=on', 'close_url': relay + '/relay/0?turn=off',
        'status_url': relay + '/status', 'status_open_match': '"ison": true'}})
    assert client.get('/api/v1/integrations').json()['physical_controls'] is True
    r = client.post('/api/v1/devices/gate/command', json={'action': 'open'})
    assert r.status_code == 200 and r.json()['external_request_sent'] is True
    assert ('GET', '/relay/0?turn=on') in Relay.calls
    status = client.post('/api/v1/devices/gate/test').json()
    assert status['status'] == 'reachable' and status['gate']['state'] == 'open'
    assert client.post('/api/v1/devices/gate/command', json={'action': 'close'}).json()['gate']['state'] == 'closing'
    assert Relay.state == 'off'
    assert client.post('/api/v1/devices/gate/command', json={'action': 'stop'}).status_code == 501, 'no stop URL configured'


def test_http_driver_outside_allowlist_is_denied(client, monkeypatch):
    monkeypatch.setenv('JARVIS_NETWORK_ALLOWLIST', '10.99.0.0/16')
    put_config(client, {'driver': 'http', 'cooldown_seconds': 0, 'http': {'open_url': 'http://127.0.0.1:9/relay/0?turn=on'}})
    r = client.post('/api/v1/devices/gate/command', json={'action': 'open'})
    assert r.status_code == 502
    events = client.get('/api/v1/devices/gate').json()['events']
    assert events[0]['result'] == 'error'


# ---------------------------------------------------------------- chat and voice

def test_chat_voice_command_opens_simulated_gate(client):
    r = client.post('/api/v1/chat', json={'message': 'Jarvis, otwórz bramę', 'input_mode': 'voice', 'model': 'demo'})
    assert r.status_code == 200
    body = r.json()
    assert body['model'] == 'parser' and body['device']['status'] == 'executed' and 'Otwieram' in body['reply']
    client.app_state.gate.last_command = 0
    status = client.post('/api/v1/chat', json={'message': 'jaki jest stan bramy', 'session_id': body['session_id'], 'input_mode': 'voice'}).json()
    assert 'otwiera się' in status['reply']


def test_chat_confirmation_dialogue(client):
    put_config(client, {'driver': 'simulator', 'require_confirmation': True, 'cooldown_seconds': 0})
    first = client.post('/api/v1/chat', json={'message': 'zamknij bramę', 'input_mode': 'voice', 'model': 'demo'}).json()
    assert first['device']['status'] == 'confirmation_required' and 'tak' in first['reply']
    sid = first['session_id']
    cancel = client.post('/api/v1/chat', json={'message': 'nie', 'session_id': sid, 'input_mode': 'voice'}).json()
    assert cancel['device']['status'] == 'cancelled'
    # Without a pending question, "tak" is ordinary chat and reaches the demo model.
    plain = client.post('/api/v1/chat', json={'message': 'tak', 'session_id': sid, 'input_mode': 'voice'}).json()
    assert plain['model'] == 'demo'
    client.post('/api/v1/chat', json={'message': 'zamknij bramę', 'session_id': sid, 'input_mode': 'voice'})
    done = client.post('/api/v1/chat', json={'message': 'tak', 'session_id': sid, 'input_mode': 'voice'}).json()
    assert done['device']['status'] == 'executed' and done['device']['action'] == 'close'


def test_chat_with_disabled_gate(client):
    put_config(client, {'driver': 'disabled'})
    r = client.post('/api/v1/chat', json={'message': 'otwórz bramę', 'model': 'demo'}).json()
    assert r['device']['status'] == 'disabled'


# ---------------------------------------------------------------- voice preferences

def test_voice_config_roundtrip(client):
    data = client.get('/api/v1/config/voice').json()
    assert data['config']['engine'] == 'browser' and data['revision'] == 0
    r = client.put('/api/v1/config/voice', json={'revision': 0, 'config': dict(data['config'], wake_word='komputer', send_to_model=True)})
    assert r.status_code == 200 and r.json()['config']['wake_word'] == 'komputer'
    assert client.put('/api/v1/config/voice', json={'revision': 0, 'config': data['config']}).status_code == 409
    assert client.put('/api/v1/config/voice', json={'revision': 1, 'config': {'engine': 'cloud'}}).status_code == 422
