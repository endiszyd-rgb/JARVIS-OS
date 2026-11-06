"""Explicit synthetic write lab. No filesystem, network or production adapter.

State is bounded, account-private and lost at restart/30 minutes idle. The demo
order is not an AutoLogika ID. Approval applies exactly the previewed revision.
"""
from copy import deepcopy
import hashlib
import json
import threading
import time
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Proposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    revision: int = Field(ge=0, strict=True)
    operation: Literal['note', 'task', 'quote', 'status']
    text: str = Field(min_length=1, max_length=2000)
    amount_grosz: int | None = Field(default=None, ge=0, le=100_000_000, strict=True)

    @model_validator(mode='after')
    def fields_match(self):
        if not self.text.strip():
            raise ValueError('Empty text')
        self.text.encode('utf-8')
        if (self.operation == 'quote') != (self.amount_grosz is not None):
            raise ValueError('Amount is required only for quotes')
        if self.operation == 'status' and self.text not in ('PRZYJETE', 'DIAGNOZA', 'WYCENA', 'NAPRAWA', 'GOTOWE'):
            raise ValueError('Unsupported lab status')
        return self


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approve: bool = Field(strict=True)
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


class Lab:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.accounts = {}

    def account(self, principal):
        if not principal.is_owner:
            raise HTTPException(403, 'Owner required')
        now = self.clock()
        self.accounts = {key: value for key, value in self.accounts.items() if now-value['touched'] < 1800}
        if principal.id not in self.accounts:
            if len(self.accounts) >= 32:
                raise HTTPException(429, 'Lab capacity reached')
            self.accounts[principal.id] = {
                'order': {'id': 'DEMO-1', 'revision': 0, 'status': 'PRZYJETE', 'notes': [], 'tasks': [], 'quotes': []},
                'proposals': {}, 'events': [], 'touched': now,
            }
        account = self.accounts[principal.id]
        account['touched'] = now
        account['proposals'] = {key: value for key, value in account['proposals'].items() if now-value['created'] < 900}
        return account

    def read(self, principal):
        with self.lock:
            return {'mode': 'synthetic_write_lab', 'production_writes': False,
                    'order': deepcopy(self.account(principal)['order']), 'volatile': True,
                    'events': deepcopy(self.account(principal)['events'])}

    def propose(self, principal, body):
        with self.lock:
            account = self.account(principal)
            key = str(body.request_id)
            fingerprint = digest(body.model_dump(mode='json'))
            existing = account['proposals'].get(key)
            if existing:
                if existing['fingerprint'] != fingerprint:
                    raise HTTPException(409, 'Request ID already used for different content')
                return deepcopy(existing['public'])
            if len(account['proposals']) >= 64:
                raise HTTPException(429, 'Too many lab proposals; wait for expiry')
            before = deepcopy(account['order'])
            if before['revision'] != body.revision:
                raise HTTPException(409, 'Lab order changed; refresh preview')
            after = deepcopy(before)
            if body.operation == 'status':
                after['status'] = body.text
            else:
                collection = {'note': 'notes', 'task': 'tasks', 'quote': 'quotes'}[body.operation]
                if len(after[collection]) >= 32:
                    raise HTTPException(409, 'Lab order collection full')
                value = {'text': body.text}
                if body.operation == 'quote':
                    value.update(amount_grosz=body.amount_grosz, currency='PLN')
                after[collection].append(value)
            after['revision'] += 1
            preview = {'id': key, 'mode': 'synthetic_write_lab', 'status': 'pending',
                       'operation': body.operation, 'before': before, 'after': after}
            preview['digest'] = digest(preview)
            if sum(len(json.dumps(row['public'])) for row in account['proposals'].values()) + len(json.dumps(preview)) > 512 * 1024:
                raise HTTPException(429, 'Lab preview byte budget reached')
            account['events'] = (account['events'] + [{'id': key, 'status': 'pending', 'revision': before['revision']}])[-100:]
            account['proposals'][key] = {'fingerprint': fingerprint, 'created': self.clock(), 'public': preview}
            return deepcopy(preview)

    def decide(self, principal, key, body):
        with self.lock:
            account = self.account(principal)
            record = account['proposals'].get(str(key))
            if record is None:
                raise HTTPException(404, 'Lab proposal missing or expired')
            proposal = record['public']
            if body.digest != proposal['digest']:
                raise HTTPException(409, 'Preview digest mismatch')
            wanted = 'applied_demo' if body.approve else 'rejected'
            if proposal['status'] != 'pending':
                if proposal['status'] != wanted:
                    raise HTTPException(409, 'Proposal already decided')
                return deepcopy(proposal)
            if body.approve:
                if account['order'] != proposal['before']:
                    raise HTTPException(409, 'Lab order changed; create a new preview')
                account['order'] = deepcopy(proposal['after'])
            account['events'] = (account['events'] + [{'id': str(key), 'status': wanted, 'revision': account['order']['revision']}])[-100:]
            proposal['status'] = wanted
            return deepcopy(proposal)


def mount(api, auth):
    lab = Lab()

    @api.get('/autologika/write-lab')
    def read(principal=Depends(auth)):
        return lab.read(principal)

    @api.post('/autologika/write-lab/proposals', status_code=201)
    def propose(body: Proposal, principal=Depends(auth)):
        return lab.propose(principal, body)

    @api.post('/autologika/write-lab/proposals/{ident}/decide')
    def decide(ident: UUID, body: Decision, principal=Depends(auth)):
        return lab.decide(principal, ident, body)

    return lab
