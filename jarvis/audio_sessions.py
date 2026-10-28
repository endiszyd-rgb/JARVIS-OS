"""Manual audio-session control only; no microphone, transport, model or audio I/O.

State lives in this process and is lost on restart. Expiry is evaluated on access
(or an explicit sweep); callers must poll and release their own audio resources.
"""
from collections import OrderedDict
from dataclasses import dataclass, field
import threading
import time
from typing import Literal
import uuid

from fastapi import Depends, HTTPException
from pydantic import Field, model_validator
from .telephony import Strict

Action = Literal[
    'activate', 'activity', 'process', 'speak', 'complete', 'resume',
    'interrupt', 'end', 'cancel', 'configure',
]


class Create(Strict):
    silence_seconds: int = Field(default=30, ge=1, le=300, strict=True)


class Event(Strict):
    event_id: uuid.UUID
    revision: int = Field(ge=0, strict=True)
    action: Action
    silence_seconds: int | None = Field(default=None, ge=1, le=300, strict=True)

    @model_validator(mode='after')
    def configuration_payload(self):
        if (self.action == 'configure') != (self.silence_seconds is not None):
            raise ValueError('Only configure requires silence_seconds')
        return self


@dataclass
class _Session:
    id: str
    silence_seconds: int
    created_at: float
    touched_at: float
    state: str = 'idle'
    revision: int = 0
    activation: int = 0
    reason: str | None = 'not_activated'
    activated_at: float | None = None
    activity_at: float | None = None
    phase_at: float | None = None
    idle_at: float | None = None
    receipts: OrderedDict = field(default_factory=OrderedDict)


class Sessions:
    """Bounded session store. The injected clock must be monotonic seconds."""

    def __init__(self, *, clock=time.monotonic, max_sessions=128,
                 max_receipts=128, max_lifetime=900, phase_timeout=120,
                 idle_retention=300):
        if min(max_sessions, max_receipts, max_lifetime, phase_timeout, idle_retention) <= 0:
            raise ValueError('Session limits must be positive')
        self.clock = clock
        self.max_sessions = max_sessions
        self.max_receipts = max_receipts
        self.max_lifetime = max_lifetime
        self.phase_timeout = phase_timeout
        self.idle_retention = idle_retention
        self._sessions = {}
        self._lock = threading.RLock()

    def _idle(self, session, reason, now):
        session.state = 'idle'
        session.reason = reason
        session.idle_at = now
        session.activated_at = session.activity_at = session.phase_at = None
        session.revision += 1

    def _expire(self, session, now):
        if session.state == 'idle':
            return
        if now - session.activated_at >= self.max_lifetime:
            self._idle(session, 'lifetime_expired', now)
        elif session.state == 'listening' and now - session.activity_at >= session.silence_seconds:
            self._idle(session, 'silence_timeout', now)
        elif session.state in ('processing', 'speaking') and now - session.phase_at >= self.phase_timeout:
            self._idle(session, 'phase_timeout', now)

    def _sweep(self, now):
        for session in self._sessions.values():
            self._expire(session, now)
        remove = [ident for ident, session in self._sessions.items()
                  if session.state == 'idle' and now - max(session.touched_at, session.idle_at) >= self.idle_retention]
        for ident in remove:
            del self._sessions[ident]
        return len(remove)

    def sweep(self):
        with self._lock:
            return self._sweep(self.clock())

    def _lookup(self, ident, now):
        session = self._sessions.get(str(ident))
        if session is None:
            raise HTTPException(404, 'Audio session missing or expired from memory')
        self._expire(session, now)
        session.touched_at = now
        return session

    def _snapshot(self, session, now, *, replayed=False, acknowledged_revision=None):
        remaining = None
        if session.state == 'listening':
            remaining = max(0, session.silence_seconds - (now - session.activity_at))
        lifetime = None if session.state == 'idle' else max(0, self.max_lifetime - (now - session.activated_at))
        return {
            'id': session.id,
            'state': session.state,
            'revision': session.revision,
            'activation': session.activation,
            'silence_seconds': session.silence_seconds,
            'remaining_silence_seconds': remaining,
            'remaining_lifetime_seconds': lifetime,
            'reason': session.reason,
            'active': session.state != 'idle',
            'replayed': replayed,
            'acknowledged_revision': acknowledged_revision,
            'storage': 'memory_only',
            'audio_io_connected': False,
        }

    def create(self, body: Create):
        with self._lock:
            now = self.clock()
            self._sweep(now)
            if len(self._sessions) >= self.max_sessions:
                raise HTTPException(429, 'Audio session capacity reached; wait for idle cleanup')
            ident = str(uuid.uuid4())
            session = _Session(ident, body.silence_seconds, now, now, idle_at=now)
            self._sessions[ident] = session
            return self._snapshot(session, now)

    def get(self, ident):
        with self._lock:
            now = self.clock()
            return self._snapshot(self._lookup(ident, now), now)

    def event(self, ident, body: Event):
        with self._lock:
            now = self.clock()
            session = self._lookup(ident, now)
            event_id = str(body.event_id)
            fingerprint = body.model_dump_json()
            previous = session.receipts.get(event_id)
            if previous is not None:
                if previous[0] != fingerprint:
                    raise HTTPException(409, 'Audio event ID reused with different data')
                # Return current state, so an old activation replay never revives
                # an expired/cancelled session or asks a client to reopen its mic.
                return self._snapshot(session, now, replayed=True, acknowledged_revision=previous[1])
            if body.revision != session.revision:
                raise HTTPException(409, 'Audio session revision changed; refresh state')
            action = body.action
            transitions = {
                ('idle', 'activate'): 'listening',
                ('listening', 'activity'): 'listening',
                ('listening', 'process'): 'processing',
                ('processing', 'speak'): 'speaking',
                ('processing', 'resume'): 'listening',
                ('speaking', 'complete'): 'listening',
                ('speaking', 'interrupt'): 'listening',
            }
            if action == 'configure' and session.state == 'idle':
                session.silence_seconds = body.silence_seconds
                session.revision += 1
            elif action in ('end', 'cancel') and session.state != 'idle':
                self._idle(session, 'ended' if action == 'end' else 'cancelled', now)
            elif (session.state, action) in transitions:
                session.state = transitions[(session.state, action)]
                session.reason = None
                session.phase_at = now
                if action == 'activate':
                    session.activation += 1
                    session.activated_at = now
                    session.idle_at = None
                if session.state == 'listening':
                    session.activity_at = now
                session.revision += 1
            else:
                raise HTTPException(409, 'Audio action is invalid in the current state')
            session.receipts[event_id] = (fingerprint, session.revision)
            while len(session.receipts) > self.max_receipts:
                session.receipts.popitem(last=False)
            return self._snapshot(session, now, acknowledged_revision=session.revision)


def mount(app, auth, store=None, prefix='/api'):
    """Register owner-only control endpoints; return the per-app memory store."""
    store = store if store is not None else Sessions()
    if hasattr(app, 'state'):
        app.state.audio_sessions = store

    @app.post(prefix+'/voice/sessions', dependencies=[Depends(auth)], status_code=201)
    def create_audio_session(body: Create):
        return store.create(body)

    @app.get(prefix+'/voice/sessions/{ident}', dependencies=[Depends(auth)])
    def get_audio_session(ident: uuid.UUID):
        return store.get(ident)

    @app.post(prefix+'/voice/sessions/{ident}/events', dependencies=[Depends(auth)])
    def audio_event(ident: uuid.UUID, body: Event):
        return store.event(ident, body)

    return store
