"""Validate optional PostgreSQL settings without DNS, sockets or database access."""
import json
import socket
import uuid

from fastapi import HTTPException
from pydantic import SecretStr
import psycopg
import pytest

from jarvis.postgres_store import PostgresConfig, PostgresStore


SENTINEL = 'postgres-config-private-sentinel'
REMOTE_DSN = (
    f'postgresql://jarvis:{SENTINEL}@db.example.test:5432/jarvis?sslmode=verify-full'
)
ENVIRONMENT = (
    'JARVIS_POSTGRES_DSN', 'JARVIS_POSTGRES_CONNECT_TIMEOUT_SECONDS',
    'JARVIS_POSTGRES_STATEMENT_TIMEOUT_MS', 'JARVIS_POSTGRES_LOCK_TIMEOUT_MS',
)
BOUNDS = (
    ('connect_timeout_seconds', 'JARVIS_POSTGRES_CONNECT_TIMEOUT_SECONDS', 1, 30),
    ('statement_timeout_ms', 'JARVIS_POSTGRES_STATEMENT_TIMEOUT_MS', 100, 30000),
    ('lock_timeout_ms', 'JARVIS_POSTGRES_LOCK_TIMEOUT_MS', 100, 10000),
)


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for key in (*ENVIRONMENT, 'PGHOST', 'PGPASSWORD', 'PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE'):
        monkeypatch.delenv(key, raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail('Configuration must not resolve hosts or open a connection')

    monkeypatch.setattr(psycopg, 'connect', forbidden)
    monkeypatch.setattr(psycopg.Connection, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)


def assert_redacted(error, *secrets):
    visible = str(error.value) + repr(error.value)
    assert SENTINEL not in visible
    for secret in secrets:
        assert secret not in visible


def test_unconfigured_backend_is_disabled_with_bounded_defaults():
    config = PostgresConfig.from_env()
    assert config.dsn is None
    assert config.enabled is False
    assert (config.connect_timeout_seconds, config.statement_timeout_ms,
            config.lock_timeout_ms) == (5, 5000, 1000)
    PostgresStore(config)


@pytest.mark.parametrize('dsn', (
    'host=127.0.0.1 user=jarvis_runtime sslmode=disable',
    'host=127.0.0.1 dbname=jarvis sslmode=disable',
    'host=127.0.0.1 sslmode=disable',
))
def test_database_and_user_cannot_be_inherited_from_ambient_settings(monkeypatch, dsn):
    monkeypatch.setenv('PGDATABASE', 'unintended_database')
    monkeypatch.setenv('PGUSER', 'unintended_user')
    with pytest.raises(ValueError):
        PostgresConfig(dsn=SecretStr(dsn))


def test_empty_environment_dsn_is_disabled(monkeypatch):
    monkeypatch.setenv('JARVIS_POSTGRES_DSN', '')
    assert PostgresConfig.from_env().enabled is False


def test_environment_dsn_is_secret_and_configuration_and_store_repr_are_redacted(monkeypatch):
    monkeypatch.setenv('JARVIS_POSTGRES_DSN', REMOTE_DSN)
    config = PostgresConfig.from_env()
    assert config.enabled is True
    assert isinstance(config.dsn, SecretStr)
    assert config.dsn.get_secret_value() == REMOTE_DSN
    store = PostgresStore(config)
    for visible in (str(config), repr(config), str(store), repr(store)):
        assert SENTINEL not in visible
        assert REMOTE_DSN not in visible


@pytest.mark.parametrize('field,environment,low,high', BOUNDS)
@pytest.mark.parametrize('boundary', ('low', 'high'))
def test_integer_boundaries_are_accepted_directly_and_from_environment(
        monkeypatch, field, environment, low, high, boundary):
    value = low if boundary == 'low' else high
    assert getattr(PostgresConfig(**{field: value}), field) == value
    monkeypatch.setenv(environment, str(value))
    assert getattr(PostgresConfig.from_env(), field) == value


@pytest.mark.parametrize('field,environment,low,high', BOUNDS)
@pytest.mark.parametrize('boundary', ('below', 'above'))
def test_out_of_range_integers_are_rejected_even_when_backend_is_disabled(
        monkeypatch, field, environment, low, high, boundary):
    value = low - 1 if boundary == 'below' else high + 1
    with pytest.raises(ValueError):
        PostgresConfig(**{field: value})
    monkeypatch.setenv(environment, str(value))
    with pytest.raises(ValueError):
        PostgresConfig.from_env()


@pytest.mark.parametrize('field,environment,low,high', BOUNDS)
@pytest.mark.parametrize('value', (True, False, 5.0, '5', None))
def test_constructor_requires_actual_integers(field, environment, low, high, value):
    with pytest.raises(ValueError):
        PostgresConfig(**{field: value})


@pytest.mark.parametrize('field,environment,low,high', BOUNDS)
@pytest.mark.parametrize('value', ('', '5.5', 'nan', SENTINEL))
def test_bad_environment_integer_does_not_echo_the_value(
        monkeypatch, field, environment, low, high, value):
    monkeypatch.setenv(environment, value)
    with pytest.raises(ValueError) as error:
        PostgresConfig.from_env()
    assert_redacted(error)


@pytest.mark.parametrize('dsn', (
    REMOTE_DSN,
    f'host=db.example.test dbname=jarvis user=jarvis password={SENTINEL} sslmode=verify-full',
    f'host=192.0.2.10 dbname=jarvis user=jarvis password={SENTINEL} sslmode=verify-full',
    f'host=2001:db8::1 dbname=jarvis user=jarvis password={SENTINEL} sslmode=verify-full',
))
def test_verified_remote_uri_and_conninfo_are_accepted_without_dns(dsn):
    config = PostgresConfig(dsn=SecretStr(dsn))
    assert config.enabled is True
    PostgresStore(config)


@pytest.mark.parametrize('host', ('localhost', '127.0.0.1', '127.0.0.2', '::1'))
def test_literal_loopback_and_localhost_can_explicitly_disable_tls(host):
    dsn = f'host={host} dbname=jarvis user=jarvis password={SENTINEL} sslmode=disable'
    assert PostgresConfig(dsn=SecretStr(dsn)).enabled is True


@pytest.mark.parametrize('mode', ('disable', 'allow', 'prefer', 'require', 'verify-ca'))
def test_remote_connections_require_verified_hostname_tls(mode):
    dsn = f'host=db.example.test password={SENTINEL} sslmode={mode}'
    with pytest.raises(ValueError) as error:
        PostgresConfig(dsn=SecretStr(dsn))
    assert_redacted(error, dsn)


@pytest.mark.parametrize('field', (
    'hostaddr=192.0.2.11', 'connect_timeout=30', 'application_name=other',
    'target_session_attrs=any', 'sslcert=/tmp/client-cert.pem',
))
def test_dsn_cannot_override_connection_policy_with_extra_libpq_fields(field):
    dsn = f'host=db.example.test password={SENTINEL} sslmode=verify-full {field}'
    with pytest.raises(ValueError) as error:
        PostgresConfig(dsn=SecretStr(dsn))
    assert_redacted(error, dsn)


@pytest.mark.parametrize('port', ('0', '-1', '65536', '5432,5433', 'private-port'))
def test_port_must_be_one_bounded_integer(port):
    dsn = f'host=db.example.test port={port} password={SENTINEL} sslmode=verify-full'
    with pytest.raises(ValueError) as error:
        PostgresConfig(dsn=SecretStr(dsn))
    assert_redacted(error, dsn)


@pytest.mark.parametrize('host', (
    'localhost.example.test', '127.0.0.1.example.test', '192.168.1.10', '0.0.0.0', '::',
))
def test_nonloopback_hosts_do_not_receive_the_local_tls_exception(host):
    dsn = f'host={host} password={SENTINEL} sslmode=disable'
    with pytest.raises(ValueError) as error:
        PostgresConfig(dsn=SecretStr(dsn))
    assert_redacted(error, dsn)


@pytest.mark.parametrize('dsn', (
    f'host=db.example.test password={SENTINEL}',
    f'password={SENTINEL} sslmode=verify-full',
    f'host=/tmp/{SENTINEL} sslmode=disable',
    f'host=@/tmp/{SENTINEL} sslmode=disable',
    f"host='db.example.test,other.example.test' password={SENTINEL} sslmode=verify-full",
    f"host='db.example.test other.example.test' password={SENTINEL} sslmode=verify-full",
    f'host=db.example.test/path password={SENTINEL} sslmode=verify-full',
    f'host=db.example.test password={SENTINEL} sslmode=verify-full service=private-service',
    f'host=db.example.test password={SENTINEL} sslmode=verify-full passfile=/tmp/private-passfile',
    f"host=db.example.test password={SENTINEL} sslmode=verify-full options='-c search_path=public'",
    f"host=db.example.test password='{SENTINEL} sslmode=verify-full",
    f'postgresql://jarvis:{SENTINEL}@db.example.test:bad/jarvis?sslmode=verify-full',
))
def test_unsafe_or_malformed_dsn_is_rejected_without_secret_echo(dsn):
    with pytest.raises(ValueError) as error:
        PostgresConfig(dsn=SecretStr(dsn))
    assert_redacted(error, dsn)


def test_direct_configuration_rejects_plain_string_secret_without_echo():
    with pytest.raises(ValueError) as error:
        PostgresConfig(dsn=REMOTE_DSN)
    assert_redacted(error, REMOTE_DSN)


def test_environment_invalid_dsn_errors_are_redacted(monkeypatch):
    dsn = f'postgresql://jarvis:{SENTINEL}@db.example.test/jarvis?sslmode=disable'
    monkeypatch.setenv('JARVIS_POSTGRES_DSN', dsn)
    with pytest.raises(ValueError) as error:
        PostgresConfig.from_env()
    assert_redacted(error, dsn)


def test_explicit_root_certificate_file_is_accepted_without_connecting(tmp_path):
    certificate = tmp_path / 'synthetic-root.pem'
    certificate.write_text('Synthetic test content; no TLS handshake is performed.\n')
    dsn = (f"host=db.example.test dbname=jarvis user=jarvis_runtime password={SENTINEL} sslmode=verify-full "
           f"sslrootcert='{certificate}'")
    assert PostgresConfig(dsn=SecretStr(dsn)).enabled is True


def test_ambient_libpq_variables_do_not_enable_an_unconfigured_backend(monkeypatch):
    monkeypatch.setenv('PGHOST', 'db.example.test')
    monkeypatch.setenv('PGPASSWORD', SENTINEL)
    monkeypatch.setenv('PGSERVICE', 'ambient-service')
    assert PostgresConfig.from_env().enabled is False


def test_dsn_without_host_cannot_inherit_an_ambient_host(monkeypatch):
    monkeypatch.setenv('PGHOST', 'db.example.test')
    monkeypatch.setenv('JARVIS_POSTGRES_DSN', f'password={SENTINEL} sslmode=verify-full')
    with pytest.raises(ValueError) as error:
        PostgresConfig.from_env()
    assert_redacted(error)


RUNTIME_FLAGS = (
    'rolsuper', 'rolbypassrls', 'rolcreatedb', 'rolcreaterole', 'rolinherit',
    'rolreplication', 'auth_super', 'auth_bypass', 'auth_createdb',
    'auth_createrole', 'auth_replication', 'owns_storage', 'extra_memberships',
    'can_create_storage',
)
DEFAULT_RUNTIME = object()


class FakeCursor:
    def __init__(self, row=None, rows=()):
        self.row, self.rows = row, rows

    def fetchone(self):
        return self.row

    def fetchall(self):
        return list(self.rows)


class FakeConnection:
    """Model psycopg's transaction/close boundary, without simulating SQL/RLS."""
    def __init__(self, runtime=DEFAULT_RUNTIME, version=1, failure=None):
        self.runtime = ({**dict.fromkeys(RUNTIME_FLAGS, False),
                         'runtime_user': 'jarvis_runtime', 'session_user': 'jarvis_runtime',
                         'member_authenticated': True} if runtime is DEFAULT_RUNTIME else runtime)
        self.version, self.failure = version, failure
        self.calls = []
        self.entered = self.committed = self.rolled_back = self.closed = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, kind, value, traceback):
        self.committed = kind is None
        self.rolled_back = kind is not None
        self.closed = True
        return False

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        if 'current_user AS runtime_user' in sql:
            return FakeCursor(self.runtime)
        if 'jarvis.schema_version()' in sql:
            if self.failure is not None:
                raise self.failure
            return FakeCursor(None if self.version is None else {'version': self.version})
        return FakeCursor()


