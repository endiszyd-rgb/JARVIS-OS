#!/usr/bin/env python3
"""Verify PostgreSQL migrations/RLS in a disposable local Docker database.

No configured database DSN is used. Only UUID-labelled resources created by this
process may be removed; credentials live in a temporary file and child env.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
import uuid
import xml.etree.ElementTree as ET


class CheckError(RuntimeError):
    pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', help='Default: postgres:16-bookworm; --memory uses pgvector/pgvector:0.8.2-pg16')
    parser.add_argument('--memory', action='store_true', help='Also prepare and verify the optional pgvector memory feature')
    parser.add_argument('--browser', action='store_true', help='With --memory, also check the built panel in local Chromium/Playwright')
    parser.add_argument('--docker-host', default='npipe:////./pipe/docker_engine' if os.name == 'nt' else 'unix:///var/run/docker.sock')
    parser.add_argument('--skip-pull', action='store_true', help='Require an already present image')
    parser.add_argument('--output', type=Path, help='Write the sanitized JSON report after cleanup')
    args = parser.parse_args(argv)
    if args.browser and not args.memory:parser.error('--browser requires --memory')
    args.image = args.image or ('pgvector/pgvector:0.8.2-pg16' if args.memory else 'postgres:16-bookworm')
    if not (args.docker_host.startswith(('unix://', 'npipe://')) or
            urlsplit(args.docker_host).hostname in ('127.0.0.1', 'localhost', '::1')):
        parser.error('A local Docker daemon is required')
    try:
        import psycopg
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
    except ImportError:
        print('PostgreSQL check FAIL: install the project dependencies first', file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parents[1]
    identity = 'jarvis-pg-' + uuid.uuid4().hex
    volume = identity + '-data'
    label = 'org.jarvis.postgres-check='
    admin_password, runtime_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    # Keep Docker registry credentials and the managed proxy configuration.
    env = {name: value for name, value in os.environ.items()
           if name not in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS',
                           'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH') and
           not name.startswith(('JARVIS_', 'PG', 'POSTGRES_'))}
    docker = ['docker', '--host=' + args.docker_host]
    stage, error = 'docker daemon', None
    cid, volume_created = None, False
    image_id, server_version, tests_count = None, None, 0
    checks = []
    dsns = []

    def redacted(value):
        for secret in (*dsns, admin_password, runtime_password):
            value = value.replace(secret, '[REDACTED]')
        # Keep a test failure useful without exposing DSNs from nested libraries.
        return re.sub(r'postgres(?:ql)?://[^\s\'\"<>]+', '[REDACTED_DSN]', value)

    def run(parts, *, timeout=60, check=True):
        result = subprocess.run(docker + parts, cwd=root, env=env, capture_output=True,
                                text=True, errors='replace', timeout=timeout)
        if check and result.returncode:
            raise CheckError('Docker command failed during ' + stage)
        return result

    def labelled_container():
        if not cid:
            return False
        result = run(['inspect', '--format', '{{index .Config.Labels "org.jarvis.postgres-check"}}', cid], check=False)
        return result.returncode == 0 and result.stdout.strip() == identity

    def port():
        published = run(['port', cid, '5432/tcp']).stdout.strip()
        if not re.fullmatch(r'127\.0\.0\.1:[0-9]+', published):
            raise CheckError('PostgreSQL must use one dynamic IPv4 loopback port')
        return int(published.rsplit(':', 1)[1])

    def dsn(username, password):
        value = make_conninfo(host='127.0.0.1', port=port(), dbname='jarvis_test',
                              user=username, password=password, sslmode='disable')
        dsns.append(value)
        return value

    def wait_database(value):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with psycopg.connect(value, connect_timeout=2) as c:
                    return c.execute('SHOW server_version').fetchone()[0]
            except psycopg.OperationalError:
                time.sleep(0.2)
        raise CheckError('PostgreSQL did not become ready within 60 seconds')

    with tempfile.TemporaryDirectory(prefix=identity + '-') as folder:
        scratch = Path(folder)
        secrets_file = scratch / 'postgres.env'
        secrets_file.write_text('POSTGRES_USER=postgres\nPOSTGRES_DB=jarvis_test\nPOSTGRES_PASSWORD=' +
                                admin_password + '\n', encoding='utf-8')
        if os.name != 'nt':
            secrets_file.chmod(0o600)
        try:
            run(['info', '--format', '{{.ServerVersion}}'], timeout=15)
            stage = 'image preparation'
            if not args.skip_pull:
                run(['pull', args.image], timeout=600)
            image_id = run(['image', 'inspect', '--format', '{{.Id}}', args.image]).stdout.strip()
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', image_id):
                raise CheckError('Expected one identified PostgreSQL image')
            stage = 'resource creation'
            run(['volume', 'create', '--label', label + identity, volume])
            volume_created = True
            cid = identity  # Also find and clean a container if `docker run` fails.
            launched = run(['run', '--detach', '--name', identity, '--label', label + identity,
                            '--env-file', str(secrets_file), '--publish', '127.0.0.1::5432',
                            '--mount', 'type=volume,src=' + volume + ',dst=/var/lib/postgresql/data',
                            '--security-opt', 'no-new-privileges:true', args.image], timeout=120)
            cid = launched.stdout.strip()
            if not re.fullmatch(r'[a-f0-9]{64}', cid) or not labelled_container():
                raise CheckError('Created container identity did not match this check')
            mounts = json.loads(run(['inspect', '--format', '{{json .Mounts}}', cid]).stdout)
            if not mounts or any(m['Type'] != 'volume' or m.get('Name') != volume for m in mounts):
                raise CheckError('PostgreSQL has a mount outside its isolated volume')
            stage = 'database startup'
            admin_dsn = dsn('postgres', admin_password)
            server_version = wait_database(admin_dsn)
            checks.append('postgres_startup')
            stage = 'test-only roles'
            with psycopg.connect(admin_dsn, connect_timeout=2) as c:
                c.execute('CREATE SCHEMA jarvis_test_guard')
                c.execute('CREATE TABLE jarvis_test_guard.isolation(id text PRIMARY KEY)')
                c.execute('INSERT INTO jarvis_test_guard.isolation VALUES(%s)', (identity,))
                c.execute('CREATE ROLE anon NOLOGIN')
                c.execute('CREATE ROLE authenticated NOLOGIN')
                # Supabase's service role bypasses RLS, so grants must deny it.
                c.execute('CREATE ROLE service_role NOLOGIN BYPASSRLS')
                c.execute(sql.SQL('CREATE ROLE jarvis_runtime LOGIN NOINHERIT NOSUPERUSER '
                                  'NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}').format(sql.Literal(runtime_password)))
                c.execute('GRANT authenticated TO jarvis_runtime')
                c.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
                if args.memory:
                    c.execute('CREATE SCHEMA jarvis_extensions')
                    c.execute('REVOKE ALL ON SCHEMA jarvis_extensions FROM PUBLIC,anon,authenticated,service_role')
                    c.execute('CREATE EXTENSION vector WITH SCHEMA jarvis_extensions')
                    c.execute('GRANT USAGE ON SCHEMA jarvis_extensions TO authenticated')
            runtime_dsn = dsn('jarvis_runtime', runtime_password)
            tests = ['tests/test_postgres_integration.py']
            if (root / 'tests/test_postgres_api.py').is_file():
                tests.append('tests/test_postgres_api.py')
            if args.memory:
                tests.append('tests/test_postgres_memory_integration.py')
                tests.append('tests/test_postgres_context_integration.py')
                tests.append('tests/test_postgres_profiles_integration.py')
                if args.browser:tests.append('tests/test_postgres_memory_browser.py')
            test_env = dict(env, JARVIS_TEST_POSTGRES_ADMIN_DSN=admin_dsn,
                            JARVIS_TEST_POSTGRES_RUNTIME_DSN=runtime_dsn,
                            JARVIS_TEST_POSTGRES_ISOLATION=identity)
            if args.memory:
                test_env['JARVIS_TEST_POSTGRES_MEMORY']='true'
                if args.browser:test_env['JARVIS_TEST_MEMORY_BROWSER']='true'
            junit = scratch / 'pytest.xml'
            stage = 'migration/RLS/API tests'
            result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-rA', '--tb=short',
                                     '--junitxml=' + str(junit), *tests], cwd=root, env=test_env,
                                    capture_output=True, text=True, errors='replace', timeout=300)
            if not junit.is_file():
                raise CheckError('PostgreSQL tests did not produce a result report')
            suites = ET.parse(junit).getroot()
            cases = list(suites.iter('testcase'))
            tests_count = len(cases)
            unsuccessful = any(case.find(tag) is not None for case in cases
                               for tag in ('failure', 'error', 'skipped'))
            if result.returncode or not tests_count or unsuccessful:
                print(redacted((result.stdout + result.stderr)[-12000:]), file=sys.stderr)
                raise CheckError('PostgreSQL tests failed or skipped; see sanitized test output')
            checks += ['migrations', 'rls', 'restricted_runtime', 'no_skipped_tests']
            # The sentinel is independent of integration-test schema lifecycle.
            stage = 'persistence sentinel'
            sentinel = uuid.uuid4()
            with psycopg.connect(admin_dsn, connect_timeout=2) as c:
                c.execute('CREATE SCHEMA jarvis_smoke')
                c.execute('CREATE TABLE jarvis_smoke.restart_sentinel(id uuid PRIMARY KEY)')
                c.execute('INSERT INTO jarvis_smoke.restart_sentinel VALUES(%s)', (sentinel,))
            stage = 'database restart'
            run(['restart', '--time', '5', cid], timeout=60)
            admin_dsn = dsn('postgres', admin_password)  # Dynamic port can change.
            wait_database(admin_dsn)
            with psycopg.connect(admin_dsn, connect_timeout=2) as c:
                if c.execute('SELECT id FROM jarvis_smoke.restart_sentinel').fetchone() != (sentinel,):
                    raise CheckError('PostgreSQL data did not survive the container restart')
            checks.append('container_restart_persistence')
        except (CheckError, OSError, ValueError, KeyError, TypeError, ET.ParseError,
                psycopg.Error, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            error = redacted(str(exc)) if isinstance(exc, CheckError) else 'Failure during ' + stage + ' (' + type(exc).__name__ + ')'
        finally:
            stage = 'cleanup'
            cleanup_failed = False
            try:
                if cid:
                    tagged = run(['inspect', '--format',
                                  '{{index .Config.Labels "org.jarvis.postgres-check"}}', cid], check=False)
                    if tagged.returncode == 0 and tagged.stdout.strip() == identity:
                        run(['rm', '--force', cid], timeout=60)
                    elif tagged.returncode == 0:
                        cleanup_failed = True
                if volume_created:
                    tagged = run(['volume', 'inspect', '--format',
                                  '{{index .Labels "org.jarvis.postgres-check"}}', volume], check=False)
                    if tagged.returncode == 0 and tagged.stdout.strip() == identity:
                        run(['volume', 'rm', volume], timeout=60)
                    else:
                        cleanup_failed = True
            except (CheckError, OSError, subprocess.TimeoutExpired):
                cleanup_failed = True
            if cleanup_failed:
                error = (error + '; ' if error else '') + 'Isolated resource cleanup failed'
        if error:
            print('PostgreSQL check FAIL: ' + error, file=sys.stderr)
            return 1

    report = {'status': 'PASS', 'checks': checks, 'tests_passed': tests_count, 'tests_skipped': 0,
              'memory_feature': args.memory, 'browser': args.browser,
              'postgres_version': server_version, 'image': args.image, 'image_id': image_id,
              'cleanup': 'removed_isolated_container_and_volume', 'production': 'not_accessed'}
    serialized = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding='utf-8')
    print(serialized, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
