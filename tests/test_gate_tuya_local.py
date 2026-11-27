"""Setti/Tuya gate on the local network (no cloud): validation, masking, protocol fallback, API helpers."""
import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from jarvis import gate
from jarvis.main import create_app

KEY = 'unit-test-key-32-characters-long'
LOCAL = {'device_id': 'bf98f7fda6623b20cfn3z1', 'local_key': 'abcdef0123456789', 'address': '192.168.1.50'}


class FakeDevice:
    """Stands in for tinytuya.Device; records calls and answers per protocol version."""
    calls = []
    working_version = 3.4
    dps = {'1': False, '101': 'closed'}

    def __init__(self, driver, version):
        self.version = version
        self.driver = driver

    def _ok(self):
        return self.version == FakeDevice.working_version and self.driver.local_key == LOCAL['local_key']

    def set_value(self, dp, value):
        FakeDevice.calls.append(('set', self.version, dp, value))
        if not self._ok():
            return {'Error': 'Check device key or version', 'Err': '914'}
        FakeDevice.dps[str(dp)] = value
        return {'dps': {str(dp): value}}

    def status(self):
        FakeDevice.calls.append(('status', self.version))
        if not self._ok():
            return {'Error': 'Check device key or version', 'Err': '914'}
        return {'dps': dict(FakeDevice.dps)}


@pytest.fixture(autouse=True)
def fake_devices(monkeypatch):
    FakeDevice.calls = []
    FakeDevice.working_version = 3.4
    FakeDevice.dps = {'1': False, '101': 'closed'}
    monkeypatch.setattr(gate.TuyaLocal, '_device', lambda self, version: FakeDevice(self.driver, version))


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / 'gate.db', KEY), headers={'X-Jarvis-Key': KEY}) as c:
        yield c


def put_config(client, config):
    revision = client.get('/api/v1/devices/gate/config').json()['revision']
    return client.put('/api/v1/devices/gate/config', json={'revision': revision, 'config': config})


@pytest.mark.parametrize('address', ['8.8.8.8', '127.0.0.1', '169.254.1.1', '0.0.0.0', '224.0.0.1', 'brama.local', '192.168.1.300'])
def test_only_lan_addresses_are_accepted(address):
    with pytest.raises(ValueError):
        gate.TuyaLocalDriver(**{**LOCAL, 'address': address})
    assert gate.TuyaLocalDriver(**{**LOCAL, 'address': ' 10.0.0.7 '}).address == '10.0.0.7'


def test_auto_protocol_tries_versions_and_remembers_the_working_one():
    config = gate.GateConfig(driver='tuya_local', tuya_local=LOCAL)
    driver = gate.TuyaLocal(config)
    result = asyncio.run(driver.command('open', {}))
    assert result == {'state': 'opening', 'external_request_sent': True}
    assert [call[:2] for call in FakeDevice.calls] == [('set', 3.3), ('set', 3.4)]
    assert driver.version == 3.4
    FakeDevice.calls = []
    asyncio.run(driver.command('close', {}))
    assert FakeDevice.calls == [('set', 3.4, 1, False)]  # no more probing


def test_wrong_key_reports_a_polish_hint_and_pulse_gate_reuses_open():
    config = gate.GateConfig(driver='tuya_local', pulse=True, tuya_local={**LOCAL, 'local_key': 'wrongwrongwrong0', 'version': '3.3'})
    with pytest.raises(HTTPException) as error:
        asyncio.run(gate.TuyaLocal(config).command('open', {}))
    assert error.value.status_code == 502 and 'zły klucz lokalny' in error.value.detail
    FakeDevice.working_version = 3.3
    ok = gate.GateConfig(driver='tuya_local', pulse=True, tuya_local={**LOCAL, 'version': '3.3'})
    asyncio.run(gate.TuyaLocal(ok).command('close', {}))
    assert FakeDevice.calls[-1] == ('set', 3.3, 1, True)


