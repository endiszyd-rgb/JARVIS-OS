"""Local identities use synthetic data and participate in the caller's transaction."""
from contextlib import closing
import hashlib
import json
import sqlite3
import uuid

from fastapi import HTTPException
import pytest

from jarvis import identity

PASSWORD = 'Synthetic Password! 123'
USER_FIELDS = {'id', 'username', 'role', 'enabled', 'revision', 'created', 'updated'}
SESSION_FIELDS = {'id', 'user_id', 'username', 'role', 'expires_at', 'revoked', 'created'}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'identities.db'
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        identity.install(connection)
        connection.commit()
        connection.execute('BEGIN IMMEDIATE')
        yield connection, path


def create(connection, username='test.user', role='observer'):
    return identity.create_user(connection, username, PASSWORD, role)


def login(connection, username='test.user', now=100.0, ttl=60):
    result = identity.issue_session(connection, username, PASSWORD, ttl, now=now)
    assert result is not None
    return result


def assert_http(code, function, *args, **kwargs):
    with pytest.raises(HTTPException) as rejected:
        function(*args, **kwargs)
    assert rejected.value.status_code == code
    return rejected.value


def test_passwords_are_salted_and_public_user_data_has_no_hash(db):
    connection, _ = db
    first, second = create(connection), create(connection, username='another.user')
    assert set(first) == USER_FIELDS and set(second) == USER_FIELDS
    assert first['id'] != second['id'] and first['revision'] == 0
    assert first['enabled'] is True
    rows = connection.execute('SELECT password_hash FROM identity_users ORDER BY username').fetchall()
    assert rows[0]['password_hash'] != rows[1]['password_hash']
    assert all(len(row['password_hash']) > 64 for row in rows)
    assert PASSWORD not in '\n'.join(connection.iterdump())
    listed = identity.list_users(connection)
    assert {item['id'] for item in listed} == {first['id'], second['id']}
    assert all(set(item) == USER_FIELDS for item in listed)
    assert 'password_hash' not in json.dumps(listed)


@pytest.mark.parametrize('username', ['ab', 'Uppercase', 'a b', "x'; DROP TABLE identity_users;--", 'a' * 65])
def test_invalid_usernames_cannot_change_database_or_echo_credentials(db, username):
    connection, _ = db
    rejected = assert_http(422, identity.create_user, connection, username, PASSWORD, 'observer')
    assert PASSWORD not in str(rejected.detail)
    assert identity.list_users(connection) == []


@pytest.mark.parametrize('password', ['short', '', 'x' * 257])
def test_password_length_is_validated_without_echoing_it(db, password):
    connection, _ = db
    rejected = assert_http(422, identity.create_user, connection, 'test.user', password, 'observer')
    assert password == '' or password not in str(rejected.detail)
    assert identity.list_users(connection) == []


def test_invalid_role_and_duplicate_username_are_rejected_without_partial_insert(db):
    connection, _ = db
    assert_http(422, identity.create_user, connection, 'test.user', PASSWORD, 'superuser')
    first = create(connection)
    assert_http(409, identity.create_user, connection, 'test.user', PASSWORD, 'owner')
    assert identity.list_users(connection) == [first]


@pytest.mark.parametrize('role,scopes', [
    ('owner', {'*'}), ('observer', {'status:read'}),
    ('home_reader', {'status:read', 'home:read'}),
    ('workshop_reader', {'status:read', 'workshop:read'}),
    ('automation_runner', {'status:read', 'scheduler:tick'}),
])
def test_session_resolves_current_identity_and_only_its_role_scopes(db, role, scopes):
    connection, _ = db
    user = create(connection, role=role)
    issued = login(connection)
    principal = identity.resolve_session(connection, issued['token'], now=101)
    assert principal.id == user['id'] and principal.kind == 'session'
    assert principal.username == user['username'] and principal.role == role
    assert principal.scopes == frozenset(scopes)
    assert principal.is_owner is (role == 'owner')
    assert principal.expires_at == issued['expires_at'] == 160.0
    assert set(issued) == {'session_id', 'token', 'expires_at', 'user'}
    assert set(issued['user']) == USER_FIELDS
    assert issued['user']['id'] == user['id']


