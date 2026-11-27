"""Workshop camera preview through go2rtc (Setti/Tuya, RTSP/ONVIF/NVR → JPEG frames).

Two modes:
- ``builtin`` (default for new installs): JARVIS runs the go2rtc bundled with the Windows installer
  on 127.0.0.1 and writes its configuration from the cameras set up in the panel — Setti/Tuya cameras
  by Device ID (credentials of the Tuya cloud project saved for the gate) or IP cameras by RTSP URL.
- ``external``: an existing go2rtc with its own go2rtc.yaml; JARVIS stores only its origin and stream names.

JARVIS never talks RTSP/WebRTC itself and never returns camera passwords: RTSP URLs are masked like the
gate secrets. Single JPEG frames are proxied to authorised sessions (scope ``cameras:view``). An external
go2rtc origin must be inside JARVIS_NETWORK_ALLOWLIST (DNS pinned to IP, no redirects, bounded size/time).
"""
import asyncio
import re
import time

import httpx
from fastapi import HTTPException
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from . import network

MAX_FRAME = 4 * 1024 * 1024
STREAM = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
CAMERA_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')
TUYA_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
SECRET_MASK = '••••••••'
BUILTIN_PORT = 1984


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Camera(Strict):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=60)
    source: Literal['tuya', 'rtsp', 'go2rtc'] = 'go2rtc'
    stream: str = Field(default='', max_length=64, description='Stream name in an external go2rtc.yaml')
    device_id: str = Field(default='', max_length=64, description='Tuya/Setti camera Device ID')
    uid: str = Field(default='', max_length=64, description='Tuya user id that owns the camera (read from the cloud)')
    resolution: Literal['sd', 'hd'] = 'sd'
    rtsp_url: str = Field(default='', max_length=300, description='rtsp://user:password@192.168.x.x:554/... (secret)')
    enabled: bool = True

    @field_validator('id')
    @classmethod
    def _id(cls, value):
        if not CAMERA_ID.fullmatch(value):
            raise ValueError('Use lowercase letters, digits, "-" or "_"')
        return value

    @model_validator(mode='after')
    def _source(self):
        if self.source == 'go2rtc' and not STREAM.fullmatch(self.stream):
            raise ValueError('Stream name may contain letters, digits, ".", "-" or "_"')
        if self.source == 'tuya':
            self.device_id = self.device_id.strip()
            if not TUYA_ID.fullmatch(self.device_id):
                raise ValueError('Enter the camera Device ID from iot.tuya.com')
            if self.uid and not TUYA_ID.fullmatch(self.uid):
                raise ValueError('Invalid Tuya UID')
        if self.source == 'rtsp' and self.rtsp_url != SECRET_MASK:
            url = self.rtsp_url.strip()
            parts = urlsplit(url)
            if parts.scheme not in ('rtsp', 'rtsps') or not parts.hostname or any(ch in url for ch in ' \n\r\t"\''):
                raise ValueError('Enter the camera address as rtsp://user:password@192.168.1.64:554/...')
            self.rtsp_url = url
        return self


class CameraConfig(Strict):
    enabled: bool = False
    # 'external' keeps configurations saved before 0.18.0 working; new installs start with 'builtin'.
    mode: Literal['builtin', 'external'] = 'external'
    go2rtc_url: str = Field(default='http://127.0.0.1:1984', max_length=200)
    refresh_ms: int = Field(default=1000, ge=250, le=10000)
    cameras: list[Camera] = Field(default_factory=list, max_length=16)

    @field_validator('go2rtc_url')
    @classmethod
    def _origin(cls, value):
        value = value.rstrip('/')
        try:
            network.validate_origin(value)
        except network.NetworkDenied as exc:
            raise ValueError(str(exc)) from None
        return value

    @field_validator('cameras')
    @classmethod
    def _unique(cls, value):
        if len({item.id for item in value}) != len(value):
            raise ValueError('Camera ids must be unique')
        return value

    @model_validator(mode='after')
    def _sources_match_mode(self):
        for item in self.cameras:
            if self.mode == 'builtin' and item.source == 'go2rtc':
                raise ValueError(f'Camera {item.id}: choose Setti/Tuya or RTSP for the built-in go2rtc')
            if self.mode == 'external' and item.source != 'go2rtc':
                raise ValueError(f'Camera {item.id}: an external go2rtc uses stream names from its own go2rtc.yaml')
        return self

    def base_url(self):
        return f'http://127.0.0.1:{BUILTIN_PORT}' if self.mode == 'builtin' else self.go2rtc_url

    @staticmethod
    def stream_name(camera):
        return camera.id if camera.source != 'go2rtc' else camera.stream

    def masked(self):
        data = self.model_dump()
        for item in data['cameras']:
            item['rtsp_set'] = bool(item['rtsp_url'])
            if item['rtsp_url']:
                item['rtsp_url'] = SECRET_MASK
        return data

    def camera(self, ident):
        for item in self.cameras:
            if item.id == ident and item.enabled:
                return item
        raise HTTPException(404, 'Camera missing or disabled')

    def public(self):
        return {'enabled': self.enabled, 'refresh_ms': self.refresh_ms,
                'cameras': [{'id': item.id, 'name': item.name} for item in self.cameras if item.enabled]}


