"""Read-only adapter for audited AutoLogika commit 681f7f5.
Only the GET routes actually present in electron/main.cjs are exposed.
"""
import os
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException

AUDITED_COMMIT = '681f7f5ecf5a1e365022a9ac1cb22b6ff443262c'

class AutoLogikaReadOnly:
    def __init__(self, base_url: str, pin: str, transport=None):
        parsed = urlsplit(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise ValueError('AUTOLOGIKA_URL must be an http(s) origin without credentials or a path')
        if not pin.isdigit() or not 6 <= len(pin) <= 12:
            raise ValueError('AUTOLOGIKA_PIN must contain 6–12 digits')
        self.url = base_url.rstrip('/')
        self.pin = pin
        self.transport = transport

    async def read(self, order_id=None):
        if order_id is not None and (type(order_id) is not int or order_id <= 0):
            raise ValueError('Positive order_id required')
        route = '/api/orders' if order_id is None else f'/api/order/{order_id}'
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                r = await client.get(self.url+route, headers={'X-Autologika-Pin': self.pin})
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, list if order_id is None else dict):
                    raise ValueError('Unexpected response type')
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, 'AutoLogika unavailable, PIN rejected or response invalid')
        return {'mode': 'live_readonly', 'audited_commit': AUDITED_COMMIT, 'data': data, 'limitations': 'orders list excludes WYDANE and is capped at 100; no full calendar/customer/report API'}


def configured_adapter():
    if os.getenv('AUTOLOGIKA_READONLY_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Read-only integration explicitly disabled')
    try:
        return AutoLogikaReadOnly(os.getenv('AUTOLOGIKA_URL', ''), os.getenv('AUTOLOGIKA_PIN', ''))
    except ValueError:
        raise HTTPException(503, 'Configure AUTOLOGIKA_URL and AUTOLOGIKA_PIN')
