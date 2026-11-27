"""Workshop gate control: explicit driver, owner-only commands, cooldown, optional confirmation, audit.

Drivers: ``simulator`` (no I/O), ``http`` (Shelly/Tasmota/ESPHome style local URLs), ``tuya_cloud``
(Smart Life / Tuya IoT OpenAPI), ``tuya_local`` (Setti/Tuya device on the workshop LAN, no cloud,
via tinytuya) and ``home_assistant`` (service call on one entity). Configuration
lives in the local database, is edited from the Control Center and never leaves the Core unmasked.
"""
import asyncio
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import time
from typing import Literal
from urllib.parse import urlsplit, parse_qsl

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from . import network

ACTIONS = ('open', 'close', 'stop', 'toggle', 'status')
# 'impulse': a one-button controller got its signal; direction is unknown (open, stop or close) until a sensor says.
STATES = ('unknown', 'open', 'closed', 'opening', 'closing', 'stopped', 'impulse')
TUYA_ENDPOINTS = ('https://openapi.tuyaeu.com', 'https://openapi.tuyaus.com', 'https://openapi.tuyacn.com', 'https://openapi.tuyain.com', 'https://openapi-ueaz.tuyaus.com', 'https://openapi-weaz.tuyaeu.com')
ENTITY = re.compile(r'^(cover|switch|button|input_boolean|script)\.[a-z0-9_]+$')
SECRET_MASK = '••••••••'


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class HttpDriver(Strict):
    """One URL per action. Query strings are allowed (``/relay/0?turn=on``)."""
    open_url: str = Field(min_length=1, max_length=500)
    close_url: str = Field(default='', max_length=500)
    stop_url: str = Field(default='', max_length=500)
    status_url: str = Field(default='', max_length=500)
    method: Literal['GET', 'POST'] = 'GET'
    body: str = Field(default='', max_length=2000)
    username: str = Field(default='', max_length=120)
    password: str = Field(default='', max_length=200)
    status_open_match: str = Field(default='', max_length=120, description='substring of the status response meaning OPEN, e.g. "ison":true')

    @field_validator('open_url', 'close_url', 'stop_url', 'status_url')
    @classmethod
    def _url(cls, value):
        if value:
            split_url(value)
        return value


class TuyaDriver(Strict):
    endpoint: str = Field(default='https://openapi.tuyaeu.com')
    access_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    access_secret: str = Field(default='', max_length=128)
    device_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    open_code: str = Field(default='switch_1', max_length=64, pattern=r'^[A-Za-z0-9_]+$')
    open_value: bool | int | str = True
    close_code: str = Field(default='switch_1', max_length=64, pattern=r'^[A-Za-z0-9_]+$')
    close_value: bool | int | str = False
    stop_code: str = Field(default='', max_length=64, pattern=r'^[A-Za-z0-9_]*$')
    stop_value: bool | int | str = True
    status_code: str = Field(default='', max_length=64, pattern=r'^[A-Za-z0-9_]*$')

    @field_validator('endpoint')
    @classmethod
    def _endpoint(cls, value):
        if value.rstrip('/') not in TUYA_ENDPOINTS:
            raise ValueError('Unknown Tuya endpoint')
        return value.rstrip('/')


TUYA_LOCAL_VERSIONS = ('auto', '3.1', '3.3', '3.4', '3.5')


def private_lan_address(value: str) -> str:
    """A device on the workshop network: private IPv4/IPv6 only (no loopback, public or link-local)."""
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        raise ValueError('Enter the device IP address, e.g. 192.168.1.50') from None
    if not address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
        raise ValueError('Only devices on the local network (e.g. 192.168.x.x) are allowed')
    return str(address)


class TuyaLocalDriver(Strict):
    """Tuya/Setti device controlled directly on the LAN (port 6668); the cloud is needed once for the local key."""
    device_id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')
    local_key: str = Field(default='', max_length=64)
    address: str = Field(min_length=1, max_length=45)
    version: Literal['auto', '3.1', '3.3', '3.4', '3.5'] = 'auto'
    open_dp: int = Field(default=1, ge=1, le=255)
    open_value: bool | int | str = True
    close_dp: int = Field(default=1, ge=1, le=255)
    close_value: bool | int | str = False
    stop_dp: int = Field(default=0, ge=0, le=255, description='0 = no stop command')
    stop_value: bool | int | str = True
    status_dp: int = Field(default=0, ge=0, le=255, description='0 = no position sensor')

    @field_validator('address')
    @classmethod
    def _address(cls, value):
        return private_lan_address(value)


