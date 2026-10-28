"""Outbound HTTP pinned to an operator-approved origin and explicit IP ranges.
DNS resolution is followed by connection to the validated IP (no DNS rebind gap).
"""
import asyncio
import ipaddress
import os
import socket
from urllib.parse import urlsplit
import httpx

class NetworkDenied(ValueError):
    pass


def validate_origin(value: str, allow_path=False):
    p = urlsplit(value)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise NetworkDenied('Use an http(s) URL without credentials, query or fragment')
    if not allow_path and p.path not in ('','/'):
        raise NetworkDenied('Base URL must contain only an origin')
    if '%' in p.netloc or '\\' in value:
        raise NetworkDenied('Invalid host')
    try:
        port = p.port or (443 if p.scheme=='https' else 80)
    except ValueError as exc:
        raise NetworkDenied('Invalid port') from exc
    return (p.scheme, p.hostname.lower(), port)


def allowed_networks():
    try:
        return [ipaddress.ip_network(x.strip()) for x in os.getenv('JARVIS_NETWORK_ALLOWLIST','127.0.0.0/8,::1/128').split(',') if x.strip()]
    except ValueError:
        raise NetworkDenied('Invalid JARVIS_NETWORK_ALLOWLIST')


def permitted(ip, networks):
    addr=ipaddress.ip_address(ip)
    effective=addr.ipv4_mapped if isinstance(addr,ipaddress.IPv6Address) and addr.ipv4_mapped else addr
    if effective.is_link_local or effective.is_unspecified or effective.is_multicast or str(effective) in ('100.100.100.200','fd00:ec2::254'):
        return False
    return any(addr.version==net.version and addr in net for net in networks)


class PinnedTransport(httpx.AsyncBaseTransport):
    def __init__(self, origin, *, inner=None, resolver=None, networks=None):
        self.origin=validate_origin(origin,allow_path=True)
        self.inner=inner or httpx.AsyncHTTPTransport(retries=0)
        self.resolver=resolver or socket.getaddrinfo
        self.networks=networks if networks is not None else allowed_networks()

    async def handle_async_request(self,request):
        # Configured origins cannot contain queries, but validated OpenAPI GET
        # arguments legitimately become query parameters on the actual request.
        # Compare scheme/host/port with only that query removed; keep all other
        # URL, DNS and IP checks unchanged.
        if validate_origin(str(request.url.copy_with(query=None)),allow_path=True)!=self.origin:
            raise NetworkDenied('Cross-origin request blocked')
        host=self.origin[1]
        records=await asyncio.to_thread(self.resolver,host,self.origin[2],0,socket.SOCK_STREAM)
        ips=list(dict.fromkeys(r[4][0] for r in records))
        if not ips or any(not permitted(ip,self.networks) for ip in ips):
            raise NetworkDenied('Destination IP is outside operator network allowlist')
        url=request.url.copy_with(host=ips[0])
        headers=request.headers.copy()
        headers['Host']=request.url.netloc.decode('ascii')
        extensions=dict(request.extensions, sni_hostname=host)
        pinned=httpx.Request(request.method,url,headers=headers,stream=request.stream,extensions=extensions)
        response=await self.inner.handle_async_request(pinned)
        response.stream=BoundedStream(response.stream)
        return response

    async def aclose(self):
        await self.inner.aclose()


class BoundedStream(httpx.AsyncByteStream):
    def __init__(self,stream): self.stream=stream
    async def __aiter__(self):
        size=0
        async for chunk in self.stream:
            size+=len(chunk)
            if size>1024*1024: raise ValueError('Transport response exceeds 1 MiB')
            yield chunk
    async def aclose(self): await self.stream.aclose()


def client(origin, *, headers=None, timeout=15):
    return httpx.AsyncClient(transport=PinnedTransport(origin), headers=headers, timeout=timeout, follow_redirects=False, trust_env=False)


async def json_request(origin,method,path,*,headers=None,params=None):
    async with client(origin,headers=headers) as c:
        async with c.stream(method, origin.rstrip('/')+path, params=params) as r:
            r.raise_for_status()
            data=bytearray()
            async for block in r.aiter_bytes():
                data.extend(block)
                if len(data)>1024*1024:
                    raise ValueError('Response exceeds 1 MiB')
            import json
            return json.loads(data)
