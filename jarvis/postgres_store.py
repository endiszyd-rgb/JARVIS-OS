"""Opt-in PostgreSQL repository: explicit credentials, checked roles and local RLS.

No schema creation or network access occurs during configuration. Each operation
uses a fresh connection and one transaction, including metadata-only audit writes.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import ipaddress
import json
import os
import re
import uuid

from fastapi import HTTPException
from pydantic import SecretStr
import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


_DSN_FIELDS = {'host', 'port', 'dbname', 'user', 'password', 'sslmode', 'sslrootcert'}
_BOUNDS = (
    ('connect_timeout_seconds', 'JARVIS_POSTGRES_CONNECT_TIMEOUT_SECONDS', 1, 30, 5),
    ('statement_timeout_ms', 'JARVIS_POSTGRES_STATEMENT_TIMEOUT_MS', 100, 30000, 5000),
    ('lock_timeout_ms', 'JARVIS_POSTGRES_LOCK_TIMEOUT_MS', 100, 10000, 1000),
)
_UNAVAILABLE = 'PostgreSQL storage is unavailable or its configuration is unsafe'


def _parse_dsn(secret):
    try:
        raw = secret.get_secret_value()
        if len(raw) > 8192 or '\x00' in raw:
            raise ValueError()
        params = conninfo_to_dict(raw)
        if set(params) - _DSN_FIELDS:
            raise ValueError()
        if not params.get('dbname') or not params.get('user'):
            raise ValueError()
        host = params.get('host', '')
        if (not host or len(host) > 253 or any(ch in host for ch in ',/\\%') or
                any(ord(ch) <= 32 or ord(ch) == 127 for ch in host)):
            raise ValueError()
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            if not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                       for label in host.rstrip('.').split('.')):
                raise ValueError()
            loopback = host.lower() == 'localhost'
        if params.get('sslmode') != 'verify-full' and not (loopback and params.get('sslmode') == 'disable'):
            raise ValueError()
        if 'port' in params and (not re.fullmatch(r'[0-9]{1,5}', params['port']) or
                                 not 1 <= int(params['port']) <= 65535):
            raise ValueError()
        if 'sslrootcert' in params and (not params['sslrootcert'] or '\x00' in params['sslrootcert']):
            raise ValueError()
        return params
    except (psycopg.Error, ValueError, TypeError, UnicodeError):
        raise ValueError('Invalid JARVIS_POSTGRES_DSN; use one explicit host and verified TLS') from None


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    dsn: SecretStr | None = field(default=None, repr=False)
    connect_timeout_seconds: int = 5
    statement_timeout_ms: int = 5000
    lock_timeout_ms: int = 1000

    def __post_init__(self):
        if self.dsn is not None and not isinstance(self.dsn, SecretStr):
            raise ValueError('JARVIS_POSTGRES_DSN must use SecretStr')
        for attribute, name, low, high, _ in _BOUNDS:
            value = getattr(self, attribute)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name} must be an integer from {low} to {high}')
        if self.enabled:
            _parse_dsn(self.dsn)

    @property
    def enabled(self):
        return self.dsn is not None and bool(self.dsn.get_secret_value())

    @classmethod
    def from_env(cls):
        values = {}
        for attribute, name, _, _, default in _BOUNDS:
            try:
                values[attribute] = int(os.environ.get(name, str(default)))
            except ValueError:
                raise ValueError(f'{name} must be a bounded integer') from None
        raw = os.environ.get('JARVIS_POSTGRES_DSN', '')
        return cls(dsn=SecretStr(raw) if raw else None, **values)


def _ident(value):
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(422, 'Invalid storage identifier') from None


def _revision(value):
    if type(value) is not int or value < 0:
        raise HTTPException(422, 'Invalid storage revision')
    return value


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _content(title, payload):
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise HTTPException(422, 'Storage title must contain 1 to 200 characters')
    try:
        if not isinstance(payload, dict) or len(_json_text(payload).encode('utf-8')) > 65536:
            raise ValueError()
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise HTTPException(422, 'Storage payload must be a JSON object of at most 65536 bytes') from None
    return title, Jsonb(payload, dumps=_json_text)


class PostgresStore:
    def __init__(self, config: PostgresConfig):
        if not isinstance(config, PostgresConfig):
            raise ValueError('PostgresStore requires PostgresConfig')
        self.config = config

    @staticmethod
    def _validate_runtime(connection):
        row = connection.execute('''
            SELECT current_user AS runtime_user, session_user AS session_user,
                   r.rolsuper, r.rolbypassrls, r.rolcreatedb, r.rolcreaterole,
                   r.rolinherit, r.rolreplication,
                   a.rolsuper AS auth_super, a.rolbypassrls AS auth_bypass,
                   a.rolcreatedb AS auth_createdb, a.rolcreaterole AS auth_createrole,
                   a.rolreplication AS auth_replication,
                   pg_catalog.pg_has_role(r.oid,a.oid,'MEMBER') AS member_authenticated,
                   EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
                          WHERE (m.member=r.oid AND m.roleid<>a.oid) OR m.member=a.oid) AS extra_memberships,
                   (pg_catalog.has_schema_privilege(r.oid,'jarvis','CREATE') OR
                    pg_catalog.has_schema_privilege(a.oid,'jarvis','CREATE')) AS can_create_storage,
                   EXISTS(SELECT 1 FROM pg_catalog.pg_namespace n
                          WHERE n.nspname='jarvis' AND
                            (n.nspowner IN (r.oid,a.oid) OR EXISTS(
                              SELECT 1 FROM pg_catalog.pg_class t
                              WHERE t.relnamespace=n.oid AND t.relowner IN (r.oid,a.oid)) OR EXISTS(
                              SELECT 1 FROM pg_catalog.pg_proc f
                              WHERE f.pronamespace=n.oid AND f.proowner IN (r.oid,a.oid)))) AS owns_storage
            FROM pg_catalog.pg_roles r CROSS JOIN pg_catalog.pg_roles a
            WHERE r.rolname=current_user AND a.rolname='authenticated'
        ''').fetchone()
        flags = ('rolsuper', 'rolbypassrls', 'rolcreatedb', 'rolcreaterole', 'rolinherit',
                 'rolreplication', 'auth_super', 'auth_bypass', 'auth_createdb',
                 'auth_createrole', 'auth_replication', 'owns_storage',
                 'extra_memberships', 'can_create_storage')
        if (row is None or row['runtime_user'] != 'jarvis_runtime' or row['session_user'] != 'jarvis_runtime'
                or not row['member_authenticated'] or any(row[name] for name in flags)):
            raise HTTPException(503, _UNAVAILABLE)

    @contextmanager
    def _connection(self, subject=None):
        if not self.config.enabled:
            raise HTTPException(503, 'PostgreSQL storage is disabled')
        # PGHOSTADDR can bypass the validated hostname, notably loopback-only TLS
        # exceptions. Service files can supply parameters omitted from a DSN.
        if any(os.environ.get(name) for name in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE')):
            raise HTTPException(503, _UNAVAILABLE)
        try:
            params = _parse_dsn(self.config.dsn)
            params.setdefault('port', '5432')
            params.update(connect_timeout=self.config.connect_timeout_seconds,
                          application_name='jarvis-runtime', row_factory=dict_row,
                          options=f'-c statement_timeout={self.config.statement_timeout_ms} '
                                  f'-c lock_timeout={self.config.lock_timeout_ms}')
            with psycopg.connect(**params) as connection:
                self._validate_runtime(connection)
                connection.execute('SET LOCAL ROLE authenticated')
                connection.execute("SELECT pg_catalog.set_config('statement_timeout', %s, true)",
                                   (str(self.config.statement_timeout_ms),))
                connection.execute("SELECT pg_catalog.set_config('lock_timeout', %s, true)",
                                   (str(self.config.lock_timeout_ms),))
                claims = {} if subject is None else {'sub': str(subject)}
                connection.execute("SELECT pg_catalog.set_config('request.jwt.claims', %s, true)",
                                   (json.dumps(claims),))
                yield connection
        except HTTPException:
            raise
        except psycopg.errors.InsufficientPrivilege:
            raise HTTPException(403, 'Storage operation is not permitted') from None
        except psycopg.errors.CheckViolation:
            raise HTTPException(422, 'Storage data violates its constraints') from None
        except (psycopg.errors.UniqueViolation, psycopg.errors.SerializationFailure,
                psycopg.errors.DeadlockDetected):
            raise HTTPException(409, 'Storage operation conflicted; refresh and retry') from None
        except (psycopg.Error, ValueError, OSError):
            raise HTTPException(503, _UNAVAILABLE) from None

    def status(self):
        with self._connection() as connection:
            row = connection.execute('SELECT jarvis.schema_version() AS version').fetchone()
            if row is None or row['version'] != 1:
                raise HTTPException(503, _UNAVAILABLE)
        return {'enabled': True, 'status': 'ready', 'schema_version': 1}

    def list(self, subject, workshop_id=None, limit=50, offset=0):
        subject = _ident(subject)
        if type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or not 0 <= offset <= 100000:
            raise HTTPException(422, 'Invalid storage page')
        workshop = _ident(workshop_id) if workshop_id is not None else None
        with self._connection(subject) as connection:
            if workshop is None:
                return connection.execute('''SELECT * FROM jarvis.records
                    ORDER BY created_at DESC,id LIMIT %s OFFSET %s''', (limit, offset)).fetchall()
            return connection.execute('''SELECT * FROM jarvis.records WHERE workshop_id=%s
                ORDER BY created_at DESC,id LIMIT %s OFFSET %s''', (workshop, limit, offset)).fetchall()

    def get(self, subject, ident):
        subject, ident = _ident(subject), _ident(ident)
        with self._connection(subject) as connection:
            row = connection.execute('SELECT * FROM jarvis.records WHERE id=%s', (ident,)).fetchone()
            if row is None:
                raise HTTPException(404, 'Storage record missing')
            return row

    @staticmethod
    def _event(connection, subject, event, ident):
        connection.execute('INSERT INTO jarvis.record_events(subject,event,record_id) VALUES(%s,%s,%s)',
                           (subject, event, ident))

    def create(self, subject, title, payload, workshop_id=None):
        subject = _ident(subject)
        workshop = _ident(workshop_id) if workshop_id is not None else None
        title, payload = _content(title, payload)
        with self._connection(subject) as connection:
            row = connection.execute('''INSERT INTO jarvis.records(owner_id,workshop_id,title,payload)
                VALUES(%s,%s,%s,%s) RETURNING *''', (subject, workshop, title, payload)).fetchone()
            self._event(connection, subject, 'created', row['id'])
            return row

    @staticmethod
    def _mutation_failure(connection, ident, revision):
        row = connection.execute('SELECT revision FROM jarvis.records WHERE id=%s', (ident,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Storage record missing')
        if row['revision'] != revision:
            raise HTTPException(409, 'Storage record revision changed; refresh')
        raise HTTPException(403, 'Storage operation is not permitted')

    def update(self, subject, ident, revision, title, payload):
        subject, ident, revision = _ident(subject), _ident(ident), _revision(revision)
        title, payload = _content(title, payload)
        with self._connection(subject) as connection:
            row = connection.execute('''UPDATE jarvis.records SET title=%s,payload=%s,revision=revision+1
                WHERE id=%s AND revision=%s RETURNING *''', (title, payload, ident, revision)).fetchone()
            if row is None:
                self._mutation_failure(connection, ident, revision)
            self._event(connection, subject, 'updated', ident)
            return row

    def delete(self, subject, ident, revision):
        subject, ident, revision = _ident(subject), _ident(ident), _revision(revision)
        with self._connection(subject) as connection:
            row = connection.execute('DELETE FROM jarvis.records WHERE id=%s AND revision=%s RETURNING id',
                                     (ident, revision)).fetchone()
            if row is None:
                self._mutation_failure(connection, ident, revision)
            self._event(connection, subject, 'deleted', ident)
            return {'deleted': str(ident)}
