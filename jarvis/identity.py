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
    'operator': frozenset({'status:read', 'gate:control', 'voice:command', 'cameras:view'}),
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
    c.execute('DELETE FROM identity_sessions WHERE expires_at<=? OR revoked=1', (at,))
    active = _all(c, 'SELECT id FROM identity_sessions WHERE user_id=? AND revoked=0 ORDER BY created,id',
                  (row['id'],))
    if len(active) >= MAX_ACTIVE_SESSIONS:
        # Keep the limit even if an imported database previously exceeded it.
        c.executemany('UPDATE identity_sessions SET revoked=1 WHERE id=?',
                      [(item['id'],) for item in active[:len(active) - MAX_ACTIVE_SESSIONS + 1]])
    ident, token, expires = str(uuid.uuid4()), secrets.token_urlsafe(32), at + ttl_seconds
    c.execute('INSERT INTO identity_sessions(id,user_id,token_digest,expires_at,revoked,created,mfa) VALUES(?,?,?,?,0,?,?)',
              (ident, row['id'], hashlib.sha256(token.encode()).hexdigest(), expires, at, int(second is not None)))
    return {'session_id': ident, 'token': token, 'expires_at': expires, 'user': _user(row, c), 'mfa': second is not None}


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
    return {'enabled': False}


def mfa_reset(c, user_id):
    """Owner recovery (lost phone): remove the factor and revoke the account's sessions."""
    _transaction(c)
    if _one(c, 'SELECT id FROM identity_users WHERE id=?', (str(user_id),)) is None:
        raise HTTPException(404, 'Account missing')
    removed = c.execute('DELETE FROM identity_mfa WHERE user_id=?', (str(user_id),)).rowcount > 0
    c.execute('UPDATE identity_sessions SET revoked=1 WHERE user_id=?', (str(user_id),))
    return {'reset': removed}
