"""Account/session authorization, audit privacy and additive schema12 migration."""
import json
import sqlite3
from fastapi.testclient import TestClient
import pytest
from jarvis.main import create_app

KEY='security-api-owner-key-32-characters'
PASSWORD='Synthetic-password-for-local-tests'
OWNER={'X-Jarvis-Key':KEY}

@pytest.mark.parametrize('database_state',['missing','corrupt'])
def test_operational_probes_ignore_stale_credentials_when_database_is_unavailable(tmp_path,database_state):
    path=tmp_path/'unavailable.db'
    with TestClient(create_app(path,KEY)) as c:
        path.unlink()
        if database_state=='corrupt':path.write_bytes(b'corrupt database sentinel')
        stale={'X-Jarvis-Key':'expired-session-synthetic-credential'}
        for route in ('/ready','/api/ready','/api/v1/ready'):
            response=c.get(route,headers=stale)
            assert response.status_code==503
            assert response.json()['status']=='not_ready'
        for route in ('/health','/','/ui/app.js'):
            assert c.get(route,headers=stale).status_code==200
        if database_state=='missing':assert not path.exists()
        else:assert path.read_bytes()==b'corrupt database sentinel'

@pytest.fixture
def client(tmp_path):
    path=tmp_path/'security.db'
    with TestClient(create_app(path,KEY)) as c:
        c.dbfile=path
        yield c

def user(c,role='observer',username='tester'):
    r=c.post('/api/v1/security/users',headers=OWNER,json={'username':username,'password':PASSWORD,'role':role})
    assert r.status_code==201,r.text
    return r.json()

def login(c,username='tester',password=PASSWORD,prefix='/api/v1'):
    r=c.post(prefix+'/auth/login',json={'username':username,'password':password})
    assert r.status_code==200,r.text
    return r.json()

@pytest.mark.parametrize('role',['observer','home_reader','workshop_reader','automation_runner'])
def test_role_sessions_cannot_access_owner_data_or_grant_themselves_privileges(client,role):
    c=client;account=user(c,role);session=login(c);headers={'X-Jarvis-Key':session['token']}
    assert c.get('/api/status',headers=headers).status_code==200
    me=c.get('/api/v1/auth/me',headers=headers).json()
    assert me['id']==account['id'] and me['role']==role and me['kind']=='session'
    for route in ('memory','telephony/settings','security/users','security/sessions','schema','reception/calls'):
        assert c.get('/api/v1/'+route,headers=headers).status_code==403,route
    assert c.post('/api/security/users',headers=headers,json={'username':'hacker','password':PASSWORD,'role':'owner'}).status_code==403
    assert c.post('/api/v1/telephony/transport/calls',headers=headers,json={'event_id':'00000000-0000-0000-0000-000000000001'}).status_code==403
    assert c.get('/api/home/states',headers=headers).status_code==(503 if role=='home_reader' else 403)
    assert c.get('/api/autologika/readonly/orders',headers=headers).status_code==(503 if role=='workshop_reader' else 403)
    assert c.get('/api/v1/autologika/snapshot/finances',headers=headers).status_code==403
    assert c.post('/api/automations/tick',headers=headers,json={}).status_code==(200 if role=='automation_runner' else 403)


def test_owner_login_shares_state_and_audits_actor_without_credentials(client):
    c=client;account=user(c,'owner');session=login(c,prefix='/api');headers={'X-Jarvis-Key':session['token']}
    note=c.post('/api/v1/memory',headers=headers,json={'text':'Private note remains private'});assert note.status_code==201
    assert len(c.get('/api/memory',headers=OWNER).json())==1
    events=c.get('/api/audit',headers=OWNER).json()
    assert any(json.loads(e['detail']).get('actor')=='session:'+account['id'] for e in events)
    serialized=json.dumps(events)
    for secret in (PASSWORD,session['token'],KEY,'Private note remains private'):assert secret not in serialized
    users=c.get('/api/security/users',headers=OWNER).text;sessions=c.get('/api/security/sessions',headers=OWNER).text
    for field in ('password_hash','token_digest',PASSWORD,session['token']):
        assert field not in users+sessions
    logout=c.post('/api/auth/logout',headers=headers);assert logout.status_code==200
    assert c.get('/api/v1/status',headers=headers).status_code==401


def test_failed_login_is_generic_but_audited_and_request_cannot_set_audit_actor(client):
    c=client;user(c)
    wrong=c.post('/api/v1/auth/login',json={'username':'tester','password':'Wrong-valid-length-password'})
    missing=c.post('/api/auth/login',json={'username':'missing','password':PASSWORD})
    assert wrong.status_code==missing.status_code==401 and wrong.json()==missing.json()
    assert c.post('/api/auth/login',json={'username':'tester','password':PASSWORD,'actor':'owner'}).status_code==422
    events=c.get('/api/audit',headers=OWNER).json()
    failed=[json.loads(e['detail']) for e in events if e['event']=='identity.login']
    assert len(failed)==2 and all(row['success'] is False and row['actor']=='anonymous' for row in failed)
    assert PASSWORD not in json.dumps(events)


