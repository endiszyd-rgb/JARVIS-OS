"""Integration checks for atomic personal-memory capture and stale turn handling."""
import hashlib
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient
from jarvis import main, memory_auto
from test_memory_auto import KEY, client, model, policy, say


MEMORY_TABLES = (
    'memory', 'memory_sources', 'memory_history', 'memory_origins',
    'memory_auto_keys', 'memory_epoch', 'memory_vectors',
)


def memory_snapshot(path):
    with sqlite3.connect(path) as db:
        return {
            table: sorted(db.execute('SELECT * FROM ' + table).fetchall(), key=repr)
            for table in MEMORY_TABLES
        }


@pytest.mark.parametrize('existing', [False, True], ids=['new-note', 'replacement'])
def test_capture_and_all_metadata_roll_back_when_finish_fails(client, monkeypatch, existing):
    policy(client, mode='auto')
    if existing:
        say(client, 'Preferuję krótkie odpowiedzi.')
    before = memory_snapshot(client.path)
    original = memory_auto.capture
    attempted = {}

    def fail_after_capture(db, session_id, turn_id):
        attempted.update(original(db, session_id, turn_id))
        attempted['turn_id'] = turn_id
        raise RuntimeError('controlled failure after capture')

    monkeypatch.setattr(memory_auto, 'capture', fail_after_capture)
    text = 'Od teraz wolę szczegółowe odpowiedzi.' if existing else 'Preferuję krótkie odpowiedzi.'
    with pytest.raises(RuntimeError, match='controlled failure after capture'):
        client.post('/api/chat', json={'message': text})

    assert attempted['status'] == ('updated' if existing else 'created')
    assert memory_snapshot(client.path) == before
    with sqlite3.connect(client.path) as db:
        receipt = db.execute('SELECT outcome FROM memory_turns WHERE turn_id=?', (attempted['turn_id'],)).fetchone()
        assert receipt == (None,)
        assert db.execute('SELECT role,state FROM chat_messages WHERE turn_id=?',
                          (attempted['turn_id'],)).fetchall() == [('user', 'failed')]
        assert db.execute('SELECT count(*) FROM chat_sessions WHERE active_turn=?',
                          (attempted['turn_id'],)).fetchone()[0] == 0


@pytest.mark.parametrize('change', ['another-session', 'manual-correction'])
def test_other_owner_write_during_reply_prevents_stale_capture(client, monkeypatch, change):
    policy(client, mode='auto')
    if change == 'manual-correction':
        ident = say(client, 'Preferuję krótkie odpowiedzi.')['memory_capture']['memory_id']
    other = TestClient(client.app, headers={'X-Jarvis-Key': KEY})
    second = {}

    def reply_after_change(request):
        if change == 'another-session':
            second.update(say(other, 'Używam Linux.', model='demo'))
            assert second['memory_capture']['status'] == 'created'
        else:
            result = other.put('/api/memory/' + ident, json={
                'revision': 0, 'text': 'Ręczna treść ważniejsza od oczekującej tury.',
                'category': 'preferences',
            })
            assert result.status_code == 200
        return httpx.Response(200, json={'message': {'content': 'Kontrolowana odpowiedź.'}})

    model(monkeypatch, reply_after_change)
    result = say(client, 'Od teraz wolę szczegółowe odpowiedzi.', model='ollama', model_name='test:local')
    assert result['memory_capture']['status'] == 'memory_changed'
    notes = client.get('/api/memory').json()
    assert len(notes) == 1
    if change == 'another-session':
        assert second['session_id'] != result['session_id']
        assert notes[0]['text'] == 'Używam Linux.'
        assert notes[0]['id'] == second['memory_capture']['memory_id']
    else:
        assert notes[0]['text'] == 'Ręczna treść ważniejsza od oczekującej tury.'
        assert notes[0]['source'] == 'owner_correction'
        assert notes[0]['revision'] == 1


def test_automatic_replacement_refreshes_fts_and_discards_previous_embedding(client):
    policy(client, mode='auto')
    ident = say(client, 'Preferuję krótkie odpowiedzi.')['memory_capture']['memory_id']
    previous_text = 'Preferuję krótkie odpowiedzi.'
    with sqlite3.connect(client.path) as db:
        db.execute('INSERT INTO memory_vectors VALUES(?,?,?,?)', (
            ident, 'controlled-embedding-v1', hashlib.sha256(previous_text.encode()).hexdigest(), '[1,0]',
        ))
    before = client.post('/api/memory/search', json={'query': 'krótkie'}).json()
    assert before['lexical_engine'] == 'fts5'
    assert [note['id'] for note in before['results']] == [ident]
    assert client.post('/api/memory/search', json={'query': 'szczegółowe'}).json()['results'] == []

    result = say(client, 'Od teraz wolę szczegółowe odpowiedzi.')
    assert result['memory_capture']['status'] == 'updated'
    assert result['memory_capture']['memory_id'] == ident
    assert client.post('/api/memory/search', json={'query': 'krótkie'}).json()['results'] == []
    after = client.post('/api/memory/search', json={'query': 'szczegółowe'}).json()
    assert [note['id'] for note in after['results']] == [ident]
    assert after['results'][0]['text'] == 'Preferuję szczegółowe odpowiedzi.'
    with sqlite3.connect(client.path) as db:
        assert db.execute('SELECT count(*) FROM memory_vectors WHERE memory_id=?', (ident,)).fetchone()[0] == 0


def test_workshop_context_excludes_even_a_supported_owner_declaration(client, monkeypatch):
    policy(client, mode='auto')
    calls = []

    class SyntheticSnapshot:
        manifest = {'created_at': '2026-10-22T00:00:00Z'}

        def read(self, domain, **options):
            calls.append((domain, options))
            if domain == 'reports':
                return {'data': {'source': 'synthetic-workshop-only'}}
            assert domain == 'finances'
            return {'data': {'month': '2026-10', 'orders_count': 0,
                             'orders_value': 0, 'paid_in_month': 0}}

    monkeypatch.setattr(main, 'configured_snapshot', lambda: SyntheticSnapshot())
    result = say(client, 'Preferuję krótkie odpowiedzi.', include_workshop_summary=True,
                 workshop_month='2026-10')
    assert result['workshop_context'] is True
    assert result['memory_capture']['status'] == 'request_excluded'
    assert calls == [('reports', {}), ('finances', {'month': '2026-10'})]
    assert client.get('/api/memory').json() == []
    with sqlite3.connect(client.path) as db:
        assert db.execute('SELECT count(*) FROM memory_origins').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM memory_auto_keys').fetchone()[0] == 0


def test_manual_only_category_does_not_report_automatic_capture_active(client):
    policy(client, mode='auto', categories=['manual'])
    saved = client.get('/api/memory/policy').json()
    assert saved['policy']['mode'] == 'auto'
    assert saved['automatic_extraction_active'] is False
    assert say(client, 'Preferuję krótkie odpowiedzi.')['memory_capture']['saved'] == 0
