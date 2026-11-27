"""Installer first-run configuration must preserve user state and isolation."""
import os
import sys
import pytest
from scripts.windows_launcher import prepare, LocalServer


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(os, 'environ', dict(os.environ))
    monkeypatch.setattr(sys, 'path', list(sys.path))
    monkeypatch.chdir(tmp_path)


def test_first_run_secret_is_unique_and_survives_restart(tmp_path):
    first = tmp_path / 'first'
    key = prepare(first)
    raw = (first / '.env').read_bytes()
    assert len(key) >= 32 and key.isascii()
    assert prepare(first) == key and (first / '.env').read_bytes() == raw
    assert prepare(tmp_path / 'second') != key


def test_invalid_existing_configuration_is_not_replaced(tmp_path):
    config = tmp_path / '.env'
    config.write_text('JARVIS_API_KEY=short\n', encoding='utf-8')
    with pytest.raises(ValueError):
        prepare(tmp_path)
    assert config.read_text(encoding='utf-8') == 'JARVIS_API_KEY=short\n'


def test_unrelated_integrations_cannot_leak_from_parent_environment(tmp_path):
    os.environ['AUTOLOGIKA_READONLY_ENABLED'] = 'true'
    os.environ['JARVIS_POSTGRES_DSN'] = 'foreign-database'
    os.environ['OPENAI_API_KEY'] = 'foreign-secret'
    prepare(tmp_path)
    assert 'AUTOLOGIKA_READONLY_ENABLED' not in os.environ
    assert 'JARVIS_POSTGRES_DSN' not in os.environ
    assert 'OPENAI_API_KEY' not in os.environ
    assert os.environ['JARVIS_DB'] == str(tmp_path / 'jarvis.db')


def test_local_server_binds_loopback_without_secret_in_url(tmp_path):
    server = LocalServer(tmp_path)
    try:
        assert server.sock.getsockname()[0] == '127.0.0.1'
        assert server.key not in server.url
        assert server.url.endswith('/control/')
    finally:
        server.sock.close()


# ----------------------------------------------------------------- desktop window (Edge/Chrome app mode)
from scripts.windows_launcher import app_command, desktop_url, find_app_browser, open_desktop, remember_port, remembered_port


def test_desktop_window_prefers_edge_then_chrome():
    env = {'PROGRAMFILES(X86)': r'C:\PF86', 'PROGRAMFILES': r'C:\PF', 'LOCALAPPDATA': r'C:\Users\e\AppData\Local'}
    edge = os.path.join('C:\\PF86', 'Microsoft', 'Edge', 'Application', 'msedge.exe')
    chrome = os.path.join('C:\\PF', 'Google', 'Chrome', 'Application', 'chrome.exe')
    found = find_app_browser(env, exists=lambda path: str(path).replace('/', '\\') in (edge.replace('/', '\\'), chrome.replace('/', '\\')))
    assert str(found).replace('/', '\\').endswith('Edge\\Application\\msedge.exe')
    found = find_app_browser(env, exists=lambda path: str(path).replace('/', '\\') == chrome.replace('/', '\\'))
    assert str(found).replace('/', '\\').endswith('Chrome\\Application\\chrome.exe')
    assert find_app_browser(env, exists=lambda path: False) is None


def test_app_window_command_has_no_secret_and_uses_localhost(tmp_path):
    command = app_command('msedge.exe', 17321, tmp_path)
    assert command[0] == 'msedge.exe'
    assert '--app=http://localhost:17321/control/#/kiosk' in command
    assert any(item.startswith('--user-data-dir=') and item.endswith('desktop-window') for item in command)
    assert not any('JARVIS_API_KEY' in item or 'key=' in item.lower() for item in command)
    assert desktop_url(8000, 'gate') == 'http://localhost:8000/control/#/gate'


def test_open_desktop_falls_back_to_default_browser(monkeypatch, tmp_path):
    opened, started = [], []
    monkeypatch.setattr('scripts.windows_launcher.webbrowser.open', opened.append)
    assert open_desktop(17321, tmp_path, environ={}) == 'browser'
    assert opened == ['http://localhost:17321/control/#/kiosk']
    edge_root = tmp_path / 'pf'
    exe = edge_root / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b'')
    assert open_desktop(17321, tmp_path, environ={'PROGRAMFILES': str(edge_root)}, runner=lambda command, **kwargs: started.append(command)) == 'app'
    assert started and started[0][0] == str(exe)


def test_second_launch_reuses_the_running_port(tmp_path):
    assert remembered_port(tmp_path) is None
    remember_port(tmp_path, 17321)
    assert remembered_port(tmp_path) == 17321
    (tmp_path / 'desktop-port.txt').write_text('99', encoding='ascii')
    assert remembered_port(tmp_path) is None  # out of range / tampered


@pytest.mark.skipif(os.name != 'nt', reason='Edge location is checked on the Windows runner')
def test_windows_runner_has_an_app_mode_browser():
    found = find_app_browser()
    assert found is not None and found.name in ('msedge.exe', 'chrome.exe')


def test_app_window_profile_allows_the_microphone_only_for_jarvis(tmp_path):
    import json
    from scripts.windows_launcher import allow_microphone
    preferences = tmp_path / 'desktop-window' / 'Default' / 'Preferences'
    preferences.parent.mkdir(parents=True)
    blocked = {'other': 1, 'profile': {'content_settings': {'exceptions': {'media_stream_mic': {
        'http://localhost:17321,*': {'setting': 2}, 'https://example.com:443,*': {'setting': 2}}}}}}
    preferences.write_text(json.dumps(blocked), encoding='utf-8')
    assert allow_microphone(tmp_path, 17321) is True
    data = json.loads(preferences.read_text(encoding='utf-8'))
    mic = data['profile']['content_settings']['exceptions']['media_stream_mic']
    assert mic['http://localhost:17321,*']['setting'] == 1 and mic['https://example.com:443,*'] == {'setting': 2}
    assert data['other'] == 1
    assert allow_microphone(tmp_path, 17321) is False  # already allowed: file left alone
    fresh = tmp_path / 'fresh'
    assert allow_microphone(fresh, 17400) is True
    assert json.loads((fresh / 'desktop-window' / 'Default' / 'Preferences').read_text())['profile']['content_settings']['exceptions']['media_stream_mic'] == {
        'http://localhost:17400,*': json.loads((fresh / 'desktop-window' / 'Default' / 'Preferences').read_text())['profile']['content_settings']['exceptions']['media_stream_mic']['http://localhost:17400,*']}
    (fresh / 'desktop-window' / 'Default' / 'Preferences').write_text('not json')
    assert allow_microphone(fresh, 17400) is False  # corrupt profile: never crashes the launcher