class HomeAssistantDriver(Strict):
    url: str = Field(default='', max_length=300)
    token: str = Field(default='', max_length=4096)
    entity_id: str = Field(min_length=3, max_length=120)
    open_service: str = Field(default='cover.open_cover', max_length=80, pattern=r'^[a-z_]+\.[a-z_]+$')
    close_service: str = Field(default='cover.close_cover', max_length=80, pattern=r'^[a-z_]+\.[a-z_]+$')
    stop_service: str = Field(default='cover.stop_cover', max_length=80, pattern=r'^[a-z_]*\.?[a-z_]*$')

    @field_validator('entity_id')
    @classmethod
    def _entity(cls, value):
        if not ENTITY.fullmatch(value):
            raise ValueError('Unsupported entity domain')
        return value

    @field_validator('url')
    @classmethod
    def _url(cls, value):
        if value:
            network.validate_origin(value)
        return value.rstrip('/')


class GateConfig(Strict):
    driver: Literal['disabled', 'simulator', 'http', 'tuya_cloud', 'tuya_local', 'home_assistant'] = 'simulator'
    name: str = Field(default='Brama warsztatu', min_length=1, max_length=80)
    require_confirmation: bool = False
    cooldown_seconds: int = Field(default=3, ge=0, le=120)
    travel_seconds: int = Field(default=15, ge=1, le=300, description='Time after which an opening/closing gate is assumed to have finished')
    pulse: bool = Field(default=False, description='Single-impulse gate: open and close send the same command')
    http: HttpDriver | None = None
    tuya: TuyaDriver | None = None
    tuya_local: TuyaLocalDriver | None = None
    home_assistant: HomeAssistantDriver | None = None

    def selected(self):
        mapping = {'http': self.http, 'tuya_cloud': self.tuya, 'tuya_local': self.tuya_local, 'home_assistant': self.home_assistant}
        if self.driver in mapping and mapping[self.driver] is None:
            raise HTTPException(422, 'Driver "' + self.driver + '" needs its configuration section')
        return mapping.get(self.driver)

    def masked(self):
        """Public view for the panel: secrets are replaced by a marker and a *_set flag."""
        data = self.model_dump()
        for section, fields in (('http', ('password',)), ('tuya', ('access_secret',)), ('tuya_local', ('local_key',)), ('home_assistant', ('token',))):
            if data.get(section):
                for name in fields:
                    data[section][name + '_set'] = bool(data[section][name])
                    data[section][name] = SECRET_MASK if data[section][name] else ''
        return data


SECRET_FIELDS = {'http': ('password',), 'tuya': ('access_secret',), 'tuya_local': ('local_key',), 'home_assistant': ('token',)}


def merge_secrets(previous: GateConfig | None, incoming: dict) -> dict:
    """A masked or empty secret in an update keeps the stored one."""
    for section, fields in SECRET_FIELDS.items():
        block = incoming.get(section)
        if not isinstance(block, dict):
            continue
        for name in fields:
            block.pop(name + '_set', None)
            value = block.get(name, '')
            if value in ('', SECRET_MASK) and previous is not None and getattr(previous, section) is not None:
                block[name] = getattr(getattr(previous, section), name)
    return incoming


def split_url(value: str):
    parts = urlsplit(value)
    origin = parts.scheme + '://' + parts.netloc
    network.validate_origin(origin)
    if parts.fragment or parts.username or parts.password or '\\' in value:
        raise ValueError('Unsupported URL')
    return origin, parts.path or '/', dict(parse_qsl(parts.query, keep_blank_values=True))


# --------------------------------------------------------------------------- storage

