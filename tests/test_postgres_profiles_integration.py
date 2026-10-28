"""Version snapshots, scoped instruction profiles and atomic deletion on real PG."""
import os
import uuid
import psycopg
import pytest
from jarvis.postgres_profiles import PostgresProfiles
from test_postgres_memory_integration import database,memory_client,owner,workshop,expect

pytestmark=pytest.mark.skipif(os.environ.get('JARVIS_TEST_POSTGRES_MEMORY')!='true',reason='Run scripts/check_postgres.py --memory for the guarded database')

@pytest.fixture
def profiles(database):return PostgresProfiles(database.memory.storage)


def test_private_profile_revisions_and_cascade_deletion(profiles,database):
    a,b=uuid.uuid4(),uuid.uuid4()
    row=profiles.create(a,'Concise','Answer briefly in Polish.')
    assert profiles.list(b)==[]
    expect(404,profiles.get,b,row['id']);expect(404,profiles.history,b,row['id'])
    assert [r['revision'] for r in profiles.history(a,row['id'])]==[0]
    updated=profiles.update(a,row['id'],0,'Detailed','Explain with examples.')
    assert updated['revision']==1
    expect(409,profiles.update,a,row['id'],0,'Stale','Must not be saved.')
    assert [r['instructions'] for r in profiles.history(a,row['id'])]==['Explain with examples.','Answer briefly in Polish.']
    profiles.delete(a,row['id'],1)
    with psycopg.connect(database.admin) as c:
        assert c.execute('SELECT count(*) FROM jarvis.memory_profile_versions WHERE profile_id=%s',(row['id'],)).fetchone()[0]==0
    with database.user(a) as c:
        assert [r[0] for r in c.execute('SELECT event FROM jarvis.memory_profile_events WHERE profile_id=%s ORDER BY created_at,id',(row['id'],))]==['created','updated','deleted']


def test_note_history_is_real_snapshots_and_is_removed_with_the_note(profiles,database):
    a,b=uuid.uuid4(),uuid.uuid4()
    note=database.memory.create(a,'Original note')
    database.memory.update(a,note['id'],0,'Corrected note')
    history=profiles.memory_history(a,note['id'])
    assert [(v['revision'],v['content']) for v in history['versions']]==[(1,'Corrected note'),(0,'Original note')]
    expect(404,profiles.memory_history,b,note['id'])
    database.memory.delete(a,note['id'],1)
    with psycopg.connect(database.admin) as c:
        assert c.execute('SELECT count(*) FROM jarvis.memory_versions WHERE memory_id=%s',(note['id'],)).fetchone()[0]==0
    expect(404,profiles.memory_history,a,note['id'])


def test_workshop_profile_history_respects_read_only_membership(profiles,database):
    writer,reader,foreign=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    scope=workshop(database,[(writer,True),(reader,False)])
    row=profiles.create(writer,'Workshop style','Use verified facts.',workshop_id=scope)
    assert profiles.list(reader)==[]
    assert profiles.list(reader,workshop_id=scope)[0]['id']==row['id']
    assert len(profiles.history(reader,row['id']))==1
    expect(403,profiles.update,reader,row['id'],0,'Not writable','Blocked')
    expect(403,profiles.delete,reader,row['id'],0)
    expect(403,profiles.create,reader,'No','Blocked',workshop_id=scope)
    expect(404,profiles.history,foreign,row['id'])
    with psycopg.connect(database.admin) as c:c.execute('DELETE FROM jarvis.memberships WHERE workshop_id=%s AND user_id=%s',(scope,writer))
    expect(404,profiles.get,writer,row['id'])


@pytest.mark.parametrize('table,column',[('memory_versions','memory_id'),('memory_profile_versions','profile_id')])
def test_runtime_cannot_edit_or_delete_version_snapshots(profiles,database,table,column):
    user=uuid.uuid4()
    row=database.memory.create(user,'Snapshot') if table=='memory_versions' else profiles.create(user,'Profile','Snapshot')
    for statement in (f'DELETE FROM jarvis.{table} WHERE {column}=%s',f'UPDATE jarvis.{table} SET revision=revision+1 WHERE {column}=%s'):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with database.user(user) as c:c.execute(statement,(row['id'],))
    with database.user(user) as c:
        assert c.execute(f'SELECT count(*) FROM jarvis.{table} WHERE {column}=%s',(row['id'],)).fetchone()[0]==1


def test_profile_audit_failure_rolls_back_profile_and_version(profiles,database):
    user=uuid.uuid4();row=profiles.create(user,'Before','Original instructions.')
    with psycopg.connect(database.admin) as c:
        c.execute("CREATE FUNCTION jarvis.fail_profile_event() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic failure'; END $$")
        c.execute('CREATE TRIGGER fail_profile_event BEFORE INSERT ON jarvis.memory_profile_events FOR EACH ROW EXECUTE FUNCTION jarvis.fail_profile_event()')
    try:
        expect(503,profiles.update,user,row['id'],0,'After','Must roll back.')
        assert profiles.get(user,row['id'])['instructions']=='Original instructions.'
        assert [v['revision'] for v in profiles.history(user,row['id'])]==[0]
    finally:
        with psycopg.connect(database.admin) as c:
            c.execute('DROP TRIGGER fail_profile_event ON jarvis.memory_profile_events');c.execute('DROP FUNCTION jarvis.fail_profile_event()')


