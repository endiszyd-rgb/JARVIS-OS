"""Account-private short context and explicit references to scoped PG memory.

No model I/O or SQLite state. A bounded database lease prevents concurrent turns;
completion and metadata audit commit atomically after current-source validation.
"""
from dataclasses import dataclass
import uuid
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from .postgres_store import PostgresStore, _ident, _revision

MAX_TURNS=64
MAX_SESSIONS=32
CONTEXT_CHARS=16000
CONTEXT_TURNS=10
_SESSION="id,owner_id,workshop_id,provider,model_name,revision,expires_at,created_at,active_turn,active_until,(to_jsonb(memory_sessions)->>'profile_id')::uuid AS profile_id,(to_jsonb(memory_sessions)->>'profile_revision')::integer AS profile_revision"


def text(value,maximum):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or '\0' in value:
        raise HTTPException(422,'Invalid conversation text')
    try:value.encode('utf-8')
    except UnicodeError:raise HTTPException(422,'Invalid conversation text encoding') from None
    return value


def references(value,*,limit=5):
    if not isinstance(value,list) or len(value)>limit:
        raise HTTPException(422,'Memory reference limit exceeded')
    result=[];seen=set()
    for ref in value:
        if not isinstance(ref,dict) or set(ref)!={'id','revision'}:
            raise HTTPException(422,'Invalid memory reference')
        ident=_ident(ref['id']);revision=_revision(ref['revision'])
        if ident in seen:raise HTTPException(422,'Memory references must be unique')
        seen.add(ident);result.append({'id':str(ident),'revision':revision})
    return result


def merge_references(refs):
    merged={}
    for ref in refs:
        old=merged.get(ref['id'])
        if old is not None and old['revision']!=ref['revision']:
            raise HTTPException(409,'Historical memory revision changed; start a new conversation')
        merged[ref['id']]=ref
    if len(merged)>20:raise HTTPException(409,'Conversation memory source limit reached; start a new conversation')
    return list(merged.values())


def bounded_history(turns):
    """Keep complete newest pairs, never a partial assistant reply or failed turn."""
    selected=[];chars=0
    for turn in turns[:CONTEXT_TURNS]:
        size=len(turn['user_text'])+len(turn['assistant_text'])
        if chars+size>CONTEXT_CHARS:break
        selected.append(turn);chars+=size
    selected.reverse()
    rows=[]
    for turn in selected:
        rows.extend(({'role':'user','content':turn['user_text']},{'role':'assistant','content':turn['assistant_text']}))
    return rows,merge_references([ref for turn in selected for ref in references(turn['memory_refs'],limit=20)])


@dataclass(frozen=True)
class PreparedContext:
    session:dict
    claim:uuid.UUID
    history:list
    history_refs:list
    memory_refs:list
    notes:list
    profile:dict|None=None


