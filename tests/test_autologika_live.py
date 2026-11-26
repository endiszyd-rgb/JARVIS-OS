"""Live read-only AutoLogika: connection settings, today's brief, parts and voice intents.

Fixtures in tests/fixtures/autologika_bcdc364 were captured from the real Autologika-OS bcdc364
schema-18 migrations and the real orderSelect/GET handlers (scripts/autologika_contract_harness.cjs),
filled with synthetic data.
"""
import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from jarvis import autologika, intents
from jarvis.main import create_app

KEY = 'autologika-live-owner-key-32-chars'
OWNER = {'X-Jarvis-Key': KEY}
PIN = '246810'
FIXTURES = Path(__file__).parent / 'fixtures' / 'autologika_bcdc364'


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def handler(seen):
    def respond(request):
        seen.append((request.method, request.url.path, request.headers.get('x-autologika-pin')))
        if request.headers.get('x-autologika-pin') != PIN:
            return httpx.Response(401, json={'error': 'Nieprawidłowy PIN'})
        if request.method != 'GET':
            return httpx.Response(405)
        if request.url.path == '/api/orders':
            return httpx.Response(200, json=fixture('orders.json'))
        if request.url.path.startswith('/api/order/'):
            name = 'order_' + request.url.path.rsplit('/', 1)[1] + '.json'
            return httpx.Response(200, json=fixture(name)) if (FIXTURES / name).exists() else httpx.Response(404)
        return httpx.Response(404)
    return respond


def test_brief_from_real_shaped_payloads():
    seen = []
    adapter = autologika.AutoLogikaReadOnly('http://127.0.0.1:8787', PIN, httpx.MockTransport(handler(seen)))
    data = asyncio.run(autologika.brief(adapter, '2026-11-26'))
    assert data['open_orders'] == 4 and data['by_status'] == {'DIAGNOZA': 1, 'NAPRAWA': 1, 'GOTOWE': 1, 'AKCEPTACJA': 1}
    assert [item['plate'] for item in data['due_today']] == ['PO12345']  # GOTOWE is not "to do today"
    assert [item['plate'] for item in data['ready']] == ['WX9876A']
    assert [item['plate'] for item in data['overdue']] == ['KR5555B']
    assert [item['plate'] for item in data['waiting_customer']] == ['KR5555B']
    assert [(item['name'], item['status']) for item in data['to_order']] == [('Zestaw rozrządu', 'DO_ZAMOWIENIA')]
    assert [(item['name'], item['status']) for item in data['on_order']] == [('Pompa wody', 'W_DRODZE')]  # ODEBRANE excluded
    assert data['partial'] is False
    # one list read + details only for the order waiting for parts; GET only
    assert [path for _, path, _ in seen] == ['/api/orders', '/api/order/2']
    assert all(method == 'GET' and pin == PIN for method, _, pin in seen)
    text = autologika.brief_text(data)
    assert 'Otwartych zleceń: 4.' in text and 'Skoda Fabia PO12345' in text and 'Gotowe do odbioru: Audi A4 WX9876A' in text
    assert 'Do zamówienia: Zestaw rozrządu (PO12345)' in text and 'Pompa wody' in text


def test_iso_utc_due_dates_use_the_local_day(monkeypatch):
    monkeypatch.setenv('TZ', 'Europe/Warsaw')
    import time
    time.tzset()
    try:
        assert autologika._date('2026-11-26T23:30:00.000Z') == '2026-11-27'
        assert autologika._date('2026-11-26') == '2026-11-26'
        assert autologika._date(None) == ''
    finally:
        monkeypatch.delenv('TZ')
        time.tzset()


@pytest.mark.parametrize('text,kind', [('Jarvis, co dziś?', 'today'), ('co mamy na dziś', 'today'), ('jakie są zlecenia', 'today'),
                                       ('co jest gotowe', 'today'), ('raport dnia', 'today'), ('jak się dziś czujesz', None),
                                       ('jaka jest dziś pogoda', None), ('co dziś na obiad zrobić w domu', None)])
def test_today_intent(text, kind):
    intent = intents.parse(text)
    assert (intent.kind if intent else None) == kind


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('AUTOLOGIKA_READONLY_ENABLED', raising=False)
    monkeypatch.delenv('AUTOLOGIKA_SNAPSHOT_ENABLED', raising=False)
    app = create_app(tmp_path / 'live.db', KEY)
    seen = []
    app.state.autologika_transport = httpx.MockTransport(handler(seen))
    with TestClient(app) as c:
        c.seen = seen
        c.path = tmp_path / 'live.db'
        yield c