def install(c):
    c.execute('INSERT OR IGNORE INTO device_config VALUES(?,?,?,?)', ('cameras', CameraConfig(mode='builtin').model_dump_json(), 0, time.time()))


def load(c):
    row = c.execute("SELECT value,revision FROM device_config WHERE id='cameras'").fetchone()
    if row is None:
        return CameraConfig(), 0
    try:
        return CameraConfig.model_validate_json(row[0]), row[1]
    except ValidationError:
        return CameraConfig(), row[1]


def save(c, incoming, expected_revision):
    stored, revision = load(c)
    if expected_revision != revision:
        raise HTTPException(409, 'Camera configuration changed; reload and retry')
    if isinstance(incoming, dict) and isinstance(incoming.get('cameras'), list):
        # A masked RTSP URL means "keep the stored one" (same rule as the gate secrets).
        previous = {item.id: item.rtsp_url for item in stored.cameras}

        def restore(item):
            if not isinstance(item, dict):
                return item
            item = {key: value for key, value in item.items() if key != 'rtsp_set'}  # read-only flag from masked()
            if item.get('rtsp_url') == SECRET_MASK:
                item['rtsp_url'] = previous.get(item.get('id'), '')
            return item
        incoming = {**incoming, 'cameras': [restore(item) for item in incoming['cameras']]}
    try:
        config = CameraConfig.model_validate(incoming)
    except ValidationError as exc:
        detail = '; '.join('.'.join(str(x) for x in e['loc']) + ': ' + e['msg'] for e in exc.errors()[:4])
        raise HTTPException(422, 'Invalid camera configuration: ' + detail) from None
    c.execute("UPDATE device_config SET value=?,revision=revision+1,updated=? WHERE id='cameras'", (config.model_dump_json(), time.time()))
    return config, revision + 1


async def frame(config: CameraConfig, camera: Camera, *, transport=None):
    """Fetch one JPEG frame from go2rtc; bounded to 4 MiB and 8 s."""
    if not config.enabled:
        raise HTTPException(503, 'Camera preview is disabled')
    base = config.base_url()
    url = base + '/api/frame.jpeg'
    try:
        async with asyncio.timeout(8):
            client = (httpx.AsyncClient(transport=transport, timeout=6, follow_redirects=False, trust_env=False)
                      if transport is not None else network.client(base, timeout=6))
            async with client:
                async with client.stream('GET', url, params={'src': config.stream_name(camera)}) as response:
                    if response.status_code != 200:
                        raise HTTPException(502, 'go2rtc answered HTTP ' + str(response.status_code) + ' for this stream')
                    kind = response.headers.get('content-type', '').split(';')[0].strip().lower()
                    if kind not in ('image/jpeg', 'image/jpg'):
                        raise HTTPException(502, 'go2rtc did not return a JPEG frame')
                    data = bytearray()
                    async for block in response.aiter_bytes():
                        data.extend(block)
                        if len(data) > MAX_FRAME:
                            raise HTTPException(502, 'Camera frame exceeds 4 MiB')
    except TimeoutError:
        raise HTTPException(504, 'Camera did not answer in time') from None
    except network.NetworkDenied:
        raise HTTPException(403, 'go2rtc address is outside JARVIS_NETWORK_ALLOWLIST') from None
    except httpx.HTTPError:
        if config.mode == 'builtin':
            raise HTTPException(502, 'Built-in go2rtc is not running') from None
        raise HTTPException(502, 'Cannot reach go2rtc') from None
    if not data.startswith(b'\xff\xd8'):
        raise HTTPException(502, 'go2rtc did not return a JPEG frame')
    return bytes(data)
