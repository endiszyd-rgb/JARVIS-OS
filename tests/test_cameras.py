"""Camera preview through go2rtc: configuration, scopes, bounded frame proxy and allowlist."""
import httpx
import pytest
from fastapi.testclient import TestClient

from jarvis.main import create_app

KEY = 'camera-test-owner-key-32-characters'
OWNER = {'X-Jarvis-Key': KEY}
PASSWORD = 'Synthetic-password-for-camera-tests'
JPEG = b'\xff\xd8\xff\xe0' + b'synthetic-frame' + b'\xff\xd9'
CONFIG = {'enabled': True, 'go2rtc_url': 'http://127.0.0.1:1984', 'refresh_ms': 1000,
          'cameras': [{'id': 'brama', 'name': 'Wjazd', 'stream': 'nvr_ch1'}, {'id': 'hala', 'name': 'Hala', 'stream': 'nvr_ch2', 'enabled': False}]}


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'cameras.db', KEY)
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.params.get('src') == 'broken':
            return httpx.Response(500)
        if request.url.params.get('src') == 'html':
            return httpx.Response(200, headers={'content-type': 'text/html'}, content=b'<html>')
        return httpx.Response(200, headers={'content-type': 'image/jpeg'}, content=JPEG)

    app.state.camera_transport = httpx.MockTransport(handler)
    with TestClient(app) as c:
        c.seen = seen
        c.app_state = app.state
        yield c


def configure(c, config=CONFIG):
    revision = c.get('/api/v1/cameras/config', headers=OWNER).json()['revision']
    return c.put('/api/v1/cameras/config', headers=OWNER, json={'revision': revision, 'config': config})


def operator(c):
    assert c.post('/api/v1/security/users', headers=OWNER, json={'username': 'mechanik', 'password': PASSWORD, 'role': 'operator'}).status_code == 201
    token = c.post('/api/v1/auth/login', json={'username': 'mechanik', 'password': PASSWORD}).json()['token']
    return {'X-Jarvis-Key': token}


def test_default_is_disabled_and_frames_refuse(client):
    assert client.get('/api/v1/cameras', headers=OWNER).json() == {'enabled': False, 'refresh_ms': 1000, 'cameras': []}
    assert client.get('/api/v1/cameras/brama/frame.jpg', headers=OWNER).status_code == 404


def test_operator_sees_names_and_frames_but_not_stream_config(client):
    assert configure(client).status_code == 200
    auth = operator(client)
    listed = client.get('/api/v1/cameras', headers=auth).json()
    assert listed == {'enabled': True, 'refresh_ms': 1000, 'cameras': [{'id': 'brama', 'name': 'Wjazd'}]}
    assert 'nvr_ch1' not in str(listed)
    frame = client.get('/api/v1/cameras/brama/frame.jpg', headers=auth)
    assert frame.status_code == 200 and frame.content == JPEG and frame.headers['content-type'] == 'image/jpeg'
    assert frame.headers['cache-control'] == 'no-store'
    assert client.seen == ['http://127.0.0.1:1984/api/frame.jpeg?src=nvr_ch1']
    assert client.get('/api/v1/cameras/hala/frame.jpg', headers=auth).status_code == 404  # disabled camera
    assert client.get('/api/v1/cameras/config', headers=auth).status_code == 403
    assert client.get('/api/v1/cameras/brama/frame.jpg').status_code == 401


def test_bad_upstream_answers_are_not_relayed(client):
    config = {**CONFIG, 'cameras': [{'id': 'a', 'name': 'A', 'stream': 'broken'}, {'id': 'b', 'name': 'B', 'stream': 'html'}]}
    assert configure(client, config).status_code == 200
    assert client.get('/api/v1/cameras/a/frame.jpg', headers=OWNER).status_code == 502
    assert client.get('/api/v1/cameras/b/frame.jpg', headers=OWNER).status_code == 502


@pytest.mark.parametrize('config', [
    {**CONFIG, 'go2rtc_url': 'rtsp://10.0.0.5:554'},
    {**CONFIG, 'go2rtc_url': 'http://admin:pass@127.0.0.1:1984'},
    {**CONFIG, 'cameras': [{'id': 'Brama!', 'name': 'x', 'stream': 's'}]},
    {**CONFIG, 'cameras': [{'id': 'a', 'name': 'x', 'stream': 'rtsp://user:pass@cam'}]},
    {**CONFIG, 'cameras': [{'id': 'a', 'name': 'x', 'stream': 's'}, {'id': 'a', 'name': 'y', 'stream': 't'}]},
    {**CONFIG, 'unknown': True},
])
def test_invalid_configuration_is_rejected(client, config):
    assert configure(client, config).status_code == 422


def test_stale_revision_conflicts(client):
    assert configure(client).status_code == 200
    assert client.put('/api/v1/cameras/config', headers=OWNER, json={'revision': 0, 'config': CONFIG}).status_code == 409


def test_go2rtc_outside_allowlist_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv('JARVIS_NETWORK_ALLOWLIST', '127.0.0.0/8')
    with TestClient(create_app(tmp_path / 'c.db', KEY)) as c:
        assert configure(c, {**CONFIG, 'go2rtc_url': 'http://10.0.0.5:1984'}).status_code == 200
        assert c.get('/api/v1/cameras/brama/frame.jpg', headers=OWNER).status_code == 403


def test_csp_allows_blob_images_for_previews(client):
    assert "img-src 'self' blob: data:" in client.get('/api/v1/cameras', headers=OWNER).headers['content-security-policy']