def install(c):
    c.execute('CREATE TABLE IF NOT EXISTS device_config(id TEXT PRIMARY KEY, value TEXT NOT NULL, revision INTEGER NOT NULL, updated REAL NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS gate_events(id INTEGER PRIMARY KEY, action TEXT NOT NULL, source TEXT NOT NULL, actor TEXT NOT NULL, result TEXT NOT NULL, detail TEXT NOT NULL, created REAL NOT NULL)')
    c.execute('INSERT OR IGNORE INTO device_config VALUES(?,?,?,?)', ('gate', GateConfig().model_dump_json(), 0, time.time()))


def load(c) -> tuple[GateConfig, int]:
    row = c.execute('SELECT value,revision FROM device_config WHERE id=?', ('gate',)).fetchone()
    if row is None:
        return GateConfig(), 0
    try:
        return GateConfig.model_validate_json(row[0]), row[1]
    except ValidationError:
        return GateConfig(), row[1]


def save(c, incoming: dict, expected_revision: int | None = None) -> tuple[GateConfig, int]:
    previous, revision = load(c)
    if expected_revision is not None and expected_revision != revision:
        raise HTTPException(409, 'Gate configuration changed; reload and retry')
    try:
        config = GateConfig(**merge_secrets(previous, incoming))
    except (ValidationError, TypeError) as exc:
        raise HTTPException(422, 'Invalid gate configuration: ' + summarize(exc)) from None
    config.selected()
    c.execute('UPDATE device_config SET value=?,revision=revision+1,updated=? WHERE id=?', (config.model_dump_json(), time.time(), 'gate'))
    return config, revision + 1


def summarize(exc):
    if isinstance(exc, ValidationError):
        return '; '.join('.'.join(str(x) for x in e['loc']) + ': ' + e['msg'] for e in exc.errors()[:4])
    return 'unexpected payload'


def record(c, action, source, actor, result, detail=None):
    c.execute('INSERT INTO gate_events(action,source,actor,result,detail,created) VALUES(?,?,?,?,?,?)',
              (action, source, actor, result, json.dumps(detail or {}, ensure_ascii=False), time.time()))
    c.execute('DELETE FROM gate_events WHERE id NOT IN (SELECT id FROM gate_events ORDER BY id DESC LIMIT 500)')


def events(c, limit=20):
    return [dict(r, detail=json.loads(r['detail'])) for r in c.execute('SELECT * FROM gate_events ORDER BY id DESC LIMIT ?', (limit,))]


# --------------------------------------------------------------------------- drivers

class Simulator:
    """M5.4 gate simulator: states, travel time, stop, no I/O."""
    live = False

    def __init__(self, config: GateConfig):
        self.config = config

    async def command(self, action, state):
        if action == 'toggle':  # one-button gate: alternates like a real impulse controller
            action = 'close' if state.get('state') in ('open', 'opening') else 'open'
        return {'state': 'opening' if action == 'open' else 'closing' if action == 'close' else 'stopped', 'external_request_sent': False}

    async def status(self, state):
        return {'state': state.get('state', 'closed'), 'external_request_sent': False}


class Http:
    live = True

    def __init__(self, config: GateConfig):
        self.config = config
        self.driver = config.http

    def _url(self, action):
        value = {'open': self.driver.open_url, 'close': self.driver.close_url or (self.driver.open_url if self.config.pulse else ''),
                 'stop': self.driver.stop_url, 'status': self.driver.status_url}[action]
        if not value:
            raise HTTPException(501, 'No URL configured for "' + action + '"')
        return split_url(value)

    async def _call(self, action, method):
        origin, path, params = self._url(action)
        auth = (self.driver.username, self.driver.password) if self.driver.username else None
        async with asyncio.timeout(15):
            async with network.client(origin, timeout=10) as client:
                response = await client.request(method, origin + path, params=params, auth=auth,
                                                content=self.driver.body.encode() if method == 'POST' and self.driver.body else None)
        text = response.text[:4000]
        if response.status_code >= 400:
            raise HTTPException(502, 'Gate controller answered HTTP ' + str(response.status_code))
        return text

    async def command(self, action, state):
        await self._call(action, self.driver.method)
        return {'state': 'opening' if action == 'open' else 'closing' if action == 'close' else 'stopped', 'external_request_sent': True}

    async def status(self, state):
        if not self.driver.status_url:
            return {'state': state.get('state', 'unknown'), 'external_request_sent': False}
        text = await self._call('status', 'GET')
        if self.driver.status_open_match:
            return {'state': 'open' if self.driver.status_open_match in text else 'closed', 'external_request_sent': True, 'raw': text[:300]}
        return {'state': state.get('state', 'unknown'), 'external_request_sent': True, 'raw': text[:300]}


