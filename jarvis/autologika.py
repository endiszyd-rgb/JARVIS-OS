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
        'snapshot_domains': ['calendar', 'orders', 'vehicles', 'parts', 'customers', 'diagnostics', 'qc', 'finances', 'reports', 'notifications'],
        'demo_is_synthetic': True,
        'limitations': ['HTTP list: at most 100 orders, excludes WYDANE',
                        'No complete calendar/customer/vehicle HTTP lists',
                        'Shared upstream PIN is not per-customer authorization',
                        'Snapshot is offline, not synchronization'],
    }


# --------------------------------------------------------------------------- live workshop brief (0.12.1)
# Re-audited 2026-11-26 against Autologika-OS bcdc364 (2026-11-21): electron/main.cjs createMobileServer
# still serves GET /api/orders (orderSelect, status!='WYDANE', LIMIT 100) and GET /api/order/{id}
# ({order, notes, diag, parts=job_part_orders+supplier, payments}); schema 18; job-part-workflow.cjs
# defines the part statuses below and keeps orders.wait_state='CZESCI' while blocking parts exist.
LIVE_AUDITED_COMMIT = 'bcdc364770ace83675ee7c2c7e6967d15dcf1197'
PARTS_TO_ORDER = frozenset({'DO_ZAMOWIENIA'})
PARTS_ON_ORDER = frozenset({'ZAMOWIONE', 'W_DRODZE'})
ORDER_STATUS_LABELS = {
    'PRZYJETE': 'przyjęte', 'DIAGNOZA': 'diagnoza', 'WYCENA': 'wycena', 'AKCEPTACJA': 'czeka na akceptację',
    'NAPRAWA': 'naprawa', 'QC_NAPRAWY': 'kontrola naprawy', 'QC_WYDANIA': 'kontrola wydania',
    'PLATNOSC': 'płatność', 'GOTOWE': 'gotowe do odbioru', 'WYDANE': 'wydane',
}
MAX_DETAIL_READS = 15

from pydantic import BaseModel, ConfigDict, Field, ValidationError  # noqa: E402

SECRET_MASK = '••••••'


class ConnectionConfig(BaseModel):
    """Live read-only connection kept in JARVIS settings (overrides the .env variables when enabled)."""
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    url: str = Field(default='http://127.0.0.1:8787', max_length=200)
    pin: str = Field(default='', max_length=12)

    def masked(self):
        return {'enabled': self.enabled, 'url': self.url, 'pin': SECRET_MASK if self.pin else '', 'pin_set': bool(self.pin)}

    def adapter(self, transport=None):
        return AutoLogikaReadOnly(self.url, self.pin, transport=transport)


def load_connection(c):
    row = c.execute("SELECT value,revision FROM device_config WHERE id='autologika'").fetchone()
    if row is None:
        return ConnectionConfig(), 0
    try:
        return ConnectionConfig.model_validate_json(row[0]), row[1]
    except ValidationError:
        return ConnectionConfig(), row[1]


def save_connection(c, incoming, expected_revision):
    import time
    previous, revision = load_connection(c)
    if expected_revision != revision:
        raise HTTPException(409, 'AutoLogika connection changed; reload and retry')
    if not isinstance(incoming, dict):
        raise HTTPException(422, 'Invalid AutoLogika connection')
    incoming = dict(incoming)
    incoming.pop('pin_set', None)
    if incoming.get('pin', '') in ('', SECRET_MASK):
        incoming['pin'] = previous.pin
    try:
        config = ConnectionConfig(**incoming)
        if config.enabled or config.pin:
            config.adapter()  # validates origin and PIN format
    except (ValidationError, TypeError, ValueError) as exc:
        raise HTTPException(422, 'Invalid AutoLogika connection: ' + (str(exc).splitlines()[0] if isinstance(exc, ValueError) and not isinstance(exc, ValidationError) else 'check URL and 6–12 digit PIN')) from None
    if c.execute("SELECT 1 FROM device_config WHERE id='autologika'").fetchone():
        c.execute("UPDATE device_config SET value=?,revision=revision+1,updated=? WHERE id='autologika'", (config.model_dump_json(), time.time()))
    else:
        c.execute("INSERT INTO device_config VALUES('autologika',?,1,?)", (config.model_dump_json(), time.time()))
    return config, revision + 1


def live_adapter(stored: ConnectionConfig | None, transport=None):
    """Settings from the panel win; otherwise the legacy .env variables; otherwise 503."""
    if stored is not None and stored.enabled:
        try:
            return stored.adapter(transport)
        except ValueError:
            raise HTTPException(503, 'Configure the AutoLogika address and PIN in JARVIS') from None
    adapter = configured_adapter()
    if transport is not None:
        adapter.transport = transport
    return adapter


