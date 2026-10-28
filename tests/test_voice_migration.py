"""Schema9→10 adds a persistent boundary between typed and voice histories."""
import sqlite3
from fastapi.testclient import TestClient
from jarvis.main import create_app

KEY='voice-migration-owner-key-32-characters'


def test_schema9_backup_preserves_history_memory_and_marks_old_sessions_text(tmp_path):
    path=tmp_path/'legacy.db'
    c=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    turn=c.post('/api/chat',json={'message':'Prywatna historia tekstowa'}).json()
    memory=c.post('/api/memory',json={'text':'Ręczna notatka'}).json()['id']
    messages=c.get('/api/chat/sessions/'+turn['session_id']+'/messages').json()
    with sqlite3.connect(path) as db:
        db.executescript('DROP TABLE chat_session_modes; PRAGMA user_version=9;')
    migrated=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    assert migrated.get('/api/chat/sessions/'+turn['session_id']).json()['input_mode']=='text'
    assert migrated.get('/api/chat/sessions/'+turn['session_id']+'/messages').json()==messages
    assert migrated.get('/api/memory').json()[0]['id']==memory
    backups=list((tmp_path/'backups').glob('before-schema12-*.sqlite3'));assert len(backups)==1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==9
        assert db.execute('SELECT content FROM chat_messages ORDER BY id').fetchone()[0]=='Prywatna historia tekstowa'
        assert db.execute('SELECT text FROM memory').fetchone()[0]=='Ręczna notatka'
        assert db.execute("SELECT name FROM sqlite_master WHERE name='chat_session_modes'").fetchone() is None
    restarted=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    assert restarted.get('/api/chat/sessions/'+turn['session_id']).json()['input_mode']=='text'
    assert len(list((tmp_path/'backups').glob('before-schema12-*.sqlite3')))==1


def test_voice_mode_survives_restart_and_mode_metadata_cascades_on_delete(tmp_path):
    path=tmp_path/'voice.db'
    c=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    first=c.post('/api/chat',json={'message':'Cześć','input_mode':'voice'}).json()
    restarted=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    ident=first['session_id']
    assert restarted.get('/api/chat/sessions/'+ident).json()['input_mode']=='voice'
    assert restarted.post('/api/chat',json={'message':'Ciąg dalszy','session_id':ident}).status_code==422
    assert restarted.post('/api/chat',json={'message':'Ciąg dalszy','session_id':ident,'input_mode':'voice'}).status_code==200
    assert restarted.delete('/api/chat/sessions/'+ident).status_code==200
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM chat_session_modes WHERE session_id=?',(ident,)).fetchone()[0]==0