class TuyaCloud:
    """Tuya IoT Platform OpenAPI (Smart Life). Requires a cloud project linked to the Smart Life account."""
    live = True
    INTERNET = [ipaddress.ip_network('0.0.0.0/0'), ipaddress.ip_network('::/0')]

    def __init__(self, config: GateConfig):
        self.config = config
        self.driver = config.tuya
        self.token = None
        self.token_expires = 0.0

    def _sign(self, method, path, body, token=''):
        t = str(int(time.time() * 1000))
        nonce = secrets.token_hex(8)
        digest = hashlib.sha256(body.encode()).hexdigest()
        string_to_sign = method + '\n' + digest + '\n' + '\n' + path
        payload = self.driver.access_id + token + t + nonce + string_to_sign
        sign = hmac.new(self.driver.access_secret.encode(), payload.encode(), hashlib.sha256).hexdigest().upper()
        headers = {'client_id': self.driver.access_id, 'sign': sign, 't': t, 'sign_method': 'HMAC-SHA256', 'nonce': nonce, 'Content-Type': 'application/json'}
        if token:
            headers['access_token'] = token
        return headers

    async def _request(self, method, path, body='', token=''):
        if not self.driver.access_secret:
            raise HTTPException(503, 'Tuya access secret is not configured')
        transport = network.PinnedTransport(self.driver.endpoint, networks=self.INTERNET)
        async with asyncio.timeout(20):
            async with httpx.AsyncClient(transport=transport, timeout=12, follow_redirects=False, trust_env=False) as client:
                response = await client.request(method, self.driver.endpoint + path, headers=self._sign(method, path, body, token), content=body.encode() if body else None)
        try:
            data = response.json()
        except ValueError:
            raise HTTPException(502, 'Tuya answered with an invalid response') from None
        if not isinstance(data, dict) or not data.get('success'):
            raise HTTPException(502, 'Tuya error ' + str(data.get('code', '?') if isinstance(data, dict) else '?') + ': ' + str(data.get('msg', '') if isinstance(data, dict) else '')[:200])
        return data.get('result')

    async def _token(self):
        if self.token and time.time() < self.token_expires - 60:
            return self.token
        result = await self._request('GET', '/v1.0/token?grant_type=1')
        if not isinstance(result, dict) or not isinstance(result.get('access_token'), str):
            raise HTTPException(502, 'Tuya token response is invalid')
        self.token = result['access_token']
        self.token_expires = time.time() + int(result.get('expire_time', 3600))
        return self.token

    async def command(self, action, state):
        if action == 'stop' and not self.driver.stop_code:
            raise HTTPException(501, 'No stop command configured for Tuya')
        code, value = {'open': (self.driver.open_code, self.driver.open_value), 'close': (self.driver.close_code, self.driver.close_value),
                       'stop': (self.driver.stop_code, self.driver.stop_value)}[action]
        if self.config.pulse and action == 'close':
            code, value = self.driver.open_code, self.driver.open_value
        token = await self._token()
        body = json.dumps({'commands': [{'code': code, 'value': value}]}, separators=(',', ':'))
        await self._request('POST', '/v1.0/iot-03/devices/' + self.driver.device_id + '/commands', body, token)
        return {'state': 'opening' if action == 'open' else 'closing' if action == 'close' else 'stopped', 'external_request_sent': True}

    async def status(self, state):
        token = await self._token()
        result = await self._request('GET', '/v1.0/iot-03/devices/' + self.driver.device_id + '/status', '', token)
        values = {item['code']: item.get('value') for item in result if isinstance(item, dict) and isinstance(item.get('code'), str)} if isinstance(result, list) else {}
        current = state.get('state', 'unknown')
        if self.driver.status_code and self.driver.status_code in values:
            value = values[self.driver.status_code]
            current = 'open' if value in (True, 'open', 'opened', 1) else 'closed' if value in (False, 'close', 'closed', 0) else current
        return {'state': current, 'external_request_sent': True, 'values': {k: values[k] for k in list(values)[:20]}}


