"""RFC 6238 time-based one-time passwords (HMAC-SHA1, 30 s, 6 digits).

Compatible with Google Authenticator, Microsoft Authenticator, Aegis, 1Password
and the iOS Passwords app. No I/O; the caller stores the secret and the last
accepted time step (replay protection).
"""
import base64
import hashlib
import hmac
import math
import secrets
import struct
import time
from urllib.parse import quote

PERIOD = 30
DIGITS = 6
WINDOW = 1  # accept the previous and next step for clock drift
SECRET_BYTES = 20


def new_secret():
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode('ascii').rstrip('=')


def _key(secret):
    padded = secret.upper() + '=' * (-len(secret) % 8)
    return base64.b32decode(padded, casefold=True)


def code_at(secret, step):
    digest = hmac.new(_key(secret), struct.pack('>Q', step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def step_at(now=None):
    value = time.time() if now is None else float(now)
    if not math.isfinite(value):
        raise ValueError('Clock must be finite')
    return int(value // PERIOD)


def normalize(code):
    if not isinstance(code, str):
        return None
    value = code.replace(' ', '').replace('-', '')
    return value if len(value) == DIGITS and value.isdigit() else None


def verify(secret, code, last_step=0, now=None):
    """Return the matched step (> last_step) or None. Constant-time per candidate."""
    value = normalize(code)
    if value is None:
        return None
    current = step_at(now)
    matched = None
    for step in range(current - WINDOW, current + WINDOW + 1):
        if hmac.compare_digest(code_at(secret, step), value) and step > last_step and matched is None:
            matched = step
    return matched


def provisioning_uri(secret, account, issuer='JARVIS OS'):
    label = quote(issuer + ':' + account, safe='')
    return (f'otpauth://totp/{label}?secret={secret}&issuer={quote(issuer, safe="")}'
            f'&algorithm=SHA1&digits={DIGITS}&period={PERIOD}')


def backup_codes(count=8):
    """Human-friendly single-use codes: 10 characters from an unambiguous alphabet."""
    alphabet = 'abcdefghjkmnpqrstuvwxyz23456789'
    codes = [''.join(secrets.choice(alphabet) for _ in range(10)) for _ in range(count)]
    return [code[:5] + '-' + code[5:] for code in codes]


def backup_digest(code):
    if not isinstance(code, str):
        return None
    value = code.strip().lower().replace('-', '').replace(' ', '')
    if len(value) != 10 or not value.isalnum() or not value.isascii():
        return None
    return hashlib.sha256(value.encode('ascii')).hexdigest()
