"""Configuration validation and direct ASGI limiter checks with a controlled clock."""
import asyncio
from dataclasses import FrozenInstanceError
import json

import pytest

from jarvis.security_limits import RateLimit, SecurityConfig


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    for key in ('JARVIS_SESSION_MINUTES', 'JARVIS_API_REQUESTS_PER_MINUTE',
                'JARVIS_LOGIN_ATTEMPTS_PER_MINUTE', 'JARVIS_CORS_ORIGINS'):
        monkeypatch.delenv(key, raising=False)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Harness:
    def __init__(self, config=None, max_clients=4096):
        self.clock = Clock()
        self.passed = []

        async def app(scope, receive, send):
            self.passed.append(scope)
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b''})

        self.limiter = RateLimit(app, config or SecurityConfig(), self.clock, max_clients)

    def request(self, path='/api/v1/status', peer='192.0.2.1', method='GET', headers=(), scope_type='http'):
        messages = []

        async def receive():
            pytest.fail('Limiter must never consume the request body')

        async def send(message):
            messages.append(message)

        scope = {'type': scope_type, 'method': method, 'path': path,
                 'client': (peer, 1234) if peer is not None else None, 'headers': list(headers)}
        asyncio.run(self.limiter(scope, receive, send))
        start = messages[0]
        return start['status'], dict(start['headers']), messages[1].get('body', b'')


def test_defaults_and_immutability():
    config = SecurityConfig.from_env()
    assert (config.session_minutes, config.api_per_minute, config.login_per_minute, config.cors_origins) == (60, 600, 10, ())
    with pytest.raises(FrozenInstanceError):
        config.session_minutes = 5


@pytest.mark.parametrize('key,value,field', [
    ('JARVIS_SESSION_MINUTES', '5', 'session_minutes'),
    ('JARVIS_SESSION_MINUTES', '1440', 'session_minutes'),
    ('JARVIS_API_REQUESTS_PER_MINUTE', '1', 'api_per_minute'),
    ('JARVIS_API_REQUESTS_PER_MINUTE', '100000', 'api_per_minute'),
    ('JARVIS_LOGIN_ATTEMPTS_PER_MINUTE', '1', 'login_per_minute'),
    ('JARVIS_LOGIN_ATTEMPTS_PER_MINUTE', '1000', 'login_per_minute'),
])
def test_configured_integer_boundaries(monkeypatch, key, value, field):
    monkeypatch.setenv(key, value)
    assert getattr(SecurityConfig.from_env(), field) == int(value)


@pytest.mark.parametrize('key,value', [
    ('JARVIS_SESSION_MINUTES', '4'), ('JARVIS_SESSION_MINUTES', '1441'),
    ('JARVIS_API_REQUESTS_PER_MINUTE', '0'), ('JARVIS_API_REQUESTS_PER_MINUTE', '100001'),
    ('JARVIS_LOGIN_ATTEMPTS_PER_MINUTE', '-1'), ('JARVIS_LOGIN_ATTEMPTS_PER_MINUTE', '1001'),
    ('JARVIS_SESSION_MINUTES', '60.5'), ('JARVIS_SESSION_MINUTES', 'nan'),
    ('JARVIS_SESSION_MINUTES', 'private-secret-sentinel'), ('JARVIS_SESSION_MINUTES', ''),
])
def test_invalid_config_is_generic(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key) as error:
        SecurityConfig.from_env()
    assert 'private-secret-sentinel' not in str(error.value)


def test_cors_normalizes_and_deduplicates_exact_origins(monkeypatch):
    monkeypatch.setenv('JARVIS_CORS_ORIGINS', ' HTTPS://Example.TEST:443/,https://example.test,http://LOCALHOST:80/,http://127.0.0.1:8000,http://[::1]/,https://other.test:8443 ')
    assert SecurityConfig.from_env().cors_origins == (
        'https://example.test', 'http://localhost', 'http://127.0.0.1:8000', 'http://[::1]', 'https://other.test:8443')


