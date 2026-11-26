"""Passkeys (WebAuthn) with a software authenticator: registration, login, replay, origins, remote access."""
import base64
import hashlib
import json
import sqlite3
import struct

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from jarvis import totp
from jarvis.main import create_app

KEY = 'passkey-test-owner-key-32-characters'
OWNER = {'X-Jarvis-Key': KEY}
PASSWORD = 'Synthetic-password-for-passkeys'
LOCAL = 'http://localhost:17321'
TUNNEL_HOST = 'jarvis.example.com'


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def unb64(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


class Authenticator:
    """Minimal platform authenticator (ES256, 'none' attestation, user verification set)."""

    def __init__(self, uv=True):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = b'cred-' + hashlib.sha256(str(id(self)).encode()).digest()[:16]
        self.count = 0
        self.uv = uv

    def _flags(self, attested=False):
        return 0x01 | (0x04 if self.uv else 0) | (0x40 if attested else 0)

    def create(self, options, origin):
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, 'big'), -3: numbers.y.to_bytes(32, 'big')})
        auth = (hashlib.sha256(options['rp']['id'].encode()).digest() + bytes([self._flags(True)]) + struct.pack('>I', self.count)
                + b'\0' * 16 + struct.pack('>H', len(self.credential_id)) + self.credential_id + cose)
        client = json.dumps({'type': 'webauthn.create', 'challenge': options['challenge'], 'origin': origin, 'crossOrigin': False}).encode()
        return {'id': b64(self.credential_id), 'rawId': b64(self.credential_id), 'type': 'public-key',
                'response': {'clientDataJSON': b64(client), 'attestationObject': b64(cbor2.dumps({'fmt': 'none', 'attStmt': {}, 'authData': auth})),
                             'transports': ['internal']},
                'clientExtensionResults': {}, 'authenticatorAttachment': 'platform'}

    def get(self, options, origin, rp_id=None):
        self.count += 1
        auth = hashlib.sha256((rp_id or options['rpId']).encode()).digest() + bytes([self._flags()]) + struct.pack('>I', self.count)
        client = json.dumps({'type': 'webauthn.get', 'challenge': options['challenge'], 'origin': origin, 'crossOrigin': False}).encode()
        signature = self.key.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {'id': b64(self.credential_id), 'rawId': b64(self.credential_id), 'type': 'public-key',
                'response': {'clientDataJSON': b64(client), 'authenticatorData': b64(auth), 'signature': b64(signature), 'userHandle': None},
                'clientExtensionResults': {}, 'authenticatorAttachment': 'platform'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('JARVIS_REMOTE_ACCESS', raising=False)
    monkeypatch.delenv('JARVIS_PASSKEY_ORIGINS', raising=False)
    with TestClient(create_app(tmp_path / 'passkeys.db', KEY), base_url='http://localhost:17321') as c:
        c.path = tmp_path / 'passkeys.db'
        yield c


def account(c, username='endi', role='owner'):
    assert c.post('/api/v1/security/users', headers=OWNER, json={'username': username, 'password': PASSWORD, 'role': role}).status_code == 201
    token = c.post('/api/v1/auth/login', json={'username': username, 'password': PASSWORD}).json()['token']
    return {'X-Jarvis-Key': token}


def register(c, auth, device, origin=LOCAL, headers=None):
    headers = {**auth, 'Origin': origin, **(headers or {})}
    options = c.post('/api/v1/auth/passkeys/register/options', headers=headers)
    assert options.status_code == 200, options.text
    data = options.json()
    assert data['options']['authenticatorSelection']['userVerification'] == 'required'
    return c.post('/api/v1/auth/passkeys/register/verify', headers=headers,
                  json={'ticket': data['ticket'], 'name': 'iPhone', 'credential': device.create(data['options'], origin)})


def login(c, device, origin=LOCAL, headers=None, username=None):
    headers = {'Origin': origin, **(headers or {})}
    options = c.post('/api/v1/auth/passkeys/login/options', headers=headers, json={'username': username} if username else {})
    assert options.status_code == 200, options.text
    data = options.json()
    return c.post('/api/v1/auth/passkeys/login/verify', headers=headers, json={'ticket': data['ticket'], 'credential': device.get(data['options'], origin)}), data


def test_register_list_login_and_delete(client):
    auth = account(client)
    phone = Authenticator()
    added = register(client, auth, phone)
    assert added.status_code == 201 and added.json()['name'] == 'iPhone' and added.json()['transports'] == ['internal']
    assert [item['name'] for item in client.get('/api/v1/auth/passkeys', headers=auth).json()] == ['iPhone']
    response, options = login(client, phone, username='endi')
    assert options['options']['allowCredentials'][0]['id'] == b64(phone.credential_id)
    assert response.status_code == 200 and response.json()['mfa'] is True and response.json()['user']['username'] == 'endi'
    me = client.get('/api/v1/auth/me', headers={'X-Jarvis-Key': response.json()['token']}).json()
    assert me['mfa'] is True and me['role'] == 'owner'
    discoverable, options = login(client, phone)  # no username: discoverable credential
    assert discoverable.status_code == 200 and options['options'].get('allowCredentials', []) == []
    with sqlite3.connect(client.path) as db:
        assert db.execute('SELECT sign_count FROM identity_passkeys').fetchone()[0] == 2
        assert 'identity.passkey_added' in [row[0] for row in db.execute('SELECT event FROM audit')]
    ident = added.json()['id']
    assert client.delete('/api/v1/auth/passkeys/' + ident, headers=auth).json() == {'removed': ident}
    assert login(client, phone)[0].status_code == 401


def test_replayed_or_wrong_assertions_are_rejected(client):
    auth = account(client)
    phone, stranger = Authenticator(), Authenticator()
    register(client, auth, phone)
    options = client.post('/api/v1/auth/passkeys/login/options', headers={'Origin': LOCAL}, json={}).json()
    assertion = phone.get(options['options'], LOCAL)
    assert client.post('/api/v1/auth/passkeys/login/verify', headers={'Origin': LOCAL}, json={'ticket': options['ticket'], 'credential': assertion}).status_code == 200
    replay = client.post('/api/v1/auth/passkeys/login/verify', headers={'Origin': LOCAL}, json={'ticket': options['ticket'], 'credential': assertion})
    assert replay.status_code == 400  # single-use challenge
    assert login(client, stranger)[0].status_code == 401  # unknown credential
    forged, _ = login(client, phone, headers={'Origin': LOCAL})
    assert forged.status_code == 200
    options = client.post('/api/v1/auth/passkeys/login/options', headers={'Origin': LOCAL}, json={}).json()
    wrong_rp = phone.get(options['options'], LOCAL, rp_id='evil.example')
    assert client.post('/api/v1/auth/passkeys/login/verify', headers={'Origin': LOCAL}, json={'ticket': options['ticket'], 'credential': wrong_rp}).status_code == 401


def test_user_verification_is_required(client):
    auth = account(client)
    assert register(client, auth, Authenticator(uv=False)).status_code == 400


def test_disabled_account_cannot_use_its_passkey(client):
    auth = account(client)
    phone = Authenticator()
    register(client, auth, phone)
    user = client.get('/api/v1/security/users', headers=OWNER).json()[0]
    assert client.patch('/api/v1/security/users/' + user['id'], headers=OWNER, json={'revision': user['revision'], 'enabled': False}).status_code == 200
    assert login(client, phone)[0].status_code == 401


@pytest.mark.parametrize('origin', ['http://127.0.0.1:17321', 'http://evil.example', 'https://evil.example', ''])
def test_ip_and_foreign_origins_are_refused(client, origin):
    auth = account(client)
    headers = {**auth, 'Origin': origin} if origin else auth
    assert client.post('/api/v1/auth/passkeys/register/options', headers=headers).status_code == 400
    assert client.post('/api/v1/auth/passkeys/login/options', headers={'Origin': origin} if origin else {}, json={}).status_code == 400


def test_owner_key_and_totp_rules(client):
    assert client.post('/api/v1/auth/passkeys/register/options', headers={**OWNER, 'Origin': LOCAL}).status_code == 409
    auth = account(client)
    setup = client.post('/api/v1/auth/mfa/setup', headers=auth).json()
    step = totp.step_at()
    assert client.post('/api/v1/auth/mfa/enable', headers=auth, json={'code': totp.code_at(setup['secret'], step)}).status_code == 200
    # a password-only session must not add a passkey once 2FA is on
    assert client.post('/api/v1/auth/passkeys/register/options', headers={**auth, 'Origin': LOCAL}).status_code == 403
    strong = client.post('/api/v1/auth/login', json={'username': 'endi', 'password': PASSWORD, 'otp': totp.code_at(setup['secret'], step + 1)}).json()['token']
    assert register(client, {'X-Jarvis-Key': strong}, Authenticator()).status_code == 201
    user = client.get('/api/v1/security/users', headers=OWNER).json()[0]
    assert client.delete('/api/v1/security/users/' + user['id'] + '/mfa', headers=OWNER).json() == {'reset': True}
    with sqlite3.connect(client.path) as db:
        assert db.execute('SELECT count(*) FROM identity_passkeys').fetchone()[0] == 0  # lost phone: reset removes passkeys too


def test_phone_enrols_over_the_tunnel_after_a_totp_login(tmp_path, monkeypatch):
    """Real flow: on the phone log in once with password + 2FA code, add Face ID, then use only Face ID."""
    monkeypatch.setenv('JARVIS_REMOTE_ACCESS', 'true')
    tunnel = {'Host': TUNNEL_HOST, 'CF-Connecting-IP': '203.0.113.9'}
    origin = 'https://' + TUNNEL_HOST
    with TestClient(create_app(tmp_path / 'remote.db', KEY), base_url='http://127.0.0.1:17321') as c:
        assert c.post('/api/v1/security/users', headers=OWNER, json={'username': 'endi', 'password': PASSWORD, 'role': 'owner'}).status_code == 201
        local = {'X-Jarvis-Key': c.post('/api/v1/auth/login', json={'username': 'endi', 'password': PASSWORD}).json()['token']}
        setup = c.post('/api/v1/auth/mfa/setup', headers=local).json()
        step = totp.step_at()
        assert c.post('/api/v1/auth/mfa/enable', headers=local, json={'code': totp.code_at(setup['secret'], step)}).status_code == 200
        password_only = c.post('/api/v1/auth/login', headers=tunnel, json={'username': 'endi', 'password': PASSWORD})
        assert password_only.status_code == 401  # 2FA account: code required
        strong = c.post('/api/v1/auth/login', headers=tunnel, json={'username': 'endi', 'password': PASSWORD, 'otp': totp.code_at(setup['secret'], step + 1)}).json()
        phone = Authenticator()
        assert register(c, {'X-Jarvis-Key': strong['token']}, phone, origin=origin, headers=tunnel).status_code == 201
        response, _ = login(c, phone, origin=origin, headers=tunnel)
        assert response.status_code == 200 and response.json()['mfa'] is True
        assert c.get('/api/v1/devices/gate', headers={'X-Jarvis-Key': response.json()['token'], **tunnel}).status_code == 200
        # the same passkey is bound to the tunnel domain and cannot be used from another origin
        assert login(c, phone, origin=LOCAL, headers={'Host': 'localhost:17321'})[0].status_code == 401