def test_status_reads_the_position_sensor():
    config = gate.GateConfig(driver='tuya_local', tuya_local={**LOCAL, 'status_dp': 101})
    FakeDevice.dps['101'] = 'open'
    result = asyncio.run(gate.TuyaLocal(config).status({'state': 'unknown'}))
    assert result['state'] == 'open' and result['protocol'] == 3.4 and result['values']['101'] == 'open'


def test_missing_key_and_stop_are_explained():
    config = gate.GateConfig(driver='tuya_local', tuya_local={**LOCAL, 'local_key': ''})
    with pytest.raises(HTTPException) as error:
        asyncio.run(gate.TuyaLocal(config).command('open', {}))
    assert error.value.status_code == 503
    with pytest.raises(HTTPException) as error:
        asyncio.run(gate.TuyaLocal(gate.GateConfig(driver='tuya_local', tuya_local=LOCAL)).command('stop', {}))
    assert error.value.status_code == 501


def test_config_masks_the_local_key_and_commands_run_through_the_api(client):
    saved = put_config(client, {'driver': 'tuya_local', 'name': 'Brama', 'tuya_local': LOCAL})
    assert saved.status_code == 200, saved.text
    config = client.get('/api/v1/devices/gate/config').json()['config']
    assert config['tuya_local']['local_key'] == gate.SECRET_MASK and config['tuya_local']['local_key_set'] is True
    assert LOCAL['local_key'] not in client.get('/api/v1/devices/gate/config').text
    resaved = put_config(client, config)  # masked key in an update keeps the stored one
    assert resaved.status_code == 200
    opened = client.post('/api/v1/devices/gate/command', json={'action': 'open'})
    assert opened.status_code == 200 and opened.json()['external_request_sent'] is True
    assert FakeDevice.calls[-1] == ('set', 3.4, 1, True)
    assert client.post('/api/v1/devices/gate/test').json()['status'] == 'reachable'
    assert put_config(client, {'driver': 'tuya_local', 'tuya_local': {**LOCAL, 'address': '8.8.8.8'}}).status_code == 422


def test_scan_endpoint_lists_lan_devices_only(client, monkeypatch):
    class FakeTinytuya:
        @staticmethod
        def deviceScan(**kwargs):
            assert kwargs['poll'] is False and kwargs['verbose'] is False
            return {'192.168.1.50': {'ip': '192.168.1.50', 'gwId': 'bf98f7fda6623b20cfn3z1', 'version': '3.4'},
                    '8.8.8.8': {'ip': '8.8.8.8', 'gwId': 'public', 'version': '3.3'},
                    '192.168.1.60': {'ip': '192.168.1.60', 'gwId': 'bad id!', 'version': '3.3'}}
    monkeypatch.setitem(__import__('sys').modules, 'tinytuya', FakeTinytuya)
    response = client.post('/api/v1/devices/gate/tuya-local/scan')
    assert response.status_code == 200
    assert response.json() == {'devices': [{'address': '192.168.1.50', 'device_id': 'bf98f7fda6623b20cfn3z1', 'version': '3.4'}]}


def test_local_key_is_read_once_from_the_saved_cloud_project(client, monkeypatch):
    assert client.post('/api/v1/devices/gate/tuya-local/key', json={'device_id': LOCAL['device_id']}).status_code == 409
    put_config(client, {'driver': 'tuya_cloud', 'tuya': {'access_id': 'abc', 'access_secret': 'cloudsecret', 'device_id': LOCAL['device_id']}})

    async def fake_token(self):
        return 'token'

    async def fake_request(self, method, path, body='', token=''):
        assert (method, path, token) == ('GET', '/v1.0/devices/' + LOCAL['device_id'], 'token')
        return {'local_key': LOCAL['local_key'], 'name': 'Sterownik bramy', 'ip': '203.0.113.5'}
    monkeypatch.setattr(gate.TuyaCloud, '_token', fake_token)
    monkeypatch.setattr(gate.TuyaCloud, '_request', fake_request)
    response = client.post('/api/v1/devices/gate/tuya-local/key', json={'device_id': LOCAL['device_id']})
    assert response.status_code == 200 and response.json() == {'local_key': LOCAL['local_key'], 'name': 'Sterownik bramy'}
    assert client.post('/api/v1/devices/gate/tuya-local/key', json={'device_id': 'bad id'}).status_code == 422


