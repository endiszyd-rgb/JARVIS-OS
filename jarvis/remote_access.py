"""Remote-access policy for use behind a tunnel (Cloudflare Tunnel, Tailscale Funnel, reverse proxy).

JARVIS listens on loopback; a tunnel client on the workshop PC forwards public
requests to it. Such requests are recognised by forwarding headers that tunnels
add, or (with remote access enabled) by a Host name that is not local.

* Remote access disabled (default): every forwarded request is refused, so an
  accidentally started tunnel exposes nothing.
* Remote access enabled: remote requests may load the static panel and log in,
  but every other API call needs an account session that was opened with a
  second factor (TOTP). The owner master key and service tokens never work
  remotely.
* Device keys (Siri shortcut on the owner's phone) work remotely only for the
  hands-free voice question and the gate command.
"""
from dataclasses import dataclass
import ipaddress
import os

FORWARD_HEADERS = ('cf-connecting-ip', 'cf-ray', 'x-forwarded-for', 'x-forwarded-host', 'forwarded', 'x-real-ip', 'tailscale-user-login')
REMOTE_PUBLIC_API = frozenset({'/api/auth/login', '/api/v1/auth/login', '/api/ready', '/api/v1/ready',
                               '/api/auth/passkeys/login/options', '/api/v1/auth/passkeys/login/options',
                               '/api/auth/passkeys/login/verify', '/api/v1/auth/passkeys/login/verify'})
DEFAULT_LOCAL_HOSTS = ('127.0.0.1', 'localhost', '::1')
DEVICE_REMOTE_API = frozenset({'/api/v1/voice/ask', '/api/v1/devices/gate/command'})
# Provider webhooks verify their own request signatures and predate this policy.
SIGNED_WEBHOOK_PREFIX = '/webhooks/'


@dataclass(frozen=True, slots=True)
class RemoteConfig:
    enabled: bool = False
    local_hosts: tuple[str, ...] = DEFAULT_LOCAL_HOSTS

    @classmethod
    def from_env(cls):
        raw = os.environ.get('JARVIS_REMOTE_ACCESS', 'false').strip().lower()
        if raw not in ('true', 'false', '1', '0', 'yes', 'no', ''):
            raise ValueError('JARVIS_REMOTE_ACCESS must be true or false')
        hosts = tuple(item.strip().lower().strip('[]') for item in os.environ.get('JARVIS_LOCAL_HOSTS', '').split(',') if item.strip())
        for host in hosts:
            if any(ch in host for ch in '/@?# ') or len(host) > 253:
                raise ValueError('JARVIS_LOCAL_HOSTS must list host names or IP addresses')
        return cls(enabled=raw in ('true', '1', 'yes'), local_hosts=hosts or DEFAULT_LOCAL_HOSTS)


def _host_name(value):
    value = (value or '').strip().lower()
    if value.startswith('['):
        return value[1:value.find(']')] if ']' in value else value
    return value.rsplit(':', 1)[0] if value.count(':') == 1 else value


def forwarded(headers):
    return any(headers.get(name) for name in FORWARD_HEADERS)


def is_remote(headers, config: RemoteConfig):
    """Forwarded requests are always remote; with remote access on, so is a non-local Host."""
    if forwarded(headers):
        return True
    return config.enabled and _host_name(headers.get('host')) not in config.local_hosts


def decide(path, principal, config: RemoteConfig):
    """Return None to allow, or (status, detail) to refuse a remote request."""
    if path.startswith(SIGNED_WEBHOOK_PREFIX):
        return None
    if not config.enabled:
        return 403, 'Remote access is disabled (set JARVIS_REMOTE_ACCESS=true on the workshop PC)'
    if not (path == '/api' or path.startswith('/api/')):
        return None  # static panel files, /health
    if path.rstrip('/') in REMOTE_PUBLIC_API:
        return None
    if principal is None:
        return None  # the route answers 401 itself
    if principal.kind == 'device':
        if path.rstrip('/') in DEVICE_REMOTE_API:
            return None
        return 403, 'A device key works remotely only for voice questions and the gate'
    if principal.kind != 'session':
        return 403, 'Remote access accepts only account sessions (not the owner key or service tokens)'
    if not principal.mfa:
        return 403, 'Remote access requires an account with two-factor authentication enabled'
    return None


def client_key(scope):
    """Rate-limit bucket: per tunnel client IP when the tunnel itself connects from loopback."""
    peer = (scope.get('client') or ('unknown',))[0]
    try:
        loopback = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        loopback = False
    if loopback:
        for name, value in scope.get('headers') or ():
            if name == b'cf-connecting-ip':
                text = value.decode('latin-1').strip()[:64]
                try:
                    return 'cf:' + str(ipaddress.ip_address(text))
                except ValueError:
                    return 'cf:invalid'
    return peer
