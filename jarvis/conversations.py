"""Persistent single-owner conversations, bounded context and per-session turn lock."""
import json
import os
import time
import uuid
from fastapi import HTTPException
from . import memory_auto
from .llm_providers import cloud_models, OpenAIConfig


def install_modes(c):
    c.execute("CREATE TABLE IF NOT EXISTS chat_session_modes(session_id TEXT PRIMARY KEY REFERENCES chat_sessions(id) ON DELETE CASCADE,input_mode TEXT NOT NULL CHECK(input_mode IN ('text','voice')))")
    c.execute("INSERT OR IGNORE INTO chat_session_modes SELECT id,'text' FROM chat_sessions")


def ollama_catalog():
    names=[x.strip() for x in os.getenv('OLLAMA_ALLOWED_MODELS',os.getenv('OLLAMA_MODEL','qwen2.5:3b')).split(',') if x.strip()]
    allow_cloud=os.getenv('JARVIS_ALLOW_CLOUD_MODELS','false').lower()=='true'
    return [{'provider':'ollama','name':name,'cloud':name.endswith(':cloud')} for name in dict.fromkeys(names) if len(name)<=150 and (allow_cloud or not name.endswith(':cloud'))]


def model_catalog():
    return [{'provider':'demo','name':'demo','cloud':False}] + ollama_catalog() + cloud_models()


def choose_model(provider,name=None):
    if provider=='demo':
        if name not in (None,'','demo'):raise HTTPException(422,'Demo does not accept an Ollama model name')
        return 'demo'
    if provider=='openai':
        configured=OpenAIConfig.from_env().model
        if name not in (None,'',configured):raise HTTPException(403,'Cloud model not on configured allowlist')
        return configured
    if provider!='ollama':raise HTTPException(422,'Unknown provider')
    name=name or os.getenv('OLLAMA_MODEL','qwen2.5:3b')
    if not any(m['provider']==provider and m['name']==name for m in ollama_catalog()):
        raise HTTPException(403,'Model not on configured allowlist')
    return name


