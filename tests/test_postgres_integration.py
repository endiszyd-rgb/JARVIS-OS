"""Real PostgreSQL migrations, RLS and least-privilege repository checks.

Run through scripts/check_postgres.py. Only its fresh, synthetic cluster is used;
normal pytest explicitly skips these checks when the two test DSNs are absent.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import uuid

from fastapi import HTTPException
import psycopg
from psycopg import sql
from pydantic import SecretStr
import pytest

from jarvis.postgres_migrations import MigrationError, migrate
from jarvis.postgres_store import PostgresConfig, PostgresStore

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not os.environ.get('JARVIS_TEST_POSTGRES_ADMIN_DSN') or
    not os.environ.get('JARVIS_TEST_POSTGRES_RUNTIME_DSN') or
    not os.environ.get('JARVIS_TEST_POSTGRES_ISOLATION'),
    reason='Isolated PostgreSQL not configured; run scripts/check_postgres.py',
)


@dataclass(repr=False)
class Database:
    admin: str = field(repr=False)
    runtime: str = field(repr=False)
    store: PostgresStore = field(repr=False)

    def __repr__(self):
        return '<isolated PostgreSQL test connections>'

    def admin_connection(self):
        return psycopg.connect(self.admin, connect_timeout=5)

    @contextmanager
    def authenticated(self, subject=None):
        with psycopg.connect(self.runtime, connect_timeout=5) as connection:
            connection.execute('SET LOCAL ROLE authenticated')
            if subject is not None:
                connection.execute("SELECT set_config('request.jwt.claims', %s, true)",
                                   (json.dumps({'sub': str(subject)}),))
            yield connection


@pytest.fixture(scope='module')
def database():
    admin = os.environ['JARVIS_TEST_POSTGRES_ADMIN_DSN']
    runtime = os.environ['JARVIS_TEST_POSTGRES_RUNTIME_DSN']
    with psycopg.connect(admin, connect_timeout=5) as connection:
        assert connection.execute('SELECT id FROM jarvis_test_guard.isolation').fetchall() == [
            (os.environ['JARVIS_TEST_POSTGRES_ISOLATION'],)
        ], 'Only the fresh, guarded Docker test cluster may be mutated'
    migrate(admin)
    return Database(admin, runtime, PostgresStore(PostgresConfig(dsn=SecretStr(runtime))))


def expect_status(status, function, *args, **kwargs):
    with pytest.raises(HTTPException) as caught:
        function(*args, **kwargs)
    assert caught.value.status_code == status
    assert 'password' not in str(caught.value.detail).lower()
    return caught.value


def workshop(database, memberships):
    ident = uuid.uuid4()
    with database.admin_connection() as connection:
        connection.execute('INSERT INTO jarvis.workshops(id,name) VALUES (%s,%s)',
                           (ident, 'Synthetic workshop ' + ident.hex[:8]))
        for subject, writable in memberships:
            connection.execute('INSERT INTO jarvis.memberships(workshop_id,user_id,can_write) VALUES (%s,%s,%s)',
                               (ident, subject, writable))
    return ident


def test_migrations_replay_preserves_rows_and_checksums(database):
    subject = uuid.uuid4()
    record = database.store.create(subject, 'Migration sentinel', {'source': 'synthetic'})
    first = migrate(database.admin)
    second = migrate(database.admin)
    assert first == second
    assert first and first[-1]['version'] == 1
    assert all(len(row['checksum']) == 64 for row in first)
    assert database.store.get(subject, record['id'])['payload'] == {'source': 'synthetic'}
    assert database.store.status() == {'enabled': True, 'status': 'ready', 'schema_version': 1}


def test_changed_or_missing_applied_migration_fails_without_touching_data(database, tmp_path):
    migrations = tmp_path / 'migrations'
    shutil.copytree(ROOT / 'migrations/postgres', migrations)
    source = sorted(migrations.glob('*.sql'))[0]
    source.write_text(source.read_text() + '\n-- Altered checksum must fail.\n')
    with pytest.raises(MigrationError):
        migrate(database.admin, migrations)
    source.unlink()
    with pytest.raises(MigrationError):
        migrate(database.admin, migrations)
    assert database.store.status()['schema_version'] == 1


def test_failed_later_migration_rolls_back_ddl_and_version(database, tmp_path):
    migrations = tmp_path / 'migrations'
    shutil.copytree(ROOT / 'migrations/postgres', migrations)
    (migrations / '0002_failure.sql').write_text(
        'CREATE TABLE jarvis.must_be_rolled_back(id integer);\n'
        'SELECT jarvis.deliberately_missing_function();\n')
    with pytest.raises(MigrationError):
        migrate(database.admin, migrations)
    with database.admin_connection() as connection:
        assert connection.execute("SELECT to_regclass('jarvis.must_be_rolled_back')").fetchone()[0] is None
    assert migrate(database.admin)[-1]['version'] == 1


def test_migration_cannot_escape_atomic_transaction_with_explicit_commit(database, tmp_path):
    migrations = tmp_path / 'migrations'
    shutil.copytree(ROOT / 'migrations/postgres', migrations)
    (migrations / '0002_escape.sql').write_text(
        'CREATE TABLE jarvis.must_not_escape_transaction(id integer);\n'
        'COMMIT;\nSELECT jarvis.deliberately_missing_function();\n')
    with pytest.raises(MigrationError):
        migrate(database.admin, migrations)
    with database.admin_connection() as connection:
        assert connection.execute("SELECT to_regclass('jarvis.must_not_escape_transaction')").fetchone()[0] is None
    assert migrate(database.admin)[-1]['version'] == 1


def test_private_crud_is_persistent_and_isolates_two_users(database):
    first, second = uuid.uuid4(), uuid.uuid4()
    record = database.store.create(first, 'Private first', {'note': 'Synthetic private content'})
    assert str(record['owner_id']) == str(first) and record['workshop_id'] is None
    assert record['revision'] == 0
    assert str(record['id']) in {str(row['id']) for row in database.store.list(first)}
    assert str(record['id']) not in {str(row['id']) for row in database.store.list(second)}
    for operation, arguments in (
        (database.store.get, (second, record['id'])),
        (database.store.update, (second, record['id'], 0, 'Attack', {})),
        (database.store.delete, (second, record['id'], 0)),
    ):
        expect_status(404, operation, *arguments)
    updated = database.store.update(first, record['id'], 0, 'Corrected', {'note': 'Changed'})
    assert updated['revision'] == 1 and updated['title'] == 'Corrected'
    # A fresh repository and connection must see durable server-side state.
    restarted = PostgresStore(PostgresConfig(dsn=SecretStr(database.runtime)))
    assert restarted.get(first, record['id'])['payload'] == {'note': 'Changed'}
    expect_status(409, restarted.update, first, record['id'], 0, 'Stale', {})
    expect_status(409, restarted.delete, first, record['id'], 0)
    assert restarted.delete(first, record['id'], 1) == {'deleted': str(record['id'])}
    expect_status(404, restarted.get, first, record['id'])


def test_workshop_membership_separates_tenants_and_read_only_access(database):
    writer, reader, outsider = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    first = workshop(database, [(writer, True), (reader, False)])
    second = workshop(database, [(outsider, True)])
    record = database.store.create(writer, 'Workshop first', {'tenant': 'first'}, workshop_id=first)
    other = database.store.create(outsider, 'Workshop second', {'tenant': 'second'}, workshop_id=second)
    assert database.store.get(reader, record['id'])['title'] == 'Workshop first'
    assert str(record['id']) in {str(row['id']) for row in database.store.list(reader, workshop_id=first)}
    assert database.store.list(reader, workshop_id=second) == []
    expect_status(404, database.store.get, reader, other['id'])
    expect_status(404, database.store.get, outsider, record['id'])
    expect_status(403, database.store.create, reader, 'Not permitted', {}, workshop_id=first)
    expect_status(403, database.store.update, reader, record['id'], 0, 'Not permitted', {})
    expect_status(403, database.store.delete, reader, record['id'], 0)
    database.store.update(writer, record['id'], 0, 'Authorized correction', {'tenant': 'first'})
    # Even the creator loses tenant data when the explicit membership is removed.
    with database.admin_connection() as connection:
        connection.execute('DELETE FROM jarvis.memberships WHERE workshop_id=%s AND user_id=%s', (first, writer))
    expect_status(404, database.store.get, writer, record['id'])


def test_rls_rejects_forged_owner_and_immutable_tenant_columns(database):
    first, second = uuid.uuid4(), uuid.uuid4()
    tenant = workshop(database, [(first, True)])
    record = database.store.create(first, 'Immutable ownership', {})
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with database.authenticated(first) as connection:
            connection.execute('INSERT INTO jarvis.records(owner_id,title,payload) VALUES (%s,%s,%s)',
                               (second, 'Forged owner', '{}'))
    for column, value in (('owner_id', second), ('workshop_id', tenant), ('id', uuid.uuid4())):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with database.authenticated(first) as connection:
                connection.execute(sql.SQL('UPDATE jarvis.records SET {}=%s WHERE id=%s').format(sql.Identifier(column)),
                                   (value, record['id']))
    assert database.store.get(first, record['id'])['revision'] == 0


def test_revision_trigger_and_constraints_apply_to_direct_sql(database):
    subject = uuid.uuid4()
    record = database.store.create(subject, 'Revision guarded', {})
    for query, parameters in (
        ('UPDATE jarvis.records SET title=%s WHERE id=%s', ('No revision', record['id'])),
        ('UPDATE jarvis.records SET revision=revision+2 WHERE id=%s', (record['id'],)),
        ('INSERT INTO jarvis.records(owner_id,title,payload) VALUES (%s,%s,%s)', (subject, 'Invalid array', '[]')),
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            with database.authenticated(subject) as connection:
                connection.execute(query, parameters)
    assert database.store.get(subject, record['id'])['revision'] == 0


def test_no_subject_sees_nothing_and_transaction_context_does_not_leak(database):
    first, second = uuid.uuid4(), uuid.uuid4()
    record = database.store.create(first, 'Context isolation', {})
    with psycopg.connect(database.runtime, connect_timeout=5) as connection:
        with connection.transaction():
            connection.execute('SET LOCAL ROLE authenticated')
            connection.execute("SELECT set_config('request.jwt.claims',%s,true)", (json.dumps({'sub': str(first)}),))
            assert connection.execute('SELECT id FROM jarvis.records WHERE id=%s', (record['id'],)).fetchone()
        with connection.transaction():
            assert connection.execute('SELECT current_user').fetchone()[0] == 'jarvis_runtime'
            assert connection.execute("SELECT current_setting('request.jwt.claims',true)").fetchone()[0] in ('', None)
            connection.execute('SET LOCAL ROLE authenticated')
            assert connection.execute('SELECT id FROM jarvis.records WHERE id=%s', (record['id'],)).fetchone() is None
            connection.execute("SELECT set_config('request.jwt.claims',%s,true)", (json.dumps({'sub': str(second)}),))
            assert connection.execute('SELECT id FROM jarvis.records WHERE id=%s', (record['id'],)).fetchone() is None
        try:
            with connection.transaction():
                connection.execute('SET LOCAL ROLE authenticated')
                connection.execute("SELECT set_config('request.jwt.claims',%s,true)", (json.dumps({'sub': str(first)}),))
                raise RuntimeError('Synthetic rollback')
        except RuntimeError:
            pass
        assert connection.execute('SELECT current_user').fetchone()[0] == 'jarvis_runtime'
        assert connection.execute("SELECT current_setting('request.jwt.claims',true)").fetchone()[0] in ('', None)


def test_memberships_are_readable_only_to_self_and_not_mutable(database):
    first, second = uuid.uuid4(), uuid.uuid4()
    tenant = workshop(database, [(first, True), (second, False)])
    with database.authenticated(first) as connection:
        rows = connection.execute('SELECT user_id FROM jarvis.memberships WHERE workshop_id=%s', (tenant,)).fetchall()
        assert rows == [(first,)]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with database.authenticated(second) as connection:
            connection.execute('UPDATE jarvis.memberships SET can_write=true WHERE user_id=%s', (second,))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with database.authenticated(second) as connection:
            connection.execute('INSERT INTO jarvis.memberships(workshop_id,user_id,can_write) VALUES (%s,%s,true)',
                               (tenant, uuid.uuid4()))


@pytest.mark.parametrize('role', ['anon', 'service_role'])
def test_anon_and_bypassrls_service_role_have_no_application_grants(database, role):
    # Fresh LOGIN probes prevent superuser privileges from masking role grants.
    login = 'jarvis_probe_' + uuid.uuid4().hex
    password = uuid.uuid4().hex + uuid.uuid4().hex
    with database.admin_connection() as connection:
        connection.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(
            sql.Identifier(login), sql.Literal(password)))
        connection.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(role), sql.Identifier(login)))
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(database.runtime, user=login, password=password, connect_timeout=5) as connection:
                connection.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
                connection.execute('SELECT * FROM jarvis.records')
    finally:
        with database.admin_connection() as connection:
            connection.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(login)))


def test_runtime_cannot_ddl_mutate_migrations_or_disable_rls(database):
    subject = uuid.uuid4()
    attempts = (
        'CREATE TABLE jarvis.unpermitted_table(id integer)',
        'UPDATE jarvis.schema_migrations SET checksum=repeat(\'0\',64)',
        'ALTER TABLE jarvis.records DISABLE ROW LEVEL SECURITY',
    )
    for statement in attempts:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with database.authenticated(subject) as connection:
                connection.execute(statement)
    with database.admin_connection() as connection:
        rows = connection.execute("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='jarvis' AND relname IN ('records','workshops','memberships')").fetchall()
    assert len(rows) == 3 and all(row[1] and row[2] for row in rows)


def test_repository_rejects_superuser_connection_instead_of_bypassing_rls(database):
    unsafe = PostgresStore(PostgresConfig(dsn=SecretStr(database.admin)))
    expect_status(503, unsafe.status)
    expect_status(503, unsafe.list, uuid.uuid4())


@pytest.mark.parametrize('attribute', ['INHERIT', 'BYPASSRLS', 'CREATEROLE', 'CREATEDB'])
def test_repository_rejects_runtime_role_that_gains_privileged_attributes(database, attribute):
    # This fixture runs only in the unique Docker cluster, never a supplied app DB.
    with database.admin_connection() as connection:
        connection.execute(sql.SQL('ALTER ROLE jarvis_runtime {}').format(sql.SQL(attribute)))
    try:
        expect_status(503, database.store.status)
    finally:
        with database.admin_connection() as connection:
            connection.execute(sql.SQL('ALTER ROLE jarvis_runtime {}').format(sql.SQL('NO' + attribute)))
    assert database.store.status()['status'] == 'ready'


def test_parameterized_payload_does_not_execute_sql(database):
    subject = uuid.uuid4()
    text = "Synthetic '); DROP TABLE jarvis.records; --"
    record = database.store.create(subject, text, {'quote': text})
    assert database.store.get(subject, record['id'])['payload']['quote'] == text
    assert database.store.status()['schema_version'] == 1


def test_record_events_are_metadata_only_private_and_survive_record_delete(database):
    first, second = uuid.uuid4(), uuid.uuid4()
    secret = 'Synthetic private payload absent from event metadata'
    record = database.store.create(first, 'Synthetic secret title', {'note': secret})
    database.store.update(first, record['id'], 0, 'Changed title', {'note': secret})
    database.store.delete(first, record['id'], 1)
    with database.authenticated(first) as connection:
        rows = connection.execute('SELECT subject,event,record_id FROM jarvis.record_events WHERE record_id=%s ORDER BY created_at,id',
                                  (record['id'],)).fetchall()
        assert sorted(row[1] for row in rows) == ['created', 'deleted', 'updated']
        assert all(row[0] == first and row[2] == record['id'] for row in rows)
        columns = connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='jarvis' AND table_name='record_events'").fetchall()
        assert {row[0] for row in columns} == {'id', 'subject', 'event', 'record_id', 'created_at'}
    with database.authenticated(second) as connection:
        assert connection.execute('SELECT id FROM jarvis.record_events WHERE record_id=%s', (record['id'],)).fetchall() == []
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with database.authenticated(first) as connection:
            connection.execute('DELETE FROM jarvis.record_events WHERE record_id=%s', (record['id'],))


def test_storage_mutation_rolls_back_when_its_atomic_event_cannot_be_written(database):
    subject = uuid.uuid4()
    record = database.store.create(subject, 'Survives event failure', {})
    with database.admin_connection() as connection:
        connection.execute("""CREATE FUNCTION jarvis.synthetic_event_failure() RETURNS trigger
                              LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic event failure'; END $$""")
        connection.execute('CREATE TRIGGER synthetic_event_failure BEFORE INSERT ON jarvis.record_events FOR EACH ROW EXECUTE FUNCTION jarvis.synthetic_event_failure()')
    try:
        expect_status(503, database.store.create, subject, 'Rolled back create', {})
        expect_status(503, database.store.update, subject, record['id'], 0, 'Rolled back update', {})
        expect_status(503, database.store.delete, subject, record['id'], 0)
        current = database.store.get(subject, record['id'])
        assert current['title'] == 'Survives event failure' and current['revision'] == 0
        assert len(database.store.list(subject)) == 1
    finally:
        with database.admin_connection() as connection:
            connection.execute('DROP TRIGGER synthetic_event_failure ON jarvis.record_events')
            connection.execute('DROP FUNCTION jarvis.synthetic_event_failure()')


