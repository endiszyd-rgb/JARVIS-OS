import sqlite3
import uuid
from fastapi.testclient import TestClient
from jarvis.main import create_app

KEY='transport-migration-owner-key-32-characters'


def test_schema10_backup_preserves_reception_memory_and_voice_history(tmp_path):
    path=tmp_path/'old.db';c=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    old=c.post('/api/reception/calls',json={}).json()
    note=c.post('/api/memory',json={'text':'Stara ręczna notatka'}).json()['id']
    voice=c.post('/api/chat',json={'message':'Prywatna historia testowa','input_mode':'voice'}).json()['session_id']
    with sqlite3.connect(path) as db:
        db.executescript('DROP TABLE transport_receipts;DROP TABLE transport_starts;DROP TABLE transport_outbox;DROP TABLE transport_calls;PRAGMA user_version=10;')
    upgraded=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    assert upgraded.get('/api/reception/calls/'+old['id']).json()==old
    assert upgraded.get('/api/memory').json()[0]['id']==note
    assert upgraded.get('/api/chat/sessions/'+voice).json()['input_mode']=='voice'
    assert upgraded.get('/api/telephony/transport/calls').json()==[]
    backups=list((tmp_path/'backups').glob('before-schema12-*.sqlite3'));assert len(backups)==1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==10
        assert db.execute('SELECT id FROM reception_calls').fetchone()[0]==old['id']
        assert db.execute('SELECT id FROM memory').fetchone()[0]==note
        assert db.execute('SELECT input_mode FROM chat_session_modes').fetchone()[0]=='voice'
        assert db.execute("SELECT name FROM sqlite_master WHERE name='transport_calls'").fetchone() is None
    started=upgraded.post('/api/telephony/transport/calls',json={'event_id':str(uuid.uuid4())})
    assert started.status_code==201 and started.json()['caller_token']
    restarted=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    assert len(restarted.get('/api/telephony/transport/calls').json())==1
    assert len(list((tmp_path/'backups').glob('before-schema12-*.sqlite3')))==1
    with sqlite3.connect(path) as db:assert db.execute('PRAGMA user_version').fetchone()[0]==12
