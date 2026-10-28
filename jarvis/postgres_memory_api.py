"""Explicit owner API for optional scoped PostgreSQL memory. No auto recall."""
import os
import uuid
from typing import Literal
from fastapi import Depends, Header, HTTPException, Query
from pydantic import BaseModel,ConfigDict,Field
from starlette.concurrency import run_in_threadpool
from .postgres_api import subject
from . import recall


class MemoryContent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    content:str=Field(min_length=1,max_length=8000)
    category:str=Field(default='note',pattern=r'^[a-z_]{1,40}$')
    source:Literal['manual','session','import']='manual'
    source_id:str=Field(default='',max_length=120)

class MemoryCreate(MemoryContent):
    workshop_id:uuid.UUID|None=None

class MemoryUpdate(MemoryContent):
    revision:int=Field(ge=0,strict=True)

class MemoryIndex(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=0,strict=True)

class MemoryQuery(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query:str=Field(min_length=1,max_length=4000)
    workshop_id:uuid.UUID|None=None
    limit:int=Field(default=5,ge=1,le=30,strict=True)


def feature_enabled():
    flag=os.getenv('JARVIS_POSTGRES_MEMORY_ENABLED','false').lower()
    if flag not in ('true','false'):
        raise HTTPException(503,'PostgreSQL memory activation is invalid')
    return flag=='true'


def embedding_config():
    try:
        return recall.embedding_config()
    except HTTPException:
        raise
    except (ValueError,TypeError):
        raise HTTPException(503,'Local memory embedding configuration is invalid') from None


async def embed(text,config):
    try:
        return (await recall.embed([text],config))[0]
    except Exception:
        raise HTTPException(502,'Local memory embedding failed; stored memory unchanged') from None


def mount(router,memory,owner_auth,authenticate):
    def active():
        if not feature_enabled() or not memory.storage.config.enabled:
            raise HTTPException(503,'PostgreSQL memory is disabled')

    @router.get('/storage/memory/status',dependencies=[Depends(owner_auth)])
    def status():
        if not feature_enabled() or not memory.storage.config.enabled:
            return {'enabled':False,'status':'disabled','memory_schema_version':None}
        return memory.status()

    @router.get('/storage/memory')
    def records(principal=Depends(owner_auth),workshop_id:uuid.UUID|None=None,
                limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=100000)):
        active()
        return memory.list(subject(principal),workshop_id=workshop_id,limit=limit,offset=offset)

    @router.post('/storage/memory',status_code=201)
    def create(body:MemoryCreate,principal=Depends(owner_auth)):
        active()
        return memory.create(subject(principal),**body.model_dump())

    @router.post('/storage/memory/search')
    async def search(body:MemoryQuery,principal=Depends(owner_auth),x_jarvis_key:str|None=Header(default=None)):
        active()
        if not body.query.strip():raise HTTPException(422,'Memory query must not be blank')
        config=embedding_config()
        value=await embed(body.query,config)
        active()
        current=authenticate(x_jarvis_key)
        return {'mode':'semantic','namespace':config[2],'workshop_id':body.workshop_id,
                'results':await run_in_threadpool(memory.semantic,subject(current),value,config[2],workshop_id=body.workshop_id,limit=body.limit)}

    @router.get('/storage/memory/{ident}')
    def get(ident:uuid.UUID,principal=Depends(owner_auth)):
        active()
        return memory.get(subject(principal),ident)

    @router.patch('/storage/memory/{ident}')
    def update(ident:uuid.UUID,body:MemoryUpdate,principal=Depends(owner_auth)):
        active()
        return memory.update(subject(principal),ident,**body.model_dump())

    @router.delete('/storage/memory/{ident}')
    def delete(ident:uuid.UUID,revision:int=Query(ge=0),principal=Depends(owner_auth)):
        active()
        return memory.delete(subject(principal),ident,revision)

    @router.post('/storage/memory/{ident}/index')
    async def index(ident:uuid.UUID,body:MemoryIndex,principal=Depends(owner_auth),x_jarvis_key:str|None=Header(default=None)):
        active()
        owner=subject(principal)
        row=await run_in_threadpool(memory.prepare_index,owner,ident,body.revision)
        config=embedding_config()
        value=await embed(row['content'],config)
        active()
        current=authenticate(x_jarvis_key)
        return await run_in_threadpool(memory.index,subject(current),ident,body.revision,row['text_hash'],value,config[2])
