"""Opt-in PostgreSQL foundation, separate from the existing SQLite modules."""
import uuid
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Stable subject for this installation's bootstrap key. Account sessions use
# their actual UUID; changing a key must not create a new private namespace.
BOOTSTRAP_SUBJECT = uuid.uuid5(uuid.NAMESPACE_URL, 'jarvis:local:bootstrap-owner')


class RecordCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)
    workshop_id: uuid.UUID | None = None

    @field_validator('title')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Title must not be blank')
        return value


class RecordUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0, strict=True)
    title: str = Field(min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)

    @field_validator('title')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Title must not be blank')
        return value


def subject(principal):
    if principal.kind == 'owner_key':
        return BOOTSTRAP_SUBJECT
    if principal.kind == 'session' and principal.is_owner:
        return uuid.UUID(principal.id)
    raise HTTPException(403, 'Owner account required')


def mount(router, store, owner_auth):
    @router.get('/storage/status', dependencies=[Depends(owner_auth)])
    def status():
        if not store.config.enabled:
            return {'enabled': False, 'status': 'disabled', 'schema_version': None}
        return store.status()

    @router.get('/storage/records')
    def records(principal=Depends(owner_auth), workshop_id: uuid.UUID | None=None,
                limit: int=Query(50, ge=1, le=200), offset: int=Query(0, ge=0, le=100000)):
        return store.list(subject(principal), workshop_id=workshop_id, limit=limit, offset=offset)

    @router.post('/storage/records', status_code=201)
    def create(body: RecordCreate, principal=Depends(owner_auth)):
        return store.create(subject(principal), body.title, body.payload, workshop_id=body.workshop_id)

    @router.get('/storage/records/{ident}')
    def get(ident: uuid.UUID, principal=Depends(owner_auth)):
        return store.get(subject(principal), ident)

    @router.patch('/storage/records/{ident}')
    def update(ident: uuid.UUID, body: RecordUpdate, principal=Depends(owner_auth)):
        return store.update(subject(principal), ident, body.revision, body.title, body.payload)

    @router.delete('/storage/records/{ident}')
    def delete(ident: uuid.UUID, revision: int=Query(ge=0), principal=Depends(owner_auth)):
        return store.delete(subject(principal), ident, revision)