def fake_connect(monkeypatch, *connections):
    pending = iter(connections)
    calls = []

    def connect(**parameters):
        calls.append(parameters)
        return next(pending)

    monkeypatch.setattr(psycopg, 'connect', connect)
    return calls


def test_disabled_status_returns_503_without_connecting():
    with pytest.raises(HTTPException) as error:
        PostgresStore(PostgresConfig()).status()
    assert error.value.status_code == 503


def test_status_checks_runtime_and_schema_in_one_transaction_with_bounded_settings(monkeypatch):
    connection = FakeConnection()
    calls = fake_connect(monkeypatch, connection)
    config = PostgresConfig(dsn=SecretStr(REMOTE_DSN), connect_timeout_seconds=3,
                            statement_timeout_ms=700, lock_timeout_ms=200)
    assert PostgresStore(config).status() == {'enabled': True, 'status': 'ready', 'schema_version': 1}
    assert len(calls) == 1
    assert calls[0]['host'] == 'db.example.test'
    assert calls[0]['sslmode'] == 'verify-full'
    assert calls[0]['connect_timeout'] == 3
    assert calls[0]['application_name'] == 'jarvis-runtime'
    assert 'statement_timeout=700' in calls[0]['options']
    assert 'lock_timeout=200' in calls[0]['options']
    sql = [statement for statement, _ in connection.calls]
    assert 'current_user AS runtime_user' in sql[0]
    assert sql[1] == 'SET LOCAL ROLE authenticated'
    assert sql[-1] == 'SELECT jarvis.schema_version() AS version'
    settings = {statement.split("'")[1]: parameters
                for statement, parameters in connection.calls if 'set_config(' in statement}
    assert settings == {'statement_timeout': ('700',), 'lock_timeout': ('200',),
                        'request.jwt.claims': ('{}',)}
    assert all(', true)' in statement for statement in sql if 'set_config(' in statement)
    assert connection.entered and connection.committed and connection.closed
    assert not connection.rolled_back


