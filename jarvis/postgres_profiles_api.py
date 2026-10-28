"""Opt-in owner CRUD and read-only version history for PG memory/profiles."""
import uuid
from fastapi import Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from .postgres_api import subject
from .postgres_memory_api import feature_enabled

class ProfileContent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=100)
    instructions:str=Field(min_length=1,max_length=4000)
class ProfileCreate(ProfileContent):
    workshop_id:uuid.UUID|None=None
class ProfileUpdate(ProfileContent):
    revision:int=Field(ge=0,strict=True)


def mount(router,profiles,owner_auth):
    def active():
        if not feature_enabled() or not profiles.storage.config.enabled:
            raise HTTPException(503,'PostgreSQL memory is disabled')
    @router.get('/storage/memory/profiles')
    def listed(principal=Depends(owner_auth),workshop_id:uuid.UUID|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=100000)):
        active();return profiles.list(subject(principal),workshop_id=workshop_id,limit=limit,offset=offset)
    @router.post('/storage/memory/profiles',status_code=201)
    def create(body:ProfileCreate,principal=Depends(owner_auth)):
        active();return profiles.create(subject(principal),**body.model_dump())
    @router.get('/storage/memory/profiles/{ident}')
    def get(ident:uuid.UUID,principal=Depends(owner_auth)):
        active();return profiles.get(subject(principal),ident)
    @router.patch('/storage/memory/profiles/{ident}')
    def update(ident:uuid.UUID,body:ProfileUpdate,principal=Depends(owner_auth)):
        active();return profiles.update(subject(principal),ident,**body.model_dump())
    @router.delete('/storage/memory/profiles/{ident}')
    def delete(ident:uuid.UUID,revision:int=Query(ge=0),principal=Depends(owner_auth)):
        active();return profiles.delete(subject(principal),ident,revision)
    @router.get('/storage/memory/profiles/{ident}/history')
    def profile_history(ident:uuid.UUID,principal=Depends(owner_auth),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=100000)):
        active();return profiles.history(subject(principal),ident,limit,offset)
    @router.get('/storage/memory/{ident}/history')
    def memory_history(ident:uuid.UUID,principal=Depends(owner_auth),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=100000)):
        active();return profiles.memory_history(subject(principal),ident,limit,offset)
