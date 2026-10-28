"""Owner-only personal-memory policy and provenance."""
import json
import re
import time
import unicodedata
import uuid
from typing import Literal
from fastapi import Depends, HTTPException
from pydantic import Field
from .telephony import Strict

Category = Literal['preferences','equipment','projects','decisions','working_style','manual']

class Policy(Strict):
    enabled: bool = True
    mode: Literal['manual','auto'] = 'manual'
    categories: list[Category] = Field(default_factory=lambda:['preferences','equipment','projects','decisions','working_style'], max_length=6)
    retention_days: int | None = Field(default=None, ge=1, le=3650)

class Save(Strict):
    revision: int = Field(ge=0)
    policy: Policy

class Note(Strict):
    text: str = Field(min_length=1,max_length=4000)
    category: Category = 'manual'

class Correction(Note):
    revision: int = Field(ge=0)

class Purge(Strict):
    dry_run: bool = True


def install(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS memory_policy(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS memory_sources(memory_id TEXT PRIMARY KEY REFERENCES memory(id) ON DELETE CASCADE,source TEXT NOT NULL,category TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0,updated REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS memory_history(id INTEGER PRIMARY KEY,memory_id TEXT NOT NULL REFERENCES memory(id) ON DELETE CASCADE,revision INTEGER NOT NULL,text TEXT NOT NULL,source TEXT NOT NULL,category TEXT NOT NULL,created REAL NOT NULL,UNIQUE(memory_id,revision));
    ''')
    c.execute('INSERT OR IGNORE INTO memory_policy VALUES(1,0,?)',(Policy().model_dump_json(),))
    c.execute("INSERT OR IGNORE INTO memory_sources SELECT id,'legacy_manual','manual',0,created FROM memory")


def policy(c):
    row=c.execute('SELECT * FROM memory_policy WHERE id=1').fetchone()
    return row['revision'],Policy.model_validate_json(row['value'])


def refuses_memory(text):
    normalized=''.join(ch for ch in unicodedata.normalize('NFD',text.lower()) if not unicodedata.combining(ch))
    return bool(re.search(r'\b(?:nie\s+(?:zapamietuj|pamietaj|zapisuj)|nie\s+chce\s+(?:tego\s+)?zapamietywac)\b',normalized))


def save_note(c,text,source,category='manual'):
    # Sources are chosen by trusted owner endpoints, never supplied by a model or caller.
    if source not in ('owner_manual','owner_chat'):raise ValueError('Unsupported personal source')
    if not text.strip():raise HTTPException(422,'Memory text is blank')
    if not policy(c)[1].enabled or refuses_memory(text):
        raise HTTPException(409,'Memory recording is disabled for this request')
    ident=str(uuid.uuid4());now=time.time()
    c.execute('INSERT INTO memory VALUES(?,?,?)',(ident,text,now))
    c.execute('INSERT INTO memory_sources VALUES(?,?,?,?,?)',(ident,source,category,0,now))
    return ident


def mount(app,db,auth,audit,prefix='/api'):
    @app.get(prefix+'/memory/policy',dependencies=[Depends(auth)])
    def get_policy():
        with db() as c:
            revision,value=policy(c)
        return {'revision':revision,'policy':value.model_dump(),
                'automatic_extraction_active':value.enabled and value.mode=='auto' and bool(set(value.categories)-{'manual'}),
                'automatic_extractor':'pl-declarations-v1',
                'excluded_from_automatic':['secrets','payment_data','customer_data']}

    @app.put(prefix+'/memory/policy',dependencies=[Depends(auth)])
    def put_policy(body:Save):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if policy(c)[0]!=body.revision:raise HTTPException(409,'Memory policy revision changed')
            c.execute('UPDATE memory_policy SET revision=revision+1,value=? WHERE id=1',(body.policy.model_dump_json(),))
            audit(c,'memory.policy_updated',{'revision':body.revision+1})
        return get_policy()

    @app.post(prefix+'/memory/retention',dependencies=[Depends(auth)])
    def retention(body:Purge):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            days=policy(c)[1].retention_days
            rows=[] if days is None else [r[0] for r in c.execute('SELECT id FROM memory WHERE created<?',(time.time()-days*86400,))]
            if not body.dry_run:
                c.executemany('DELETE FROM memory WHERE id=?',[(ident,) for ident in rows])
                audit(c,'memory.retention',{'count':len(rows)})
        return {'dry_run':body.dry_run,'count':len(rows),'retention_days':days}

    @app.get(prefix+'/memory/{ident}/history',dependencies=[Depends(auth)])
    def history(ident:str):
        with db() as c:
            if not c.execute('SELECT 1 FROM memory WHERE id=?',(ident,)).fetchone():raise HTTPException(404,'Memory missing')
            return [dict(r) for r in c.execute('SELECT revision,text,source,category,created FROM memory_history WHERE memory_id=? ORDER BY revision',(ident,))]

    @app.get(prefix+'/memory/{ident}/origins',dependencies=[Depends(auth)])
    def origins(ident:str):
        with db() as c:
            if not c.execute('SELECT 1 FROM memory WHERE id=?',(ident,)).fetchone():raise HTTPException(404,'Memory missing')
            return [dict(r) for r in c.execute('''SELECT o.revision,o.session_id,o.turn_id,o.quote,o.extractor,o.created,
                EXISTS(SELECT 1 FROM chat_sessions s WHERE s.id=o.session_id) AS session_available
                FROM memory_origins o WHERE memory_id=? ORDER BY revision''',(ident,))]

    @app.put(prefix+'/memory/{ident}',dependencies=[Depends(auth)])
    def correct(ident:str,body:Correction):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not policy(c)[1].enabled or refuses_memory(body.text):raise HTTPException(409,'Memory recording is disabled for this request')
            if not body.text.strip():raise HTTPException(422,'Memory text is blank')
            row=c.execute('SELECT m.text,s.* FROM memory m JOIN memory_sources s ON s.memory_id=m.id WHERE m.id=?',(ident,)).fetchone()
            if not row:raise HTTPException(404,'Memory missing')
            if row['revision']!=body.revision:raise HTTPException(409,'Memory revision changed')
            now=time.time()
            c.execute('INSERT INTO memory_history(memory_id,revision,text,source,category,created) VALUES(?,?,?,?,?,?)',
                      (ident,row['revision'],row['text'],row['source'],row['category'],now))
            c.execute('UPDATE memory SET text=? WHERE id=?',(body.text,ident))
            c.execute("UPDATE memory_sources SET source='owner_correction',category=?,revision=revision+1,updated=? WHERE memory_id=?",(body.category,now,ident))
            c.execute('DELETE FROM memory_vectors WHERE memory_id=?',(ident,))
            audit(c,'memory.corrected',{'id':ident,'revision':body.revision+1})
        return {'id':ident,'revision':body.revision+1}
