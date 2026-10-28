#!/usr/bin/env python3
"""Smoke-test the actual Compose core using isolated synthetic data and resources."""
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
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid


class SmokeError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='jarvis-m12-core:local')
    parser.add_argument('--skip-build', action='store_true')
    parser.add_argument('--ca-bundle', type=Path)
    parser.add_argument('--docker-host')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.ca_bundle and not args.ca_bundle.is_file():
        parser.error('--ca-bundle must point to an existing file')
    project = 'jarvis-m12-' + uuid.uuid4().hex
    key = secrets.token_urlsafe(36)
    env = {name: value for name, value in os.environ.items() if not name.startswith(
        ('COMPOSE_', 'JARVIS_', 'AUTOLOGIKA_', 'OLLAMA_', 'HA_', 'TWILIO_',
         'WHATSAPP_', 'WYOMING_', 'MEMORY_', 'N8N_'))}
    docker = ['docker']
    if args.docker_host:
        env.pop('DOCKER_CONTEXT', None)
        env['DOCKER_HOST'] = args.docker_host
        docker += ['--host', args.docker_host]
    logs = []

    def run(command, timeout=60, check=True):
        result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True,
                                errors='replace', timeout=timeout)
        logs.append((' '.join(command), (result.stdout + result.stderr)[-8000:]))
        if check and result.returncode:
            raise SmokeError(f'Command failed ({result.returncode}): {" ".join(command)}')
        return result.stdout.strip()

    with tempfile.TemporaryDirectory(prefix=project + '-') as folder:
        scratch = Path(folder)
        dotenv, override = scratch / 'smoke.env', scratch / 'override.yaml'
        flags = {name: 'false' for name in re.findall(r'\$\{([A-Z_][A-Z0-9_]*)',
                 (root / 'compose.yaml').read_text(encoding='utf-8'))
                 if name.endswith('_ENABLED') or name == 'JARVIS_ALLOW_CLOUD_MODELS'}
        flags.update(JARVIS_API_KEY=key, JARVIS_NETWORK_ALLOWLIST='127.0.0.0/8,::1/128')
        dotenv.write_text(''.join(f'{name}={value}\n' for name, value in sorted(flags.items())), encoding='utf-8')
        if os.name != 'nt':
            dotenv.chmod(0o600)
        # !override prevents inheriting any user data mount or fixed host port.
        content = ('services:\n  core:\n    image: ' + json.dumps(args.image) + '\n'
                   '    ports: !override\n      - "127.0.0.1::8000"\n'
                   '    volumes: !override\n      - "smoke-data:/app/data"\n'
                   '    environment:\n      JARVIS_API_KEY: ' + json.dumps(key) + '\n'
                   + ''.join('      ' + name + ': "false"\n' for name in sorted(flags) if flags[name] == 'false'))
        if args.ca_bundle:
            content += '    build:\n      secrets:\n        - proxy_ca\n'
        content += 'volumes:\n  smoke-data: {}\n'
        if args.ca_bundle:
            content += 'secrets:\n  proxy_ca:\n    file: ' + json.dumps(str(args.ca_bundle.resolve())) + '\n'
        override.write_text(content, encoding='utf-8')
        if os.name != 'nt':
            override.chmod(0o600)
        compose = docker + ['compose', '--project-directory', str(root), '--env-file', str(dotenv),
                            '-f', str(root / 'compose.yaml'), '-f', str(override), '--project-name', project]
        error, cid, checks, image_id = None, None, [], None
        try:
            endpoint = args.docker_host or (env.get('DOCKER_HOST') if not env.get('DOCKER_CONTEXT') else None)
            endpoint = endpoint or run(docker + ['context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'])
            if not (endpoint.startswith(('unix://', 'npipe://')) or
                    urlsplit(endpoint).hostname in ('127.0.0.1', 'localhost', '::1')):
                raise SmokeError('This loopback smoke test requires a local Docker daemon')
            run(compose + ['config', '--quiet'])
            if not args.skip_build:
                run(compose + ['build', 'core'], timeout=600)
            run(compose + ['up', '--detach', '--no-build', '--no-deps', 'core'], timeout=120)
            cid = run(compose + ['ps', '--quiet', 'core'])
            if not re.fullmatch(r'[a-f0-9]{12,64}', cid):
                raise SmokeError('Expected exactly one smoke-test core container')
            labels, mount_data = run(docker + ['inspect', '--format', '{{json .Config.Labels}}\n{{json .Mounts}}', cid]).splitlines()
            if json.loads(labels).get('com.docker.compose.project') != project:
                raise SmokeError('Container project label does not match this smoke test')
            mounts = json.loads(mount_data)
            if not mounts or any(mount['Type'] != 'volume' or not mount.get('Name', '').startswith(project + '_') for mount in mounts):
                raise SmokeError('Core has an unexpected non-project data mount')
            def mapped_origin():
                published = run(compose + ['port', 'core', '8000'])
                if not re.fullmatch(r'127\.0\.0\.1:[0-9]+', published):
                    raise SmokeError('Core must publish exactly one dynamic IPv4 loopback port')
                return 'http://' + published
            origin = mapped_origin()
            opener = build_opener(ProxyHandler({}), NoRedirect())

            def request(path, method='GET', body=None, expected=200, owner=False, wrong_key=False, raw=False):
                headers = {'X-Jarvis-Key': key} if owner else ({'X-Jarvis-Key': 'synthetic-invalid-key'} if wrong_key else {})
                if body is not None:
                    body = json.dumps(body).encode()
                    headers['Content-Type'] = 'application/json'
                req = Request(origin + path, data=body, method=method, headers=headers)
                try:
                    response = opener.open(req, timeout=2)
                except HTTPError as exc:
                    response = exc
                with response:
                    data = response.read(1024 * 1024)
                    if response.code != expected:
                        raise SmokeError(f'{method} {path}: expected HTTP {expected}, received {response.code}')
                    return data.decode('utf-8') if raw else json.loads(data) if data and response.headers.get_content_type() == 'application/json' else None

            def wait_ready():
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    try:
                        if request('/health')['status'] == 'ok' and request('/ready')['status'] == 'ready':
                            return
                    except (OSError, URLError, SmokeError, ValueError, TypeError):
                        pass
                    time.sleep(0.5)
                raise SmokeError('Core health/readiness did not pass within 60 seconds')

            wait_ready()
            html = request('/control/', raw=True)
            assets = re.findall(r'(?:src|href)="(/control/assets/[^"<>]+\.(?:js|css))"', html)
            if not assets or not any(asset.endswith('.js') for asset in assets) or not any(asset.endswith('.css') for asset in assets):
                raise SmokeError('Built Control Center must reference local JavaScript and CSS')
            for asset in assets:
                if not request(asset, raw=True):
                    raise SmokeError('Built Control Center asset is empty')
            request('/control/assets/missing.js', expected=404)
            request('/api/v1/status', expected=401)
            request('/api/v1/status', expected=401, wrong_key=True)
            request('/api/v1/status', owner=True)
            note = request('/api/v1/memory', 'POST', {'text': 'Synthetic Docker persistence check'}, 201, True)
            run(compose + ['restart', 'core'], timeout=60)
            # A zero host-port binding may receive a new port on restart.
            origin = mapped_origin()
            wait_ready()
            if not any(row['id'] == note['id'] for row in request('/api/v1/memory', owner=True)):
                raise SmokeError('Synthetic memory was lost after restarting core')
            request('/api/v1/memory', 'POST', {'text': 'x' * 70000}, 413, True)
            image_id = run(docker + ['inspect', '--format', '{{.Image}}', cid])
            uid = run(docker + ['exec', cid, 'id', '-u'])
            if not uid.isdecimal() or int(uid) == 0:
                raise SmokeError('Core must run as a non-root user')
            deadline = time.monotonic() + 60
            while run(docker + ['inspect', '--format', '{{.State.Health.Status}}', cid], timeout=5) != 'healthy':
                if time.monotonic() >= deadline:
                    raise SmokeError('Docker HEALTHCHECK did not become healthy within 60 seconds')
                time.sleep(0.5)
            checks = ['control_ui_assets', 'compose', 'health', 'readiness', 'auth', 'memory_restart', 'body_limit', 'non_root', 'docker_health']
        except (SmokeError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            error = str(exc) or type(exc).__name__
            try:
                run(compose + ['logs', '--no-color', '--tail', '40', 'core'], timeout=10, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        finally:
            try:
                run(compose + ['down', '--volumes', '--remove-orphans', '--timeout', '5'], timeout=60)
            except (SmokeError, OSError, subprocess.TimeoutExpired) as exc:
                error = (error + '; ' if error else '') + f'Cleanup failed: {exc}'
        if error:
            detail = '\n'.join(command + '\n' + output for command, output in logs[-8:])
            print(('Docker smoke FAIL: ' + error + '\n' + detail).replace(key, '[REDACTED]'), file=sys.stderr)
            return 1
    print(json.dumps({'status': 'PASS', 'checks': checks, 'cleanup': 'removed_project_volumes',
                      'integrations': 'disabled', 'image': args.image, 'image_id': image_id}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
