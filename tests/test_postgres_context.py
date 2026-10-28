"""Bounds, complete history pairs and source provenance, without model/PG I/O."""
import asyncio
import uuid
import pytest
from fastapi import HTTPException
from jarvis.postgres_context import text,references,merge_references,bounded_history
from jarvis.postgres_context_api import Capacity

@pytest.mark.parametrize('value',['','  ','x'*8001,'\0invalid','\ud800'])
def test_invalid_conversation_text_is_refused(value):
    with pytest.raises(HTTPException) as invalid:text(value,8000)
    assert invalid.value.status_code==422

@pytest.mark.parametrize('refs',[
 [{'id':str(uuid.uuid4()),'revision':True}], [{'id':'invalid','revision':0}],
 [{'id':str(uuid.uuid4()),'revision':0,'role':'owner'}],
 [{'id':str(uuid.uuid4()),'revision':0} for _ in range(6)],
])
def test_reference_schema_limits_precede_any_transport(refs):
    with pytest.raises(HTTPException) as invalid:references(refs)
    assert invalid.value.status_code==422


def test_duplicate_and_conflicting_provenance_is_never_silently_replaced():
    ref={'id':str(uuid.uuid4()),'revision':0}
    with pytest.raises(HTTPException):references([ref,ref])
    assert merge_references([ref,ref])==[ref]
    with pytest.raises(HTTPException) as changed:merge_references([ref,dict(ref,revision=1)])
    assert changed.value.status_code==409
    with pytest.raises(HTTPException):merge_references([{'id':str(uuid.uuid4()),'revision':0} for _ in range(21)])


def test_history_keeps_complete_newest_pairs_and_their_sources():
    ref={'id':str(uuid.uuid4()),'revision':0}
    turns=[{'user_text':f'Question{i}', 'assistant_text':'x'*4000,'memory_refs':[ref]} for i in range(12,0,-1)]
    rows,refs=bounded_history(turns)
    assert len(rows)==6 and [row['content'] for row in rows[::2]]==['Question10','Question11','Question12']
    assert refs==[ref]
    huge=[{'user_text':'Question','assistant_text':'x'*16000,'memory_refs':[ref]}]
    assert bounded_history(huge)==([],[])


def test_capacity_timeout_and_cancellation_release_slots():
    async def run():
        capacity=Capacity(timeout_seconds=0.02,max_concurrent=1)
        async with capacity.slot():
            with pytest.raises(HTTPException) as full:
                async with capacity.slot():pytest.fail('No second slot allowed')
            assert full.value.status_code==429
        with pytest.raises(HTTPException) as timeout:
            async with capacity.slot():await asyncio.Event().wait()
        assert timeout.value.status_code==504 and capacity._active==0
        async with capacity.slot():pass
    asyncio.run(run())