def _summary(order):
    keys = ('id', 'title', 'status', 'wait_state', 'due_at', 'plate', 'make', 'model', 'customer', 'opened_at')
    data = {key: order.get(key) for key in keys}
    data['status_label'] = ORDER_STATUS_LABELS.get(str(order.get('status') or ''), str(order.get('status') or '').lower())
    return data


def _date(value):
    """Local calendar day of an AutoLogika date: plain 'YYYY-MM-DD' or ISO timestamps (often UTC 'Z')."""
    from datetime import datetime
    text = str(value or '').strip()
    if len(text) > 10 and ('T' in text or ' ' in text):
        try:
            moment = datetime.fromisoformat(text.replace('Z', '+00:00'))
            if moment.tzinfo is not None:
                moment = moment.astimezone()
            return moment.strftime('%Y-%m-%d')
        except ValueError:
            pass
    return text[:10]


async def brief(adapter, today: str):
    """Today's workshop picture from the live read-only API: no writes, at most 1 + 15 GET requests."""
    orders = (await adapter.read())['data']
    open_orders = [row for row in orders if row.get('status') != 'WYDANE']
    by_status = {}
    for row in open_orders:
        key = str(row.get('status') or 'NIEZNANY')
        by_status[key] = by_status.get(key, 0) + 1
    active = [row for row in open_orders if row.get('status') not in ('GOTOWE', 'WYDANE')]
    due_today = [_summary(row) for row in active if _date(row.get('due_at')) == today]
    overdue = [_summary(row) for row in active if row.get('due_at') and _date(row.get('due_at')) < today]
    ready = [_summary(row) for row in open_orders if row.get('status') == 'GOTOWE']
    waiting_customer = [_summary(row) for row in open_orders if row.get('wait_state') in ('KLIENT', 'DECYZJA') or row.get('status') == 'AKCEPTACJA']
    parts_orders = [row for row in open_orders if row.get('wait_state') == 'CZESCI']
    to_order, on_order = [], []
    for row in parts_orders[:MAX_DETAIL_READS]:
        detail = (await adapter.read(row['id']))['data']
        for part in detail['parts']:
            status = str(part.get('status') or '').upper()
            item = {'order_id': row['id'], 'plate': row.get('plate'), 'name': part.get('name'), 'part_no': part.get('part_no'),
                    'qty': part.get('qty'), 'status': status, 'supplier': part.get('supplier'), 'expected_at': part.get('expected_at')}
            if status in PARTS_TO_ORDER:
                to_order.append(item)
            elif status in PARTS_ON_ORDER:
                on_order.append(item)
    return {'mode': 'live_readonly', 'audited_commit': LIVE_AUDITED_COMMIT, 'date': today,
            'open_orders': len(open_orders), 'by_status': by_status, 'due_today': due_today, 'overdue': overdue,
            'ready': ready, 'waiting_customer': waiting_customer, 'waiting_parts_orders': len(parts_orders),
            'to_order': to_order, 'on_order': on_order, 'partial': len(parts_orders) > MAX_DETAIL_READS or len(orders) >= 100,
            'limitations': 'Live list excludes WYDANE and is capped at 100 orders; parts read only for orders waiting for parts (max 15).'}


def _vehicle(item):
    return ' '.join(str(item.get(key)) for key in ('make', 'model') if item.get(key)) or (item.get('title') or 'zlecenie')


def _part(item):
    label = item.get('name') or item.get('part_no') or 'część'
    return label + (f" ({item['plate']})" if item.get('plate') else f" (zlecenie {item['order_id']})")


def brief_text(data):
    parts = [f"Otwartych zleceń: {data['open_orders']}."]
    if data['due_today']:
        parts.append('Na dziś: ' + ', '.join(f"{_vehicle(item)} {item.get('plate') or ''} — {item['status_label']}".replace('  ', ' ') for item in data['due_today'][:6]) + '.')
    if data['overdue']:
        parts.append(f"Po terminie: {len(data['overdue'])}.")
    if data['ready']:
        parts.append('Gotowe do odbioru: ' + ', '.join(f"{_vehicle(item)} {item.get('plate') or ''}".strip() for item in data['ready'][:6]) + '.')
    if data['waiting_customer']:
        parts.append(f"Czeka na decyzję klienta: {len(data['waiting_customer'])}.")
    return ' '.join(parts) + ' ' + parts_text(data)


def parts_text(data):
    bits = []
    if data['to_order']:
        bits.append('Do zamówienia: ' + ', '.join(_part(item) for item in data['to_order'][:8]) + (f" i {len(data['to_order']) - 8} więcej" if len(data['to_order']) > 8 else '') + '.')
    if data['on_order']:
        bits.append('Zamówione, w drodze: ' + ', '.join(_part(item) for item in data['on_order'][:8]) + (f" i {len(data['on_order']) - 8} więcej" if len(data['on_order']) > 8 else '') + '.')
    if not bits:
        bits.append('Żadne zlecenie nie czeka na części.')
    if data.get('partial'):
        bits.append('(lista może być niepełna)')
    return ' '.join(bits)