def test_sessions_store_only_a_digest_and_public_list_excludes_secrets(db):
    connection, _ = db
    create(connection)
    first, second = login(connection), login(connection)
    assert first['session_id'] != second['session_id']
    assert first['token'] != second['token'] and len(first['token']) >= 32
    stored = connection.execute('SELECT token_digest FROM identity_sessions WHERE id=?', (first['session_id'],)).fetchone()
    assert stored['token_digest'] == hashlib.sha256(first['token'].encode()).hexdigest()
    dump = '\n'.join(connection.iterdump())
    assert first['token'] not in dump and second['token'] not in dump and PASSWORD not in dump
    listed = identity.list_sessions(connection)
    assert len(listed) == 2 and all(set(row) == SESSION_FIELDS for row in listed)
    serialized = json.dumps(listed)
    for secret in (first['token'], second['token'], PASSWORD, stored['token_digest']):
        assert secret not in serialized


def test_bad_password_unknown_username_and_disabled_account_fail_generically(db, monkeypatch):
    connection, _ = db
    user = create(connection)
    calls = []
    original = identity.hashlib.pbkdf2_hmac

    def observed(*args, **kwargs):
        calls.append((args[0], args[3]))
        return original(*args, **kwargs)

    monkeypatch.setattr(identity.hashlib, 'pbkdf2_hmac', observed)
    assert identity.issue_session(connection, user['username'], 'Wrong Password! 123', 60, now=100) is None
    assert identity.issue_session(connection, 'unknown.user', PASSWORD, 60, now=100) is None
    identity.change_user(connection, user['id'], 0, enabled=False)
    assert identity.issue_session(connection, user['username'], PASSWORD, 60, now=100) is None
    assert calls == [('sha256', 600000)] * 3
    assert identity.list_sessions(connection) == []


@pytest.mark.parametrize('now,present', [(159.999, True), (160.0, False), (161.0, False)])
def test_session_expiry_has_no_grace_period_at_the_boundary(db, now, present):
    connection, _ = db
    create(connection)
    issued = login(connection)
    assert (identity.resolve_session(connection, issued['token'], now=now) is not None) is present


@pytest.mark.parametrize('token', [None, '', 'x' * 257, 123, 'ą' * 40, "'; DROP TABLE identity_users;--"])
def test_malformed_or_unknown_tokens_fail_closed(db, token):
    connection, _ = db
    create(connection)
    assert identity.resolve_session(connection, token, now=100) is None
    assert len(identity.list_users(connection)) == 1


def test_owner_revocation_and_logout_invalidate_only_the_target_session(db):
    connection, _ = db
    create(connection)
    first = identity.issue_session(connection, 'test.user', PASSWORD, 3600)
    second = identity.issue_session(connection, 'test.user', PASSWORD, 3600)
    assert identity.revoke_session(connection, first['session_id']) is True
    assert identity.resolve_session(connection, first['token']) is None
    assert identity.resolve_session(connection, second['token']) is not None
    assert identity.logout(connection, second['token']) == second['session_id']
    assert identity.logout(connection, second['token']) is None
    assert identity.resolve_session(connection, second['token']) is None
    assert identity.revoke_session(connection, str(uuid.uuid4())) is False


def test_expired_session_cannot_be_used_for_logout(db):
    connection, _ = db
    create(connection)
    issued = login(connection, now=0.0, ttl=1)
    assert identity.logout(connection, issued['token']) is None


def test_role_change_revokes_all_sessions_and_rejects_stale_updates(db):
    connection, _ = db
    user = create(connection, role='owner')
    first, second = login(connection), login(connection)
    changed = identity.change_user(connection, user['id'], 0, role='home_reader')
    assert changed['revision'] == 1 and changed['role'] == 'home_reader'
    assert set(changed) == USER_FIELDS
    assert identity.resolve_session(connection, first['token'], now=101) is None
    assert identity.resolve_session(connection, second['token'], now=101) is None
    assert_http(409, identity.change_user, connection, user['id'], 0, role='owner')
    assert identity.list_users(connection)[0] == changed
    third = login(connection)
    assert identity.resolve_session(connection, third['token'], now=101).scopes == frozenset({'status:read', 'home:read'})