class HomeAssistant:
    live = True

    def __init__(self, config: GateConfig):
        import os
        self.config = config
        self.driver = config.home_assistant
        self.url = self.driver.url or os.getenv('HA_URL', '').rstrip('/')
        self.token = self.driver.token or os.getenv('HA_TOKEN', '')
        if not self.url or not self.token:
            raise HTTPException(503, 'Home Assistant URL and token are required')
        network.validate_origin(self.url)

    async def _call(self, method, path, body=None):
        async with asyncio.timeout(15):
            async with network.client(self.url, headers={'Authorization': 'Bearer ' + self.token}, timeout=10) as client:
                response = await client.request(method, self.url + path, json=body)
        if response.status_code >= 400:
            raise HTTPException(502, 'Home Assistant answered HTTP ' + str(response.status_code))
        try:
            return response.json()
        except ValueError:
            return None

    async def command(self, action, state):
        service = {'open': self.driver.open_service, 'close': self.driver.close_service, 'stop': self.driver.stop_service}[action]
        if self.config.pulse and action == 'close':
            service = self.driver.open_service
        if not service or '.' not in service:
            raise HTTPException(501, 'No service configured for "' + action + '"')
        domain, name = service.split('.', 1)
        await self._call('POST', '/api/services/' + domain + '/' + name, {'entity_id': self.driver.entity_id})
        return {'state': 'opening' if action == 'open' else 'closing' if action == 'close' else 'stopped', 'external_request_sent': True}

    async def status(self, state):
        data = await self._call('GET', '/api/states/' + self.driver.entity_id)
        value = data.get('state') if isinstance(data, dict) else None
        mapping = {'open': 'open', 'closed': 'closed', 'opening': 'opening', 'closing': 'closing', 'on': 'open', 'off': 'closed'}
        return {'state': mapping.get(value, state.get('state', 'unknown')), 'external_request_sent': True, 'raw': value}


class TuyaLocal:
    """Setti/Tuya on the workshop Wi‑Fi without the cloud (tinytuya, TCP 6668, AES with the device's local key)."""
    live = True
    TRY_VERSIONS = (3.3, 3.4, 3.5, 3.1)

    def __init__(self, config: GateConfig, device_factory=None):
        self.config = config
        self.driver = config.tuya_local
        self.factory = device_factory
        self.version = None if self.driver.version == 'auto' else float(self.driver.version)

    def _device(self, version):
        if self.factory is not None:
            return self.factory(self.driver, version)
        import tinytuya
        device = tinytuya.Device(self.driver.device_id, self.driver.address, self.driver.local_key, version=version,
                                 connection_timeout=4, connection_retry_limit=1, connection_retry_delay=1)
        device.set_socketPersistent(False)
        return device

    @staticmethod
    def _check(result):
        if isinstance(result, dict) and result.get('Error'):
            code = str(result.get('Err', ''))
            hint = {'901': 'urządzenie nie odpowiada pod tym adresem IP', '905': 'urządzenie nie odpowiada pod tym adresem IP',
                    '914': 'zły klucz lokalny albo wersja protokołu', '904': 'nieprawidłowa odpowiedź — sprawdź wersję protokołu'}.get(code, '')
            raise HTTPException(502, 'Tuya local error ' + code + ': ' + str(result.get('Error'))[:120] + (' — ' + hint if hint else ''))
        return result

    async def _call(self, operation):
        if not self.driver.local_key:
            raise HTTPException(503, 'Tuya local key is not configured')
        versions = (self.version,) if self.version else self.TRY_VERSIONS
        last = None
        for version in versions:
            try:
                async with asyncio.timeout(15):
                    result = self._check(await asyncio.to_thread(operation, self._device(version)))
                self.version = version  # remember the protocol that answered
                return result
            except HTTPException as exc:
                last = exc
        raise last

    async def command(self, action, state):
        driver = self.driver
        if action == 'stop' and not driver.stop_dp:
            raise HTTPException(501, 'No stop command configured for this gate')
        dp, value = {'open': (driver.open_dp, driver.open_value), 'close': (driver.close_dp, driver.close_value),
                     'stop': (driver.stop_dp, driver.stop_value)}[action]
        if self.config.pulse and action == 'close':
            dp, value = driver.open_dp, driver.open_value
        await self._call(lambda device: device.set_value(dp, value))
        return {'state': 'opening' if action == 'open' else 'closing' if action == 'close' else 'stopped', 'external_request_sent': True}

    async def status(self, state):
        result = await self._call(lambda device: device.status())
        values = result.get('dps', {}) if isinstance(result, dict) else {}
        current = state.get('state', 'unknown')
        if self.driver.status_dp and str(self.driver.status_dp) in values:
            value = values[str(self.driver.status_dp)]
            current = 'open' if value in (True, 'open', 'opened', 1) else 'closed' if value in (False, 'close', 'closed', 0) else current
        return {'state': current, 'external_request_sent': True, 'values': {str(k): values[k] for k in list(values)[:20]},
                'protocol': self.version}


