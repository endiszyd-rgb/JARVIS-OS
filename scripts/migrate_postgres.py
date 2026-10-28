#!/usr/bin/env python3
"""Apply JARVIS-only Postgres migrations using an explicit migration DSN."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.postgres_migrations import MigrationError, migrate, migrate_memory


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory',action='store_true',help='Optional memory migration after foundation and administrative pgvector preparation')
    args=parser.parse_args()
    # Deliberately no DSN command-line flag: secrets must not enter shell
    # history or process argument listings. Never fall back to runtime DSNs.
    dsn = os.environ.get('JARVIS_POSTGRES_MIGRATION_DSN', '')
    if not dsn.strip():
        print('Set JARVIS_POSTGRES_MIGRATION_DSN for the separate migration account', file=sys.stderr)
        return 2
    try:
        result = (migrate_memory if args.memory else migrate)(dsn)
    except MigrationError:
        print('Postgres migration failed; no changes were committed', file=sys.stderr)
        return 1
    print(json.dumps({'status': 'migrated', 'feature': 'memory' if args.memory else 'foundation', 'migrations': result}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
