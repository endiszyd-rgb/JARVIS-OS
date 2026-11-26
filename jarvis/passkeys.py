"""Passkeys (WebAuthn): log in with Face ID, Touch ID, Windows Hello or a security key.

A passkey verified with user verification (biometrics or device PIN) proves possession of the
device and the person, so it opens a session flagged ``mfa`` — accepted for remote access like
a TOTP login. Origins: ``https://<Host of the request>`` (the tunnel domain), any
``http://localhost:<port>`` and the explicit list ``JARVIS_PASSKEY_ORIGINS``. Browsers do not
allow passkeys on raw IP addresses (open the local panel via http://localhost:17321).
Challenges live in process memory for 2 minutes and are single-use.
"""
import json
import os
import secrets
import threading
import time
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement, UserVerificationRequirement)

from . import identity

RP_NAME = 'JARVIS OS'
TTL = 120
MAX_PENDING = 256


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class RegisterVerify(Strict):
    ticket: str = Field(min_length=16, max_length=64)
    name: str = Field(default='Telefon', min_length=1, max_length=60)
    credential: dict


class LoginOptions(Strict):
    username: str | None = Field(default=None, pattern=r'^[a-z][a-z0-9_.-]{2,63}$')


class LoginVerify(Strict):
    ticket: str = Field(min_length=16, max_length=64)
    credential: dict


def allowed_origin(request: Request):
    """Return (origin, rp_id) for this request or raise 400."""
    origin = (request.headers.get('origin') or '').strip().rstrip('/')
    parts = urlsplit(origin)
    host = (request.headers.get('host') or '').strip().lower()
    extra = {item.strip().rstrip('/') for item in os.environ.get('JARVIS_PASSKEY_ORIGINS', '').split(',') if item.strip()}
    ok = bool(parts.hostname) and parts.path in ('', '/') and not parts.query and (
        origin in extra
        or (parts.scheme == 'https' and parts.netloc.lower() == host)
        or (parts.scheme == 'http' and parts.hostname == 'localhost'))
    if not ok:
        raise HTTPException(400, 'Passkeys need the panel opened via HTTPS (tunnel) or http://localhost, not an IP address')
    return origin, parts.hostname


class Challenges:
    def __init__(self):
        self._items = {}
        self._lock = threading.Lock()

    def put(self, **entry):
        ticket = secrets.token_urlsafe(24)
        now = time.monotonic()
        with self._lock:
            self._items = {key: value for key, value in self._items.items() if value['expires'] > now}
            if len(self._items) >= MAX_PENDING:
                raise HTTPException(429, 'Too many pending passkey requests')
            self._items[ticket] = dict(entry, expires=now + TTL)
        return ticket

    def take(self, ticket, purpose):
        with self._lock:
            entry = self._items.pop(ticket, None)
        if entry is None or entry['expires'] <= time.monotonic() or entry['purpose'] != purpose:
            raise HTTPException(400, 'Passkey request expired; try again')
        return entry