def test_role_change_disable_revoke_expiry_and_restart_are_enforced(client):
    c=client;account=user(c);old=login(c);headers={'X-Jarvis-Key':old['token']}
    changed=c.patch('/api/security/users/'+account['id'],headers=OWNER,json={'revision':0,'role':'home_reader'})
    assert changed.status_code==200 and changed.json()['revision']==1
    assert c.get('/api/status',headers=headers).status_code==401
    assert c.patch('/api/v1/security/users/'+account['id'],headers=OWNER,json={'revision':0,'role':'owner'}).status_code==409
    active=login(c)
    with TestClient(create_app(c.dbfile,KEY)) as restarted:
        assert restarted.get('/api/v1/auth/me',headers={'X-Jarvis-Key':active['token']}).json()['role']=='home_reader'
    assert c.delete('/api/security/sessions/'+active['session_id'],headers=OWNER).status_code==200
    assert c.get('/api/status',headers={'X-Jarvis-Key':active['token']}).status_code==401
    expiring=login(c)
    with sqlite3.connect(c.dbfile) as db:db.execute('UPDATE identity_sessions SET expires_at=0 WHERE id=?',(expiring['session_id'],))
    assert c.get('/api/status',headers={'X-Jarvis-Key':expiring['token']}).status_code==401
    disabled=c.patch('/api/security/users/'+account['id'],headers=OWNER,json={'revision':1,'enabled':False})
    assert disabled.status_code==200
    assert c.post('/api/auth/login',json={'username':'tester','password':PASSWORD}).status_code==401


def test_login_limits_are_shared_by_aliases_and_cors_is_explicit(tmp_path,monkeypatch):
    monkeypatch.setenv('JARVIS_LOGIN_ATTEMPTS_PER_MINUTE','2')
    monkeypatch.setenv('JARVIS_CORS_ORIGINS','https://panel.example')
    with TestClient(create_app(tmp_path/'limits.db',KEY)) as c:
        data={'username':'missing','password':PASSWORD}
        assert c.post('/api/auth/login',json=data).status_code==401
        assert c.post('/api/v1/auth/login',json=data).status_code==401
        limited=c.post('/api/auth/login',json=data,headers={'Origin':'https://panel.example','X-Forwarded-For':'203.0.113.77'})
        assert limited.status_code==429 and int(limited.headers['Retry-After'])>0
        assert limited.headers['access-control-allow-origin']=='https://panel.example'
        allowed=c.options('/api/v1/status',headers={'Origin':'https://panel.example','Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'X-Jarvis-Key'})
        assert allowed.status_code==200
        denied=c.options('/api/v1/status',headers={'Origin':'https://other.example','Access-Control-Request-Method':'GET'})
        assert denied.status_code==400 and 'access-control-allow-origin' not in denied.headers
        assert c.get('/api/status',headers={**OWNER,'Origin':'https://other.example'}).status_code==200
        assert 'access-control-allow-origin' not in c.get('/ready',headers={'Origin':'https://other.example'}).headers


def test_schema11_backup_preserves_private_data_and_old_service_tokens(tmp_path):
    path=tmp_path/'old.db'
    with TestClient(create_app(path,KEY),headers=OWNER) as c:
        note=c.post('/api/memory',json={'text':'Preserved migration note'}).json()
        token=c.post('/api/security/tokens',json={'name':'old worker','scopes':['status:read']}).json()
    with sqlite3.connect(path) as db:
        db.executescript('DROP TABLE identity_sessions; DROP TABLE identity_users; PRAGMA user_version=11;')
    with TestClient(create_app(path,KEY)) as c:
        assert c.get('/ready').status_code==200
        assert c.get('/api/memory',headers=OWNER).json()[0]['id']==note['id']
        assert c.get('/api/v1/status',headers={'X-Jarvis-Key':token['token']}).status_code==200
        assert c.get('/api/security/users',headers=OWNER).json()==[]
        backup=list((tmp_path/'backups').glob('before-schema12-*.sqlite3'));assert len(backup)==1
        with sqlite3.connect(backup[0]) as db:
            assert db.execute('PRAGMA user_version').fetchone()[0]==11
            assert db.execute('SELECT text FROM memory').fetchone()[0]=='Preserved migration note'
            assert db.execute("SELECT name FROM sqlite_master WHERE name='identity_users'").fetchone() is None
    with TestClient(create_app(path,KEY)) as c:assert c.get('/ready').status_code==200
    assert len(list((tmp_path/'backups').glob('before-schema12-*.sqlite3')))==1
