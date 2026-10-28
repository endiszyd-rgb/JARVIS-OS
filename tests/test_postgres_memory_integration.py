"""Actual isolated PostgreSQL/pgvector, never a configured user database."""
from contextlib import contextmanager
from dataclasses import dataclass,field
import json
import os
from pathlib import Path
import shutil
import uuid
import psycopg
import pytest
from pydantic import SecretStr
from fastapi import HTTPException
from jarvis.postgres_store import PostgresConfig,PostgresStore
from jarvis.postgres_memory import PostgresMemory
from jarvis.postgres_migrations import migrate,migrate_memory,MigrationError

pytestmark=pytest.mark.skipif(os.environ.get('JARVIS_TEST_POSTGRES_MEMORY')!='true',reason='Run scripts/check_postgres.py --memory for an isolated pgvector cluster')
NAMESPACE='a'*64

@dataclass(repr=False)
class MemoryDatabase:
    admin:str=field(repr=False)
    runtime:str=field(repr=False)
    memory:PostgresMemory=field(repr=False)
    def __repr__(self):return '<guarded isolated pgvector test>'
    @contextmanager
    def user(self,subject):
        with psycopg.connect(self.runtime) as c:
            c.execute('SET LOCAL ROLE authenticated')
            c.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':str(subject)}),))
            yield c

@pytest.fixture(scope='module')
def database():
    admin=os.environ['JARVIS_TEST_POSTGRES_ADMIN_DSN'];runtime=os.environ['JARVIS_TEST_POSTGRES_RUNTIME_DSN']
    with psycopg.connect(admin) as c:
        assert c.execute('SELECT id FROM jarvis_test_guard.isolation').fetchall()==[(os.environ['JARVIS_TEST_POSTGRES_ISOLATION'],)]
    migrate(admin);migrate_memory(admin)
    return MemoryDatabase(admin,runtime,PostgresMemory(PostgresStore(PostgresConfig(dsn=SecretStr(runtime)))))

def expect(status,fn,*args,**kwargs):
    with pytest.raises(HTTPException) as caught:fn(*args,**kwargs)
    assert caught.value.status_code==status

def workshop(db,users):
    ident=uuid.uuid4()
    with psycopg.connect(db.admin) as c:
        c.execute('INSERT INTO jarvis.workshops(id,name) VALUES(%s,%s)',(ident,'Synthetic memory workshop'))
        for user,write in users:
            c.execute('INSERT INTO jarvis.memberships(workshop_id,user_id,can_write) VALUES(%s,%s,%s)',(ident,user,write))
    return ident

def index(db,user,row,values=(1,0),namespace=NAMESPACE):
    return db.memory.index(user,row['id'],row['revision'],row['text_hash'],list(values),namespace)


def test_memory_migration_replay_and_foundation_remain_independent(database):
    db=database;user=uuid.uuid4()
    row=db.memory.create(user,'Migration memory sentinel')
    assert migrate_memory(db.admin)==migrate_memory(db.admin)
    assert migrate(db.admin)[-1]['version']==1
    assert db.memory.storage.status()['schema_version']==1
    assert db.memory.status()['pgvector_version']=='0.8.2'
    assert db.memory.get(user,row['id'])['content']=='Migration memory sentinel'


def test_private_scopes_and_immutable_identity_are_enforced_by_sql(database):
    db=database;a,b=uuid.uuid4(),uuid.uuid4()
    row=db.memory.create(a,'Private memory')
    assert db.memory.list(b)==[]
    expect(404,db.memory.get,b,row['id'])
    expect(404,db.memory.update,b,row['id'],0,'Steal')
    expect(404,db.memory.delete,b,row['id'],0)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.user(a) as c:c.execute('UPDATE jarvis.memory_records SET owner_id=%s WHERE id=%s',(b,row['id']))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db.user(b) as c:c.execute('INSERT INTO jarvis.memory_records(owner_id,content) VALUES(%s,%s)',(a,'Forged'))


