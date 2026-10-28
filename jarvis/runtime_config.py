"""Validated local runtime settings and an independent, read-only readiness probe."""
from contextlib import closing
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import sqlite3

from pydantic import SecretStr


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    database_path: Path = Path('data/jarvis.db')
    api_key: SecretStr = field(default_factory=lambda: SecretStr(''))
    sqlite_timeout_seconds: float = 15.0

    def __post_init__(self):
        raw_path = os.fspath(self.database_path)
        if not isinstance(raw_path, str) or not raw_path.strip() or '\x00' in raw_path:
            raise ValueError('JARVIS_DB must be a nonempty filesystem path')
        object.__setattr__(self, 'database_path', Path(raw_path))
        try:
            timeout = float(self.sqlite_timeout_seconds)
        except (TypeError, ValueError, OverflowError):
            raise ValueError('JARVIS_SQLITE_TIMEOUT_SECONDS must be finite and greater than 0 up to 60') from None
        if not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError('JARVIS_SQLITE_TIMEOUT_SECONDS must be finite and greater than 0 up to 60')
        object.__setattr__(self, 'sqlite_timeout_seconds', timeout)
        if not isinstance(self.api_key, SecretStr):
            raise ValueError('Runtime owner key must use SecretStr')

    @classmethod
    def from_env(cls, db_path=None, api_key=None):
        """Explicit values, including an empty key, take precedence over the environment."""
        path = os.environ.get('JARVIS_DB', 'data/jarvis.db') if db_path is None else db_path
        key = os.environ.get('JARVIS_API_KEY', '') if api_key is None else api_key
        if not isinstance(key, (str, SecretStr)):
            raise ValueError('JARVIS_API_KEY must be a string')
        return cls(
            database_path=path,
            api_key=key if isinstance(key, SecretStr) else SecretStr(key),
            sqlite_timeout_seconds=os.environ.get('JARVIS_SQLITE_TIMEOUT_SECONDS', '15'),
        )

    @property
    def owner_key_configured(self):
        key = self.api_key.get_secret_value()
        return 24 <= len(key) <= 256 and key.isascii() and not key.startswith('replace-')


def readiness(config: RuntimeConfig, expected_schema: int = 11) -> dict:
    """Probe existing data with mode=ro; never initialize a database or use the network.

    SQLite may create WAL coordination sidecars while reading an existing WAL
    database. Avoid immutable mode: it would ignore an active write-ahead log.
    """
    database_ok = False
    try:
        if config.database_path.is_file():
            uri = config.database_path.absolute().as_uri() + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=min(config.sqlite_timeout_seconds, 2.0))) as connection:
                accessible = connection.execute('SELECT 1').fetchone() == (1,)
                schema = connection.execute('PRAGMA user_version').fetchone()[0]
                database_ok = accessible and schema == expected_schema
    except (OSError, ValueError, sqlite3.Error):
        # Readiness is public operational state, not a source of paths or SQL errors.
        database_ok = False
    checks = {'owner_key': config.owner_key_configured, 'database': database_ok}
    return {
        'status': 'ready' if all(checks.values()) else 'not_ready',
        'checks': checks,
        'optional_integrations_probed': False,
    }