def test_one_button_controller_sends_the_close_signal_for_open():
    config = gate.GateConfig(driver='tuya_local', tuya_local={**LOCAL, 'version': '3.4', 'open_value': False, 'close_value': False})
    driver = gate.TuyaLocal(config)
    asyncio.run(driver.command('open', {}))
    asyncio.run(driver.command('close', {}))
    assert FakeDevice.calls == [('set', 3.4, 1, False), ('set', 3.4, 1, False)]


# ---------------------------------------------------------------- one button "Brama" (impulse controller)

def test_one_button_gate_turns_open_and_close_into_one_impulse(client):
    put_config(client, {'driver': 'tuya_local', 'pulse': True, 'cooldown_seconds': 0,
                        'tuya_local': {**LOCAL, 'version': '3.4', 'open_value': False, 'close_value': False}})
    for action in ('toggle', 'open', 'close'):
        response = client.post('/api/v1/devices/gate/command', json={'action': action})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['action'] == 'toggle' and body['gate']['state'] == 'impulse' and body['gate']['state_label'] == 'ruszona'
    assert FakeDevice.calls == [('set', 3.4, 1, False)] * 3  # always the configured "Brama" signal


def test_voice_jarvis_brama_sends_the_impulse(client):
    put_config(client, {'driver': 'tuya_local', 'pulse': True, 'tuya_local': {**LOCAL, 'version': '3.4', 'open_value': False}})
    reply = client.post('/api/v1/chat', json={'message': 'Jarvis, brama', 'input_mode': 'voice', 'model': 'demo'}).json()
    assert reply['model'] == 'parser' and reply['reply'].startswith('Uruchamiam:') and reply['device']['action'] == 'toggle'
    assert FakeDevice.calls == [('set', 3.4, 1, False)]


def test_toggle_on_a_two_button_gate_picks_the_next_move(client):
    put_config(client, {'driver': 'simulator', 'cooldown_seconds': 0})
    first = client.post('/api/v1/devices/gate/command', json={'action': 'toggle'}).json()
    second = client.post('/api/v1/devices/gate/command', json={'action': 'toggle'}).json()
    assert (first['action'], first['gate']['state']) == ('open', 'opening')
    assert (second['action'], second['gate']['state']) == ('close', 'closing')


def test_one_button_confirmation_asks_to_start_the_gate(client):
    put_config(client, {'driver': 'tuya_local', 'pulse': True, 'require_confirmation': True, 'tuya_local': {**LOCAL, 'version': '3.4'}})
    asked = client.post('/api/v1/devices/gate/command', json={'action': 'open'}).json()
    assert asked['status'] == 'confirmation_required' and asked['prompt'] == 'Uruchomić bramę?' and FakeDevice.calls == []
    done = client.post('/api/v1/devices/gate/command', json={'action': 'toggle', 'confirm_token': asked['confirm_token']}).json()
    assert done['status'] == 'executed' and len(FakeDevice.calls) == 1


@pytest.mark.parametrize('text', ['Jarvis, brama', 'jarvis brama!', 'brama', 'rusz bramę', 'Jarvis uruchom bramę', 'brama proszę'])
def test_brama_phrases_are_the_toggle_command(text):
    from jarvis import intents
    assert intents.parse(text).action == 'toggle'


@pytest.mark.parametrize('text', ['brama jest zepsuta', 'ile kosztuje brama', 'kup bramę'])
def test_other_sentences_about_the_gate_are_not_commands(text):
    from jarvis import intents
    assert intents.parse(text) is None
