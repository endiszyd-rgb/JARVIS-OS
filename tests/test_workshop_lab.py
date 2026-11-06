import concurrent.futures
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from jarvis.identity import Principal
from jarvis.workshop_lab import Lab, Proposal, Decision
from jarvis.main import create_app

OWNER = Principal('one', 'session', 'owner', frozenset({'*'}))
OTHER = Principal('two', 'session', 'owner', frozenset({'*'}))
READER = Principal('reader', 'session', 'workshop_reader', frozenset({'workshop:read'}))


def proposal(operation='note', revision=0, **extra):
    return Proposal(request_id=uuid4(), revision=revision, operation=operation,
                    text='DIAGNOZA' if operation == 'status' else 'Synthetic text', **extra)


def decide(lab, preview, approve=True, owner=OWNER):
    return lab.decide(owner, preview['id'], Decision(approve=approve, digest=preview['digest']))


@pytest.mark.parametrize('operation', ['note', 'task', 'quote', 'status'])
def test_preview_never_mutates_and_approval_applies_exactly_once(operation):
    lab = Lab()
    body = proposal(operation, **({'amount_grosz': 12345} if operation == 'quote' else {}))
    before = lab.read(OWNER)['order']
    preview = lab.propose(OWNER, body)
    assert lab.read(OWNER)['order'] == before
    assert lab.propose(OWNER, body) == preview
    assert decide(lab, preview)['status'] == 'applied_demo'
    assert decide(lab, preview)['status'] == 'applied_demo'
    assert lab.read(OWNER)['order'] == preview['after']
    assert lab.read(OTHER)['order'] == before


def test_rejection_digest_and_account_isolation():
    lab = Lab()
    preview = lab.propose(OWNER, proposal())
    with pytest.raises(HTTPException) as error:
        decide(lab, preview, owner=OTHER)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        lab.decide(OWNER, preview['id'], Decision(approve=True, digest='0'*64))
    assert decide(lab, preview, False)['status'] == 'rejected'
    with pytest.raises(HTTPException):
        decide(lab, preview)
    assert lab.read(OWNER)['order']['notes'] == []


def test_conflicting_previews_and_concurrent_double_approval():
    lab = Lab()
    previews = [lab.propose(OWNER, proposal()) for _ in range(2)]
    def attempt(preview):
        try:
            return decide(lab, preview)['status']
        except HTTPException as error:
            return error.status_code
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(attempt, previews))
    assert set(outcomes) == {'applied_demo', 409}
    assert len(lab.read(OWNER)['order']['notes']) == 1


def test_expiry_capacity_request_collision_and_unauthorized():
    now = [0]
    lab = Lab(lambda: now[0])
    body = proposal()
    preview = lab.propose(OWNER, body)
    with pytest.raises(HTTPException):
        lab.propose(OWNER, body.model_copy(update={'text': 'changed'}))
    with pytest.raises(HTTPException) as error:
        lab.read(READER)
    assert error.value.status_code == 403
    for _ in range(63):
        lab.propose(OWNER, proposal())
    with pytest.raises(HTTPException) as error:
        lab.propose(OWNER, proposal())
    assert error.value.status_code == 429
    now[0] = 901
    with pytest.raises(HTTPException) as error:
        decide(lab, preview)
    assert error.value.status_code == 404
    assert lab.propose(OWNER, proposal())['status'] == 'pending'


@pytest.mark.parametrize('extra', [{'amount_grosz': 1}, {'text': ''}, {'revision': True}, {'text': '\ud800'}])
def test_invalid_input(extra):
    values = dict(request_id=uuid4(), revision=0, operation='note', text='Synthetic')
    values.update(extra)
    with pytest.raises((ValidationError, UnicodeError)):
        Proposal(**values)


def test_api_is_owner_only_and_never_uses_live_transport(tmp_path, monkeypatch):
    from jarvis import autologika
    monkeypatch.setattr(autologika, 'configured_adapter', lambda: pytest.fail('No live adapter permitted'))
    client = TestClient(create_app(tmp_path/'core.db', 'a'*32))
    assert client.get('/api/v1/autologika/write-lab').status_code == 401
    client.headers['X-Jarvis-Key'] = 'a'*32
    preview = client.post('/api/v1/autologika/write-lab/proposals', json=proposal().model_dump(mode='json')).json()
    response = client.post('/api/v1/autologika/write-lab/proposals/'+preview['id']+'/decide',
                           json={'approve': True, 'digest': preview['digest']})
    assert response.status_code == 200
    assert response.json()['status'] == 'applied_demo'
    assert client.get('/api/v1/autologika/write-lab').json()['production_writes'] is False
    invalid = client.post('/api/v1/autologika/write-lab/proposals', json={'text': 'PRIVATE_INVALID_BODY'})
    assert invalid.status_code == 422 and 'PRIVATE_INVALID_BODY' not in invalid.text

def test_api_roles_account_isolation_and_revoked_session(tmp_path):
    client = TestClient(create_app(tmp_path/'core.db', 'a'*32))
    owner_headers = {'X-Jarvis-Key': 'a'*32}
    sessions = {}
    for name, role in [('first', 'owner'), ('second', 'owner'), ('reader', 'workshop_reader')]:
        password = 'Synthetic-password-for-local-tests'
        assert client.post('/api/v1/security/users', headers=owner_headers,
                           json={'username': name, 'password': password, 'role': role}).status_code == 201
        response = client.post('/api/v1/auth/login', json={'username': name, 'password': password}).json()
        sessions[name] = response
    first = {'X-Jarvis-Key': sessions['first']['token']}
    second = {'X-Jarvis-Key': sessions['second']['token']}
    reader = {'X-Jarvis-Key': sessions['reader']['token']}
    body = proposal().model_dump(mode='json')
    preview = client.post('/api/v1/autologika/write-lab/proposals', headers=first, json=body).json()
    path = '/api/v1/autologika/write-lab/proposals/'+preview['id']+'/decide'
    decision = {'approve': True, 'digest': preview['digest']}
    assert client.post(path, headers=second, json=decision).status_code == 404
    assert client.get('/api/v1/autologika/write-lab', headers=reader).status_code == 403
    assert client.post('/api/v1/autologika/write-lab/proposals', headers=reader, json=body).status_code == 403
    assert client.post(path, headers=reader, json=decision).status_code == 403
    assert client.post('/api/v1/auth/logout', headers=first).status_code == 200
    assert client.post(path, headers=first, json=decision).status_code == 401


def test_mutating_returned_preview_cannot_change_approved_data():
    lab = Lab()
    preview = lab.propose(OWNER, proposal())
    preview['after']['status'] = 'GOTOWE'
    result = decide(lab, preview)
    assert result['after']['status'] == 'PRZYJETE'
    events = lab.read(OWNER)['events']
    assert [event['status'] for event in events] == ['pending', 'applied_demo']
    assert 'Synthetic text' not in str(events)
