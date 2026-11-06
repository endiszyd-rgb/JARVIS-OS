import asyncio
import socket

from aiohttp import web
import pytest
from fastapi.testclient import TestClient

from jarvis import home, home_ws, network
from jarvis.main import create_app


def configure(monkeypatch, url):
    for name, value in {'HA_READONLY_ENABLED': 'true', 'HA_URL': url,
                        'HA_TOKEN': 'synthetic-ha-secret', 'HA_ALLOWED_ENTITIES': 'sensor.allowed',
                        'JARVIS_NETWORK_ALLOWLIST': '127.0.0.0/8,::1/128'}.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize('case', ['ok', 'auth_invalid', 'wrong_id', 'error', 'malformed', 'oversized', 'redirect', 'slow'])
def test_real_websocket_protocol_and_cleanup(monkeypatch, case):
    async def scenario():
        commands = []
        trap = []
        async def handler(request):
            if case == 'redirect':
                raise web.HTTPFound('/trap')
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            try:
                if case == 'slow':
                    await asyncio.sleep(.1)
                    return ws
                await ws.send_json({'type': 'auth_required'})
                commands.append(await ws.receive_json())
                await ws.send_json({'type': 'auth_invalid' if case == 'auth_invalid' else 'auth_ok'})
                if case == 'auth_invalid':
                    return ws
                commands.append(await ws.receive_json())
                if case == 'malformed':
                    await ws.send_str('not JSON')
                elif case == 'oversized':
                    await ws.send_str('x'*(1024*1024+1))
                else:
                    await ws.send_json({'id': 2 if case == 'wrong_id' else 1, 'type': 'result',
                                        'success': case != 'error', 'result': [
                        {'entity_id': 'sensor.allowed', 'state': '21', 'attributes': {'friendly_name': 'Room', 'private': 'not exported'}},
                        {'entity_id': 'person.private', 'state': 'home', 'attributes': {}},
                    ]})
                await ws.receive()
                return ws
            finally:
                await ws.close()
        async def trap_handler(request):
            trap.append(True)
            return web.Response()
        app = web.Application()
        app.router.add_get('/api/websocket', handler)
        app.router.add_get('/trap', trap_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        await web.SockSite(runner, sock).start()
        configure(monkeypatch, f'http://localhost:{port}')
        if case == 'slow':
            monkeypatch.setattr(home_ws, 'DEADLINE', .02)
        try:
            if case == 'ok':
                result = await home_ws.states()
                assert result['controls_enabled'] is False
                assert result['states'] == [{'entity_id': 'sensor.allowed', 'state': '21', 'attributes': {'friendly_name': 'Room'}}]
                assert commands == [{'type': 'auth', 'access_token': 'synthetic-ha-secret'}, {'id': 1, 'type': 'get_states'}]
            else:
                with pytest.raises(Exception):
                    await home_ws.states()
            assert trap == []
        finally:
            await runner.cleanup()
    asyncio.run(scenario())


def test_destination_denied_before_any_connect(monkeypatch):
    configure(monkeypatch, 'http://127.0.0.1:8123')
    monkeypatch.setenv('JARVIS_NETWORK_ALLOWLIST', '10.0.0.0/8')
    with pytest.raises(network.NetworkDenied):
        asyncio.run(home_ws.states())


def test_cancel_releases_capacity(monkeypatch):
    async def scenario():
        entered = asyncio.Event()
        async def wait():
            entered.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(home_ws, '_states', wait)
        task = asyncio.create_task(home_ws.states())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(4):
            assert home_ws.SLOTS.acquire(blocking=False)
        for _ in range(4):
            home_ws.SLOTS.release()
    asyncio.run(scenario())


def test_filtered_duplicates_and_private_attributes():
    with pytest.raises(ValueError):
        home.filtered([{'entity_id': 'sensor.a', 'state': 'x'}]*2, {'sensor.a'})
    assert home.filtered([{'entity_id': 'sensor.a', 'state': 'x', 'attributes': {'access_token': 'secret'}}], {'sensor.a'})['states'][0]['attributes'] == {}


def test_api_auth_and_redacted_transport_failure(tmp_path, monkeypatch):
    client = TestClient(create_app(tmp_path/'core.db', 'a'*32))
    assert client.get('/api/v1/home/websocket/states').status_code == 401
    async def fail():
        raise ValueError('synthetic-ha-secret')
    monkeypatch.setattr(home_ws, 'states', fail)
    response = client.get('/api/v1/home/websocket/states', headers={'X-Jarvis-Key': 'a'*32})
    assert response.status_code == 502 and 'synthetic-ha-secret' not in response.text


def test_scoped_token_rechecked_after_transport(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path/'core.db'
    client = TestClient(create_app(path, 'a'*32), headers={'X-Jarvis-Key': 'a'*32})
    issued = client.post('/api/security/tokens', json={'name': 'ha-reader', 'scopes': ['home:read']}).json()
    headers = {'X-Jarvis-Key': issued['token']}
    async def read():
        return home.filtered([{'entity_id': 'sensor.allowed', 'state': 'private'}], {'sensor.allowed'})
    monkeypatch.setattr(home_ws, 'states', read)
    assert client.get('/api/v1/home/websocket/states', headers=headers).status_code == 200
    async def revoked_read():
        with sqlite3.connect(path) as db:
            db.execute('UPDATE access_tokens SET expires=0 WHERE id=?', (issued['id'],))
        return await read()
    monkeypatch.setattr(home_ws, 'states', revoked_read)
    result = client.get('/api/v1/home/websocket/states', headers=headers)
    assert result.status_code == 401 and 'private' not in result.text