def scan_lan(seconds=8):
    """Listen for Tuya UDP broadcasts on the LAN; returns devices without contacting any cloud."""
    import tinytuya
    found = tinytuya.deviceScan(verbose=False, maxretry=seconds, color=False, poll=False)
    devices = []
    for ip, info in (found or {}).items():
        try:
            address = private_lan_address(str(info.get('ip') or ip))
        except ValueError:
            continue
        device_id = str(info.get('gwId') or info.get('id') or '')
        if re.fullmatch(r'[A-Za-z0-9_-]{1,64}', device_id):
            devices.append({'address': address, 'device_id': device_id, 'version': str(info.get('version') or '')[:5]})
    return sorted(devices, key=lambda item: item['address'])[:50]


async def cloud_device_info(config: GateConfig, device_id: str):
    """Read the device's local key (and name) once through the Tuya cloud project already saved in settings."""
    if config.tuya is None or not config.tuya.access_secret:
        raise HTTPException(409, 'Save the Tuya cloud access (Access ID/Secret) first')
    cloud = TuyaCloud(config.model_copy(update={'driver': 'tuya_cloud'}))
    token = await cloud._token()
    result = await cloud._request('GET', '/v1.0/devices/' + device_id, '', token)
    if not isinstance(result, dict) or not isinstance(result.get('local_key'), str) or not result['local_key']:
        raise HTTPException(502, 'Tuya did not return a local key for this device')
    return {'local_key': result['local_key'][:64], 'name': str(result.get('name') or '')[:80]}


DRIVERS = {'simulator': Simulator, 'http': Http, 'tuya_cloud': TuyaCloud, 'tuya_local': TuyaLocal, 'home_assistant': HomeAssistant}


# --------------------------------------------------------------------------- controller