def test_workshop_memory_never_merges_with_private_or_other_workshop(database):
    db=database;a,b,c=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    w1=workshop(db,[(a,True),(b,False)]);w2=workshop(db,[(c,True)])
    own=db.memory.create(a,'Private own');shared=db.memory.create(a,'First workshop',workshop_id=w1)
    foreign=db.memory.create(c,'Second workshop',workshop_id=w2)
    assert [r['id'] for r in db.memory.list(a)]==[own['id']]
    assert [r['id'] for r in db.memory.list(b,workshop_id=w1)]==[shared['id']]
    assert db.memory.list(b,workshop_id=w2)==[]
    expect(404,db.memory.get,b,foreign['id'])
    expect(403,db.memory.create,b,'Read-only cannot write',workshop_id=w1)
    expect(403,db.memory.update,b,shared['id'],0,'Not allowed')
    expect(403,db.memory.prepare_index,b,shared['id'],0)
    with psycopg.connect(db.admin) as connection:
        connection.execute('DELETE FROM jarvis.memberships WHERE workshop_id=%s AND user_id=%s',(w1,a))
    expect(404,db.memory.get,a,shared['id'])
    assert db.memory.get(a,own['id'])['content']=='Private own'


def test_pgvector_search_filters_subject_scope_namespace_and_dimensions(database):
    db=database;a,b=uuid.uuid4(),uuid.uuid4();w=workshop(db,[(a,True)])
    near=index(db,a,db.memory.create(a,'Near memory'),(1,0))
    far=index(db,a,db.memory.create(a,'Far memory'),(0,1))
    index(db,b,db.memory.create(b,'Foreign closer'),(1,0))
    index(db,a,db.memory.create(a,'Workshop closer',workshop_id=w),(1,0))
    index(db,a,db.memory.create(a,'Other namespace'),(1,0),'b'*64)
    index(db,a,db.memory.create(a,'Other dimension'),(1,0,0))
    found=db.memory.semantic(a,[1,0],NAMESPACE)
    assert [r['id'] for r in found]==[near['id'],far['id']]
    assert found[0]['distance']==pytest.approx(0) and found[1]['distance']==pytest.approx(1)
    assert len(db.memory.semantic(a,[1,0],NAMESPACE,workshop_id=w))==1
    assert db.memory.semantic(b,[1,0],NAMESPACE,workshop_id=w)==[]


def test_correction_invalidates_vectors_and_stale_index_cannot_overwrite(database):
    db=database;user=uuid.uuid4()
    first=db.memory.create(user,'Original text')
    prepared=db.memory.prepare_index(user,first['id'],0)
    changed=db.memory.update(user,first['id'],0,'Corrected text')
    assert changed['text_hash']!=prepared['text_hash'] and changed['revision']==1
    expect(409,db.memory.index,user,first['id'],0,prepared['text_hash'],[1,0],NAMESPACE)
    indexed=index(db,user,changed)
    assert indexed['indexed'] and indexed['revision']==2
    updated=db.memory.update(user,first['id'],2,'Changed again')
    assert not updated['indexed'] and updated['embedding_namespace'] is None
    assert db.memory.semantic(user,[1,0],NAMESPACE)==[]
    expect(409,db.memory.delete,user,first['id'],2)
    assert db.memory.delete(user,first['id'],3)=={'deleted':str(first['id'])}


def test_memory_audit_contains_only_metadata_and_rolls_back_with_failure(database):
    db=database;user=uuid.uuid4();row=db.memory.create(user,'Private audit sentinel')
    with db.user(user) as c:
        events=c.execute('SELECT subject,event,memory_id,revision FROM jarvis.memory_events WHERE memory_id=%s',(row['id'],)).fetchall()
        assert events==[(user,'created',row['id'],0)]
        columns=c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='jarvis' AND table_name='memory_events'").fetchall()
        assert {r[0] for r in columns}=={'id','subject','event','memory_id','revision','created_at'}
    with psycopg.connect(db.admin) as c:
        c.execute("CREATE FUNCTION jarvis.fail_memory_event() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic failure'; END $$")
        c.execute('CREATE TRIGGER fail_memory_event BEFORE INSERT ON jarvis.memory_events FOR EACH ROW EXECUTE FUNCTION jarvis.fail_memory_event()')
    try:
        expect(503,db.memory.update,user,row['id'],0,'Must roll back')
        assert db.memory.get(user,row['id'])['content']=='Private audit sentinel'
    finally:
        with psycopg.connect(db.admin) as c:
            c.execute('DROP TRIGGER fail_memory_event ON jarvis.memory_events');c.execute('DROP FUNCTION jarvis.fail_memory_event()')