def test_disabling_user_revokes_sessions_and_prevents_new_ones(db):
    connection, _ = db
    user = create(connection)
    issued = login(connection)
    disabled = identity.change_user(connection, user['id'], 0, enabled=False)
    assert disabled['enabled'] is False
    assert identity.resolve_session(connection, issued['token'], now=101) is None
    assert identity.issue_session(connection, user['username'], PASSWORD, 60, now=101) is None
    enabled = identity.change_user(connection, user['id'], 1, enabled=True)
    assert enabled['revision'] == 2
    assert identity.resolve_session(connection, issued['token'], now=101) is None
    assert login(connection)['user']['enabled'] is True


@pytest.mark.parametrize('enabled', [0, 1, 'true', 'false'])
def test_user_enabled_flag_does_not_coerce_other_types(db, enabled):
    connection, _ = db
    user = create(connection)
    assert_http(422, identity.change_user, connection, user['id'], 0, enabled=enabled)
    assert identity.list_users(connection)[0] == user


@pytest.mark.parametrize('ttl', [0, -1, 86401, True, 1.5, '60'])
def test_session_lifetime_requires_a_bounded_integer(db, ttl):
    connection, _ = db
    create(connection)
    with pytest.raises(ValueError):
        identity.issue_session(connection, 'test.user', PASSWORD, ttl, now=100)
    assert identity.list_sessions(connection) == []


def test_helpers_do_not_commit_or_open_an_independent_transaction(db):
    connection, path = db
    user = create(connection)
    issued = login(connection)
    identity.change_user(connection, user['id'], 0, role='home_reader')
    assert connection.in_transaction
    with closing(sqlite3.connect(path)) as observer:
        assert observer.execute('SELECT count(*) FROM identity_users').fetchone()[0] == 0
        assert observer.execute('SELECT count(*) FROM identity_sessions').fetchone()[0] == 0
    connection.rollback()
    assert identity.list_users(connection) == [] and identity.list_sessions(connection) == []
    assert identity.resolve_session(connection, issued['token'], now=101) is None


def test_outer_rollback_restores_existing_user_and_its_sessions(db):
    connection, _ = db
    user = create(connection, role='owner')
    issued = login(connection)
    connection.commit()
    connection.execute('BEGIN IMMEDIATE')
    identity.change_user(connection, user['id'], 0, enabled=False)
    assert identity.resolve_session(connection, issued['token'], now=101) is None
    connection.rollback()
    restored = identity.list_users(connection)[0]
    assert restored['enabled'] is True and restored['revision'] == 0
    assert identity.resolve_session(connection, issued['token'], now=101).is_owner


def test_mutation_helpers_require_the_callers_active_transaction(db):
    connection, _ = db
    connection.rollback()
    with pytest.raises(ValueError, match='transaction'):
        create(connection)
    assert not connection.in_transaction
    assert identity.list_users(connection) == []


def test_session_cap_revokes_the_oldest_active_token(db):
    connection, _ = db
    create(connection)
    issued = [login(connection, now=100 + index, ttl=1000) for index in range(17)]
    assert identity.resolve_session(connection, issued[0]['token'], now=200) is None
    assert identity.resolve_session(connection, issued[1]['token'], now=200) is not None
    assert identity.resolve_session(connection, issued[-1]['token'], now=200) is not None
    rows = identity.list_sessions(connection)
    assert len(rows) <= 17
    assert sum(not row['revoked'] for row in rows) == 16


def test_user_capacity_is_enforced_without_changing_existing_accounts(db):
    connection, _ = db
    first = create(connection)
    connection.executemany('''INSERT INTO identity_users(id,username,password_hash,role,enabled,revision,created,updated)
        SELECT ?,?,password_hash,role,enabled,revision,created,updated FROM identity_users WHERE id=?''',
        [(str(uuid.uuid4()), 'user' + str(index), first['id']) for index in range(255)])
    assert len(identity.list_users(connection)) == 256
    assert_http(409, identity.create_user, connection, 'over.capacity', PASSWORD, 'observer')
    assert len(identity.list_users(connection)) == 256