def test_separate_migrator_without_superuser_can_provision_memberships_under_force_rls(database):
    name='jarvis_migration_'+uuid.uuid4().hex
    password=uuid.uuid4().hex+uuid.uuid4().hex
    connection_info=psycopg.conninfo.conninfo_to_dict(database.admin)
    # CREATE DATABASE runs outside a transaction; the guard above proves this
    # cluster belongs to the isolated runner before any administrative action.
    with psycopg.connect(database.admin,autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}').format(sql.Identifier(name),sql.Literal(password)))
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        admin.execute(sql.SQL('GRANT CONNECT,CREATE ON DATABASE {} TO {}').format(sql.Identifier(name),sql.Identifier(name)))
    try:
        connection_info.update(dbname=name,user=name,password=password)
        dsn=psycopg.conninfo.make_conninfo(**connection_info)
        assert migrate(dsn)[-1]['version']==1
        with psycopg.connect(dsn) as migrator:
            role=migrator.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
            assert role==(False,False)
            workshop_id,user_id=uuid.uuid4(),uuid.uuid4()
            migrator.execute('INSERT INTO jarvis.workshops(id,name) VALUES(%s,%s)',(workshop_id,'Limited migrator workshop'))
            migrator.execute('INSERT INTO jarvis.memberships(workshop_id,user_id,can_write) VALUES(%s,%s,true)',(workshop_id,user_id))
            assert migrator.execute('SELECT user_id FROM jarvis.memberships').fetchall()==[(user_id,)]
            flags=migrator.execute("SELECT relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='jarvis' AND relname IN ('workshops','memberships')").fetchall()
            assert flags==[(True,),(True,)]
    finally:
        with psycopg.connect(database.admin,autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(name)))
