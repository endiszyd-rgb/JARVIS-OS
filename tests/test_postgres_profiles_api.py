"""Disabled feature and strict ownership/input boundaries for profile endpoints."""
import pytest
from test_postgres_memory_api import client


def test_disabled_profile_and_version_endpoints_do_not_contact_pg(client):
    ident='00000000-0000-4000-8000-000000000001'
    for prefix in ('/api','/api/v1'):
        assert client.get(prefix+'/storage/memory/profiles').status_code==503
        assert client.post(prefix+'/storage/memory/profiles',json={'name':'Style','instructions':'Be concise.'}).status_code==503
        assert client.get(prefix+'/storage/memory/'+ident+'/history').status_code==503


@pytest.mark.parametrize('body',[
 {'name':'Style','instructions':'Text','owner_id':'forged'},
 {'name':'Style','instructions':'Text','role':'owner'},
 {'name':'Style','instructions':'Text','revision':0},
 {'name':'Style','instructions':'x'*4001},
 {'name':'','instructions':'Text'},
 {'name':'Style','instructions':''},
])
def test_profile_authority_and_initial_revision_cannot_be_supplied(client,body):
    assert client.post('/api/storage/memory/profiles',json=body).status_code==422
