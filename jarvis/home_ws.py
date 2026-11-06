"""Bounded one-shot HA WebSocket reads; no service calls or subscriptions."""
import asyncio
import socket
import threading
from fastapi import HTTPException

import aiohttp
from aiohttp.abc import AbstractResolver

from . import home, network

DEADLINE = 20
SLOTS = threading.BoundedSemaphore(4)


class FixedResolver(AbstractResolver):
    def __init__(self, host, port, ips):
        self.host, self.port, self.ips = host, port, ips

    async def resolve(self, host, port=0, family=socket.AF_INET):
        if (host.lower(), port) != (self.host, self.port):
            raise network.NetworkDenied('Cross-origin connection blocked')
        return [{'hostname': host, 'host': ip, 'port': port,
                 'family': socket.AF_INET6 if ':' in ip else socket.AF_INET,
                 'proto': socket.IPPROTO_TCP, 'flags': socket.AI_NUMERICHOST} for ip in self.ips]

    async def close(self):
        pass


async def _states():
    url, token, allowed = home.config()
    scheme, host, port = network.validate_origin(url)
    async with asyncio.timeout(DEADLINE):
        records = await asyncio.to_thread(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
        ips = list(dict.fromkeys(row[4][0] for row in records))
        nets = network.allowed_networks()
        if not ips or any(not network.permitted(ip, nets) for ip in ips):
            raise network.NetworkDenied('Destination outside allowlist')
        # aiohttp bypasses its resolver for numeric hosts; these too were checked above.
        connector = aiohttp.TCPConnector(resolver=FixedResolver(host, port, ips), use_dns_cache=False, limit=1)
        trace = aiohttp.TraceConfig()

        async def deny_redirect(*args):
            raise network.NetworkDenied('WebSocket redirects are forbidden')

        trace.on_request_redirect.append(deny_redirect)
        async with aiohttp.ClientSession(connector=connector, trust_env=False,
                                        cookie_jar=aiohttp.DummyCookieJar(), trace_configs=[trace]) as client:
            ws_url = ('wss' if scheme == 'https' else 'ws') + url[len(scheme):] + '/api/websocket'
            async with client.ws_connect(ws_url, max_msg_size=1024*1024,
                                         timeout=aiohttp.ClientWSTimeout(ws_receive=5, ws_close=1)) as ws:
                async def receive():
                    data = await ws.receive_json()
                    if not isinstance(data, dict):
                        raise ValueError('Invalid WebSocket envelope')
                    return data

                if (await receive()).get('type') != 'auth_required':
                    raise ValueError('Invalid auth challenge')
                await ws.send_json({'type': 'auth', 'access_token': token})
                if (await receive()).get('type') != 'auth_ok':
                    raise ValueError('Authentication failed')
                await ws.send_json({'id': 1, 'type': 'get_states'})
                result = await receive()
                if result.get('type') != 'result' or type(result.get('id')) is not int or result['id'] != 1 or result.get('success') is not True:
                    raise ValueError('Invalid command result')
                # Recheck local config after I/O; changes never return stale authorization.
                if home.config() != (url, token, allowed):
                    raise ValueError('Configuration changed during request')
                return home.filtered(result.get('result'), allowed)


async def states():
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(429, 'Home Assistant read capacity reached')
    try:
        return await _states()
    finally:
        SLOTS.release()
