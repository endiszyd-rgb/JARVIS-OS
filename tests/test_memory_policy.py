import sqlite3
from fastapi.testclient import TestClient
import pytest
from jarvis.main import create_app

KEY='memory-policy-test-owner-key-32-chars'

def client(path):
    return TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})


def test_schema7_migration_backup_and_restart(tmp_path):
    path=tmp_path/'old.db'
    # A schema7 database with existing manual data and no provenance tables.
    old=client(path)
    ident=old.post('/api/memory',json={'text':'Stara ręczna notatka'}).json()['id']
    with sqlite3.connect(path) as c:
        c.executescript('DROP TABLE memory_history; DROP TABLE memory_sources; DROP TABLE memory_policy; PRAGMA user_version=7;')
    upgraded=client(path)
    note=upgraded.get('/api/memory').json()[0]
    assert note['id']==ident and note['text']=='Stara ręczna notatka'
    assert note['source']=='legacy_manual' and note['revision']==0
    backups=list((tmp_path/'backups').glob('before-schema12-*.sqlite3'))
    assert len(backups)==1
    with sqlite3.connect(backups[0]) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==7
        assert c.execute('SELECT text FROM memory').fetchone()[0]=='Stara ręczna notatka'
        assert c.execute("SELECT name FROM sqlite_master WHERE name='memory_sources'").fetchone() is None
    restarted=client(path)
    assert restarted.get('/api/memory').json()[0]['source']=='legacy_manual'
    assert len(list((tmp_path/'backups').glob('before-schema12-*.sqlite3')))==1


def test_policy_is_separate_persistent_and_revisioned(tmp_path):
    path=tmp_path/'core.db';c=client(path)
    previous=c.get('/api/status').json()['settings']
    value=c.get('/api/memory/policy').json()
    assert value['automatic_extraction_active'] is False
    value['policy'].update(mode='auto',categories=['projects'],retention_days=30)
    body={'revision':value['revision'],'policy':value['policy']}
    assert c.put('/api/memory/policy',json=body).status_code==200
    assert c.put('/api/memory/policy',json=body).status_code==409
    assert c.get('/api/status').json()['settings']==previous
    saved=client(path).get('/api/memory/policy').json()
    assert saved['policy']['retention_days']==30 and saved['revision']==1
    assert saved['automatic_extraction_active'] is True
    token=c.post('/api/security/tokens',json={'name':'reader','scopes':['status:read']}).json()['token']
    assert c.get('/api/memory/policy',headers={'X-Jarvis-Key':token}).status_code==403


@pytest.mark.parametrize('text',['Nie zapamiętuj tej informacji','tego nie pamietaj','zapamiętaj ale nie zapisuj tego'])
def test_do_not_remember_blocks_manual_and_chat(tmp_path,text):
    c=client(tmp_path/'core.db')
    assert c.post('/api/memory',json={'text':text}).status_code==409
    assert c.post('/api/chat',json={'message':'zapamiętaj '+text}).status_code==409
    assert c.get('/api/memory').json()==[]


def test_disabled_policy_blocks_both_paths(tmp_path):
    c=client(tmp_path/'core.db');p=c.get('/api/memory/policy').json()
    p['policy']['enabled']=False
    c.put('/api/memory/policy',json={'revision':0,'policy':p['policy']})
    assert c.post('/api/memory',json={'text':'Moje preferencje'}).status_code==409
    assert c.post('/api/chat',json={'message':'zapamiętaj moje preferencje'}).status_code==409
    assert c.get('/api/memory').json()==[]


def test_sources_correction_conflict_history_and_delete(tmp_path):
    path=tmp_path/'core.db';c=client(path)
    c.post('/api/chat',json={'message':'zapamiętaj mój projekt Jarvis'})
    chat_note=c.get('/api/memory').json()[0]
    assert chat_note['source']=='owner_chat'
    ident=c.post('/api/memory',json={'text':'Mam Saab','category':'equipment'}).json()['id']
    assert c.post('/api/memory',json={'text':'x','source':'customer'}).status_code==422
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO memory_vectors VALUES(?,?,?,?)',(ident,'test','hash','[1,0]'))
    body={'text':'Mam Opel','category':'equipment','revision':0}
    assert c.put('/api/memory/'+ident,json=body).status_code==200
    assert c.put('/api/memory/'+ident,json=body).status_code==409
    history=c.get('/api/memory/'+ident+'/history').json()
    assert history[0]['text']=='Mam Saab' and history[0]['source']=='owner_manual'
    note=next(n for n in c.get('/api/memory').json() if n['id']==ident)
    assert note['source']=='owner_correction' and note['revision']==1
    assert c.post('/api/memory/search',json={'query':'Opel'}).json()['results'][0]['id']==ident
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM memory_vectors WHERE memory_id=?',(ident,)).fetchone()[0]==0
    assert c.delete('/api/memory/'+ident).status_code==200
    assert c.get('/api/memory/'+ident+'/history').status_code==404
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM memory_history WHERE memory_id=?',(ident,)).fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM memory_sources WHERE memory_id=?',(ident,)).fetchone()[0]==0
    assert client(path).get('/api/memory').json()[0]['id']==chat_note['id']


def test_retention_is_explicit_and_reception_isolated(tmp_path):
    path=tmp_path/'core.db';c=client(path)
    c.post('/api/memory',json={'text':'stare'})
    with sqlite3.connect(path) as db:db.execute('UPDATE memory SET created=0')
    settings=c.get('/api/memory/policy').json();settings['policy']['retention_days']=10
    c.put('/api/memory/policy',json={'revision':0,'policy':settings['policy']})
    assert c.post('/api/memory/retention',json={}).json()['count']==1
    assert len(c.get('/api/memory').json())==1
    assert c.post('/api/memory/retention',json={'dry_run':False}).json()['count']==1
    assert c.get('/api/memory').json()==[]
    before=c.get('/api/memory/policy').json()
    c.post('/api/reception/calls',json={})
    assert c.get('/api/memory').json()==[]
    assert c.get('/api/memory/policy').json()==before
