"""Read-only adapter for audited AutoLogika commit 681f7f5.
Only the GET routes actually present in electron/main.cjs are exposed.
"""
import asyncio
import json
import os
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_DEADLINE = 12

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
            async with asyncio.timeout(REQUEST_DEADLINE):
                async with httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                    async with client.stream('GET', self.url+route, headers={'X-Autologika-Pin': self.pin}) as response:
                        response.raise_for_status()
                        length = response.headers.get('content-length')
                        if length is not None and (not length.isdecimal() or int(length) > MAX_RESPONSE_BYTES):
                            raise ValueError('Response too large')
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise ValueError('Response too large')
                            body.extend(chunk)
                        data = json.loads(body)
                        validate_response(data, order_id)
        except (httpx.HTTPError, ValueError, TimeoutError, RecursionError):
            raise HTTPException(502, 'AutoLogika unavailable, PIN rejected or response invalid') from None
        return {'mode': 'live_readonly', 'audited_commit': AUDITED_COMMIT, 'data': data, 'limitations': 'orders list excludes WYDANE and is capped at 100; no full calendar/customer/report API'}


def configured_adapter():
    if os.getenv('AUTOLOGIKA_READONLY_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Read-only integration explicitly disabled')
    try:
        return AutoLogikaReadOnly(os.getenv('AUTOLOGIKA_URL', ''), os.getenv('AUTOLOGIKA_PIN', ''))
    except ValueError:
        raise HTTPException(503, 'Configure AUTOLOGIKA_URL and AUTOLOGIKA_PIN')


def validate_response(data, order_id):
    """Validate only the source-audited envelope, without inventing optional columns."""
    def valid_order(row):
        return isinstance(row, dict) and type(row.get('id')) is int and row['id'] > 0
    if order_id is None:
        if not isinstance(data, list) or len(data) > 100 or not all(valid_order(row) for row in data):
            raise ValueError('Invalid orders list')
        if len({row['id'] for row in data}) != len(data):
            raise ValueError('Duplicate order IDs')
    else:
        if not isinstance(data, dict) or not valid_order(data.get('order')) or data['order']['id'] != order_id:
            raise ValueError('Invalid order identity')
        if not all(isinstance(data.get(key), dict) for key in ('notes', 'diag')):
            raise ValueError('Invalid order detail')
        for key in ('parts', 'payments'):
            rows = data.get(key)
            if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get('order_id') == order_id for row in rows):
                raise ValueError('Invalid related order rows')


def capabilities():
    return {
        'audited_commit': AUDITED_COMMIT,
        'live_enabled': os.getenv('AUTOLOGIKA_READONLY_ENABLED', 'false').lower() == 'true',
        'connection_verified': False,
        'http_reads': ['/api/orders', '/api/order/{id}'],
        'http_writes': [],
        'snapshot_domains': ['calendar', 'orders', 'vehicles', 'parts', 'customers', 'diagnostics', 'finances', 'reports', 'notifications'],
        'demo_is_synthetic': True,
        'limitations': ['HTTP list: at most 100 orders, excludes WYDANE',
                        'No complete calendar/customer/vehicle HTTP lists',
                        'Shared upstream PIN is not per-customer authorization',
                        'Snapshot is offline, not synchronization'],
    }
