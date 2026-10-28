"""Query parameters must preserve the approved origin and DNS/IP pinning."""
import asyncio
import socket
import httpx
import pytest
from jarvis import network


def test_get_query_reaches_only_the_pinned_approved_origin():
    async def scenario():
        seen, resolved = [], []
        def resolver(host, port, *args):
            resolved.append((host, port))
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', port))]
        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={'ok': True})
        transport = network.PinnedTransport('http://approved.test:8765', resolver=resolver,
                                            inner=httpx.MockTransport(handler))
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get('http://approved.test:8765/read', params={'item': 7, 'url': 'https://evil.test/private'})
            assert response.status_code == 200
            with pytest.raises(network.NetworkDenied):
                await client.get('http://evil.test:8765/read?item=7')
        assert resolved == [('approved.test', 8765)] and len(seen) == 1
        assert seen[0].url.host == '127.0.0.1' and seen[0].headers['Host'] == 'approved.test:8765'
        assert dict(seen[0].url.params) == {'item': '7', 'url': 'https://evil.test/private'}
    asyncio.run(scenario())


def test_configured_origin_with_query_remains_invalid():
    with pytest.raises(network.NetworkDenied):
        network.PinnedTransport('http://approved.test/read?item=7')


def test_query_cannot_bypass_destination_ip_allowlist():
    async def scenario():
        def resolver(host, port, *args):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('203.0.113.9', port))]
        transport = network.PinnedTransport('http://approved.test', resolver=resolver,
            inner=httpx.MockTransport(lambda request: pytest.fail('Unapproved IP must never receive a request')))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(network.NetworkDenied):
                await client.get('http://approved.test/read?item=7')
    asyncio.run(scenario())
