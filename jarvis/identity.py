"""Local account credentials and opaque sessions inside the caller's transaction.

This module opens no connections and never commits. Passwords use salted
PBKDF2-HMAC-SHA256; session secrets are returned once and stored only as SHA-256.
"""
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import re
import secrets
import sqlite3
import time
from types import MappingProxyType
import uuid

from fastapi import HTTPException

from . import totp


ROLES = MappingProxyType({
    'owner': frozenset({'*'}),
    'observer': frozenset({'status:read'}),
    'home_reader': frozenset({'status:read', 'home:read'}),
    'workshop_reader': frozenset({'status:read', 'workshop:read'}),
    'automation_runner': frozenset({'status:read', 'scheduler:tick'}),
    # Workshop staff on a phone/tablet: gate, voice commands and camera preview only.
    'operator': frozenset({'status:read', 'gate:control', 'voice:command', 'voice:ask', 'cameras:view'}),
})
MFA_REQUIRED = 'mfa_required'
ITERATIONS = 600_000
MAX_USERS = 256
MAX_ACTIVE_SESSIONS = 16
USERNAME = re.compile(r'^[a-z][a-z0-9_.-]{2,63}$')
TOKEN = re.compile(r'^[A-Za-z0-9_-]{32,256}$')


@dataclass(frozen=True, slots=True)
class Principal:
    id: str
    kind: str
    role: str
    scopes: frozenset[str]
    username: str | None = None
    expires_at: float | None = None
    mfa: bool = False

    @property
    def is_owner(self):
        return self.role == 'owner'


def _role_check():
    return 'role IN (' + ','.join("'" + name + "'" for name in ROLES) + ')'


_USERS_DDL = '''CREATE TABLE IF NOT EXISTS {name}(
        id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK({check}),
        enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), revision INTEGER NOT NULL CHECK(revision>=0),
        created REAL NOT NULL, updated REAL NOT NULL)'''


def _rebuild_users(c):
    """Schema 13: widen the role CHECK (adds 'operator') keeping ids, hashes and sessions.

    SQLite cannot alter a CHECK constraint, so the table is copied under
    foreign_keys=OFF inside one transaction (documented SQLite procedure).
    """
    if c.in_transaction:
        c.commit()
    c.execute('PRAGMA foreign_keys=OFF')
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute(_USERS_DDL.format(name='identity_users_v13', check=_role_check()))
        c.execute('INSERT INTO identity_users_v13 SELECT id,username,password_hash,role,enabled,revision,created,updated FROM identity_users')
        c.execute('DROP TABLE identity_users')
        c.execute('ALTER TABLE identity_users_v13 RENAME TO identity_users')
        if c.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Account migration would break session references')
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        c.execute('PRAGMA foreign_keys=ON')


