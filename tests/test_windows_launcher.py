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