class Controller:
    """Process-wide gate state: last known position, cooldown, pending confirmations."""

    def __init__(self):
        self.state = {'state': 'unknown', 'changed': None, 'last_action': None, 'last_result': None}
        self.last_command = 0.0
        self.pending: dict[str, tuple[str, float]] = {}
        self.lock = asyncio.Lock()
        self._driver_cache: tuple[int, object] | None = None

    def driver(self, config: GateConfig, revision: int):
        if config.driver == 'disabled':
            raise HTTPException(503, 'Gate control is disabled in settings')
        config.selected()
        if self._driver_cache and self._driver_cache[0] == revision:
            return self._driver_cache[1]
        instance = DRIVERS[config.driver](config)
        self._driver_cache = (revision, instance)
        return instance

    def settle(self, config: GateConfig):
        """Opening/closing finishes after travel time; the simulator relies on this entirely."""
        if self.state['state'] in ('opening', 'closing', 'impulse') and self.state['changed'] and time.time() - self.state['changed'] >= config.travel_seconds:
            self.state['state'] = {'opening': 'open', 'closing': 'closed', 'impulse': 'unknown'}[self.state['state']]
        return self.state

    def confirmation(self, action, key):
        self.pending = {k: v for k, v in self.pending.items() if v[1] > time.time()}
        token = secrets.token_urlsafe(12)
        self.pending[key] = (action + ':' + token, time.time() + 12)
        return token

    def consume(self, action, key, token):
        entry = self.pending.pop(key, None)
        if entry is None or entry[1] < time.time():
            return False
        return hmac.compare_digest(entry[0], action + ':' + (token or ''))

    def cancel(self, key):
        return self.pending.pop(key, None) is not None

    async def execute(self, config, revision, action, *, source, actor, c_factory, audit, confirm_key=None, confirm_token=None):
        if action not in ACTIONS:
            raise HTTPException(422, 'Unknown gate action')
        driver = self.driver(config, revision)
        if config.pulse and action in ('open', 'close'):
            action = 'toggle'  # one-button gate ("Brama"): open/close are the same impulse
        elif action == 'toggle' and not config.pulse:
            action = 'close' if self.settle(config)['state'] in ('open', 'opening') else 'open'  # two-button gate: next move
        if action == 'status':
            async with self.lock:
                try:
                    result = await driver.status(self.settle(config))
                except HTTPException:
                    raise
                except (httpx.HTTPError, network.NetworkDenied, TimeoutError, ValueError, OSError):
                    raise HTTPException(502, 'Gate controller is unreachable') from None
                self.state['state'] = result['state']
            return self.describe(config, result)
        if config.require_confirmation and not self.consume(action, confirm_key or source, confirm_token):
            token = self.confirmation(action, confirm_key or source)
            return {'status': 'confirmation_required', 'action': action, 'confirm_token': token, 'expires_in': 12,
                    'prompt': {'open': 'Otworzyć bramę?', 'close': 'Zamknąć bramę?', 'stop': 'Zatrzymać bramę?', 'toggle': 'Uruchomić bramę?'}[action], 'gate': self.describe(config)}
        async with self.lock:
            if time.time() - self.last_command < config.cooldown_seconds:
                raise HTTPException(429, 'Gate cooldown active; wait ' + str(config.cooldown_seconds) + ' s between commands')
            self.last_command = time.time()
            try:
                if action == 'toggle' and not isinstance(driver, Simulator):
                    # the impulse is the configured "open" signal (Settings → Brama → Sygnał przycisku Brama)
                    result = dict(await driver.command('open', self.settle(config)), state='impulse')
                else:
                    result = await driver.command(action, self.settle(config))
                outcome = 'ok'
            except HTTPException as exc:
                outcome = 'error'
                with c_factory() as c:
                    record(c, action, source, actor, outcome, {'detail': exc.detail, 'driver': config.driver})
                    audit(c, 'gate.failed', {'action': action, 'source': source, 'driver': config.driver})
                raise
            except (httpx.HTTPError, network.NetworkDenied, TimeoutError, ValueError, OSError):
                with c_factory() as c:
                    record(c, action, source, actor, 'error', {'detail': 'unreachable', 'driver': config.driver})
                    audit(c, 'gate.failed', {'action': action, 'source': source, 'driver': config.driver})
                raise HTTPException(502, 'Gate controller is unreachable') from None
            self.state.update(state=result['state'], changed=time.time(), last_action=action, last_result=outcome)
            with c_factory() as c:
                record(c, action, source, actor, outcome, {'driver': config.driver, 'external_request_sent': result['external_request_sent']})
                audit(c, 'gate.command', {'action': action, 'source': source, 'driver': config.driver, 'live': driver.live})
        return {'status': 'executed', 'action': action, 'external_request_sent': result['external_request_sent'], 'gate': self.describe(config, result)}

    def describe(self, config: GateConfig, result=None):
        state = self.settle(config)
        data = {'name': config.name, 'driver': config.driver, 'live': DRIVERS.get(config.driver, Simulator).live if config.driver != 'disabled' else False,
                'state': state['state'], 'state_label': LABELS.get(state['state'], state['state']), 'changed': state['changed'],
                'last_action': state['last_action'], 'require_confirmation': config.require_confirmation, 'pulse': config.pulse}
        if result and 'raw' in result:
            data['raw'] = result['raw']
        if result and 'values' in result:
            data['values'] = result['values']
        return data


LABELS = {'unknown': 'nieznany', 'open': 'otwarta', 'closed': 'zamknięta', 'opening': 'otwiera się', 'closing': 'zamyka się', 'stopped': 'zatrzymana', 'impulse': 'ruszona'}
