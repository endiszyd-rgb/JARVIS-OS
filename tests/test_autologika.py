import asyncio
import httpx
import pytest
from fastapi import HTTPException
from jarvis.autologika import AutoLogikaReadOnly


def test_readonly_routes_and_header():
    requests=[]
    def handler(req):
        requests.append(req)
        return httpx.Response(200,json=[] if req.url.path=='/api/orders' else {'order':{'id':1}})
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