def test_claims_are_bound_transaction_local_and_do_not_leak_to_the_next_operation(monkeypatch):
    subject = uuid.uuid4()
    private, public = FakeConnection(), FakeConnection()
    calls = fake_connect(monkeypatch, private, public)
    store = PostgresStore(PostgresConfig(dsn=SecretStr(REMOTE_DSN)))
    assert store.list(subject, limit=7, offset=3) == []
    assert store.status()['status'] == 'ready'
    assert len(calls) == 2
    for connection, expected in ((private, {'sub': str(subject)}), (public, {})):
        claims = [(sql, params) for sql, params in connection.calls if "'request.jwt.claims'" in sql]
        assert len(claims) == 1
        assert json.loads(claims[0][1][0]) == expected
        assert str(subject) not in claims[0][0]
        assert ', true)' in claims[0][0]
        assert connection.committed and connection.closed
    query, parameters = private.calls[-1]
    assert 'LIMIT %s OFFSET %s' in query and parameters == (7, 3)


@pytest.mark.parametrize('unsafe_flag', RUNTIME_FLAGS)
def test_unsafe_runtime_privileges_are_rejected_before_role_claims_or_storage_queries(monkeypatch, unsafe_flag):
    connection = FakeConnection()
    connection.runtime[unsafe_flag] = True
    fake_connect(monkeypatch, connection)
    with pytest.raises(HTTPException) as error:
        PostgresStore(PostgresConfig(dsn=SecretStr(REMOTE_DSN))).status()
    assert error.value.status_code == 503
    assert len(connection.calls) == 1
    assert connection.rolled_back and connection.closed and not connection.committed
    assert_redacted(error)


