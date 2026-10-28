"""Reception changes participate in the transport's existing SQLite transaction."""
from contextlib import contextmanager
import json
import sqlite3
import time
import uuid

from fastapi import HTTPException
import pytest

from jarvis.main import create_app
from jarvis.reception import Event, Reception, Start

KEY='reception-atomic-owner-test-key-32-characters'
AT='2026-10-28T10:00:00+01:00'
TABLES=('reception_calls','reception_events','reception_cases','audit')


def snapshot(path):
    with sqlite3.connect(path) as c:
        return {table:c.execute('SELECT * FROM '+table).fetchall() for table in TABLES}


@pytest.fixture
def store(tmp_path):
    path=tmp_path/'atomic.db'
    create_app(path,KEY)

    @contextmanager
    def db():
        c=sqlite3.connect(path)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:c.close()

    def audit(c,event,detail):
        c.execute('INSERT INTO audit(event,detail,created) VALUES(?,?,?)',(event,json.dumps(detail),time.time()))

    def forbidden_db():raise AssertionError('Transaction helper opened a second connection')
    return path,db,Reception(db,audit),Reception(forbidden_db,audit)


def event(revision,action='turn',**changes):
    return Event(event_id=uuid.uuid4(),revision=revision,action=action,at=AT,**changes)


def test_start_and_intake_case_receipt_and_audit_roll_back_with_outer_transport(store):
    path,db,_,helper=store
    before=snapshot(path)
    with pytest.raises(RuntimeError,match='controlled routing failure'):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            call=helper.start_in_transaction(c,Start(caller='+48500123456'))
            result=helper.apply_in_transaction(c,call['id'],event(0,text='Pilna sprawa',scenario='crisis'))
            assert result['revision']==1 and result['case_id']
            assert c.in_transaction
            assert c.execute('SELECT count(*) FROM reception_calls').fetchone()[0]==1
            assert c.execute('SELECT count(*) FROM reception_events').fetchone()[0]==1
            assert c.execute('SELECT count(*) FROM reception_cases').fetchone()[0]==1
            assert c.execute('SELECT count(*) FROM audit').fetchone()[0]==2
            raise RuntimeError('controlled routing failure')
    assert snapshot(path)==before


def test_existing_call_updates_and_finish_roll_back_without_touching_committed_call(store):
    path,db,public,helper=store
    call=public.start(Start())
    before=snapshot(path)
    with pytest.raises(RuntimeError,match='controlled adapter failure'):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            updated=helper.apply_in_transaction(c,call['id'],event(0,text='Nie działają hamulce'))
            ended=helper.apply_in_transaction(c,call['id'],event(updated['revision'],'finish'))
            assert ended['state']=='ended' and ended['case_id']
            assert c.in_transaction
            raise RuntimeError('controlled adapter failure')
    assert snapshot(path)==before
    assert public.get(call['id'])['revision']==0
    assert public.cases()==[]


def test_helpers_commit_only_with_outer_success_and_preserve_idempotency(store):
    path,db,public,helper=store
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        call=helper.start_in_transaction(c,Start())
        body=event(0,text='Zwykła sprawa')
        first=helper.apply_in_transaction(c,call['id'],body)
        repeated=helper.apply_in_transaction(c,call['id'],body)
        assert first['revision']==repeated['revision']==1 and repeated['replayed']
        assert len(repeated['messages'])==3
        assert c.execute('SELECT count(*) FROM reception_events').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM audit').fetchone()[0]==2
        # A separate connection cannot observe uncommitted helper writes.
        with sqlite3.connect(path) as observer:
            assert observer.execute('SELECT count(*) FROM reception_calls').fetchone()[0]==0
    result=public.get(call['id'])
    assert result['revision']==1 and result['messages'][-2]['text']=='Zwykła sprawa'
    assert result['calls_placed'] is False and result['notifications_sent'] is False


def test_helper_requires_outer_transaction_and_does_not_start_one(store):
    _,db,public,helper=store
    call=public.start(Start())
    with db() as c:
        assert not c.in_transaction
        with pytest.raises(ValueError,match='active transaction'):
            helper.start_in_transaction(c,Start())
        assert not c.in_transaction
        with pytest.raises(ValueError,match='active transaction'):
            helper.apply_in_transaction(c,call['id'],event(0,text='Test'))
        assert not c.in_transaction
    assert public.get(call['id'])['revision']==0


def test_stale_event_leaves_outer_transaction_under_callers_control(store):
    _,db,public,helper=store
    call=public.start(Start())
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(HTTPException) as rejected:
            helper.apply_in_transaction(c,call['id'],event(9,text='Stare zdarzenie'))
        assert rejected.value.status_code==409 and c.in_transaction
        accepted=helper.apply_in_transaction(c,call['id'],event(0,text='Aktualne zdarzenie'))
        assert accepted['revision']==1
    assert public.get(call['id'])['revision']==1