@pytest.mark.parametrize('value', [
    '*', 'null', 'https://*.example.test', 'http://example.test', 'http://localhost.evil.test',
    'https://private-secret-sentinel@example.test', 'https://user:private-secret-sentinel@example.test',
    'https://example.test/path', 'https://example.test/?query=private-secret-sentinel',
    'https://example.test?', 'https://example.test#', 'https://example.test/#private-secret-sentinel',
    'file:///private-secret-sentinel', 'https://example.test:65536', 'https://example.test:bad',
    'https://example.test\\@evil.test', 'https://exa mple.test', 'https://example.test\n.evil.test',
    'https://[::1%25eth0]', 'https://',
])
def test_invalid_cors_is_rejected_without_echo(monkeypatch, value):
    monkeypatch.setenv('JARVIS_CORS_ORIGINS', value)
    with pytest.raises(ValueError, match='JARVIS_CORS_ORIGINS') as error:
        SecurityConfig.from_env()
    assert 'private-secret-sentinel' not in str(error.value)


def test_burst_rejection_retry_after_and_exact_window_renewal():
    h = Harness(SecurityConfig(api_per_minute=2))
    assert h.request()[0] == h.request('/api/status')[0] == 204
    status, headers, body = h.request()
    assert status == 429 and headers[b'cache-control'] == b'no-store'
    assert headers[b'retry-after'] == b'60'
    assert json.loads(body) == {'detail': 'Rate limit exceeded'}
    h.clock.now = 59.01
    assert h.request()[1][b'retry-after'] == b'1'
    h.clock.now = 60
    assert h.request()[0] == 204
    assert len(h.passed) == 3


def test_login_aliases_share_budget_and_rejections_still_spend_global_budget():
    h = Harness(SecurityConfig(api_per_minute=3, login_per_minute=1))
    assert h.request('/api/auth/login', method='POST')[0] == 204
    assert h.request('/api/v1/auth/login', method='POST')[0] == 429
    assert h.request('/api/v1/auth/login/', method='POST')[0] == 429
    assert h.request('/api/status')[0] == 429
    assert len(h.passed) == 1
    h.clock.now = 60
    assert h.request('/api/v1/auth/login', method='POST')[0] == 204


def test_peer_isolation_and_forwarded_headers_cannot_bypass_limits():
    h = Harness(SecurityConfig(api_per_minute=1))
    assert h.request()[0] == 204
    spoof = [(b'x-forwarded-for', b'198.51.100.99'), (b'forwarded', b'for=198.51.100.99'), (b'x-real-ip', b'198.51.100.99')]
    assert h.request(headers=spoof)[0] == 429
    assert h.request(peer='192.0.2.2', headers=[(b'x-forwarded-for', b'192.0.2.1')])[0] == 204
    assert len(h.limiter._clients) == 2


def test_capacity_is_bounded_without_evicting_recent_clients_and_expired_entries_are_pruned():
    h = Harness(SecurityConfig(api_per_minute=1), max_clients=2)
    assert h.request(peer='192.0.2.1')[0] == 204
    h.clock.now = 10
    assert h.request(peer='192.0.2.2')[0] == 204
    for index in range(20):
        assert h.request(peer=f'198.51.100.{index}')[0] == 429
        assert len(h.limiter._clients) == 2
    assert h.request(peer='192.0.2.1')[0] == 429
    assert h.request(peer='192.0.2.2')[0] == 429
    h.clock.now = 60
    assert h.request(peer='192.0.2.3')[0] == 204
    assert set(h.limiter._clients) == {'192.0.2.2', '192.0.2.3'}


def test_options_non_api_and_non_http_skip_limits_and_unknown_peer_is_one_bucket():
    h = Harness(SecurityConfig(api_per_minute=1), max_clients=1)
    for path, method, scope_type in [('/api/v1/status', 'OPTIONS', 'http'), ('/health', 'GET', 'http'),
                                     ('/ready', 'GET', 'http'), ('/apiculture', 'GET', 'http'),
                                     ('/api/v1/status', 'GET', 'websocket')]:
        assert h.request(path, peer=None, method=method, scope_type=scope_type)[0] == 204
    assert not h.limiter._clients
    assert h.request(peer=None)[0] == 204
    assert h.request('/api/unknown/version', peer=None)[0] == 429
    assert len(h.limiter._clients) == 1
