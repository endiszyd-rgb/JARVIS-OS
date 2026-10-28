"""Durable owner/caller transport laboratory. No carrier or live call adapter."""
from datetime import datetime,timezone
import hashlib
import hmac
import json
import re
import secrets
import uuid
from fastapi import Depends,Header,HTTPException
from pydantic import Field,model_validator
from . import reception,telephony
from .telephony_adapter import Command,Ack,LabAdapter

class Limits(telephony.Strict):
    owner_wait_seconds:int=Field(default=30,ge=1,le=120,strict=True)
    max_call_seconds:int=Field(default=600,ge=30,le=1800,strict=True)
    max_owner_attempts:int=Field(default=1,ge=0,le=1,strict=True)
    max_simulated_cost_units:int=Field(default=2,ge=0,le=10,strict=True)
    max_turns:int=Field(default=24,ge=1,le=24,strict=True)
class Start(telephony.Strict):
    event_id:uuid.UUID
    caller:str=Field(default='',pattern=r'^(?:|\+[1-9][0-9]{6,14})$')
    limits:Limits=Field(default_factory=Limits)
class CallerEvent(telephony.Strict):
    event_id:uuid.UUID
    revision:int=Field(ge=0,strict=True)
    action: str = Field(pattern=r'^(turn|hangup)$')
    text:str=Field(default='',max_length=4000)
    @model_validator(mode='after')
    def payload(self):
        if self.action=='turn' and not self.text.strip():raise ValueError('Customer text required')
        if self.action=='hangup' and self.text:raise ValueError('Hangup has no text')
        return self
class OwnerEvent(telephony.Strict):
    event_id:uuid.UUID
    revision:int=Field(ge=0,strict=True)
    action:str=Field(pattern=r'^(dispatch|accept|decline|no_answer|finish|rotate_caller_token)$')
    attempt_id:uuid.UUID|None=None
    fail_next_owner:bool=False
    @model_validator(mode='after')
    def payload(self):
        if (self.action in ('accept','decline','no_answer'))!=(self.attempt_id is not None):raise ValueError('Owner decision requires the private attempt ID only')
        if self.fail_next_owner and self.action!='dispatch':raise ValueError('Fault injection belongs to lab dispatch')
        return self