class Conversations:
    def __init__(self,db,audit):self.db=db;self.audit=audit

    def create(self,title,provider,name,input_mode='text'):
        name=choose_model(provider,name)
        ident=str(uuid.uuid4());now=time.time()
        with self.db() as c:
            c.execute('INSERT INTO chat_sessions VALUES(?,?,?,?,?,?,NULL,NULL)',(ident,title,provider,name,now,now))
            c.execute('INSERT INTO chat_session_modes VALUES(?,?)',(ident,input_mode))
            self.audit(c,'chat.session_created',{'id':ident,'provider':provider})
        return {'id':ident,'title':title,'provider':provider,'model_name':name,'created':now,'updated':now,'input_mode':input_mode}

    def get(self,ident):
        with self.db() as c:
            row=c.execute('SELECT s.*,m.input_mode FROM chat_sessions s JOIN chat_session_modes m ON m.session_id=s.id WHERE s.id=?',(ident,)).fetchone()
        if not row:raise HTTPException(404,'Chat session missing')
        with self.db() as c:
            count=c.execute('SELECT COUNT(*) FROM chat_messages WHERE session_id=?',(ident,)).fetchone()[0]
        return dict(row,message_count=count)

    def list(self,limit,offset):
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT s.id,s.title,s.provider,s.model_name,s.created,s.updated,s.active_turn,m.input_mode FROM chat_sessions s JOIN chat_session_modes m ON m.session_id=s.id ORDER BY s.updated DESC,s.id LIMIT ? OFFSET ?',(limit,offset))]

    def messages(self,ident,limit=100,offset=0):
        self.get(ident)
        with self.db() as c:
            return [dict(r) for r in c.execute('SELECT id,role,content,created,state,turn_id FROM chat_messages WHERE session_id=? ORDER BY id LIMIT ? OFFSET ?',(ident,limit,offset))]

    def begin(self,ident,provider,name,text,allow_memory=True,input_mode='text'):
        turn=str(uuid.uuid4());now=time.time()
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM chat_sessions WHERE id=?',(ident,)).fetchone()
            if not row:raise HTTPException(404,'Chat session missing')
            mode=c.execute('SELECT input_mode FROM chat_session_modes WHERE session_id=?',(ident,)).fetchone()
            if not mode or mode[0]!=input_mode:raise HTTPException(422,'Use the original text/voice mode or create a separate session')
            if row['active_turn'] and now-row['active_since']<180:
                raise HTTPException(409,'A turn is already running in this session')
            if row['active_turn']:
                c.execute("UPDATE chat_messages SET state='failed' WHERE turn_id=? AND state='pending'",(row['active_turn'],))
                self.audit(c,'chat.stale_turn_recovered',{'session_id':ident})
            # Only successful prior turns are context. Failed/pending requests never leak into a reply.
            rows=c.execute("SELECT role,content FROM chat_messages WHERE session_id=? AND state='completed' ORDER BY id DESC LIMIT 20",(ident,)).fetchall()
            history=[];chars=0
            for item in rows:
                if chars+len(item['content'])>24000:break
                history.append({'role':item['role'],'content':item['content']});chars+=len(item['content'])
            history.reverse()
            c.execute('UPDATE chat_sessions SET active_turn=?,active_since=?,provider=?,model_name=?,updated=? WHERE id=?',(turn,now,provider,name,now,ident))
            c.execute("INSERT INTO chat_messages(session_id,turn_id,role,content,created,state) VALUES(?,?,'user',?,?,'pending')",(ident,turn,text,now))
            memory_auto.begin(c,ident,turn,allow_memory)
        return turn,history

    def finish(self,ident,turn,reply):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT active_turn FROM chat_sessions WHERE id=?',(ident,)).fetchone()
            if not row or row[0]!=turn:raise HTTPException(409,'Turn no longer active')
            captured=memory_auto.capture(c,ident,turn)
            c.execute("UPDATE chat_messages SET state='completed' WHERE turn_id=? AND role='user'",(turn,))
            c.execute("INSERT INTO chat_messages(session_id,turn_id,role,content,created,state) VALUES(?,?,'assistant',?,?,'completed')",(ident,turn,reply,time.time()))
            c.execute('UPDATE chat_sessions SET active_turn=NULL,active_since=NULL,updated=? WHERE id=?',(time.time(),ident))
            self.audit(c,'chat.turn_completed',{'session_id':ident,'turn_id':turn})
            self.audit(c,'memory.auto_capture',{'session_id':ident,'turn_id':turn,**captured})
        return captured

    def fail(self,ident,turn):
        with self.db() as c:
            c.execute("UPDATE chat_messages SET state='failed' WHERE turn_id=? AND state='pending'",(turn,))
            c.execute('UPDATE chat_sessions SET active_turn=NULL,active_since=NULL WHERE id=? AND active_turn=?',(ident,turn))
            self.audit(c,'chat.turn_failed',{'session_id':ident,'turn_id':turn})

    def remove(self,ident):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT active_turn,active_since FROM chat_sessions WHERE id=?',(ident,)).fetchone()
            if not row:raise HTTPException(404,'Chat session missing')
            if row[0] and time.time()-row[1]<180:raise HTTPException(409,'Wait for active turn before deleting')
            c.execute('DELETE FROM chat_sessions WHERE id=?',(ident,))
            self.audit(c,'chat.session_deleted',{'id':ident})

    def prune(self,days,dry_run):
        cutoff=time.time()-days*86400
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            count=c.execute('SELECT COUNT(*) FROM chat_sessions WHERE updated<? AND active_turn IS NULL',(cutoff,)).fetchone()[0]
            if not dry_run:
                c.execute('DELETE FROM chat_sessions WHERE updated<? AND active_turn IS NULL',(cutoff,))
                self.audit(c,'chat.retention_applied',{'days':days,'sessions_deleted':count})
        return {'dry_run':dry_run,'sessions':count}
