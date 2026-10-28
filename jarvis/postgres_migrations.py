"""Explicit, atomic migrations for the separate JARVIS Postgres schema.

This module is never called by Core startup. Use a separate migration account;
the HTTP runtime must not receive its DSN or schema ownership.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re


DEFAULT_MIGRATIONS = Path(__file__).resolve().parents[1] / 'migrations' / 'postgres'
_NAME = re.compile(r'(?P<version>[0-9]{4})_[a-z][a-z0-9_]*\.sql\Z')
_LOCK = 0x4A41525649535047
_ERROR = 'Postgres migration failed; no changes were committed'
_TRANSACTION_COMMANDS = {'BEGIN', 'START', 'COMMIT', 'END', 'ROLLBACK',
                         'ABORT', 'SAVEPOINT', 'RELEASE', 'PREPARE'}


class MigrationError(RuntimeError):
    """Deliberately contains no connection strings, SQL or server diagnostics."""


@dataclass(frozen=True, slots=True)
class _Migration:
    version: int
    name: str
    checksum: str
    sql: str


def _check_transaction_control(sql):
    """Reject transaction-control statements before executing any migration.

    PostgreSQL functions commonly contain BEGIN/END inside dollar-quoted
    bodies. Inspect statement beginnings while skipping strings and nested
    comments, rather than rejecting those legitimate function definitions.
    Migration SQL is trusted source code, not a sandbox for arbitrary SQL.
    """
    offset, first = 0, True
    while offset < len(sql):
        char = sql[offset]
        if char.isspace():
            offset += 1
            continue
        if sql.startswith('--', offset):
            newline = sql.find('\n', offset + 2)
            offset = len(sql) if newline < 0 else newline + 1
            continue
        if sql.startswith('/*', offset):
            depth, offset = 1, offset + 2
            while offset < len(sql) and depth:
                if sql.startswith('/*', offset):
                    depth += 1
                    offset += 2
                elif sql.startswith('*/', offset):
                    depth -= 1
                    offset += 2
                else:
                    offset += 1
            if depth:
                raise MigrationError(_ERROR)
            continue
        if char in ("'", '"'):
            escaping = (char == "'" and offset > 0 and sql[offset - 1] in 'eE'
                        and (offset < 2 or not (sql[offset - 2].isalnum() or sql[offset - 2] == '_')))
            offset += 1
            while offset < len(sql):
                if escaping and sql[offset] == '\\':
                    offset += 2
                elif sql[offset] == char:
                    offset += 1
                    if offset < len(sql) and sql[offset] == char:
                        offset += 1
                    else:
                        break
                else:
                    offset += 1
            else:
                raise MigrationError(_ERROR)
            first = False
            continue
        if char == '$':
            match = re.match(r'\$(?:[a-zA-Z_][a-zA-Z0-9_]*)?\$', sql[offset:])
            if match:
                tag = match[0]
                end = sql.find(tag, offset + len(tag))
                if end < 0:
                    raise MigrationError(_ERROR)
                offset = end + len(tag)
                first = False
                continue
        if char == ';':
            first = True
            offset += 1
            continue
        match = re.match(r'[a-zA-Z_][a-zA-Z0-9_]*', sql[offset:])
        if match:
            if first and match[0].upper() in _TRANSACTION_COMMANDS:
                raise MigrationError(_ERROR)
            offset += len(match[0])
        else:
            offset += 1
        first = False


def _read_migrations(directory):
    files = sorted(Path(directory).glob('*.sql'))
    if not files:
        raise MigrationError(_ERROR)
    migrations = []
    for path in files:
        match = _NAME.fullmatch(path.name)
        if match is None or path.is_symlink() or not path.is_file():
            raise MigrationError(_ERROR)
        raw = path.read_bytes()
        sql = raw.decode('utf-8')
        if not sql.strip() or '\x00' in sql:
            raise MigrationError(_ERROR)
        _check_transaction_control(sql)
        migrations.append(_Migration(int(match['version']), path.name,
                                     hashlib.sha256(raw).hexdigest(), sql))
    if [item.version for item in migrations] != list(range(1, len(migrations) + 1)):
        raise MigrationError(_ERROR)
    return migrations


def _migrate(dsn, migrations_dir, history_table):
    """Apply pending files once, or fail with complete transactional rollback.

    Existing files, names and SHA-256 values must exactly match recorded
    history. Removing an applied migration or supplying an older directory
    fails as well. Returns all applied version/name/checksum dictionaries.
    """
    try:
        if not isinstance(dsn, str) or not dsn.strip():
            raise MigrationError(_ERROR)
        migrations = _read_migrations(migrations_dir)
        import psycopg
        from psycopg import sql
        history = sql.Identifier('jarvis', history_table)

        with psycopg.connect(dsn, connect_timeout=5) as connection:
            connection.execute("SET LOCAL statement_timeout = '30s'")
            connection.execute("SET LOCAL lock_timeout = '5s'")
            connection.execute('SELECT pg_catalog.pg_advisory_xact_lock(%s)', (_LOCK,))
            connection.execute('CREATE SCHEMA IF NOT EXISTS jarvis')
            connection.execute('REVOKE ALL ON SCHEMA jarvis FROM PUBLIC')
            connection.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
                version integer PRIMARY KEY CHECK (version > 0),
                name text NOT NULL UNIQUE,
                checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{{64}}$'),
                applied_at timestamptz NOT NULL DEFAULT pg_catalog.statement_timestamp()
            )''').format(history))
            connection.execute(sql.SQL('REVOKE ALL ON {} FROM PUBLIC').format(history))
            applied = connection.execute(
                sql.SQL('SELECT version, name, checksum FROM {} ORDER BY version').format(history)
            ).fetchall()
            expected = [(item.version, item.name, item.checksum) for item in migrations]
            if applied != expected[:len(applied)]:
                raise MigrationError(_ERROR)
            for item in migrations[len(applied):]:
                connection.execute(item.sql)
                connection.execute(sql.SQL('''INSERT INTO {}(version, name, checksum)
                                      VALUES (%s, %s, %s)''').format(history),
                                   (item.version, item.name, item.checksum))
        return [{'version': item.version, 'name': item.name, 'checksum': item.checksum}
                for item in migrations]
    except Exception:
        # A psycopg exception may contain connection parameters, migration SQL
        # or payload values. Never propagate it through CLI/API error output.
        raise MigrationError(_ERROR) from None


def migrate(dsn, migrations_dir=None):
    return _migrate(dsn, DEFAULT_MIGRATIONS if migrations_dir is None else migrations_dir, 'schema_migrations')


def migrate_memory(dsn, migrations_dir=None):
    """Explicit optional feature, after foundation and admin-installed pgvector.

    A separate history keeps the existing foundation usable without installing
    an extension or granting its installation rights to the HTTP runtime.
    """
    directory = DEFAULT_MIGRATIONS.parent / 'postgres_memory' if migrations_dir is None else migrations_dir
    return _migrate(dsn, directory, 'memory_schema_migrations')