@pytest.mark.parametrize('field,value', (
    ('runtime_user', 'postgres'), ('session_user', 'postgres'), ('member_authenticated', False),
))
def test_wrong_runtime_identity_or_missing_authenticated_membership_fails_closed(monkeypatch, field, value):
    connection = FakeConnection()
    connection.runtime[field] = value
    fake_connect(monkeypatch, connection)
    with pytest.raises(HTTPException) as error:
        PostgresStore(PostgresConfig(dsn=SecretStr(REMOTE_DSN))).status()
    assert error.value.status_code == 503
    assert len(connection.calls) == 1
    assert connection.rolled_back and connection.closed


def test_absent_runtime_role_metadata_fails_closed(monkeypatch):
    connection = FakeConnection(runtime=None)
    fake_connect(monkeypatch, connection)
    with pytest.raises(HTTPException) as error:
        PostgresStore(PostgresConfig(dsn=SecretStr(REMOTE_DSN))).status()
    assert error.value.status_code == 503
    assert len(connection.calls) == 1
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize('version', (None, 0, 2))
def test_schema_mismatch_rolls_back_and_closes_the_connection(monkeypatch, version):
    connection = FakeConnection(version=version)
    fake_connect(monkeypatch, connection)
    with pytest.raises(HTTPException) as error:
        PostgresStore(PostgresConfig(dsn=SecretStr(REMOTE_DSN))).status()
    assert error.value.status_code == 503
    assert connection.rolled_back and connection.closed and not connection.committed


