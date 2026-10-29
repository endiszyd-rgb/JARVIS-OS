import asyncio
import httpx
import pytest
from fastapi import HTTPException
from jarvis.autologika import AutoLogikaReadOnly


def test_readonly_routes_and_header():
    requests=[]
    def handler(req):
        requests.append(req)
        return httpx.Response(200,json=[] if req.url.path=='/api/orders' else {'order':{'id':1},'notes':{},'diag':{},'parts':[],'payments':[]})
    adapter=AutoLogikaReadOnly('http://localhost:8787','123456',httpx.MockTransport(handler))
    assert asyncio.run(adapter.read())['mode']=='live_readonly'
    assert asyncio.run(adapter.read(1))['data']['order']['id']==1
    assert [r.url.path for r in requests]==['/api/orders','/api/order/1']
    assert all(r.method=='GET' and r.headers['X-Autologika-Pin']=='123456' for r in requests)


def test_redirect_never_leaks_pin():
    requests=[]
    def handler(req):
        requests.append(req)
        return httpx.Response(302,headers={'Location':'http://other.invalid'})
    adapter=AutoLogikaReadOnly('http://localhost:8787','123456',httpx.MockTransport(handler))
    with pytest.raises(HTTPException):
        asyncio.run(adapter.read())
    assert len(requests)==1


def test_bad_origin():
    with pytest.raises(ValueError):
        AutoLogikaReadOnly('http://user:pass@localhost','123456')


def test_disabled_without_config(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from jarvis.main import create_app
    monkeypatch.delenv('AUTOLOGIKA_READONLY_ENABLED',raising=False)
    c=TestClient(create_app(tmp_path/'x.db','a'*32),headers={'X-Jarvis-Key':'a'*32})
    assert c.get('/api/autologika/readonly/orders').status_code==503
    assert c.get('/api/autologika/readonly/orders/0').status_code==422

@pytest.mark.parametrize('data,order_id', [
    ({},None), ([{'id':True}],None), ([{'id':1},{'id':1}],None),
    ([{'id':n+1} for n in range(101)],None),
    ({'order':{'id':2},'notes':{},'diag':{},'parts':[],'payments':[]},1),
    ({'order':{'id':1},'notes':{},'diag':{},'parts':[{'order_id':2}],'payments':[]},1),
    ({'order':{'id':1}},1),
])
def test_contract_rejects_invalid_or_cross_order_data(data,order_id):
    adapter=AutoLogikaReadOnly('http://localhost:8787','123456',httpx.MockTransport(lambda req:httpx.Response(200,json=data)))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(adapter.read(order_id))
    assert exc.value.status_code==502
    assert '123456' not in exc.value.detail


def test_response_size_is_bounded_without_length(monkeypatch):
    import jarvis.autologika as module
    monkeypatch.setattr(module,'MAX_RESPONSE_BYTES',16)
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'['+b' '*16
            raise AssertionError('Must stop reading after size limit')
    adapter=AutoLogikaReadOnly('http://localhost:8787','123456',httpx.MockTransport(lambda req:httpx.Response(200,stream=Body())))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(adapter.read())
    assert exc.value.status_code==502


def test_total_deadline_stops_slow_stream(monkeypatch):
    import jarvis.autologika as module
    monkeypatch.setattr(module,'REQUEST_DEADLINE',.01)
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(1)
            yield b'[]'
    adapter=AutoLogikaReadOnly('http://localhost:8787','123456',httpx.MockTransport(lambda req:httpx.Response(200,stream=Body())))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(adapter.read())
    assert exc.value.status_code==502


@pytest.mark.parametrize('status',[301,401,404,500])
def test_upstream_errors_never_echo_body(status):
    adapter=AutoLogikaReadOnly('http://localhost:8787','123456',httpx.MockTransport(lambda req:httpx.Response(status,text='private customer 123456')))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(adapter.read())
    assert 'private' not in exc.value.detail and '123456' not in exc.value.detail


def test_capabilities_require_auth_and_do_not_probe(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from jarvis.main import create_app
    monkeypatch.setenv('AUTOLOGIKA_URL','http://secret-host.invalid')
    monkeypatch.setenv('AUTOLOGIKA_PIN','876543')
    c=TestClient(create_app(tmp_path/'core.db','a'*32))
    assert c.get('/api/v1/autologika/capabilities').status_code==401
    result=c.get('/api/v1/autologika/capabilities',headers={'X-Jarvis-Key':'a'*32})
    assert result.status_code==200
    assert result.json()['http_writes']==[]
    assert result.json()['connection_verified'] is False
    assert '876543' not in result.text and 'secret-host' not in result.text