@pytest.mark.parametrize('role',['anon','service_role'])
def test_platform_roles_have_no_memory_access(database,role):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with psycopg.connect(database.admin) as c:
            c.execute('SET LOCAL ROLE '+role)
            c.execute('SELECT * FROM jarvis.memory_records')


def test_memory_migration_checksum_failure_is_atomic(database,tmp_path):
    source=Path(__file__).resolve().parents[1]/'migrations/postgres_memory'
    destination=tmp_path/'memory';shutil.copytree(source,destination)
    first=destination/'0001_memory.sql';first.write_text(first.read_text()+'\n-- Mutated checksum\n')
    with pytest.raises(MigrationError):migrate_memory(database.admin,destination)
    first.write_bytes((source/'0001_memory.sql').read_bytes())
    (destination/'0005_failure.sql').write_text('CREATE TABLE jarvis.memory_rolled_back(id int); SELECT jarvis.missing_memory_function();')
    with pytest.raises(MigrationError):migrate_memory(database.admin,destination)
    with psycopg.connect(database.admin) as c:
        assert c.execute("SELECT to_regclass('jarvis.memory_rolled_back')").fetchone()[0] is None
    assert database.memory.status()['memory_schema_version']==4


@pytest.fixture
def memory_client(database,tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from jarvis.main import create_app
    monkeypatch.setenv('JARVIS_POSTGRES_DSN',database.runtime)
    monkeypatch.setenv('JARVIS_POSTGRES_MEMORY_ENABLED','true')
    key='synthetic-memory-real-api-key-32chars'
    with TestClient(create_app(tmp_path/'memory-api.db',key),headers={'X-Jarvis-Key':key}) as client:
        yield client


def owner(client,name):
    password='synthetic-memory-owner-password-32chars'
    account=client.post('/api/security/users',json={'username':name,'password':password,'role':'owner'})
    assert account.status_code==201,account.text
    session=client.post('/api/auth/login',json={'username':name,'password':password})
    assert session.status_code==200,session.text
    return account.json()['id'],{'X-Jarvis-Key':session.json()['token']}


@contextmanager
def embedding_server(monkeypatch,on_input=None):
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    import threading
    seen=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append(value)
            assert self.path=='/api/embed' and value['truncate'] is False
            if on_input:on_input(value)
            raw=json.dumps({'embeddings':[[1,0] for _ in value['input']]}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setenv('JARVIS_EMBEDDINGS_ENABLED','true');monkeypatch.setenv('OLLAMA_EMBED_MODEL','synthetic-memory:local')
    monkeypatch.setenv('OLLAMA_EMBED_URL',f'http://127.0.0.1:{server.server_port}')
    monkeypatch.setenv('JARVIS_NETWORK_ALLOWLIST','127.0.0.0/8,::1/128')
    try:yield seen
    finally:server.shutdown();server.server_close();thread.join(timeout=5)


def test_real_memory_api_crud_embedding_protocol_search_and_private_subjects(memory_client,monkeypatch):
    c=memory_client
    alice,a=owner(c,'memory.alice');bob,b=owner(c,'memory.bob')
    assert c.get('/api/storage/memory/status',headers=a).json()['memory_schema_version']==4
    first=c.post('/api/storage/memory',headers=a,json={'content':'Synthetic Alice memory','source':'manual'})
    assert first.status_code==201,first.text
    row=first.json();ident=row['id']
    assert row['owner_id']==alice and row['revision']==0 and row['indexed'] is False
    assert c.get('/api/storage/memory/'+ident,headers=b).status_code==404
    assert c.get('/api/storage/memory',headers=b).json()==[]
    with embedding_server(monkeypatch) as seen:
        indexed=c.post('/api/storage/memory/'+ident+'/index',headers=a,json={'revision':0})
        assert indexed.status_code==200,indexed.text
        assert indexed.json()['indexed'] and indexed.json()['revision']==1
        found=c.post('/api/storage/memory/search',headers=a,json={'query':'Synthetic query'})
        assert found.status_code==200,found.text
        assert [r['id'] for r in found.json()['results']]==[ident]
        assert c.post('/api/storage/memory/search',headers=b,json={'query':'Synthetic query'}).json()['results']==[]
        assert seen[0]['input']==['Synthetic Alice memory'] and seen[1]['input']==['Synthetic query']
        before=len(seen)
        assert c.post('/api/storage/memory/'+ident+'/index',headers=b,json={'revision':1}).status_code==404
        assert c.post('/api/storage/memory/'+ident+'/index',headers=a,json={'revision':0}).status_code==409
        assert len(seen)==before
    updated=c.patch('/api/storage/memory/'+ident,headers=a,json={'revision':1,'content':'Corrected memory'})
    assert updated.status_code==200 and updated.json()['indexed'] is False and updated.json()['revision']==2
    assert c.delete('/api/storage/memory/'+ident+'?revision=1',headers=a).status_code==409
    assert c.delete('/api/storage/memory/'+ident+'?revision=2',headers=a).status_code==200
    assert c.get('/api/storage/memory/'+ident,headers=a).status_code==404
    audit=c.get('/api/audit').text
    assert 'Synthetic Alice memory' not in audit and 'Synthetic query' not in audit


@pytest.mark.parametrize('change',['revision','revocation'])
def test_memory_api_rechecks_revision_and_current_owner_after_embedding(memory_client,database,monkeypatch,change):
    import sqlite3
    c=memory_client;user,headers=owner(c,'memory.race')
    row=c.post('/api/storage/memory',headers=headers,json={'content':'Prepared text'}).json()
    def alter(_payload):
        if change=='revision':
            database.memory.update(uuid.UUID(user),row['id'],0,'Changed while embedding')
        else:
            with sqlite3.connect(c.app.state.runtime_config.database_path) as db:db.execute('UPDATE identity_sessions SET revoked=1')
    with embedding_server(monkeypatch,alter) as seen:
        response=c.post('/api/storage/memory/'+row['id']+'/index',headers=headers,json={'revision':0})
        assert response.status_code==(409 if change=='revision' else 401),response.text
        assert len(seen)==1
    persisted=database.memory.get(uuid.UUID(user),row['id'])
    assert not persisted['indexed'] and persisted['revision']==(1 if change=='revision' else 0)


def test_workshop_memory_api_requires_explicit_scope_and_writable_membership(memory_client,database,monkeypatch):
    c=memory_client;a,ha=owner(c,'memory.writer');b,hb=owner(c,'memory.reader')
    w=workshop(database,[(uuid.UUID(a),True),(uuid.UUID(b),False)])
    record=c.post('/api/storage/memory',headers=ha,json={'content':'Workshop memory','workshop_id':str(w)}).json()
    assert c.get('/api/storage/memory',headers=ha).json()==[]
    assert [r['id'] for r in c.get('/api/storage/memory?workshop_id='+str(w),headers=hb).json()]==[record['id']]
    with embedding_server(monkeypatch) as seen:
        assert c.post('/api/storage/memory/'+record['id']+'/index',headers=hb,json={'revision':0}).status_code==403
        assert seen==[]
        assert c.post('/api/storage/memory/'+record['id']+'/index',headers=ha,json={'revision':0}).status_code==200
        assert c.post('/api/storage/memory/search',headers=hb,json={'query':'Workshop'}).json()['results']==[]
        found=c.post('/api/storage/memory/search',headers=hb,json={'query':'Workshop','workshop_id':str(w)})
        assert [r['id'] for r in found.json()['results']]==[record['id']]
