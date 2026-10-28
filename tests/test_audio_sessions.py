import uuid

from fastapi import FastAPI, HTTPException, Header
from fastapi.testclient import TestClient
import pytest

from jarvis.audio_sessions import Create, Event, Sessions, mount


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now
    def advance(self, seconds): self.now += seconds


def apply(store, session, action, **extra):
    return store.event(session['id'], Event(event_id=uuid.uuid4(), revision=session['revision'], action=action, **extra))


def status_error(code, action):
    with pytest.raises(HTTPException) as raised:
        action()
    assert raised.value.status_code == code


def test_manual_full_cycle_and_interrupt():
    clock = Clock(); store = Sessions(clock=clock)
    state = store.create(Create())
    assert state['state'] == 'idle' and state['silence_seconds'] == 30
    state = apply(store, state, 'activate')
    assert state['state'] == 'listening' and state['activation'] == 1
    state = apply(store, state, 'process')
    assert state['state'] == 'processing'
    state = apply(store, state, 'speak')
    assert state['state'] == 'speaking'
    state = apply(store, state, 'interrupt')
    assert state['state'] == 'listening'
    state = apply(store, state, 'process')
    state = apply(store, state, 'speak')
    state = apply(store, state, 'complete')
    assert state['state'] == 'listening'
    state = apply(store, state, 'end')
    assert state['state'] == 'idle' and state['reason'] == 'ended'
    state = apply(store, state, 'activate')
    assert state['activation'] == 2 and state['state'] == 'listening'
    state = apply(store, state, 'cancel')
    assert state['state'] == 'idle' and state['reason'] == 'cancelled'
    assert state['audio_io_connected'] is False


def test_exact_silence_boundary_and_activity_resets_timer():
    clock = Clock(); store = Sessions(clock=clock)
    state = apply(store, store.create(Create(silence_seconds=10)), 'activate')
    clock.advance(9.9)
    assert store.get(state['id'])['state'] == 'listening'
    state = apply(store, state, 'activity')
    clock.advance(9.9)
    assert store.get(state['id'])['state'] == 'listening'
    clock.advance(.1)
    state = store.get(state['id'])
    assert state['state'] == 'idle' and state['reason'] == 'silence_timeout'
    assert state['revision'] == 3
    assert store.get(state['id'])['revision'] == 3  # expiry only once


def test_speaking_ignores_listening_silence_but_has_phase_timeout():
    clock = Clock(); store = Sessions(clock=clock, phase_timeout=60)
    state = apply(store, store.create(Create(silence_seconds=2)), 'activate')
    state = apply(store, state, 'process')
    state = apply(store, state, 'speak')
    clock.advance(3)
    assert store.get(state['id'])['state'] == 'speaking'
    clock.advance(57)
    state = store.get(state['id'])
    assert state['state'] == 'idle' and state['reason'] == 'phase_timeout'


def test_resume_and_lifetime_expiry_despite_activity():
    clock = Clock(); store = Sessions(clock=clock, max_lifetime=10)
    state = apply(store, store.create(Create()), 'activate')
    state = apply(store, state, 'process')
    state = apply(store, state, 'resume')
    clock.advance(9)
    state = apply(store, state, 'activity')
    clock.advance(1)
    state = store.get(state['id'])
    assert state['state'] == 'idle' and state['reason'] == 'lifetime_expired'


def test_events_are_idempotent_conflicts_and_expired_replay_stays_idle():
    clock = Clock(); store = Sessions(clock=clock)
    state = store.create(Create())
    event = Event(event_id=uuid.uuid4(), revision=0, action='activate')
    first = store.event(state['id'], event)
    replay = store.event(state['id'], event)
    assert replay['replayed'] is True and replay['revision'] == first['revision']
    changed = event.model_copy(update={'action':'end'})
    status_error(409, lambda: store.event(state['id'], changed))
    clock.advance(30)
    replay = store.event(state['id'], event)
    assert replay['replayed'] is True and replay['state'] == 'idle'
    assert replay['reason'] == 'silence_timeout' and replay['acknowledged_revision'] == 1
    status_error(409, lambda: apply(store, first, 'activity'))


def test_invalid_transitions_and_configuration():
    store = Sessions(); state = store.create(Create())
    status_error(409, lambda: apply(store, state, 'speak'))
    assert store.get(state['id'])['revision'] == 0
    state = apply(store, state, 'configure', silence_seconds=45)
    assert state['silence_seconds'] == 45
    state = apply(store, state, 'activate')
    status_error(409, lambda: apply(store, state, 'configure', silence_seconds=20))
    state = apply(store, state, 'cancel')
    assert state['reason'] == 'cancelled'
    with pytest.raises(ValueError): Create(silence_seconds=0)
    with pytest.raises(ValueError): Create(silence_seconds=True)
    with pytest.raises(ValueError): Event(event_id=uuid.uuid4(),revision=0,action='activate',silence_seconds=20)
    with pytest.raises(ValueError): Event(event_id=uuid.uuid4(),revision=0,action='configure')


