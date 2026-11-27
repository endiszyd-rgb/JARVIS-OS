"""Built-in go2rtc: cameras configured in the panel (Setti/Tuya by Device ID, RTSP), generated config, process control."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from jarvis import cameras, gate, go2rtc
from jarvis.main import create_app

KEY = 'camera-builtin-owner-key-32-chars-x'
OWNER = {'X-Jarvis-Key': KEY}
JPEG = b'\xff\xd8\xff\xe0' + b'synthetic-frame' + b'\xff\xd9'
RTSP = 'rtsp://admin:Synthetic-RTSP-pass@192.168.1.64:554/Streaming/Channels/102'
TUYA = {'access_id': 'abcdef123', 'access_secret': 'Synthetic-cloud-secret', 'device_id': 'gatedevice01'}


class FakeProcess:
    def __init__(self, args, **kwargs):
        self.args, self.kwargs, self.alive = args, kwargs, True
        self.pid = 40000 + len(FakeProcess.started)
        FakeProcess.started.append(self)

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.alive = False

    def kill(self):
        self.alive = False


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    FakeProcess.started = []
    tools = tmp_path / 'tools'
    tools.mkdir()
    (tools / 'go2rtc.exe').write_bytes(b'fake')
    (tools / 'ffmpeg.exe').write_bytes(b'fake')
    monkeypatch.setenv('JARVIS_GO2RTC_BIN', str(tools / 'go2rtc.exe'))
    monkeypatch.setenv('JARVIS_FFMPEG_BIN', str(tools / 'ffmpeg.exe'))
    monkeypatch.setattr(go2rtc.subprocess, 'Popen', FakeProcess)
    return tmp_path


@pytest.fixture
def client(runtime):
    app = create_app(runtime / 'data' / 'jarvis.db', KEY)
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, headers={'content-type': 'image/jpeg'}, content=JPEG)
    app.state.camera_transport = httpx.MockTransport(handler)
    with TestClient(app, headers=OWNER) as c:
        c.seen, c.data = seen, runtime / 'data'
        yield c


def put(c, path, config):
    revision = c.get(path).json()['revision']
    return c.put(path, json={'revision': revision, 'config': config})


def test_render_builds_tuya_and_rtsp_sources_and_listens_on_loopback_only():
    config = cameras.CameraConfig(mode='builtin', enabled=True, cameras=[
        {'id': 'zewnetrzna', 'name': 'Zewnętrzna', 'source': 'tuya', 'device_id': 'cam1', 'uid': 'eu123'},
        {'id': 'hala', 'name': 'Hala', 'source': 'rtsp', 'rtsp_url': RTSP},
        {'id': 'bez-uid', 'name': 'X', 'source': 'tuya', 'device_id': 'cam2'}])
    text, problems = go2rtc.render(config, gate.TuyaDriver(**TUYA), 'C:/JARVIS/tools/ffmpeg.exe')
    document = json.loads(text)  # JSON is valid YAML for go2rtc
    assert document['api']['listen'] == '127.0.0.1:1984' and document['rtsp'] == {'listen': ''}
    assert document['ffmpeg']['bin'] == 'C:/JARVIS/tools/ffmpeg.exe'
    assert document['streams']['hala'] == RTSP
    assert document['streams']['zewnetrzna'] == ('tuya://openapi.tuyaeu.com?device_id=cam1&uid=eu123&client_id=abcdef123'
                                                 '&client_secret=Synthetic-cloud-secret&resolution=sd')
    assert 'bez-uid' not in document['streams'] and any('UID' in item for item in problems)
    _, missing = go2rtc.render(config, None)
    assert any('chmury Tuya' in item for item in missing)


@pytest.mark.parametrize('camera', [
    {'id': 'a', 'name': 'A', 'source': 'rtsp', 'rtsp_url': 'http://192.168.1.5/'},
    {'id': 'a', 'name': 'A', 'source': 'rtsp', 'rtsp_url': 'rtsp://x@192.168.1.5/a b'},
    {'id': 'a', 'name': 'A', 'source': 'tuya', 'device_id': 'bad id'},
    {'id': 'a', 'name': 'A', 'source': 'go2rtc', 'stream': 'nvr'}])
def test_builtin_mode_rejects_bad_sources(camera):
    with pytest.raises(ValueError):
        cameras.CameraConfig(mode='builtin', cameras=[camera])


def test_manager_starts_once_restarts_on_change_and_stops(runtime):
    manager = go2rtc.Manager.from_env(runtime / 'data')
    config = cameras.CameraConfig(mode='builtin', enabled=True, cameras=[{'id': 'hala', 'name': 'Hala', 'source': 'rtsp', 'rtsp_url': RTSP}])
    status = manager.apply(config)
    assert status['available'] and status['running'] and len(FakeProcess.started) == 1
    first = FakeProcess.started[0]
    assert first.args[1:] == ['-config', str(runtime / 'data' / 'go2rtc' / 'go2rtc.yaml')]
    manager.apply(config)
    assert len(FakeProcess.started) == 1  # unchanged config: no restart
    changed = config.model_copy(update={'cameras': [config.cameras[0].model_copy(update={'resolution': 'hd', 'rtsp_url': RTSP + 'x'})]})
    manager.apply(changed)
    assert len(FakeProcess.started) == 2 and first.alive is False
    assert manager.apply(changed.model_copy(update={'enabled': False}))['running'] is False
    assert FakeProcess.started[1].alive is False


def test_manager_without_binary_reports_not_installed(tmp_path):
    manager = go2rtc.Manager(tmp_path, None)
    config = cameras.CameraConfig(mode='builtin', enabled=True, cameras=[{'id': 'hala', 'name': 'Hala', 'source': 'rtsp', 'rtsp_url': RTSP}])
    assert manager.apply(config) == {'available': False, 'running': False, 'ffmpeg': False, 'problems': [], 'error': 'go2rtc nie jest zainstalowany'}


def test_panel_cameras_run_through_builtin_go2rtc_without_leaking_passwords(client):
    read = client.get('/api/v1/cameras/config').json()
    assert read['config']['mode'] == 'builtin' and read['builtin']['available'] is True and read['builtin']['running'] is False
    saved = put(client, '/api/v1/cameras/config', {'enabled': True, 'mode': 'builtin', 'cameras': [
        {'id': 'hala', 'name': 'Hala', 'source': 'rtsp', 'rtsp_url': RTSP}]})
    assert saved.status_code == 200, saved.text
    assert saved.json()['builtin']['running'] is True
    shown = client.get('/api/v1/cameras/config')
    assert 'Synthetic-RTSP-pass' not in shown.text
    camera = shown.json()['config']['cameras'][0]
    assert camera['rtsp_url'] == cameras.SECRET_MASK and camera['rtsp_set'] is True
    again = put(client, '/api/v1/cameras/config', shown.json()['config'])  # masked URL keeps the stored one
    assert again.status_code == 200 and len(FakeProcess.started) == 1
    assert RTSP in (client.data / 'go2rtc' / 'go2rtc.yaml').read_text(encoding='utf-8')
    frame = client.get('/api/v1/cameras/hala/frame.jpg')
    assert frame.status_code == 200 and frame.content == JPEG
    assert client.seen[-1] == 'http://127.0.0.1:1984/api/frame.jpeg?src=hala'
    assert put(client, '/api/v1/cameras/config', {'enabled': True, 'mode': 'builtin', 'cameras': [
        {'id': 'x', 'name': 'X', 'source': 'go2rtc', 'stream': 'nvr'}]}).status_code == 422


def test_tuya_camera_uid_is_read_from_the_saved_cloud_project_and_restarts_go2rtc(client, monkeypatch):
    assert client.post('/api/v1/cameras/tuya-info', json={'device_id': 'cam1'}).status_code == 409
    assert put(client, '/api/v1/devices/gate/config', {'driver': 'tuya_cloud', 'tuya': TUYA}).status_code == 200

    async def fake_token(self):
        return 'token'

    async def fake_request(self, method, path, body='', token=''):
        assert (method, path) == ('GET', '/v1.0/devices/cam1')
        return {'uid': 'eu1700000000abc', 'name': 'Kamera zewnętrzna', 'category': 'sp', 'online': True, 'local_key': 'not-returned'}
    monkeypatch.setattr(gate.TuyaCloud, '_token', fake_token)
    monkeypatch.setattr(gate.TuyaCloud, '_request', fake_request)
    info = client.post('/api/v1/cameras/tuya-info', json={'device_id': 'cam1'})
    assert info.json() == {'uid': 'eu1700000000abc', 'name': 'Kamera zewnętrzna', 'category': 'sp', 'online': True}
    saved = put(client, '/api/v1/cameras/config', {'enabled': True, 'mode': 'builtin', 'cameras': [
        {'id': 'zewnetrzna', 'name': 'Zewnętrzna', 'source': 'tuya', 'device_id': 'cam1', 'uid': 'eu1700000000abc'}]})
    assert saved.status_code == 200 and saved.json()['builtin']['problems'] == []
    assert 'Synthetic-cloud-secret' not in saved.text
    text = (client.data / 'go2rtc' / 'go2rtc.yaml').read_text(encoding='utf-8')
    assert 'device_id=cam1&uid=eu1700000000abc' in text
    # a new Tuya secret in the gate settings rewrites the camera config too
    put(client, '/api/v1/devices/gate/config', {'driver': 'tuya_cloud', 'tuya': {**TUYA, 'access_secret': 'Rotated-secret'}})
    assert 'Rotated-secret' in (client.data / 'go2rtc' / 'go2rtc.yaml').read_text(encoding='utf-8')
    assert len(FakeProcess.started) == 2 and FakeProcess.started[0].alive is False


def test_go2rtc_left_by_a_killed_jarvis_is_closed_but_other_processes_are_not(runtime, monkeypatch):
    folder = runtime / 'data' / 'go2rtc'
    folder.mkdir(parents=True)
    killed = []
    monkeypatch.setattr(go2rtc.os, 'kill', lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(go2rtc.time, 'sleep', lambda seconds: None)
    config = cameras.CameraConfig(mode='builtin', enabled=True, cameras=[{'id': 'hala', 'name': 'Hala', 'source': 'rtsp', 'rtsp_url': RTSP}])
    (folder / 'go2rtc.pid').write_text('31337')
    monkeypatch.setattr(go2rtc.Manager, '_is_go2rtc', staticmethod(lambda pid: pid == 31337))
    manager = go2rtc.Manager.from_env(runtime / 'data')
    manager.apply(config)
    assert killed == [31337] and (folder / 'go2rtc.pid').read_text() == str(FakeProcess.started[-1].pid)
    manager.stop()
    assert not (folder / 'go2rtc.pid').exists()
    (folder / 'go2rtc.pid').write_text('4242')  # a reused PID that is not go2rtc
    go2rtc.Manager.from_env(runtime / 'data').apply(config)
    assert killed == [31337]
