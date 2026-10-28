"""Built UI assets are public, bounded to their directory and independent of DB."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jarvis.control_ui import mount
from jarvis.main import create_app

KEY='control-ui-test-owner-key-32-characters'


def test_missing_build_is_explicit_without_breaking_legacy_panel(tmp_path):
    app=FastAPI();mount(app,tmp_path/'absent')
    with TestClient(app) as c:
        assert c.get('/control').status_code==503
        assert c.get('/control/').status_code==503
        assert c.get('/control/assets/missing.js').status_code==404
    with TestClient(create_app(tmp_path/'core.db',KEY)) as c:
        assert c.get('/').status_code==200
        assert c.get('/ui/app.js').status_code==200


def test_built_assets_have_correct_content_and_reject_traversal_or_symlinks(tmp_path):
    base=tmp_path/'dist';(base/'assets').mkdir(parents=True)
    (base/'index.html').write_text('<!doctype html><title>React fixture</title>')
    (base/'assets'/'index-demo.js').write_text('export const safe=true;')
    (base/'assets'/'index-demo.css').write_text('body { color: white; }')
    secret=tmp_path/'private.txt';secret.write_text('Synthetic private file outside assets')
    try:(base/'assets'/'escape.js').symlink_to(secret)
    except (OSError,NotImplementedError):pass
    app=FastAPI();mount(app,base)
    with TestClient(app) as c:
        for path in ('/control','/control/'):
            assert c.get(path).status_code==200
        script=c.get('/control/assets/index-demo.js')
        assert script.status_code==200 and 'javascript' in script.headers['content-type']
        assert c.get('/control/assets/index-demo.css').headers['content-type'].startswith('text/css')
        for name in ('%2e%2e%2fprivate.txt','nested/file.js','escape.js','index-demo.js.map','.env','index-demo.js%00','private.txt'):
            response=c.get('/control/assets/'+name)
            assert response.status_code==404
            assert 'Synthetic private file' not in response.text


@pytest.mark.parametrize('path',['/control','/control/','/control/assets/missing.js'])
def test_control_ui_does_not_create_missing_database_for_stale_header(tmp_path,path):
    database=tmp_path/'missing.db'
    with TestClient(create_app(database,KEY)) as c:
        database.unlink()
        response=c.get(path,headers={'X-Jarvis-Key':'stale-control-session-credential'})
        assert response.status_code in (200,404,503)
        assert not database.exists()
        assert response.headers['Content-Security-Policy'].startswith("default-src 'self'")
        assert 'unsafe-inline' not in response.headers['Content-Security-Policy']
