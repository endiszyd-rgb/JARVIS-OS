"""Validated security settings and bounded, process-local peer rate limits."""
from dataclasses import dataclass
import ipaddress
import json
import math
import os
import re
import time
from urllib.parse import urlsplit


def _origins(values):
    result = []
    for value in values:
        try:
            if not isinstance(value, str) or any(ord(ch) < 33 or ord(ch) == 127 for ch in value) or any(ch in value for ch in '\\?#'):
                raise ValueError()
            parsed = urlsplit(value)
            host, port = parsed.hostname, parsed.port
            if parsed.scheme not in ('https', 'http') or not host or '%' in host or parsed.username is not None or parsed.password is not None or parsed.path not in ('', '/'):
                raise ValueError()
            if port is not None and not 1 <= port <= 65535:
                raise ValueError()
            try:
                address = ipaddress.ip_address(host)
                loopback = address.is_loopback
                host = '[' + address.compressed + ']' if address.version == 6 else str(address)
            except ValueError:
                host = host.encode('idna').decode('ascii').lower()
                if len(host) > 253 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in host.rstrip('.').split('.')):
                    raise ValueError()
                loopback = host == 'localhost'
            if parsed.scheme == 'http' and not loopback:
                raise ValueError()
            origin = parsed.scheme + '://' + host
            if port is not None and port != (443 if parsed.scheme == 'https' else 80):
                origin += ':' + str(port)
            if origin not in result:
                result.append(origin)
        except (ValueError, UnicodeError):
            raise ValueError('JARVIS_CORS_ORIGINS must contain explicit HTTPS or loopback HTTP origins') from None
    return tuple(result)


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    session_minutes: int = 60
    api_per_minute: int = 600
    login_per_minute: int = 10
    cors_origins: tuple[str, ...] = ()

    def __post_init__(self):
        for field, name, low, high in (
            ('session_minutes', 'JARVIS_SESSION_MINUTES', 5, 1440),
            ('api_per_minute', 'JARVIS_API_REQUESTS_PER_MINUTE', 1, 100000),
            ('login_per_minute', 'JARVIS_LOGIN_ATTEMPTS_PER_MINUTE', 1, 1000),
        ):
            value = getattr(self, field)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name} must be an integer from {low} to {high}')
        if not isinstance(self.cors_origins, tuple):
            raise ValueError('JARVIS_CORS_ORIGINS must be an immutable tuple of origins')
        object.__setattr__(self, 'cors_origins', _origins(self.cors_origins))

    @classmethod
    def from_env(cls):
        values = {}
        for field, name, default in (
            ('session_minutes', 'JARVIS_SESSION_MINUTES', 60),
            ('api_per_minute', 'JARVIS_API_REQUESTS_PER_MINUTE', 600),
            ('login_per_minute', 'JARVIS_LOGIN_ATTEMPTS_PER_MINUTE', 10),
        ):
            try:
                values[field] = int(os.environ.get(name, str(default)))
            except ValueError:
                raise ValueError(f'{name} must be a bounded integer') from None
        raw = os.environ.get('JARVIS_CORS_ORIGINS', '')
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
            raise ValueError('JARVIS_CORS_ORIGINS must contain explicit origins')
        values['cors_origins'] = tuple(value.strip() for value in raw.split(',') if value.strip())
        return cls(**values)


@dataclass(slots=True)
class _Window:
    start: float
    api: int = 0
    login: int = 0


class RateLimit:
    """Fixed 60-second windows. Limits are per process, with no proxy-header trust."""
    def __init__(self, app, config, clock=time.monotonic, max_clients=4096):
        if type(max_clients) is not int or max_clients < 1:
            raise ValueError('max_clients must be a positive integer')
        self.app, self.config, self.clock = app, config, clock
        self.max_clients = max_clients
        self._clients = {}

    async def _reject(self, send, remaining):
        body = json.dumps({'detail': 'Rate limit exceeded'}).encode()
        await send({'type': 'http.response.start', 'status': 429, 'headers': [
            (b'content-type', b'application/json'), (b'cache-control', b'no-store'),
            (b'retry-after', str(max(1, math.ceil(remaining))).encode()),
        ]})
        await send({'type': 'http.response.body', 'body': body})

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] != 'http' or scope['method'] == 'OPTIONS' or not (path == '/api' or path.startswith('/api/')):
            return await self.app(scope, receive, send)
        now = self.clock()
        peer = (scope.get('client') or ('unknown',))[0]
        window = self._clients.get(peer)
        if window is None or now - window.start >= 60:
            self._clients = {client: entry for client, entry in self._clients.items() if now - entry.start < 60}
            if len(self._clients) >= self.max_clients:
                return await self._reject(send, min(entry.start + 60 - now for entry in self._clients.values()))
            window = self._clients[peer] = _Window(now)
        # No await between checking/updating counters, including both login aliases.
        if window.api >= self.config.api_per_minute:
            return await self._reject(send, window.start + 60 - now)
        window.api += 1
        if path.startswith('/api/v1/'):
            path = '/api/' + path[len('/api/v1/'):]
        if path.rstrip('/') == '/api/auth/login':
            if window.login >= self.config.login_per_minute:
                return await self._reject(send, window.start + 60 - now)
            window.login += 1
        return await self.app(scope, receive, send)
