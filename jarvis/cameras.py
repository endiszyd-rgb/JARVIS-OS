"""Workshop camera preview through a local go2rtc server (RTSP/ONVIF/NVR → JPEG frames).

JARVIS never talks RTSP itself and never exposes camera addresses or passwords.
go2rtc (https://github.com/AlexxIT/go2rtc) runs on the workshop PC with the
camera/NVR streams configured in its own go2rtc.yaml; JARVIS stores only the
go2rtc origin and stream names and proxies single JPEG frames to authorised
sessions (scope ``cameras:view``). The go2rtc origin must be inside
JARVIS_NETWORK_ALLOWLIST (DNS pinned to IP, no redirects, bounded size/time).
"""
import asyncio
import re
import time

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from . import network

MAX_FRAME = 4 * 1024 * 1024
STREAM = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
CAMERA_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Camera(Strict):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=60)
    stream: str = Field(min_length=1, max_length=64, description='Stream name from go2rtc.yaml')
    enabled: bool = True

    @field_validator('id')
    @classmethod
    def _id(cls, value):
        if not CAMERA_ID.fullmatch(value):
            raise ValueError('Use lowercase letters, digits, "-" or "_"')
        return value

    @field_validator('stream')
    @classmethod
    def _stream(cls, value):
        if not STREAM.fullmatch(value):
            raise ValueError('Stream name may contain letters, digits, ".", "-" or "_"')
        return value


class CameraConfig(Strict):
    enabled: bool = False
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

    def camera(self, ident):
        for item in self.cameras:
            if item.id == ident and item.enabled:
                return item
        raise HTTPException(404, 'Camera missing or disabled')

    def public(self):
        return {'enabled': self.enabled, 'refresh_ms': self.refresh_ms,
                'cameras': [{'id': item.id, 'name': item.name} for item in self.cameras if item.enabled]}


def install(c):
    c.execute('INSERT OR IGNORE INTO device_config VALUES(?,?,?,?)', ('cameras', CameraConfig().model_dump_json(), 0, time.time()))


def load(c):
    row = c.execute("SELECT value,revision FROM device_config WHERE id='cameras'").fetchone()
    if row is None:
        return CameraConfig(), 0
    try:
        return CameraConfig.model_validate_json(row[0]), row[1]
    except ValidationError:
        return CameraConfig(), row[1]


def save(c, incoming, expected_revision):
    _, revision = load(c)
    if expected_revision != revision:
        raise HTTPException(409, 'Camera configuration changed; reload and retry')
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
    url = config.go2rtc_url + '/api/frame.jpeg'
    try:
        async with asyncio.timeout(8):
            client = (httpx.AsyncClient(transport=transport, timeout=6, follow_redirects=False, trust_env=False)
                      if transport is not None else network.client(config.go2rtc_url, timeout=6))
            async with client:
                async with client.stream('GET', url, params={'src': camera.stream}) as response:
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
        raise HTTPException(502, 'Cannot reach go2rtc') from None
    if not data.startswith(b'\xff\xd8'):
        raise HTTPException(502, 'go2rtc did not return a JPEG frame')
    return bytes(data)
