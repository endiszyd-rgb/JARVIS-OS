"""Pure bounds before any optional PostgreSQL or embedding I/O."""
import pytest
from fastapi import HTTPException
from jarvis.postgres_memory import content_values,embedding_value,PostgresMemory
from jarvis.postgres_store import PostgresStore,PostgresConfig


@pytest.mark.parametrize('content,extra', [('',{}),('   ',{}),('x'*8001,{}),('note',{'category':'Owner Role'}),
 ('note',{'source':'unknown'}),('note',{'source_id':'x'*121}),('\ud800',{})])
def test_memory_content_and_provenance_are_bounded(content,extra):
    with pytest.raises(HTTPException) as denied:content_values(content,**extra)
    assert denied.value.status_code==422


@pytest.mark.parametrize('embedding,namespace', [([], 'a'*64),([0,0], 'a'*64),([True,0], 'a'*64),
 ([float('nan')], 'a'*64),([float('inf')], 'a'*64),([1]*4097, 'a'*64),([1,0], 'other')])
def test_memory_vectors_are_finite_nonzero_and_bound_to_namespace(embedding,namespace):
    with pytest.raises(HTTPException) as denied:embedding_value(embedding,namespace)
    assert denied.value.status_code==422


def test_embedding_normalization_and_explicit_disabled_storage():
    assert embedding_value([3,4],'a'*64)==('[0.6,0.8]',2)
    memory=PostgresMemory(PostgresStore(PostgresConfig()))
    with pytest.raises(HTTPException) as disabled:memory.status()
    assert disabled.value.status_code==503
