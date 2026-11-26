"""Second factor (TOTP), operator role, remote-access policy, voice command endpoint and schema 13 migration."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from examples.workshop_fixture import create_fixture
from jarvis import identity, remote_access, totp
from jarvis.main import create_app
from jarvis.workshop import build_snapshot

KEY = 'remote-access-owner-key-32-characters'
OWNER = {'X-Jarvis-Key': KEY}
PASSWORD = 'Synthetic-password-for-remote-tests'
TUNNEL = {'CF-Connecting-IP': '203.0.113.7', 'Host': 'jarvis.example.com'}


# ------------------------------------------------------------------ TOTP primitives

RFC_SECRET = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'  # ASCII "12345678901234567890"


@pytest.mark.parametrize('when,code', [(59, '287082'), (1111111109, '081804'), (1234567890, '005924'), (2000000000, '279037')])
def test_totp_matches_rfc6238_vectors(when, code):
    assert totp.code_at(RFC_SECRET, totp.step_at(when)) == code
    assert totp.verify(RFC_SECRET, code, 0, now=when) == totp.step_at(when)


def test_totp_rejects_replay_drift_and_garbage():
    now = 1_700_000_000
    step = totp.step_at(now)
    code = totp.code_at(RFC_SECRET, step)
    assert totp.verify(RFC_SECRET, code, step, now=now) is None  # already used
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step - 1), 0, now=now) == step - 1
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step - 3), 0, now=now) is None
    for bad in (None, '', '12345', '1234567', 'abcdef', 123456):
        assert totp.verify(RFC_SECRET, bad, 0, now=now) is None
    assert totp.verify(RFC_SECRET, code[:3] + ' ' + code[3:], 0, now=now) == step


def test_secrets_uri_and_backup_codes():
    secret = totp.new_secret()
    assert len(secret) == 32 and secret.isalnum()
    uri = totp.provisioning_uri(secret, 'endi')
    assert uri.startswith('otpauth://totp/JARVIS%20OS%3Aendi?secret=' + secret)
    codes = totp.backup_codes()
    assert len(codes) == 8 == len(set(codes)) and all(len(code) == 11 and code[5] == '-' for code in codes)
    assert totp.backup_digest(codes[0]) == totp.backup_digest(codes[0].upper().replace('-', ' '))
    assert totp.backup_digest('short') is None


# ------------------------------------------------------------------ API helpers

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('JARVIS_REMOTE_ACCESS', raising=False)
    with TestClient(create_app(tmp_path / 'remote.db', KEY)) as c:
        c.path = tmp_path / 'remote.db'
        yield c


@pytest.fixture
def remote_client(tmp_path, monkeypatch):
    monkeypatch.setenv('JARVIS_REMOTE_ACCESS', 'true')
    with TestClient(create_app(tmp_path / 'remote.db', KEY), base_url='http://127.0.0.1:17321') as c:
        yield c


def make_user(c, username='endi', role='owner'):
    r = c.post('/api/v1/security/users', headers=OWNER, json={'username': username, 'password': PASSWORD, 'role': role})
    assert r.status_code == 201, r.text
    return r.json()


def login(c, username='endi', otp=None, headers=None):
    body = {'username': username, 'password': PASSWORD}
    if otp is not None:
        body['otp'] = otp
    return c.post('/api/v1/auth/login', json=body, headers=headers or {})


def session(c, username='endi', otp=None, headers=None):
    r = login(c, username, otp, headers)
    assert r.status_code == 200, r.text
    return {'X-Jarvis-Key': r.json()['token']}


def enroll(c, auth):
    setup = c.post('/api/v1/auth/mfa/setup', headers=auth)
    assert setup.status_code == 200, setup.text
    secret = setup.json()['secret']
    assert setup.json()['uri'].startswith('otpauth://totp/')
    step = totp.step_at()
    enabled = c.post('/api/v1/auth/mfa/enable', headers=auth, json={'code': totp.code_at(secret, step)})
    assert enabled.status_code == 200, enabled.text
    return secret, step, enabled.json()['backup_codes']


# ------------------------------------------------------------------ second factor

def test_enrollment_login_replay_and_backup_codes(client):
    make_user(client)
    auth = session(client)
    assert client.get('/api/v1/auth/mfa', headers=auth).json() == {'enabled': False, 'pending': False, 'backup_codes_left': 0}
    secret, step, backups = enroll(client, auth)
    assert len(backups) == 8
    assert client.get('/api/v1/auth/mfa', headers=auth).json() == {'enabled': True, 'pending': False, 'backup_codes_left': 8}
    assert client.post('/api/v1/auth/mfa/setup', headers=auth).status_code == 409

    missing = login(client)
    assert missing.status_code == 401 and missing.json()['detail'] == 'Second factor required'
    assert login(client, otp='000000').status_code == 401
    assert login(client, otp=totp.code_at(secret, step)).status_code == 401  # used during enrollment

    fresh = totp.code_at(secret, step + 1)
    ok = login(client, otp=fresh)
    assert ok.status_code == 200 and ok.json()['mfa'] is True
    assert client.get('/api/v1/auth/me', headers={'X-Jarvis-Key': ok.json()['token']}).json()['mfa'] is True
    assert login(client, otp=fresh).status_code == 401  # replay

    assert login(client, otp=backups[0]).status_code == 200
    assert login(client, otp=backups[0]).status_code == 401  # single use
    listed = client.get('/api/v1/security/users', headers=OWNER).json()
    assert listed[0]['mfa_enabled'] is True

    with sqlite3.connect(client.path) as db:
        dump = '\n'.join(db.iterdump())
    assert all(code not in dump and code.replace('-', '') not in dump for code in backups)
    events = [row[0] for row in sqlite3.connect(client.path).execute("SELECT event FROM audit WHERE event LIKE 'identity.mfa%'")]
    assert 'identity.mfa_enabled' in events and secret not in dump.split('identity_mfa')[0]


def test_disable_needs_password_and_code_and_owner_can_reset(client):
    user = make_user(client)
    auth = session(client)
    secret, step, backups = enroll(client, auth)
    bad = client.post('/api/v1/auth/mfa/disable', headers=auth, json={'password': 'wrong-password-123', 'code': totp.code_at(secret, step + 1)})
    assert bad.status_code == 401
    ok = client.post('/api/v1/auth/mfa/disable', headers=auth, json={'password': PASSWORD, 'code': backups[1]})
    assert ok.status_code == 200 and ok.json() == {'enabled': False}
    assert client.get('/api/v1/auth/me', headers=auth).status_code == 401  # sessions revoked
    auth = session(client)  # no second factor any more
    enroll(client, auth)
    reset = client.delete('/api/v1/security/users/' + user['id'] + '/mfa', headers=OWNER)
    assert reset.status_code == 200 and reset.json() == {'reset': True}
    assert login(client).status_code == 200


def test_owner_key_cannot_enroll_a_second_factor(client):
    assert client.post('/api/v1/auth/mfa/setup', headers=OWNER).status_code == 409


# ------------------------------------------------------------------ operator role

def test_operator_controls_gate_and_voice_but_not_settings(client):
    make_user(client, 'mechanik', 'operator')
    auth = session(client, 'mechanik')
    overview = client.get('/api/v1/devices/gate', headers=auth)
    assert overview.status_code == 200
    assert set(overview.json()['config']) == {'name', 'driver', 'require_confirmation'} and 'drivers' not in overview.json()
    assert client.get('/api/v1/devices/gate/config', headers=auth).status_code == 403
    assert client.post('/api/v1/devices/gate/test', headers=auth).status_code == 403
    assert client.get('/api/v1/memory', headers=auth).status_code == 403
    assert client.post('/api/v1/chat', headers=auth, json={'message': 'otwórz bramę'}).status_code == 403
    opened = client.post('/api/v1/devices/gate/command', headers=auth, json={'action': 'open'})
    assert opened.status_code == 200 and opened.json()['action'] == 'open'

    voice = client.post('/api/v1/voice/command', headers=auth, json={'text': 'Jarvis, zamknij bramę'})
    assert voice.status_code == 200, voice.text
    assert voice.json()['handled'] is True and voice.json()['ai_generated'] is False
    unknown = client.post('/api/v1/voice/command', headers=auth, json={'text': 'opowiedz dowcip'})
    assert unknown.json()['handled'] is False
    parts = client.post('/api/v1/voice/command', headers=auth, json={'text': 'co trzeba zamówić'})
    assert parts.json()['handled'] is False and 'nie ma dostępu' in parts.json()['reply']
    actors = [row[0] for row in sqlite3.connect(client.path).execute('SELECT actor FROM gate_events')]
    assert actors and all(actor.startswith('session:') for actor in actors)


def test_other_roles_cannot_use_gate_or_voice(client):
    make_user(client, 'observer', 'observer')
    auth = session(client, 'observer')
    assert client.get('/api/v1/devices/gate', headers=auth).status_code == 403
    assert client.post('/api/v1/voice/command', headers=auth, json={'text': 'otwórz bramę'}).status_code == 403


def test_parts_voice_command_reads_snapshot(tmp_path, monkeypatch):
    source = create_fixture(tmp_path / 'source.db')
    dest = tmp_path / 'workshop.snapshot.sqlite3'
    build_snapshot(source, dest)
    monkeypatch.setenv('AUTOLOGIKA_SNAPSHOT_ENABLED', 'true')
    monkeypatch.setenv('AUTOLOGIKA_SNAPSHOT_PATH', str(dest))
    with TestClient(create_app(tmp_path / 'core.db', KEY)) as c:
        r = c.post('/api/v1/voice/command', headers=OWNER, json={'text': 'Jarvis, jakie części są w drodze?'})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data['handled'] is True and 'DEMO-001' in data['reply'] and 'kopii AutoLogiki' in data['reply']
        assert [item['part_no'] for item in data['parts']['on_order']] == ['DEMO-001'] and data['parts']['to_order'] == []
        chat = c.post('/api/v1/chat', headers=OWNER, json={'message': 'co trzeba zamówić?'})
        assert chat.status_code == 200 and chat.json()['model'] == 'parser'


# ------------------------------------------------------------------ remote policy

def test_tunnel_requests_are_refused_while_remote_access_is_disabled(client):
    assert client.get('/api/v1/status', headers=OWNER).status_code == 200
    refused = client.get('/api/v1/status', headers={**OWNER, **TUNNEL})
    assert refused.status_code == 403 and 'disabled' in refused.json()['detail']
    assert refused.headers['x-frame-options'] == 'DENY'
    assert client.get('/control/', headers=TUNNEL).status_code == 403
    assert client.get('/health', headers=TUNNEL).status_code == 200


def test_remote_access_needs_account_session_with_second_factor(remote_client):
    c = remote_client
    assert c.get('/api/v1/status', headers=OWNER).status_code == 200  # local owner key still works
    assert c.get('/api/v1/status', headers={**OWNER, **TUNNEL}).status_code == 403
    assert c.get('/api/v1/status', headers={**OWNER, 'Host': 'jarvis.example.com'}).status_code == 403
    assert c.get('/control/', headers=TUNNEL).status_code not in (401, 403)  # static panel is not refused (503 = UI not built)
    make_user(c)
    plain = session(c, headers=TUNNEL)  # login itself is allowed remotely
    denied = c.get('/api/v1/status', headers={**plain, **TUNNEL})
    assert denied.status_code == 403 and 'two-factor' in denied.json()['detail']
    secret, step, _ = enroll(c, session(c))  # enrollment happens locally
    strong = session(c, otp=totp.code_at(secret, step + 1), headers=TUNNEL)
    assert c.get('/api/v1/status', headers={**strong, **TUNNEL}).status_code == 200
    assert c.get('/api/v1/devices/gate', headers={**strong, **TUNNEL}).status_code == 200
    token = c.post('/api/v1/security/tokens', headers=OWNER, json={'name': 'worker', 'scopes': ['status:read']}).json()['token']
    assert c.get('/api/v1/status', headers={'X-Jarvis-Key': token, **TUNNEL}).status_code == 403


def test_signed_webhooks_keep_their_own_authentication(client):
    assert remote_access.decide('/webhooks/twilio/whatsapp', None, remote_access.RemoteConfig()) is None


@pytest.mark.parametrize('headers,expected', [
    ({'host': '127.0.0.1:17321'}, False), ({'host': 'localhost'}, False), ({'host': '[::1]:17321'}, False),
    ({'host': 'jarvis.example.com'}, True), ({'host': '192.168.1.20:17321'}, True),
    ({'host': '127.0.0.1', 'x-forwarded-for': '203.0.113.1'}, True), ({'host': 'localhost', 'cf-connecting-ip': '1.2.3.4'}, True),
])
def test_remote_detection(headers, expected):
    assert remote_access.is_remote(headers, remote_access.RemoteConfig(enabled=True)) is expected


def test_local_hosts_and_flag_from_env(monkeypatch):
    monkeypatch.setenv('JARVIS_REMOTE_ACCESS', 'true')
    monkeypatch.setenv('JARVIS_LOCAL_HOSTS', '127.0.0.1, 192.168.1.20')
    config = remote_access.RemoteConfig.from_env()
    assert config.enabled and not remote_access.is_remote({'host': '192.168.1.20:17321'}, config)
    monkeypatch.setenv('JARVIS_REMOTE_ACCESS', 'maybe')
    with pytest.raises(ValueError):
        remote_access.RemoteConfig.from_env()


def test_rate_limit_bucket_uses_tunnel_client_only_from_loopback():
    tunnel = {'client': ('127.0.0.1', 5000), 'headers': [(b'cf-connecting-ip', b'203.0.113.9')]}
    assert remote_access.client_key(tunnel) == 'cf:203.0.113.9'
    spoofed = {'client': ('192.168.1.50', 5000), 'headers': [(b'cf-connecting-ip', b'203.0.113.9')]}
    assert remote_access.client_key(spoofed) == '192.168.1.50'
    assert remote_access.client_key({'client': ('127.0.0.1', 1), 'headers': [(b'cf-connecting-ip', b'x')]}) == 'cf:invalid'


# ------------------------------------------------------------------ schema 13 migration

def test_schema12_accounts_and_sessions_survive_role_constraint_rebuild(tmp_path):
    path = tmp_path / 'old.db'
    with TestClient(create_app(path, KEY)) as c:
        make_user(c, 'stary', 'observer')
        old = session(c, 'stary')
    with sqlite3.connect(path) as db:
        db.executescript('''
            PRAGMA foreign_keys=OFF;
            DROP TABLE identity_mfa;
            CREATE TABLE users_old(id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('owner','observer','home_reader','workshop_reader','automation_runner')),
                enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), revision INTEGER NOT NULL CHECK(revision>=0),
                created REAL NOT NULL, updated REAL NOT NULL);
            INSERT INTO users_old SELECT * FROM identity_users;
            DROP TABLE identity_users; ALTER TABLE users_old RENAME TO identity_users;
            CREATE TABLE sessions_old(id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES identity_users(id) ON DELETE CASCADE,
                token_digest TEXT NOT NULL UNIQUE, expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
            INSERT INTO sessions_old SELECT id,user_id,token_digest,expires_at,revoked,created FROM identity_sessions;
            DROP TABLE identity_sessions; ALTER TABLE sessions_old RENAME TO identity_sessions;
            PRAGMA user_version=12;''')
    with TestClient(create_app(path, KEY)) as c:
        assert c.get('/api/v1/auth/me', headers=old).json()['username'] == 'stary'  # session kept
        make_user(c, 'mechanik', 'operator')
        assert c.get('/ready').status_code == 200
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 13
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert "'operator'" in db.execute("SELECT sql FROM sqlite_master WHERE name='identity_users'").fetchone()[0]
    assert len(list((tmp_path / 'backups').glob('before-schema13-*.sqlite3'))) == 1


def test_identity_rejects_unknown_role_after_migration(tmp_path):
    db = sqlite3.connect(':memory:')
    identity.install(db)
    db.execute('BEGIN')
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO identity_users VALUES('x','abc','h','superuser',1,0,0,0)")