def install(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS transport_calls(id TEXT PRIMARY KEY,reception_id TEXT NOT NULL UNIQUE REFERENCES reception_calls(id) ON DELETE CASCADE,revision INTEGER NOT NULL,payload TEXT NOT NULL,caller_digest TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS transport_starts(event_id TEXT PRIMARY KEY,digest TEXT NOT NULL,call_id TEXT NOT NULL REFERENCES transport_calls(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS transport_receipts(call_id TEXT NOT NULL REFERENCES transport_calls(id) ON DELETE CASCADE,channel TEXT NOT NULL,event_id TEXT NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(call_id,channel,event_id));
    CREATE TABLE IF NOT EXISTS transport_outbox(id TEXT PRIMARY KEY,call_id TEXT NOT NULL REFERENCES transport_calls(id) ON DELETE CASCADE,seq INTEGER NOT NULL,channel TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,UNIQUE(call_id,seq));
    ''')


def digest(body):return hashlib.sha256(body.model_dump_json().encode()).hexdigest()
def token_digest(token):return hashlib.sha256(token.encode()).hexdigest()


def assessment(text):
    """Closed full-message lab fixtures, deliberately not semantic caller AI."""
    value=reception.normalized(text.strip()).removesuffix('.')
    patterns={
        'prosze o rozmowe z wlascicielem':'contact_requested',
        'ponownie prosze o wlasciciela i odrzucam pomoc asystenta':'insistent',
        'po naprawie nie dzialaja hamulce':'crisis',
    }
    kind=patterns.get(value,'unclear')
    return {'effective_kind':kind,'extracted':{},'source':'closed_transport_lab_fixtures','needs_clarification':kind=='unclear'}


class Transport:
    def __init__(self,db,audit,clock=None,adapter=None):
        self.db=db;self.audit=audit;self.reception=reception.Reception(db,audit)
        self.clock=clock or (lambda:datetime.now(timezone.utc));self.adapter=adapter or LabAdapter()
    def _now(self):
        at=self.clock()
        if at.utcoffset() is None:raise ValueError('Transport clock requires timezone')
        return at
    def _load(self,c,ident):
        row=c.execute('SELECT * FROM transport_calls WHERE id=?',(ident,)).fetchone()
        if row is None:raise HTTPException(404,'Transport lab call missing')
        return row,json.loads(row['payload'])
    def _reception(self,c,row):
        rec=c.execute('SELECT * FROM reception_calls WHERE id=?',(row['reception_id'],)).fetchone()
        if rec is None:raise HTTPException(404,'Transport lab call missing')
        return reception.render(rec)
    def _rec_event(self,c,row,action,at,text='',analysis=None):
        rec=self._reception(c,row)
        body=reception.Event(event_id=uuid.uuid4(),revision=rec['revision'],action=action,at=at,text=text)
        return self.reception.apply_in_transaction(c,row['reception_id'],body,analysis)
    def _save(self,c,row,p,at):
        c.execute('UPDATE transport_calls SET revision=revision+1,payload=?,updated=? WHERE id=?',(json.dumps(p,ensure_ascii=False),at.timestamp(),row['id']))
        return self._load(c,row['id'])
    def _queue(self,c,row,channel,kind,payload,at):
        command=Command(id=uuid.uuid4(),call_id=row['id'],channel=channel,kind=kind,payload=payload)
        seq=c.execute('SELECT COALESCE(MAX(seq),0)+1 FROM transport_outbox WHERE call_id=?',(row['id'],)).fetchone()[0]
        if seq>200:raise HTTPException(409,'Transport command limit reached')
        c.execute('INSERT INTO transport_outbox VALUES(?,?,?,?,?,?,?,?)',(str(command.id),row['id'],seq,channel,kind,json.dumps(command.payload,ensure_ascii=False),'pending',at.timestamp()))
    def _cancel_pending(self,c,row):
        c.execute("UPDATE transport_outbox SET status='cancelled' WHERE call_id=? AND status='pending'",(row['id'],))
    def _fallback(self,c,row,p,at,reason):
        self._cancel_pending(c,row)
        rec=self._reception(c,row)
        if rec['state']=='owner_pending':self._rec_event(c,row,'owner_no_answer',at)
        elif rec['state']!='ended':
            # Persist a callback case even when no owner attempt was affordable.
            payload=json.loads(c.execute('SELECT payload FROM reception_calls WHERE id=?',(row['reception_id'],)).fetchone()[0])
            payload['owner_outcome']=reason;self.reception.case(c,row['reception_id'],payload)
            c.execute('UPDATE reception_calls SET payload=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),row['reception_id']))
        p.update(state='reception',attempt_finished=True,deadline=None,outcome=reason)
        self._queue(c,row,'caller','say',{'text':'Nie udało się przekazać rozmowy. Zapisano prośbę o oddzwonienie, bez obietnicy godziny.'},at)
        if p['attempt_id']:self._queue(c,row,'owner','cancel',{'attempt_id':p['attempt_id'],'reason':reason},at)
    def _end(self,c,row,p,at,reason):
        self._cancel_pending(c,row)
        if self._reception(c,row)['state']!='ended':self._rec_event(c,row,'finish',at)
        if p['attempt_id']:self._queue(c,row,'owner','cancel',{'attempt_id':p['attempt_id'],'reason':reason},at)
        self._queue(c,row,'caller','end',{'text':'Zakończono połączenie laboratoryjne.'},at)
        self._queue(c,row,'system','end',{},at)
        p.update(state='ended',deadline=None,attempt_finished=True,outcome=reason)
    def _refresh(self,c,row,p,at):
        changed=False
        if p['state']!='ended' and at.timestamp()>=p['expires_at']:
            self._end(c,row,p,at,'call_timeout');changed=True
        elif p['state'] in ('waiting_owner','bridge_pending') and at.timestamp()>=p['deadline']:
            self._fallback(c,row,p,at,'owner_timeout');changed=True
        if changed:
            self.audit(c,'transport.expired',{'id':row['id'],'outcome':p['outcome']})
            return self._save(c,row,p,at)
        return row,p
    def _caller_auth(self,row,p,token,at):
        candidate=token_digest(token) if isinstance(token,str) and 1<=len(token)<=200 else ''
        if not candidate or not hmac.compare_digest(row['caller_digest'],candidate) or at.timestamp()>p['expires_at']+300:
            raise HTTPException(401,'Unauthorized call channel')
    def _public(self,c,row,p,replayed=False):
        messages=[{'id':r['id'],'text':json.loads(r['payload'])['text']} for r in c.execute("SELECT id,payload FROM transport_outbox WHERE call_id=? AND channel='caller' AND status='delivered' ORDER BY seq",(row['id'],))]
        state={'waiting_owner':'waiting','bridge_pending':'waiting','bridged_lab':'connected_lab'}.get(p['state'],p['state'])
        return {'id':row['id'],'revision':row['revision'],'state':state,'messages':messages,'mode':'transport_lab','carrier_connected':False,'calls_placed':False,'notifications_sent':False,'replayed':replayed}
    def _owner(self,c,row,p,replayed=False):
        rec=self._reception(c,row)
        commands=[dict(r,payload=json.loads(r['payload'])) for r in c.execute('SELECT id,seq,channel,kind,payload,status FROM transport_outbox WHERE call_id=? ORDER BY seq',(row['id'],))]
        return {'id':row['id'],'revision':row['revision'],**p,'reception_id':row['reception_id'],'case_id':rec['case_id'],
                'owner_briefing':rec['owner_briefing'] if p['offer_delivered'] else None,'decision':rec['decision'],
                'commands':commands,'mode':'transport_lab','carrier_connected':False,'calls_placed':False,'notifications_sent':False,'replayed':replayed}
    def start(self,body):
        at=self._now();token=None
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT * FROM transport_starts WHERE event_id=?',(str(body.event_id),)).fetchone()
            if old:
                if old['digest']!=digest(body):raise HTTPException(409,'Start event reused with different data')
                row,p=self._load(c,old['call_id']);row,p=self._refresh(c,row,p,at);result=self._owner(c,row,p,True)
            else:
                if c.execute('SELECT count(*) FROM transport_calls').fetchone()[0]>=256:raise HTTPException(409,'Lab capacity reached; remove ended calls')
                rec=self.reception.start_in_transaction(c,reception.Start(caller=body.caller));ident=str(uuid.uuid4());token=secrets.token_urlsafe(32)
                p={'state':'reception','limits':body.limits.model_dump(),'attempts':0,'simulated_cost_units':0,'turns':0,
                   'attempt_id':None,'attempt_finished':False,'offer_delivered':False,'deadline':None,'outcome':None,'consent_event_id':None,'expires_at':at.timestamp()+body.limits.max_call_seconds}
                c.execute('INSERT INTO transport_calls VALUES(?,?,0,?,?,?,?)',(ident,rec['id'],json.dumps(p),token_digest(token),at.timestamp(),at.timestamp()))
                row,p=self._load(c,ident);self._queue(c,row,'caller','say',{'text':reception.GREETING},at)
                c.execute('INSERT INTO transport_starts VALUES(?,?,?)',(str(body.event_id),digest(body),ident));self.audit(c,'transport.started',{'id':ident})
                result=self._owner(c,row,p)
        return {**result,'caller_token':token}
    def get(self,ident,token=None,caller=False):
        at=self._now()
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            try:row,p=self._load(c,ident)
            except HTTPException:
                if caller:raise HTTPException(401,'Unauthorized call channel')
                raise
            if caller:self._caller_auth(row,p,token,at)
            row,p=self._refresh(c,row,p,at)
            return self._public(c,row,p) if caller else self._owner(c,row,p)
    def list(self):
        at=self._now();result=[]
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            for item in c.execute('SELECT * FROM transport_calls ORDER BY updated DESC LIMIT 50').fetchall():
                row,p=self._refresh(c,item,json.loads(item['payload']),at)
                result.append({'id':row['id'],'revision':row['revision'],'state':p['state']})
        return result
    def delete(self,ident):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');row,p=self._load(c,ident)
            if p['state']!='ended':raise HTTPException(409,'Finish the lab call before deleting')
            c.execute('DELETE FROM reception_calls WHERE id=?',(row['reception_id'],));self.audit(c,'transport.deleted',{'id':ident})
        return {'deleted':ident}
    def _turn(self,c,row,p,body,at):
        if p['state']!='reception':raise HTTPException(409,'Customer turn is not allowed in this state')
        if p['turns']>=p['limits']['max_turns']:raise HTTPException(409,'Customer turn limit reached; hang up')
        rec=self._rec_event(c,row,'turn',at,body.text,assessment(body.text));p['turns']+=1
        if rec['state']=='owner_pending':
            if p['attempt_finished'] or p['attempts']>=p['limits']['max_owner_attempts'] or p['simulated_cost_units']+1>p['limits']['max_simulated_cost_units']:
                self._fallback(c,row,p,at,'owner_limit');return
            p.update(state='waiting_owner',attempt_id=str(uuid.uuid4()),deadline=at.timestamp()+p['limits']['owner_wait_seconds'],offer_delivered=False)
            p['attempts']+=1;p['simulated_cost_units']+=1
            self._queue(c,row,'caller','hold',{'text':'Proszę poczekać na decyzję właściciela. To laboratoryjny test przekazania.'},at)
            self._queue(c,row,'owner','offer',{'attempt_id':p['attempt_id'],'briefing':rec['owner_briefing']},at)
        else:
            self._queue(c,row,'caller','say',{'text':rec['messages'][-1]['text']},at)
    def _decision(self,c,row,p,body,at):
        if p['state']!='waiting_owner' or str(body.attempt_id)!=p['attempt_id'] or not p['offer_delivered']:
            raise HTTPException(409,'No delivered current owner offer')
        if body.action=='accept':
            policy=telephony.Policy.model_validate_json(c.execute('SELECT value FROM telephony_policy WHERE id=1').fetchone()[0])
            rec=self._reception(c,row)
            if not telephony.evaluate(policy,at,rec['situation'])['eligible_for_owner_contact']:
                self._fallback(c,row,p,at,'policy_changed');return
            if p['simulated_cost_units']+1>p['limits']['max_simulated_cost_units']:
                self._fallback(c,row,p,at,'cost_limit');return
            p['simulated_cost_units']+=1;p['consent_event_id']=str(body.event_id);p['state']='bridge_pending'
            self._queue(c,row,'system','bridge',{'attempt_id':p['attempt_id'],'consent_event_id':str(body.event_id)},at)
        else:
            self._rec_event(c,row,'owner_decline' if body.action=='decline' else 'owner_no_answer',at)
            self._fallback(c,row,p,at,'owner_declined' if body.action=='decline' else 'owner_no_answer')
    def _dispatch(self,c,row,p,body,at):
        failed=False
        for _ in range(20):
            command_row=c.execute("SELECT * FROM transport_outbox WHERE call_id=? AND status='pending' ORDER BY seq LIMIT 1",(row['id'],)).fetchone()
            if command_row is None:break
            command=Command(id=command_row['id'],call_id=row['id'],channel=command_row['channel'],kind=command_row['kind'],payload=json.loads(command_row['payload']))
            if command.kind=='bridge':
                if p['state']!='bridge_pending' or command.payload['attempt_id']!=p['attempt_id'] or command.payload['consent_event_id']!=p['consent_event_id']:
                    c.execute("UPDATE transport_outbox SET status='cancelled' WHERE id=?",(str(command.id),));continue
                policy=telephony.Policy.model_validate_json(c.execute('SELECT value FROM telephony_policy WHERE id=1').fetchone()[0])
                if not telephony.evaluate(policy,at,self._reception(c,row)['situation'])['eligible_for_owner_contact']:
                    self._fallback(c,row,p,at,'policy_changed');continue
            try:
                if body.fail_next_owner and not failed and command.kind in ('offer','bridge'):
                    failed=True;raise ValueError('Controlled transport failure')
                ack=Ack.model_validate(self.adapter.deliver(command).model_dump())
                if ack.command_id!=command.id or not ack.accepted:raise ValueError('Invalid acknowledgement')
            except Exception:
                c.execute("UPDATE transport_outbox SET status='failed' WHERE id=?",(str(command.id),))
                if command.kind in ('offer','bridge'):self._fallback(c,row,p,at,'adapter_failure')
                else:self._end(c,row,p,at,'adapter_failure');self._cancel_pending(c,row);break
                continue
            c.execute("UPDATE transport_outbox SET status='delivered' WHERE id=?",(str(command.id),))
            if command.kind=='offer':p['offer_delivered']=True
            if command.kind=='bridge':
                rec=self._rec_event(c,row,'owner_accept',at)
                if rec['state']!='connected_lab':raise RuntimeError('Reception changed during the bridge transaction')
                p.update(state='bridged_lab',deadline=None,attempt_finished=True,outcome='accepted_in_lab')
                self._queue(c,row,'caller','say',{'text':'Właściciel przyjął rozmowę w laboratorium. Nie zestawiono rzeczywistego połączenia.'},at)
    def event(self,ident,body,caller=False,token=None):
        at=self._now();error=None;new_token=None;channel='caller' if caller else 'owner'
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            try:row,p=self._load(c,ident)
            except HTTPException:
                if caller:raise HTTPException(401,'Unauthorized call channel')
                raise
            if caller:self._caller_auth(row,p,token,at)
            row,p=self._refresh(c,row,p,at)
            old=c.execute('SELECT digest FROM transport_receipts WHERE call_id=? AND channel=? AND event_id=?',(ident,channel,str(body.event_id))).fetchone()
            replay=old is not None
            if old and old[0]!=digest(body):error=HTTPException(409,'Event ID reused with different contents')
            elif not old:
                if row['revision']!=body.revision:error=HTTPException(409,'Transport revision changed; refresh')
                elif c.execute('SELECT count(*) FROM transport_receipts WHERE call_id=?',(ident,)).fetchone()[0]>=128 and body.action not in ('finish','hangup'):
                    error=HTTPException(409,'Transport event limit reached; finish the call')
                else:
                    c.execute('SAVEPOINT transport_action')
                    try:
                        if caller:
                            if p['state']=='ended':raise HTTPException(409,'Call ended')
                            if body.action=='hangup':self._end(c,row,p,at,'caller_hangup')
                            else:self._turn(c,row,p,body,at)
                        elif body.action=='dispatch':self._dispatch(c,row,p,body,at)
                        elif body.action=='finish':
                            if p['state']=='ended':raise HTTPException(409,'Call ended')
                            self._end(c,row,p,at,'owner_finished')
                        elif body.action=='rotate_caller_token':
                            if p['state']=='ended':raise HTTPException(409,'Call ended')
                            new_token=secrets.token_urlsafe(32);c.execute('UPDATE transport_calls SET caller_digest=? WHERE id=?',(token_digest(new_token),ident))
                        else:self._decision(c,row,p,body,at)
                        c.execute('INSERT INTO transport_receipts VALUES(?,?,?,?)',(ident,channel,str(body.event_id),digest(body)))
                        row,p=self._save(c,row,p,at);self.audit(c,'transport.event',{'id':ident,'channel':channel,'action':body.action,'state':p['state']})
                    except HTTPException as exc:
                        c.execute('ROLLBACK TO transport_action');row,p=self._load(c,ident);error=exc;new_token=None
                    finally:c.execute('RELEASE transport_action')
            result=self._public(c,row,p,replay) if caller else self._owner(c,row,p,replay)
        if error:raise error
        return result if caller else {**result,'caller_token':new_token}


def mount(app,db,auth,audit,prefix='/api'):
    store=Transport(db,audit)
    if hasattr(app, 'state'):app.state.telephony_transport=store
    @app.post(prefix+'/telephony/transport/calls',dependencies=[Depends(auth)],status_code=201)
    def start(body:Start):return store.start(body)
    @app.get(prefix+'/telephony/transport/calls',dependencies=[Depends(auth)])
    def calls():return store.list()
    @app.get(prefix+'/telephony/transport/calls/{ident}',dependencies=[Depends(auth)])
    def owner(ident:uuid.UUID):return store.get(str(ident))
    @app.post(prefix+'/telephony/transport/calls/{ident}/events',dependencies=[Depends(auth)])
    def owner_event(ident:uuid.UUID,body:OwnerEvent):return store.event(str(ident),body)
    @app.delete(prefix+'/telephony/transport/calls/{ident}',dependencies=[Depends(auth)])
    def remove(ident:uuid.UUID):return store.delete(str(ident))
    @app.get(prefix+'/telephony/transport/caller/{ident}')
    def caller(ident:uuid.UUID,x_jarvis_call_token:str|None=Header(default=None)):
        return store.get(str(ident),x_jarvis_call_token,True)
    @app.post(prefix+'/telephony/transport/caller/{ident}/events')
    def caller_event(ident:uuid.UUID,body:CallerEvent,x_jarvis_call_token:str|None=Header(default=None)):
        return store.event(str(ident),body,True,x_jarvis_call_token)
    return store