@pytest.mark.parametrize('environment', ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE'))
def test_ambient_connection_overrides_are_rejected_before_connect(monkeypatch, environment):
    monkeypatch.setenv(environment, SENTINEL)
    with pytest.raises(HTTPException) as error:
        PostgresStore(PostgresConfig(dsn=SecretStr(REMOTE_DSN))).status()
    assert error.value.status_code == 503
    assert_redacted(error)


def test_connection_error_is_redacted_before_leaving_the_repository(monkeypatch):
    def fail_connect(**parameters):
        raise psycopg.OperationalError(f'connection failed: {REMOTE_DSN}')

    monkeypatch.setattr(psycopg, 'connect', fail_connect)
    with pytest.raises(HTTPException) as error:
        PostgresStore(PostgresConfig(dsn=SecretStr(REMOTE_DSN))).status()
    assert error.value.status_code == 503
    assert_redacted(error, REMOTE_DSN)


def test_query_error_rolls_back_closes_and_redacts_backend_details(monkeypatch):
    connection = FakeConnection(failure=psycopg.OperationalError(f'backend detail: {SENTINEL}'))
    fake_connect(monkeypatch, connection)
    with pytest.raises(HTTPException) as error:
        PostgresStore(PostgresConfig(dsn=SecretStr(REMOTE_DSN))).status()
    assert error.value.status_code == 503
    assert_redacted(error)
    assert connection.rolled_back and connection.closed and not connection.committed
