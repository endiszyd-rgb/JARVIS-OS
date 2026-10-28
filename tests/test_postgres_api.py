"""HTTP identity binding for optional PostgreSQL; real tests use an isolated DB."""
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from jarvis.main import create_app
from jarvis.postgres_api import BOOTSTRAP_SUBJECT

KEY='postgres-api-synthetic-owner-key-32-chars'
OWNER={'X-Jarvis-Key':KEY}
PASSWORD='Synthetic-postgres-account-password'


def test_disabled_postgres_is_explicit_and_existing_sqlite_remains_usable(tmp_path,monkeypatch):
    monkeypatch.setenv('JARVIS_POSTGRES_DSN','')
    with TestClient(create_app(tmp_path/'disabled.db',KEY)) as c:
        assert c.get('/api/v1/storage/status').status_code==401
        for prefix in ('/api','/api/v1'):
            assert c.get(prefix+'/storage/status',headers=OWNER).json()=={
                'enabled':False,'status':'disabled','schema_version':None}
            assert c.get(prefix+'/storage/records',headers=OWNER).status_code==503
            assert c.post(prefix+'/storage/records',headers=OWNER,json={'title':'Disabled'}).status_code==503
        assert c.post('/api/memory',headers=OWNER,json={'text':'SQLite is preserved'}).status_code==201
        assert c.get('/ready').status_code==200


@pytest.fixture
def postgres_client(tmp_path,monkeypatch):
    admin=os.environ.get('JARVIS_TEST_POSTGRES_ADMIN_DSN')
    runtime=os.environ.get('JARVIS_TEST_POSTGRES_RUNTIME_DSN')
    guard=os.environ.get('JARVIS_TEST_POSTGRES_ISOLATION')
    if not admin or not runtime or not guard:pytest.skip('Run scripts/check_postgres.py for isolated real PostgreSQL tests')
    import psycopg
    with psycopg.connect(admin,connect_timeout=5) as connection:
        assert connection.execute('SELECT id FROM jarvis_test_guard.isolation').fetchall()==[(guard,)]
    from jarvis.postgres_migrations import migrate
    migrate(admin)
    monkeypatch.setenv('JARVIS_POSTGRES_DSN',runtime)
    with TestClient(create_app(tmp_path/'pg-api.db',KEY)) as c:yield c


def login_owner(c,username):
    account=c.post('/api/security/users',headers=OWNER,json={
        'username':username,'password':PASSWORD,'role':'owner'})
    assert account.status_code==201,account.text
    session=c.post('/api/v1/auth/login',json={'username':username,'password':PASSWORD})
    assert session.status_code==200,session.text
    return account.json(),{'X-Jarvis-Key':session.json()['token']}


def test_verified_subjects_are_bound_to_distinct_private_postgres_rows(postgres_client):
    c=postgres_client
    alice,a=login_owner(c,'alice');bob,b=login_owner(c,'bob')
    assert c.get('/api/v1/storage/status',headers=a).json()['schema_version']==1
    record=c.post('/api/v1/storage/records',headers=a,json={'title':'Alice private','payload':{'note':'synthetic'}})
    assert record.status_code==201,record.text
    row=record.json();ident=row['id']
    assert row['owner_id']==alice['id'] and row['workshop_id'] is None and row['revision']==0
    assert c.get('/api/storage/records/'+ident,headers=a).json()['payload']=={'note':'synthetic'}
    for headers in (b,OWNER):
        assert c.get('/api/storage/records/'+ident,headers=headers).status_code==404
        assert c.patch('/api/storage/records/'+ident,headers=headers,json={'revision':0,'title':'Stolen'}).status_code==404
        assert c.delete('/api/storage/records/'+ident+'?revision=0',headers=headers).status_code==404
        assert all(item['id']!=ident for item in c.get('/api/storage/records',headers=headers).json())
    for field,value in (('owner_id',bob['id']),('subject',bob['id']),('workshop_id',str(uuid.uuid4()))):
        assert c.patch('/api/storage/records/'+ident,headers=a,json={
            'revision':0,'title':'Forged',field:value}).status_code==422
    assert c.post('/api/storage/records',headers=a,json={'title':'Bad','owner_id':bob['id']}).status_code==422
    assert c.post('/api/storage/records',headers=a,json={'title':'Unknown workshop','workshop_id':str(uuid.uuid4())}).status_code in (403,422)
    changed=c.patch('/api/storage/records/'+ident,headers=a,json={'revision':0,'title':'Updated','payload':{'v':2}})
    assert changed.status_code==200 and changed.json()['revision']==1
    assert c.patch('/api/v1/storage/records/'+ident,headers=a,json={'revision':0,'title':'Stale'}).status_code==409
    assert c.delete('/api/storage/records/'+ident+'?revision=0',headers=a).status_code==409
    assert c.delete('/api/v1/storage/records/'+ident+'?revision=1',headers=a).status_code==200
    assert c.get('/api/storage/records/'+ident,headers=a).status_code==404


def test_bootstrap_namespace_is_stable_and_session_revocation_still_applies(postgres_client):
    c=postgres_client
    created=c.post('/api/storage/records',headers=OWNER,json={'title':'Bootstrap private'})
    assert created.status_code==201,created.text
    row=created.json();assert row['owner_id']==str(BOOTSTRAP_SUBJECT)
    account,headers=login_owner(c,'owner.session')
    assert c.get('/api/storage/records/'+row['id'],headers=headers).status_code==404
    assert c.post('/api/auth/logout',headers=headers).status_code==200
    assert c.get('/api/storage/records',headers=headers).status_code==401
    observer=c.post('/api/security/users',headers=OWNER,json={'username':'observer','password':PASSWORD,'role':'observer'})
    assert observer.status_code==201
    login=c.post('/api/auth/login',json={'username':'observer','password':PASSWORD}).json()
    assert c.get('/api/storage/records',headers={'X-Jarvis-Key':login['token']}).status_code==403
    assert c.delete('/api/storage/records/'+row['id']+'?revision=0',headers=OWNER).status_code==200
