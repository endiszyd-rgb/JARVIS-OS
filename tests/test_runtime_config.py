"""Runtime configuration and readiness use synthetic local databases only."""
from contextlib import closing
from pathlib import Path
import os
import socket
import sqlite3

from pydantic import SecretStr
import pytest

from jarvis.runtime_config import RuntimeConfig, readiness


KEY = 'synthetic-owner-key-for-runtime-tests'


@pytest.fixture(autouse=True)
def clear_runtime_env(monkeypatch):
    for name in ('JARVIS_DB', 'JARVIS_API_KEY', 'JARVIS_SQLITE_TIMEOUT_SECONDS'):
        monkeypatch.delenv(name, raising=False)


def database(path, schema=11):
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(f'PRAGMA user_version={schema}')
        connection.execute('CREATE TABLE fixture(value TEXT)')
        connection.commit()
    return path


def test_defaults_are_local_and_owner_is_unconfigured():
    config = RuntimeConfig.from_env()
    assert config.database_path == Path('data/jarvis.db')
    assert config.sqlite_timeout_seconds == 15.0
    assert isinstance(config.api_key, SecretStr)
    assert not config.owner_key_configured


def test_environment_and_explicit_values_preserve_secret_masking(monkeypatch, tmp_path):
    monkeypatch.setenv('JARVIS_DB', str(tmp_path / 'environment.db'))
    monkeypatch.setenv('JARVIS_API_KEY', KEY)
    monkeypatch.setenv('JARVIS_SQLITE_TIMEOUT_SECONDS', '0.25')
    configured = RuntimeConfig.from_env()
    assert configured.database_path == tmp_path / 'environment.db'
    assert configured.api_key.get_secret_value() == KEY
    assert configured.sqlite_timeout_seconds == 0.25
    assert configured.owner_key_configured
    assert KEY not in repr(configured)
    assert KEY not in str(configured.api_key)
    override = RuntimeConfig.from_env(db_path=tmp_path / 'explicit.db', api_key='')
    assert override.database_path == tmp_path / 'explicit.db'
    assert override.api_key.get_secret_value() == ''
    assert not override.owner_key_configured


@pytest.mark.parametrize('value', ['', ' ', 'bad-timeout-secret', '0', '-1', '60.01', 'nan', 'NaN', 'inf', '-inf', '1e309'])
def test_bad_timeout_has_generic_error(monkeypatch, value):
    monkeypatch.setenv('JARVIS_SQLITE_TIMEOUT_SECONDS', value)
    with pytest.raises(ValueError, match='JARVIS_SQLITE_TIMEOUT_SECONDS') as error:
        RuntimeConfig.from_env(api_key=KEY)
    assert KEY not in str(error.value)
    assert 'bad-timeout-secret' not in str(error.value)


@pytest.mark.parametrize('value', ['', '   ', '\x00bad'])
def test_bad_database_path_rejected_without_disclosing_input(monkeypatch, value):
    if '\x00' not in value:
        monkeypatch.setenv('JARVIS_DB', value)
        create = RuntimeConfig.from_env
    else:
        create = lambda: RuntimeConfig.from_env(db_path=value)
    with pytest.raises(ValueError, match='JARVIS_DB') as error:
        create()
    assert '\x00bad' not in str(error.value)


def test_explicit_empty_path_does_not_fall_back_to_environment(monkeypatch, tmp_path):
    monkeypatch.setenv('JARVIS_DB', str(tmp_path / 'valid.db'))
    with pytest.raises(ValueError, match='JARVIS_DB'):
        RuntimeConfig.from_env(db_path='')


@pytest.mark.parametrize('key,configured', [
    ('a' * 23, False), ('a' * 24, True), ('a' * 256, True), ('a' * 257, False),
    ('replace-' + 'a' * 30, False), ('ą' * 24, False), ('', False),
])
def test_owner_key_boundaries_fail_closed(key, configured):
    assert RuntimeConfig.from_env(api_key=key).owner_key_configured is configured