def mount(router, db, self_auth, audit, config, ready):
    challenges = Challenges()

    def account(principal):
        if principal.kind != 'session':
            raise HTTPException(409, 'Passkeys belong to an account; log in with a username')
        return principal

    @router.get('/auth/passkeys')
    def list_passkeys(principal=Depends(self_auth)):
        principal = account(principal)
        with db() as c:
            return identity.passkey_list(c, principal.id)

    @router.post('/auth/passkeys/register/options')
    def register_options(request: Request, principal=Depends(self_auth)):
        principal = account(principal)
        origin, rp_id = allowed_origin(request)
        with db() as c:
            if identity.mfa_status(c, principal.id)['enabled'] and not principal.mfa:
                raise HTTPException(403, 'Log in with your 2FA code before adding a passkey')
            existing = identity.passkey_credentials(c, principal.id)  # exclude every device of this account
        options = generate_registration_options(
            rp_id=rp_id, rp_name=RP_NAME, user_name=principal.username, user_id=principal.id.encode(),
            user_display_name=principal.username,
            authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.PREFERRED,
                                                                   user_verification=UserVerificationRequirement.REQUIRED),
            exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(item)) for item in existing])
        ticket = challenges.put(purpose='register', challenge=options.challenge, user_id=principal.id, origin=origin, rp_id=rp_id)
        return {'ticket': ticket, 'options': json.loads(options_to_json(options))}

    @router.post('/auth/passkeys/register/verify', status_code=201)
    def register_verify(body: RegisterVerify, request: Request, principal=Depends(self_auth)):
        principal = account(principal)
        entry = challenges.take(body.ticket, 'register')
        origin, rp_id = allowed_origin(request)
        if entry['user_id'] != principal.id or (origin, rp_id) != (entry['origin'], entry['rp_id']):
            raise HTTPException(400, 'Passkey request does not match this session')
        try:
            verified = verify_registration_response(credential=body.credential, expected_challenge=entry['challenge'],
                                                    expected_rp_id=rp_id, expected_origin=origin, require_user_verification=True)
        except (InvalidRegistrationResponse, ValueError, KeyError, TypeError):
            raise HTTPException(400, 'Passkey could not be verified') from None
        transports = [item for item in (body.credential.get('response') or {}).get('transports', []) if isinstance(item, str)]
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            item = identity.passkey_add(c, principal.id, bytes_to_base64url(verified.credential_id), verified.credential_public_key,
                                        verified.sign_count, body.name.strip() or 'Urządzenie', transports, rp_id)
            audit(c, 'identity.passkey_added', {'subject': principal.id, 'passkey': item['id']})
        return item

    @router.delete('/auth/passkeys/{ident}')
    def delete_passkey(ident: str, principal=Depends(self_auth)):
        principal = account(principal)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not identity.passkey_delete(c, principal.id, ident):
                raise HTTPException(404, 'Passkey missing')
            audit(c, 'identity.passkey_removed', {'subject': principal.id, 'passkey': ident})
        return {'removed': ident}

    @router.post('/auth/passkeys/login/options')
    def login_options(body: LoginOptions, request: Request):
        if not ready():
            raise HTTPException(503, 'Owner bootstrap configuration is incomplete')
        origin, rp_id = allowed_origin(request)
        allow = []
        if body.username:
            with db() as c:
                row = c.execute('SELECT id FROM identity_users WHERE username=? AND enabled=1', (body.username,)).fetchone()
                # Unknown names get the same response shape (discoverable passkeys still work).
                allow = identity.passkey_credentials(c, row[0], rp_id) if row else []
        options = generate_authentication_options(
            rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED,
            allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(item)) for item in allow])
        ticket = challenges.put(purpose='login', challenge=options.challenge, origin=origin, rp_id=rp_id)
        return {'ticket': ticket, 'options': json.loads(options_to_json(options))}

    @router.post('/auth/passkeys/login/verify')
    def login_verify(body: LoginVerify, request: Request):
        if not ready():
            raise HTTPException(503, 'Owner bootstrap configuration is incomplete')
        entry = challenges.take(body.ticket, 'login')
        origin, rp_id = allowed_origin(request)
        if (origin, rp_id) != (entry['origin'], entry['rp_id']):
            raise HTTPException(400, 'Passkey request does not match this address')
        credential_id = body.credential.get('id') if isinstance(body.credential.get('id'), str) else ''
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = identity.passkey_lookup(c, credential_id[:512], rp_id)
            result = None
            if row is not None:
                try:
                    verified = verify_authentication_response(
                        credential=body.credential, expected_challenge=entry['challenge'], expected_rp_id=rp_id,
                        expected_origin=origin, credential_public_key=row['public_key'],
                        credential_current_sign_count=row['sign_count'], require_user_verification=True)
                    result = identity.passkey_login(c, row, verified.new_sign_count, config.session_minutes * 60)
                except (InvalidAuthenticationResponse, ValueError, KeyError, TypeError):
                    result = None
            detail = {'success': result is not None, 'method': 'passkey'}
            if result:
                detail.update(subject=result['user']['id'], mfa=True)
            audit(c, 'identity.login', detail)
        if result is None:
            raise HTTPException(401, 'Invalid credentials')
        return result