class PostgresContext:
    def __init__(self,storage:PostgresStore):
        if not isinstance(storage,PostgresStore):raise ValueError('PostgresContext requires checked PostgresStore')
        self.storage=storage

    @staticmethod
    def public(row):
        return {key:value for key,value in row.items() if key not in ('active_turn','active_until')}

    @staticmethod
    def _get(c,ident,*,lock=False,active=False):
        row=c.execute('SELECT '+_SESSION+',expires_at<=statement_timestamp() AS expired FROM jarvis.memory_sessions WHERE id=%s'+(' FOR UPDATE' if lock else ''),(ident,)).fetchone()
        if row is None:raise HTTPException(404,'Memory conversation missing')
        if active and row['expired']:raise HTTPException(410,'Memory conversation expired')
        return row

    @staticmethod
    def _event(c,subject,row,event):
        c.execute('INSERT INTO jarvis.memory_session_events(subject,session_id,event,revision) VALUES(%s,%s,%s,%s)',
                  (subject,row['id'],event,row['revision']))

    @staticmethod
    def _notes(c,scope,refs):
        notes=[]
        # Metadata from prior turns never grants access; each row passes current RLS.
        for ref in refs:
            row=c.execute('SELECT id,workshop_id,revision,content FROM jarvis.memory_records WHERE id=%s',(_ident(ref['id']),)).fetchone()
            if row is None:raise HTTPException(409,'A selected or historical memory source is unavailable; start a new conversation')
            if row['workshop_id']!=scope:raise HTTPException(403,'Memory source is outside this conversation scope')
            if row['revision']!=ref['revision']:raise HTTPException(409,'Memory source revision changed; start a new conversation')
            notes.append({'id':str(row['id']),'revision':row['revision'],'content':row['content']})
        return notes

    @staticmethod
    def _profile(c,row):
        if row.get('profile_id') is None:return None
        # Current RLS includes read-only workshop membership; row locks would apply UPDATE policies.
        profile=c.execute('SELECT id,workshop_id,revision,instructions FROM jarvis.memory_profiles WHERE id=%s',(row['profile_id'],)).fetchone()
        if profile is None or profile['revision']!=row['profile_revision']:
            raise HTTPException(409,'Pinned profile unavailable or changed; start a new conversation')
        if profile['workshop_id']!=row['workshop_id']:
            raise HTTPException(403,'Profile is outside this conversation scope')
        return {'id':str(profile['id']),'revision':profile['revision'],'instructions':profile['instructions']}

    def create(self,subject,provider,model,*,workshop_id=None,ttl_minutes=60,profile_ref=None):
        subject=_ident(subject);scope=_ident(workshop_id) if workshop_id is not None else None
        if provider not in ('ollama','openai'):raise HTTPException(422,'Unsupported memory conversation provider')
        text(model,150)
        if type(ttl_minutes) is not int or not 1<=ttl_minutes<=1440:raise HTTPException(422,'Invalid conversation TTL')
        refs=references([profile_ref]) if profile_ref is not None else []
        with self.storage._connection(subject) as c:
            if refs:self._profile(c,{'profile_id':_ident(refs[0]['id']),'profile_revision':refs[0]['revision'],'workshop_id':scope})
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,11471))',(str(subject),))
            count=c.execute('SELECT count(*) AS count FROM jarvis.memory_sessions WHERE expires_at>statement_timestamp()').fetchone()['count']
            if count>=MAX_SESSIONS:raise HTTPException(429,'Active memory conversation limit reached')
            if refs:
                row=c.execute("INSERT INTO jarvis.memory_sessions(owner_id,workshop_id,provider,model_name,expires_at,profile_id,profile_revision) VALUES(%s,%s,%s,%s,statement_timestamp()+(%s * interval '1 minute'),%s,%s) RETURNING "+_SESSION,
                              (subject,scope,provider,model,ttl_minutes,_ident(refs[0]['id']),refs[0]['revision'])).fetchone()
            else:
                row=c.execute("INSERT INTO jarvis.memory_sessions(owner_id,workshop_id,provider,model_name,expires_at) VALUES(%s,%s,%s,%s,statement_timestamp()+(%s * interval '1 minute')) RETURNING "+_SESSION,
                              (subject,scope,provider,model,ttl_minutes)).fetchone()
            self._event(c,subject,row,'created')
            return self.public(row)

    def get(self,subject,ident):
        with self.storage._connection(_ident(subject)) as c:return self.public(self._get(c,_ident(ident)))

    def list(self,subject,limit=50,offset=0):
        if type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or not 0<=offset<=100000:raise HTTPException(422,'Invalid conversation page')
        with self.storage._connection(_ident(subject)) as c:
            return [self.public(row) for row in c.execute('SELECT '+_SESSION+',expires_at<=statement_timestamp() AS expired FROM jarvis.memory_sessions ORDER BY created_at DESC,id LIMIT %s OFFSET %s',(limit,offset)).fetchall()]

    def history(self,subject,ident):
        with self.storage._connection(_ident(subject)) as c:
            row=self._get(c,_ident(ident),active=True)
            profile=self._profile(c,row)
            turns=c.execute('SELECT user_text,assistant_text,memory_refs FROM jarvis.memory_turns WHERE session_id=%s ORDER BY sequence DESC LIMIT 10',(row['id'],)).fetchall()
            history,refs=bounded_history(turns)
            self._notes(c,row['workshop_id'],refs)
            return {'session_id':row['id'],'revision':row['revision'],'messages':history,'context_limit_chars':CONTEXT_CHARS,'context_limit_messages':20}

    def begin(self,subject,ident,revision,refs):
        subject,ident,revision=_ident(subject),_ident(ident),_revision(revision);refs=references(refs)
        with self.storage._connection(subject) as c:
            row=self._get(c,ident,lock=True,active=True)
            if row['revision']!=revision:raise HTTPException(409,'Conversation revision changed; refresh')
            if row['revision']>=MAX_TURNS:raise HTTPException(409,'Conversation turn limit reached')
            busy=c.execute('SELECT active_turn IS NOT NULL AND active_until>statement_timestamp() AS busy FROM jarvis.memory_sessions WHERE id=%s',(ident,)).fetchone()['busy']
            if busy:raise HTTPException(409,'A turn is already running in this conversation')
            profile=self._profile(c,row)
            turns=c.execute('SELECT user_text,assistant_text,memory_refs FROM jarvis.memory_turns WHERE session_id=%s ORDER BY sequence DESC LIMIT 10',(ident,)).fetchall()
            history,history_refs=bounded_history(turns)
            merge_references(history_refs+refs)
            self._notes(c,row['workshop_id'],history_refs)
            notes=self._notes(c,row['workshop_id'],refs)
            claim=uuid.uuid4()
            c.execute("UPDATE jarvis.memory_sessions SET active_turn=%s,active_until=statement_timestamp()+interval '120 seconds' WHERE id=%s",(claim,ident))
            return PreparedContext(row,claim,history,history_refs,refs,notes,profile)

    def validate(self,subject,prepared):
        with self.storage._connection(_ident(subject)) as c:
            row=self._get(c,prepared.session['id'],active=True)
            self._claimed(c,row,prepared)
            self._profile(c,row)
            self._notes(c,row['workshop_id'],merge_references(prepared.history_refs+prepared.memory_refs))
            return row

    @staticmethod
    def _claimed(c,row,prepared):
        if row['active_turn']!=prepared.claim or row['revision']!=prepared.session['revision']:
            raise HTTPException(409,'Conversation turn claim changed')
        alive=c.execute('SELECT active_until>statement_timestamp() AS alive FROM jarvis.memory_sessions WHERE id=%s',(row['id'],)).fetchone()['alive']
        if not alive:raise HTTPException(409,'Conversation turn lease expired')

    def finish(self,subject,prepared,message,reply,*,authorize=None):
        subject=_ident(subject);text(message,8000);text(reply,32000)
        with self.storage._connection(subject) as c:
            row=self._get(c,prepared.session['id'],lock=True,active=True)
            self._claimed(c,row,prepared)
            self._profile(c,row)
            all_refs=merge_references(prepared.history_refs+prepared.memory_refs)
            self._notes(c,row['workshop_id'],all_refs)
            if authorize is not None:authorize()
            c.execute('INSERT INTO jarvis.memory_turns(id,session_id,sequence,user_text,assistant_text,memory_refs) VALUES(%s,%s,%s,%s,%s,%s)',
                      (prepared.claim,row['id'],row['revision']+1,message,reply,Jsonb(all_refs)))
            result=c.execute('UPDATE jarvis.memory_sessions SET revision=revision+1,active_turn=NULL,active_until=NULL WHERE id=%s RETURNING '+_SESSION,(row['id'],)).fetchone()
            self._event(c,subject,result,'completed')
            return self.public(result)

    def release(self,subject,prepared):
        with self.storage._connection(_ident(subject)) as c:
            c.execute('UPDATE jarvis.memory_sessions SET active_turn=NULL,active_until=NULL WHERE id=%s AND active_turn=%s',(prepared.session['id'],prepared.claim))

    def delete(self,subject,ident,revision):
        subject,ident,revision=_ident(subject),_ident(ident),_revision(revision)
        with self.storage._connection(subject) as c:
            row=self._get(c,ident,lock=True)
            if row['revision']!=revision:raise HTTPException(409,'Conversation revision changed; refresh')
            busy=c.execute('SELECT active_turn IS NOT NULL AND active_until>statement_timestamp() AS busy FROM jarvis.memory_sessions WHERE id=%s',(ident,)).fetchone()['busy']
            if busy and not row['expired']:raise HTTPException(409,'Conversation turn is running')
            c.execute('DELETE FROM jarvis.memory_sessions WHERE id=%s',(ident,))
            self._event(c,subject,row,'deleted')
            return {'deleted':str(ident)}