def connect(c, pin=PIN, enabled=True):
    revision = c.get('/api/v1/autologika/connection', headers=OWNER).json()['revision']
    return c.put('/api/v1/autologika/connection', headers=OWNER, json={'revision': revision, 'config': {'enabled': enabled, 'url': 'http://127.0.0.1:8787', 'pin': pin}})


def test_connection_settings_mask_pin_keep_it_on_resave_and_test(client):
    initial = client.get('/api/v1/autologika/connection', headers=OWNER).json()
    assert initial['config'] == {'enabled': False, 'url': 'http://127.0.0.1:8787', 'pin': '', 'pin_set': False}
    saved = connect(client)
    assert saved.status_code == 200 and saved.json()['config']['pin'] == '••••••' and PIN not in saved.text
    resaved = client.put('/api/v1/autologika/connection', headers=OWNER, json={'revision': 1, 'config': {**saved.json()['config'], 'enabled': True}})
    assert resaved.status_code == 200
    tested = client.post('/api/v1/autologika/connection/test', headers=OWNER)
    assert tested.json() == {'status': 'connected', 'open_orders': 4}
    assert client.put('/api/v1/autologika/connection', headers=OWNER, json={'revision': 0, 'config': {'enabled': True}}).status_code == 409


@pytest.mark.parametrize('config', [{'enabled': True, 'url': 'ftp://x', 'pin': PIN}, {'enabled': True, 'url': 'http://127.0.0.1:8787', 'pin': '12'},
                                    {'enabled': True, 'url': 'http://u:p@127.0.0.1:8787', 'pin': PIN}, {'enabled': True, 'url': 'http://127.0.0.1:8787/api', 'pin': PIN},
                                    {'enabled': True, 'url': 'http://127.0.0.1:8787', 'pin': PIN, 'extra': 1}])
def test_invalid_connection_is_rejected(client, config):
    assert client.put('/api/v1/autologika/connection', headers=OWNER, json={'revision': 0, 'config': config}).status_code == 422


def test_wrong_pin_reports_unavailable_without_leaking(client):
    connect(client, pin='999999')
    response = client.post('/api/v1/autologika/connection/test', headers=OWNER)
    assert response.status_code == 502 and '999999' not in response.text


def test_today_endpoint_chat_and_voice(client):
    assert client.post('/api/v1/voice/command', headers=OWNER, json={'text': 'co dziś?'}).json()['reply'].startswith('Nie mam połączenia z AutoLogiką')
    connect(client)
    today = client.get('/api/v1/autologika/today', headers=OWNER)
    assert today.status_code == 200 and today.json()['mode'] == 'live_readonly' and today.json()['open_orders'] == 4
    voice = client.post('/api/v1/voice/command', headers=OWNER, json={'text': 'Jarvis, co dziś?'}).json()
    assert voice['handled'] is True and voice['reply'].startswith('Otwartych zleceń: 4.') and voice['ai_generated'] is False
    parts = client.post('/api/v1/chat', headers=OWNER, json={'message': 'co trzeba zamówić?'}).json()
    assert parts['model'] == 'parser' and parts['parts']['source'] == 'live' and 'Zestaw rozrządu' in parts['reply']
    assert {method for method, _, _ in client.seen} == {'GET'}


def test_operator_cannot_read_workshop_data(client):
    connect(client)
    assert client.post('/api/v1/security/users', headers=OWNER, json={'username': 'mechanik', 'password': 'Synthetic-password-123', 'role': 'operator'}).status_code == 201
    token = client.post('/api/v1/auth/login', json={'username': 'mechanik', 'password': 'Synthetic-password-123'}).json()['token']
    auth = {'X-Jarvis-Key': token}
    assert client.get('/api/v1/autologika/today', headers=auth).status_code == 403
    assert client.get('/api/v1/autologika/connection', headers=auth).status_code == 403
    assert client.post('/api/v1/voice/command', headers=auth, json={'text': 'co dziś?'}).json()['handled'] is False
    assert client.seen == []


def test_live_failure_falls_back_to_snapshot_message_for_parts(client):
    connect(client, pin='999999')
    reply = client.post('/api/v1/voice/command', headers=OWNER, json={'text': 'co trzeba zamówić'}).json()
    assert reply['handled'] is True and 'kopia AutoLogiki nie jest skonfigurowana' in reply['reply']