def test_sessions_are_isolated_and_process_restart_drops_state():
    clock = Clock(); store = Sessions(clock=clock)
    first = apply(store, store.create(Create(silence_seconds=5)), 'activate')
    second = apply(store, store.create(Create(silence_seconds=20)), 'activate')
    clock.advance(5)
    assert store.get(first['id'])['reason'] == 'silence_timeout'
    assert store.get(second['id'])['state'] == 'listening'
    restarted = Sessions(clock=clock)
    status_error(404, lambda: restarted.get(second['id']))


def test_storage_capacity_idle_cleanup_and_receipt_bound():
    clock = Clock(); store = Sessions(clock=clock,max_sessions=1,max_receipts=2,idle_retention=5)
    state = store.create(Create())
    status_error(429, lambda: store.create(Create()))
    state = apply(store, state, 'activate')
    for _ in range(4): state = apply(store, state, 'activity')
    assert len(store._sessions[state['id']].receipts) == 2
    clock.advance(5)
    assert store.sweep() == 0  # active sessions never evicted by idle retention
    state = apply(store, store.get(state['id']), 'end')
    clock.advance(5)
    new = store.create(Create())
    assert new['id'] != state['id']
    status_error(404, lambda: store.get(state['id']))


def test_mount_enforces_owner_dependency_validation_and_app_isolation():
    def auth(x_owner_key: str | None = Header(default=None)):
        if x_owner_key != 'owner': raise HTTPException(403,'Owner only')
    app = FastAPI(); clock = Clock()
    mount(app,auth,Sessions(clock=clock))
    c = TestClient(app)
    assert c.post('/api/voice/sessions',json={}).status_code == 403
    headers = {'X-Owner-Key':'owner'}
    r = c.post('/api/voice/sessions',headers=headers,json={})
    assert r.status_code == 201
    ident = r.json()['id']; base = '/api/voice/sessions/'+ident
    assert c.get(base).status_code == 403
    assert c.post(base+'/events',json={}).status_code == 403
    assert c.post(base+'/events',headers=headers,json={'event_id':str(uuid.uuid4()),'revision':0,'action':'activate'}).json()['state'] == 'listening'
    clock.advance(30)
    assert c.get(base,headers=headers).json()['reason'] == 'silence_timeout'
    assert c.post('/api/voice/sessions',headers=headers,json={'silence_seconds':301}).status_code == 422
    assert c.get('/api/voice/sessions/not-a-uuid',headers=headers).status_code == 422
    other = FastAPI(); mount(other,auth)
    assert TestClient(other).get(base,headers=headers).status_code == 404


def test_newly_expired_session_keeps_full_idle_retention_window():
    clock = Clock()
    store = Sessions(clock=clock, idle_retention=5)
    session = apply(store, store.create(Create()), 'activate')
    clock.advance(100)
    assert store.sweep() == 0
    assert store.get(session['id'])['reason'] == 'silence_timeout'
    clock.advance(4.9)
    assert store.sweep() == 0
    clock.advance(.1)
    assert store.sweep() == 1
    status_error(404, lambda: store.get(session['id']))


def test_core_app_audio_routes_require_owner_and_do_not_mutate_other_domains(tmp_path):
    from jarvis.main import create_app

    key = 'audio-session-owner-test-key-32-characters'
    app = create_app(tmp_path/'core.db', key)
    c = TestClient(app, headers={'X-Jarvis-Key':key})
    before = {path:c.get(path).json() for path in ['/api/memory','/api/reception/calls','/api/reception/cases']}
    service = c.post('/api/security/tokens',json={'name':'status-reader','scopes':['status:read']}).json()['token']
    service_headers = {'X-Jarvis-Key':service}
    assert c.post('/api/voice/sessions',headers=service_headers,json={}).status_code == 403
    response = c.post('/api/voice/sessions',json={'silence_seconds':45})
    assert response.status_code == 201
    state = response.json()
    base = '/api/voice/sessions/'+state['id']
    assert c.get(base,headers=service_headers).status_code == 403
    event = {'event_id':str(uuid.uuid4()),'revision':0,'action':'activate'}
    assert c.post(base+'/events',headers=service_headers,json=event).status_code == 403
    active = c.post(base+'/events',json=event)
    assert active.status_code == 200 and active.json()['state'] == 'listening'
    assert active.json()['silence_seconds'] == 45
    assert c.get(base).json()['revision'] == 1
    cancelled = c.post(base+'/events',json={'event_id':str(uuid.uuid4()),'revision':1,'action':'cancel'})
    assert cancelled.status_code == 200 and cancelled.json()['reason'] == 'cancelled'
    assert before == {path:c.get(path).json() for path in before}