def test_ready_checks_schema_without_network_or_mutation(monkeypatch, tmp_path):
    # Windows forbids '?' in filenames; retain spaces and URI delimiters.
    name = 'data #% database.db' if os.name == 'nt' else 'data ?#% database.db'
    path = database(tmp_path / name)
    before = path.read_bytes()
    entries = set(tmp_path.iterdir())

    def forbidden(*args, **kwargs):
        pytest.fail('Readiness attempted network access')

    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    config = RuntimeConfig.from_env(db_path=path, api_key=KEY)
    assert readiness(config) == {
        'status': 'ready', 'checks': {'owner_key': True, 'database': True},
        'optional_integrations_probed': False,
    }
    assert path.read_bytes() == before
    assert set(tmp_path.iterdir()) == entries


@pytest.mark.parametrize('kind', ['missing', 'directory', 'corrupt', 'old_schema', 'new_schema'])
def test_unavailable_database_is_generic_and_never_created(tmp_path, kind):
    path = tmp_path / 'private-database-location.db'
    if kind == 'directory':
        path.mkdir()
    elif kind == 'corrupt':
        path.write_bytes(b'not a SQLite database')
    elif kind in ('old_schema', 'new_schema'):
        database(path, 10 if kind == 'old_schema' else 12)
    before = set(tmp_path.iterdir())
    result = readiness(RuntimeConfig.from_env(db_path=path, api_key=KEY))
    assert result == {
        'status': 'not_ready', 'checks': {'owner_key': True, 'database': False},
        'optional_integrations_probed': False,
    }
    assert str(path) not in str(result)
    assert KEY not in str(result)
    assert set(tmp_path.iterdir()) == before


def test_empty_owner_key_keeps_database_check_independent(tmp_path):
    path = database(tmp_path / 'valid.db')
    result = readiness(RuntimeConfig.from_env(db_path=path, api_key=''))
    assert result['status'] == 'not_ready'
    assert result['checks'] == {'owner_key': False, 'database': True}


def test_expected_schema_can_be_overridden(tmp_path):
    path = database(tmp_path / 'schema12.db', 12)
    assert readiness(RuntimeConfig.from_env(db_path=path, api_key=KEY), expected_schema=12)['status'] == 'ready'


@pytest.mark.parametrize('timeout,expected_timeout', [('60', 2.0), ('0.01', 0.01)])
@pytest.mark.parametrize('schema', [10, 11])
def test_probe_uses_read_only_uri_bounded_timeout_and_closes_connections(monkeypatch, tmp_path, timeout, expected_timeout, schema):
    path = database(tmp_path / 'valid.db', schema)
    monkeypatch.setenv('JARVIS_SQLITE_TIMEOUT_SECONDS', timeout)
    real_connect = sqlite3.connect
    opened = []

    def inspected_connect(database_uri, **kwargs):
        assert database_uri.startswith('file:') and database_uri.endswith('?mode=ro')
        assert kwargs == {'uri': True, 'timeout': expected_timeout}
        connection = real_connect(database_uri, **kwargs)
        opened.append(connection)
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            connection.execute('CREATE TABLE must_not_exist(id INTEGER)')
        return connection

    monkeypatch.setattr(sqlite3, 'connect', inspected_connect)
    readiness(RuntimeConfig.from_env(db_path=path, api_key=KEY))
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        opened[0].execute('SELECT 1')


def test_probe_closes_connection_after_sql_error_without_logging(monkeypatch, tmp_path, caplog):
    path = tmp_path / 'private-corrupt-location.db'
    path.write_bytes(b'corrupt SQLite file')
    real_connect = sqlite3.connect
    opened = []

    def tracked_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, 'connect', tracked_connect)
    assert readiness(RuntimeConfig.from_env(db_path=path, api_key=KEY))['status'] == 'not_ready'
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        opened[0].execute('SELECT 1')
    assert not caplog.records


def test_locked_database_is_not_ready_and_recovers_after_release(monkeypatch, tmp_path):
    path = database(tmp_path / 'locked.db')
    monkeypatch.setenv('JARVIS_SQLITE_TIMEOUT_SECONDS', '0.01')
    config = RuntimeConfig.from_env(db_path=path, api_key=KEY)
    with closing(sqlite3.connect(path)) as lock:
        lock.execute('BEGIN EXCLUSIVE')
        assert readiness(config)['checks']['database'] is False
        lock.rollback()
    assert readiness(config)['status'] == 'ready'