def test_owner_profile_api_and_note_version_routes_are_not_record_ids(memory_client):
    c=memory_client;_,a=owner(c,'profiles.alice');_,b=owner(c,'profiles.bob')
    created=c.post('/api/storage/memory/profiles',headers=a,json={'name':'My profile','instructions':'Use short answers.'})
    assert created.status_code==201,created.text
    row=created.json();route='/api/storage/memory/profiles/'+row['id']
    assert c.get('/api/storage/memory/profiles',headers=b).json()==[]
    assert c.get(route+'/history',headers=b).status_code==404
    changed=c.patch(route,headers=a,json={'revision':0,'name':'New style','instructions':'Use detailed answers.'})
    assert changed.status_code==200,changed.text
    assert [v['revision'] for v in c.get(route+'/history',headers=a).json()]==[1,0]
    assert c.patch(route,headers=a,json={'revision':0,'name':'Stale','instructions':'No.'}).status_code==409
    note=c.post('/api/storage/memory',headers=a,json={'content':'Versioned API note'}).json()
    assert c.get('/api/storage/memory/'+note['id']+'/history',headers=a).json()['versions'][0]['content']=='Versioned API note'
    assert c.delete(route+'?revision=1',headers=a).status_code==200
    assert c.get(route+'/history',headers=a).status_code==404


@pytest.mark.parametrize('change',['update','delete'])
def test_pinned_profile_changes_reject_context_before_and_after_inference(profiles,database,change):
    from jarvis.postgres_context import PostgresContext
    context=PostgresContext(database.memory.storage);user=uuid.uuid4()
    p=profiles.create(user,'Pinned','Answer in short Polish sentences.')
    session=context.create(user,'ollama','synthetic:local',profile_ref={'id':str(p['id']),'revision':0})
    claim=context.begin(user,session['id'],0,[])
    assert claim.profile['instructions']==p['instructions']
    if change=='update':profiles.update(user,p['id'],0,'New','Changed instructions')
    else:profiles.delete(user,p['id'],0)
    expect(409,context.validate,user,claim)
    expect(409,context.finish,user,claim,'Question','Old response')
    context.release(user,claim)
    expect(409,context.begin,user,session['id'],0,[])
    expect(409,context.history,user,session['id'])
    assert context.get(user,session['id'])['revision']==0
    context.delete(user,session['id'],0)


def test_profile_scope_revision_and_immutable_session_pin(profiles,database):
    from jarvis.postgres_context import PostgresContext
    ctx=PostgresContext(database.memory.storage);a,b=uuid.uuid4(),uuid.uuid4()
    w=workshop(database,[(a,True),(b,False)])
    private=profiles.create(a,'Private','Private style');shared=profiles.create(a,'Shared','Shared style',workshop_id=w)
    ref=lambda p,rev=0:{'id':str(p['id']),'revision':rev}
    expect(409,ctx.create,b,'ollama','synthetic:local',profile_ref=ref(private))
    expect(409,ctx.create,a,'ollama','synthetic:local',profile_ref=ref(private,1))
    expect(403,ctx.create,a,'ollama','synthetic:local',profile_ref=ref(private),workshop_id=w)
    expect(403,ctx.create,a,'ollama','synthetic:local',profile_ref=ref(shared))
    s=ctx.create(b,'ollama','synthetic:local',profile_ref=ref(shared),workshop_id=w)
    claim=ctx.begin(b,s['id'],0,[]);assert claim.profile['instructions']=='Shared style';ctx.release(b,claim)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with database.user(b) as c:c.execute('UPDATE jarvis.memory_sessions SET profile_revision=1 WHERE id=%s',(s['id'],))
    with psycopg.connect(database.admin) as c:c.execute('DELETE FROM jarvis.memberships WHERE workshop_id=%s AND user_id=%s',(w,b))
    expect(404,ctx.begin,b,s['id'],0,[])


@pytest.mark.parametrize('change',[None,'update','delete'])
def test_actual_http_profile_instructions_are_pinned_and_revalidated(memory_client,database,monkeypatch,change):
    from test_postgres_context_integration import llm_server
    c=memory_client;user,headers=owner(c,'profile.chat')
    profile=c.post('/api/storage/memory/profiles',headers=headers,json={'name':'Profile','instructions':'PROFILE STYLE: concise Polish.'}).json()
    def alter(_):
        if change=='update':c.app.state.postgres_profiles.update(uuid.UUID(user),profile['id'],0,'New','Different style')
        elif change=='delete':c.app.state.postgres_profiles.delete(uuid.UUID(user),profile['id'],0)
    with llm_server(monkeypatch,alter) as seen:
        created=c.post('/api/storage/memory/conversations',headers=headers,json={'model':'ollama','profile_ref':{'id':profile['id'],'revision':0}})
        assert created.status_code==201,created.text
        s=created.json();route='/api/storage/memory/conversations/'+s['id']
        answer=c.post(route+'/turns',headers=headers,json={'revision':0,'message':'ustaw imię Intruder'})
        assert answer.status_code==(409 if change else 200),answer.text
        assert 'PROFILE STYLE: concise Polish.' in seen[0]['messages'][0]['content']
        assert 'tools' not in seen[0] and c.get('/api/proposals').json()==[]
        assert c.get(route,headers=headers).json()['revision']==(0 if change else 1)
        if change:
            again=c.post(route+'/turns',headers=headers,json={'revision':0,'message':'No stale profile'})
            assert again.status_code==409 and len(seen)==1
        assert c.get('/api/chat/sessions').json()==[]