def install(c):
    """Add only JARVIS tables; execute DDL without an implicit transaction commit."""
    row = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='identity_users'").fetchone()
    if row is None:
        c.execute(_USERS_DDL.format(name='identity_users', check=_role_check()))
    elif "'operator'" not in row[0]:
        _rebuild_users(c)
    c.execute('''CREATE TABLE IF NOT EXISTS identity_sessions(
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES identity_users(id) ON DELETE CASCADE,
        token_digest TEXT NOT NULL UNIQUE, expires_at REAL NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)), created REAL NOT NULL,
        mfa INTEGER NOT NULL DEFAULT 0 CHECK(mfa IN (0,1)))''')
    columns = {item[1] for item in c.execute('PRAGMA table_info(identity_sessions)')}
    if 'mfa' not in columns:
        c.execute('ALTER TABLE identity_sessions ADD COLUMN mfa INTEGER NOT NULL DEFAULT 0 CHECK(mfa IN (0,1))')
    c.execute('CREATE INDEX IF NOT EXISTS identity_sessions_user ON identity_sessions(user_id)')
    c.execute('''CREATE TABLE IF NOT EXISTS identity_mfa(
        user_id TEXT PRIMARY KEY REFERENCES identity_users(id) ON DELETE CASCADE,
        secret TEXT NOT NULL, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
        last_step INTEGER NOT NULL DEFAULT 0, backup_codes TEXT NOT NULL DEFAULT '[]',
        created REAL NOT NULL, updated REAL NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS identity_passkeys(
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES identity_users(id) ON DELETE CASCADE,
        credential_id TEXT NOT NULL UNIQUE, public_key BLOB NOT NULL, sign_count INTEGER NOT NULL CHECK(sign_count>=0),
        name TEXT NOT NULL, transports TEXT NOT NULL DEFAULT '[]', created REAL NOT NULL, last_used REAL,
        rp_id TEXT NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS identity_passkeys_user ON identity_passkeys(user_id)')
    c.execute('''CREATE TABLE IF NOT EXISTS identity_device_keys(
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES identity_users(id) ON DELETE CASCADE,
        name TEXT NOT NULL, token_digest TEXT NOT NULL UNIQUE, created REAL NOT NULL, last_used REAL,
        revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)))''')
    c.execute('CREATE INDEX IF NOT EXISTS identity_device_keys_user ON identity_device_keys(user_id)')


def _transaction(c):
    if not c.in_transaction:
        raise ValueError('Identity mutation requires an active transaction')


def _one(c, sql, values=()):
    cursor = c.execute(sql, values)
    row = cursor.fetchone()
    return dict(zip((item[0] for item in cursor.description), row)) if row is not None else None


def _all(c, sql, values=()):
    cursor = c.execute(sql, values)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _now(value=None):
    try:
        value = time.time() if value is None else float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('Identity clock must be finite') from None
    if not math.isfinite(value):
        raise ValueError('Identity clock must be finite')
    return value


def _password_bytes(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        return None
    try:
        return password.encode('utf-8')
    except UnicodeError:
        return None


def _hash_password(encoded):
    salt = secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac('sha256', encoded, salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}'


def _verify_password(encoded, stored):
    usable = True
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split('$')
        if algorithm != 'pbkdf2_sha256' or iterations != str(ITERATIONS):
            raise ValueError()
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
        if len(salt) != 32 or len(expected) != 32:
            raise ValueError()
    except (AttributeError, TypeError, ValueError):
        # Malformed stored credentials fail closed without a cheap login path.
        salt, expected, usable = bytes(32), bytes(32), False
    actual = hashlib.pbkdf2_hmac('sha256', encoded, salt, ITERATIONS)
    return hmac.compare_digest(actual, expected) and usable


_DUMMY_PASSWORD = b'non-account password used only for verification work'
_DUMMY_HASH = _hash_password(_DUMMY_PASSWORD)


def _user(row, c=None):
    data = {name: (bool(row[name]) if name == 'enabled' else row[name])
            for name in ('id', 'username', 'role', 'enabled', 'revision', 'created', 'updated')}
    if c is not None:
        data['mfa_enabled'] = c.execute('SELECT 1 FROM identity_mfa WHERE user_id=? AND enabled=1', (row['id'],)).fetchone() is not None
    return data


def create_user(c, username, password: str, role):
    _transaction(c)
    encoded = _password_bytes(password)
    if not isinstance(username, str) or not USERNAME.fullmatch(username):
        raise HTTPException(422, 'Invalid account username')
    if not isinstance(role, str) or role not in ROLES:
        raise HTTPException(422, 'Invalid account role')
    if encoded is None:
        raise HTTPException(422, 'Password must contain 12 to 256 valid characters')
    if _one(c, 'SELECT id FROM identity_users WHERE username=?', (username,)):
        raise HTTPException(409, 'Account username already exists')
    if c.execute('SELECT count(*) FROM identity_users').fetchone()[0] >= MAX_USERS:
        raise HTTPException(409, 'Account capacity reached')
    ident, now = str(uuid.uuid4()), _now()
    try:
        c.execute('INSERT INTO identity_users VALUES(?,?,?,?,1,0,?,?)',
                  (ident, username, _hash_password(encoded), role, now, now))
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'Account username already exists') from None
    return _user(_one(c, 'SELECT * FROM identity_users WHERE id=?', (ident,)), c)


def list_users(c):
    return [_user(row, c) for row in _all(c, 'SELECT * FROM identity_users ORDER BY created,id')]


def change_user(c, ident, revision, role=None, enabled=None):
    _transaction(c)
    if type(revision) is not int or revision < 0:
        raise HTTPException(422, 'Invalid account revision')
    if role is None and enabled is None:
        raise HTTPException(422, 'Specify an account change')
    if role is not None and (not isinstance(role, str) or role not in ROLES):
        raise HTTPException(422, 'Invalid account role')
    if enabled is not None and type(enabled) is not bool:
        raise HTTPException(422, 'Invalid account enabled state')
    row = _one(c, 'SELECT * FROM identity_users WHERE id=?', (str(ident),))
    if row is None:
        raise HTTPException(404, 'Account missing')
    if revision != row['revision']:
        raise HTTPException(409, 'Account revision changed; refresh')
    c.execute('UPDATE identity_users SET role=?,enabled=?,revision=revision+1,updated=? WHERE id=?',
              (row['role'] if role is None else role, row['enabled'] if enabled is None else int(enabled),
               _now(), row['id']))
    c.execute('UPDATE identity_sessions SET revoked=1 WHERE user_id=?', (row['id'],))
    return _user(_one(c, 'SELECT * FROM identity_users WHERE id=?', (row['id'],)), c)


def issue_session(c, username, password, ttl_seconds, now=None, otp=None):
    """Verify credentials, prune expired/revoked rows and allow <=16 live sessions.

    A successful seventeenth login revokes the oldest session. Revoked metadata
    is pruned at the next successful login; durable security events belong to
    the caller's audit log. Failed logins do not mutate session/account rows.
    """
    _transaction(c)
    if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 86400:
        raise ValueError('Session lifetime must be an integer from 1 to 86400 seconds')
    at = _now(now)
    valid_username = isinstance(username, str) and USERNAME.fullmatch(username)
    row = _one(c, 'SELECT * FROM identity_users WHERE username=?', (username,)) if valid_username else None
    encoded = _password_bytes(password)
    stored = row['password_hash'] if row and row['enabled'] else _DUMMY_HASH
    matched = _verify_password(encoded if encoded is not None else _DUMMY_PASSWORD, stored)
    if row is None or not row['enabled'] or encoded is None or not matched or row['role'] not in ROLES:
        return None
    second = _one(c, 'SELECT * FROM identity_mfa WHERE user_id=? AND enabled=1', (row['id'],))
    if second is not None:
        if otp is None or otp == '':
            return MFA_REQUIRED
        if not _consume_second_factor(c, second, otp, at):
            return None
    return _open_session(c, row, ttl_seconds, at, mfa=second is not None)


def _open_session(c, row, ttl_seconds, at, mfa):
    """Prune, enforce <=16 live sessions per account and store only the token digest."""
    c.execute('DELETE FROM identity_sessions WHERE expires_at<=? OR revoked=1', (at,))
    active = _all(c, 'SELECT id FROM identity_sessions WHERE user_id=? AND revoked=0 ORDER BY created,id',
                  (row['id'],))
    if len(active) >= MAX_ACTIVE_SESSIONS:
        # Keep the limit even if an imported database previously exceeded it.
        c.executemany('UPDATE identity_sessions SET revoked=1 WHERE id=?',
                      [(item['id'],) for item in active[:len(active) - MAX_ACTIVE_SESSIONS + 1]])
    ident, token, expires = str(uuid.uuid4()), secrets.token_urlsafe(32), at + ttl_seconds
    c.execute('INSERT INTO identity_sessions(id,user_id,token_digest,expires_at,revoked,created,mfa) VALUES(?,?,?,?,0,?,?)',
              (ident, row['id'], hashlib.sha256(token.encode()).hexdigest(), expires, at, int(bool(mfa))))
    return {'session_id': ident, 'token': token, 'expires_at': expires, 'user': _user(row, c), 'mfa': bool(mfa)}


def _token_digest(token):
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return None
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def resolve_session(c, token, now=None):
    digest = _token_digest(token)
    if digest is None:
        return None
    row = _one(c, '''SELECT u.id,u.username,u.role,u.enabled,s.expires_at,s.revoked,s.mfa
                    FROM identity_sessions s JOIN identity_users u ON u.id=s.user_id
                    WHERE s.token_digest=?''', (digest,))
    if (row is None or not row['enabled'] or row['revoked'] or
            row['expires_at'] <= _now(now) or row['role'] not in ROLES):
        return None
    return Principal(id=row['id'], kind='session', role=row['role'], scopes=ROLES[row['role']],
                     username=row['username'], expires_at=row['expires_at'], mfa=bool(row['mfa']))


def list_sessions(c):
    rows = _all(c, '''SELECT s.id,s.user_id,u.username,u.role,s.expires_at,s.revoked,s.created,s.mfa
                     FROM identity_sessions s JOIN identity_users u ON u.id=s.user_id
                     ORDER BY s.created DESC,s.id''')
    return [{**row, 'revoked': bool(row['revoked']), 'mfa': bool(row['mfa'])} for row in rows]


def revoke_session(c, ident):
    """Idempotently revoke an existing session; False means its record is absent."""
    _transaction(c)
    return c.execute('UPDATE identity_sessions SET revoked=1 WHERE id=?', (str(ident),)).rowcount > 0


def logout(c, token, now=None):
    _transaction(c)
    digest = _token_digest(token)
    if digest is None:
        return None
    row = _one(c, '''SELECT s.id FROM identity_sessions s JOIN identity_users u ON u.id=s.user_id
                    WHERE s.token_digest=? AND s.revoked=0 AND s.expires_at>? AND u.enabled=1''',
               (digest, _now(now)))
    if row is None:
        return None
    c.execute('UPDATE identity_sessions SET revoked=1 WHERE id=?', (row['id'],))
    return row['id']


# --------------------------------------------------------------------------- second factor (TOTP)

def _consume_second_factor(c, second, otp, at):
    """Accept a fresh TOTP step or an unused backup code; both are single-use."""
    step = totp.verify(second['secret'], otp, second['last_step'], now=at)
    if step is not None:
        c.execute('UPDATE identity_mfa SET last_step=?,updated=? WHERE user_id=?', (step, at, second['user_id']))
        return True
    digest = totp.backup_digest(otp)
    codes = json.loads(second['backup_codes'])
    matched = next((item for item in codes if digest is not None and hmac.compare_digest(item, digest)), None)
    if matched is None:
        return False
    codes.remove(matched)
    c.execute('UPDATE identity_mfa SET backup_codes=?,updated=? WHERE user_id=?', (json.dumps(codes), at, second['user_id']))
    return True


def mfa_status(c, user_id):
    row = _one(c, 'SELECT enabled,backup_codes FROM identity_mfa WHERE user_id=?', (str(user_id),))
    if row is None:
        return {'enabled': False, 'pending': False, 'backup_codes_left': 0}
    return {'enabled': bool(row['enabled']), 'pending': not row['enabled'],
            'backup_codes_left': len(json.loads(row['backup_codes'])) if row['enabled'] else 0}


def mfa_begin(c, user_id, username):
    """Create (or replace) a pending secret; an active second factor must be disabled first."""
    _transaction(c)
    current = _one(c, 'SELECT enabled FROM identity_mfa WHERE user_id=?', (str(user_id),))
    if current is not None and current['enabled']:
        raise HTTPException(409, 'Second factor is already enabled')
    secret, now = totp.new_secret(), _now()
    c.execute('INSERT OR REPLACE INTO identity_mfa VALUES(?,?,0,0,?,?,?)', (str(user_id), secret, '[]', now, now))
    return {'secret': secret, 'uri': totp.provisioning_uri(secret, username),
            'period': totp.PERIOD, 'digits': totp.DIGITS}


def mfa_enable(c, user_id, code):
    _transaction(c)
    row = _one(c, 'SELECT * FROM identity_mfa WHERE user_id=?', (str(user_id),))
    if row is None or row['enabled']:
        raise HTTPException(409, 'Start second-factor setup first')
    step = totp.verify(row['secret'], code, 0)
    if step is None:
        raise HTTPException(422, 'Invalid authenticator code')
    codes = totp.backup_codes()
    c.execute('UPDATE identity_mfa SET enabled=1,last_step=?,backup_codes=?,updated=? WHERE user_id=?',
              (step, json.dumps([totp.backup_digest(item) for item in codes]), _now(), row['user_id']))
    return {'enabled': True, 'backup_codes': codes}


def mfa_disable(c, user_id, password, code):
    """Self-service removal needs the password and a current code; revokes all sessions."""
    _transaction(c)
    user = _one(c, 'SELECT * FROM identity_users WHERE id=?', (str(user_id),))
    second = _one(c, 'SELECT * FROM identity_mfa WHERE user_id=? AND enabled=1', (str(user_id),))
    encoded = _password_bytes(password)
    if user is None or second is None:
        raise HTTPException(409, 'Second factor is not enabled')
    if encoded is None or not _verify_password(encoded, user['password_hash']) or not _consume_second_factor(c, second, code, _now()):
        raise HTTPException(401, 'Invalid credentials')
    c.execute('DELETE FROM identity_mfa WHERE user_id=?', (user['id'],))
    c.execute('UPDATE identity_sessions SET revoked=1 WHERE user_id=?', (user['id'],))
    c.execute('UPDATE identity_device_keys SET revoked=1 WHERE user_id=?', (user['id'],))
    return {'enabled': False}


def mfa_reset(c, user_id):
    """Owner recovery (lost phone): remove the factor and revoke the account's sessions."""
    _transaction(c)
    if _one(c, 'SELECT id FROM identity_users WHERE id=?', (str(user_id),)) is None:
        raise HTTPException(404, 'Account missing')
    removed = c.execute('DELETE FROM identity_mfa WHERE user_id=?', (str(user_id),)).rowcount > 0
    removed = c.execute('DELETE FROM identity_passkeys WHERE user_id=?', (str(user_id),)).rowcount > 0 or removed
    c.execute('UPDATE identity_sessions SET revoked=1 WHERE user_id=?', (str(user_id),))
    c.execute('UPDATE identity_device_keys SET revoked=1 WHERE user_id=?', (str(user_id),))
    return {'reset': removed}


# --------------------------------------------------------------------------- passkeys (WebAuthn: Face ID / Touch ID / Windows Hello)

MAX_PASSKEYS = 10


def passkey_list(c, user_id):
    return [{**row, 'transports': json.loads(row['transports'])} for row in
            _all(c, 'SELECT id,name,transports,created,last_used,rp_id FROM identity_passkeys WHERE user_id=? ORDER BY created,id', (str(user_id),))]


def passkey_credentials(c, user_id, rp_id=None):
    sql, values = 'SELECT credential_id FROM identity_passkeys WHERE user_id=?', [str(user_id)]
    if rp_id is not None:
        sql, values = sql + ' AND rp_id=?', values + [rp_id]
    return [row['credential_id'] for row in _all(c, sql, tuple(values))]


def passkey_add(c, user_id, credential_id, public_key, sign_count, name, transports, rp_id):
    _transaction(c)
    if c.execute('SELECT count(*) FROM identity_passkeys WHERE user_id=?', (str(user_id),)).fetchone()[0] >= MAX_PASSKEYS:
        raise HTTPException(409, 'Passkey limit reached; remove an old device first')
    if c.execute('SELECT 1 FROM identity_passkeys WHERE credential_id=?', (credential_id,)).fetchone():
        raise HTTPException(409, 'This passkey is already registered')
    ident = str(uuid.uuid4())
    c.execute('INSERT INTO identity_passkeys(id,user_id,credential_id,public_key,sign_count,name,transports,created,last_used,rp_id) VALUES(?,?,?,?,?,?,?,?,NULL,?)',
              (ident, str(user_id), credential_id, public_key, int(sign_count), name, json.dumps(list(transports)[:8]), _now(), rp_id))
    return next(item for item in passkey_list(c, user_id) if item['id'] == ident)


def passkey_delete(c, user_id, ident):
    _transaction(c)
    return c.execute('DELETE FROM identity_passkeys WHERE id=? AND user_id=?', (str(ident), str(user_id))).rowcount > 0


def passkey_lookup(c, credential_id, rp_id):
    """Credential registered for this RP with its enabled account, or None (unknown, other domain, disabled)."""
    row = _one(c, '''SELECT p.id passkey_id,p.public_key,p.sign_count,u.* FROM identity_passkeys p
                    JOIN identity_users u ON u.id=p.user_id WHERE p.credential_id=? AND p.rp_id=?''', (credential_id, rp_id))
    if row is None or not row['enabled'] or row['role'] not in ROLES:
        return None
    return row


def passkey_login(c, row, new_sign_count, ttl_seconds, now=None):
    """A verified passkey with user verification (Face ID/PIN) counts as two factors."""
    _transaction(c)
    at = _now(now)
    c.execute('UPDATE identity_passkeys SET sign_count=?,last_used=? WHERE id=?', (int(new_sign_count), at, row['passkey_id']))
    return _open_session(c, row, ttl_seconds, at, mfa=True)


# --------------------------------------------------------------------------- device keys (Siri shortcut on the owner's phone)
# A device key lets one phone ask questions and run the gate hands-free through the tunnel, where account
# sessions would need a fresh 2FA login. It is deliberately narrow: only the scopes below (never settings,
# memory, cameras or the owner's '*'), only for accounts that have 2FA, shown once, stored as SHA-256 and
# revoked together with the account's second factor.

DEVICE_SCOPES = frozenset({'voice:ask', 'gate:control'})
MAX_DEVICE_KEYS = 8
DEVICE_NAME = re.compile(r'^[\w ąćęłńóśźżĄĆĘŁŃÓŚŹŻ.\'’-]{1,40}$')


def _device_scopes(role):
    allowed = ROLES.get(role, frozenset())
    return DEVICE_SCOPES if '*' in allowed else DEVICE_SCOPES & allowed


def create_device_key(c, user_id, name, now=None):
    _transaction(c)
    name = (name or '').strip()
    if not DEVICE_NAME.fullmatch(name):
        raise HTTPException(422, 'Device name: 1-40 letters, digits, spaces, dots or dashes')
    user = _one(c, 'SELECT id,role,enabled FROM identity_users WHERE id=?', (str(user_id),))
    if user is None or not user['enabled']:
        raise HTTPException(404, 'Account missing')
    if c.execute('SELECT 1 FROM identity_mfa WHERE user_id=? AND enabled=1', (user['id'],)).fetchone() is None:
        raise HTTPException(409, 'Enable two-factor authentication before adding a device key')
    if not _device_scopes(user['role']):
        raise HTTPException(403, 'This role cannot use device keys')
    active = c.execute('SELECT COUNT(*) FROM identity_device_keys WHERE user_id=? AND revoked=0', (user['id'],)).fetchone()[0]
    if active >= MAX_DEVICE_KEYS:
        raise HTTPException(409, 'Too many device keys; revoke an unused one first')
    token = secrets.token_urlsafe(36)
    ident = str(uuid.uuid4())
    c.execute('INSERT INTO identity_device_keys(id,user_id,name,token_digest,created) VALUES(?,?,?,?,?)',
              (ident, user['id'], name, _token_digest(token), _now(now)))
    return {'id': ident, 'name': name, 'token': token, 'scopes': sorted(_device_scopes(user['role']))}


def list_device_keys(c, user_id):
    rows = _all(c, 'SELECT id,name,created,last_used FROM identity_device_keys WHERE user_id=? AND revoked=0 ORDER BY created',
                (str(user_id),))
    return rows


def revoke_device_key(c, user_id, ident):
    _transaction(c)
    return c.execute('UPDATE identity_device_keys SET revoked=1 WHERE id=? AND user_id=? AND revoked=0',
                     (str(ident), str(user_id))).rowcount > 0


def resolve_device_key(c, token, now=None):
    digest = _token_digest(token)
    if digest is None:
        return None
    row = _one(c, '''SELECT k.id,k.last_used,u.username,u.role,u.enabled FROM identity_device_keys k
                    JOIN identity_users u ON u.id=k.user_id WHERE k.token_digest=? AND k.revoked=0''', (digest,))
    if row is None or not row['enabled'] or row['role'] not in ROLES or not _device_scopes(row['role']):
        return None
    at = _now(now)
    if row['last_used'] is None or at - row['last_used'] > 300:  # coarse, to avoid a write per request
        c.execute('UPDATE identity_device_keys SET last_used=? WHERE id=?', (at, row['id']))
    # role 'device' on purpose: never is_owner, so the owner's "*" bypass in authenticate() cannot apply.
    return Principal(id=row['id'], kind='device', role='device', scopes=_device_scopes(row['role']), username=row['username'])

