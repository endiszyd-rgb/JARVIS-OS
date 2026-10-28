"""Text-only laboratory for a receptionist. No carrier, LLM tools or AutoLogika writes."""
from datetime import datetime,timezone
import hashlib
import json
import time
import unicodedata
import uuid
from typing import Literal
from fastapi import HTTPException
from pydantic import Field,field_validator
from .telephony import Strict,Policy,evaluate

GREETING='Dzień dobry, tu wirtualny asystent warsztatu AutoLogika. W czym mogę pomóc?'

class Facts(Strict):
    name:str=Field(default='',max_length=120)
    phone:str=Field(default='',pattern=r'^(?:|\+[1-9][0-9]{6,14})$')
    vehicle:str=Field(default='',max_length=200)
    issue:str=Field(default='',max_length=2000)
    preferred_time:str=Field(default='',max_length=200)

class Start(Strict):
    caller:str=Field(default='',pattern=r'^(?:|\+[1-9][0-9]{6,14})$')

class Event(Strict):
    at:datetime|None=None
    @field_validator('at')
    @classmethod
    def aware(cls,value):
        if value is not None and value.utcoffset() is None:raise ValueError('Explicit timezone offset required')
        return value

    event_id:uuid.UUID
    revision:int=Field(ge=0)
    action:Literal['turn','finish','owner_accept','owner_decline','owner_no_answer']
    text:str=Field(default='',max_length=4000)
    facts:Facts|None=None
    # Optional explicit test scenario; never provided by an untrusted phone caller.
    scenario:Literal['routine','contact_requested','insistent','crisis']|None=None


def install(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS reception_calls(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS reception_events(call_id TEXT NOT NULL REFERENCES reception_calls(id) ON DELETE CASCADE,event_id TEXT NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(call_id,event_id));
    CREATE TABLE IF NOT EXISTS reception_cases(id TEXT PRIMARY KEY,call_id TEXT UNIQUE NOT NULL REFERENCES reception_calls(id) ON DELETE CASCADE,payload TEXT NOT NULL,updated REAL NOT NULL);
    ''')


def normalized(text):return ''.join(ch for ch in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(ch)).replace('ł','l')


def classify(text,requests):
    """Conservative lab cues only, not a production conversational classifier."""
    value=normalized(text)
    emergency=any(s in value for s in ['nie dzialaja hamulce','wyciek paliwa','pali sie samochod','pozar samochodu'])
    request=any(s in value for s in ['wlasciciel','andreas','z szefem','z mechanikiem'])
    if emergency:return 'crisis','keyword_lab',requests
    if request:return ('insistent' if requests else 'contact_requested'),'keyword_lab',requests+1
    return 'routine','keyword_lab',requests


def render(row,replay=False):
    return {'id':row['id'],'revision':row['revision'],**json.loads(row['payload']),
            'mode':'reception_lab','carrier_connected':False,'calls_placed':False,'notifications_sent':False,'replayed':replay}


class Reception:
    def __init__(self,db,audit):self.db=db;self.audit=audit

    def start(self,body):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            return self.start_in_transaction(c,body)

    def start_in_transaction(self,c,body):
        """Create a lab call inside the transport's existing write transaction."""
        if not c.in_transaction:raise ValueError('Reception helper requires an active transaction')
        ident=str(uuid.uuid4());now=time.time()
        payload={'state':'reception','caller':body.caller,'facts':Facts().model_dump(),'owner_requests':0,'situation':'routine',
                 'messages':[{'role':'assistant','text':GREETING}], 'decision':None,'case_id':None,'owner_briefing':None,'owner_outcome':None}
        c.execute('INSERT INTO reception_calls VALUES(?,0,?,?,?)',(ident,json.dumps(payload,ensure_ascii=False),now,now))
        self.audit(c,'reception.lab_started',{'id':ident})
        return render(c.execute('SELECT * FROM reception_calls WHERE id=?',(ident,)).fetchone())

    def get(self,ident):
        with self.db() as c:row=c.execute('SELECT * FROM reception_calls WHERE id=?',(ident,)).fetchone()
        if row is None:raise HTTPException(404,'Lab call missing')
        return render(row)

    def list(self):
        with self.db() as c:rows=c.execute('SELECT * FROM reception_calls ORDER BY updated DESC,id LIMIT 50').fetchall()
        return [{'id':r['id'],'revision':r['revision'],'state':json.loads(r['payload'])['state'],'updated':r['updated'],'mode':'reception_lab'} for r in rows]

    def cases(self):
        with self.db() as c:rows=c.execute('SELECT * FROM reception_cases ORDER BY updated DESC,id LIMIT 100').fetchall()
        return [{'id':r['id'],'call_id':r['call_id'],**json.loads(r['payload']),'updated':r['updated'],'mode':'reception_lab'} for r in rows]

    def delete(self,ident):
        with self.db() as c:
            if not c.execute('DELETE FROM reception_calls WHERE id=?',(ident,)).rowcount:raise HTTPException(404,'Lab call missing')
            self.audit(c,'reception.lab_deleted',{'id':ident})
        return {'deleted':ident,'related_cases_deleted':True}

    def case(self,c,ident,p):
        p['case_id']=p['case_id'] or str(uuid.uuid4())
        text={'facts':p['facts'],'caller':p['caller'],'priority':'urgent' if p['situation'] in ('crisis','insistent') else 'normal',
              'situation':p['situation'],'status':'follow_up','owner_outcome':p['owner_outcome'],
              'notes':[m['text'] for m in p['messages'] if m['role']=='customer'][-10:],
              'auto_booking':False,'autologika_written':False}
        c.execute('INSERT INTO reception_cases VALUES(?,?,?,?) ON CONFLICT(call_id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',
                  (p['case_id'],ident,json.dumps(text,ensure_ascii=False),time.time()))

    def preflight(self,ident,body):
        digest=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        with self.db() as c:
            row=c.execute('SELECT * FROM reception_calls WHERE id=?',(ident,)).fetchone()
            if row is None:raise HTTPException(404,'Lab call missing')
            old=c.execute('SELECT digest FROM reception_events WHERE call_id=? AND event_id=?',(ident,str(body.event_id))).fetchone()
        if old:
            if old[0]!=digest:raise HTTPException(409,'Event ID reused with different contents')
            return render(row,replay=True)
        if row['revision']!=body.revision:raise HTTPException(409,'Lab call changed; reload')
        if json.loads(row['payload'])['state']!='reception':raise HTTPException(409,'Lab call is not accepting customer turns')
        if row['revision']>=60:raise HTTPException(409,'Lab event limit reached')
        return None

    def apply(self,ident,body,analysis=None):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            return self.apply_in_transaction(c,ident,body,analysis)

    def apply_in_transaction(self,c,ident,body,analysis=None):
        """Update call, receipt, case and audit without owning the outer commit."""
        if not c.in_transaction:raise ValueError('Reception helper requires an active transaction')
        digest=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        row=c.execute('SELECT * FROM reception_calls WHERE id=?',(ident,)).fetchone()
        if row is None:raise HTTPException(404,'Lab call missing')
        old=c.execute('SELECT digest FROM reception_events WHERE call_id=? AND event_id=?',(ident,str(body.event_id))).fetchone()
        if old:
            if old[0]!=digest:raise HTTPException(409,'Event ID reused with different contents')
            return render(row,replay=True)
        if row['revision']!=body.revision:raise HTTPException(409,'Lab call changed; reload')
        p=json.loads(row['payload'])
        if p['state']=='ended':raise HTTPException(409,'Lab call already ended')
        if row['revision']>=60 and body.action!='finish':raise HTTPException(409,'Lab event limit reached; finish or delete call')
        pol=c.execute('SELECT revision,value FROM telephony_policy WHERE id=1').fetchone()
        policy=Policy.model_validate_json(pol['value']);at=body.at or datetime.now(timezone.utc)
        if body.action=='turn':
            if p['state']!='reception':raise HTTPException(409,'Resolve owner decision before another customer turn')
            if not body.text.strip():raise HTTPException(422,'Customer text required')
            if body.facts is not None:p['facts']=body.facts.model_dump()
            p['messages'].append({'role':'customer','text':body.text})
            kind,source,count=classify(body.text,p['owner_requests'])
            if analysis is not None:
                p['analysis']=analysis
                kind=analysis['effective_kind'];source=analysis['source'];count=p['owner_requests']
                # Require an earlier request before treating insistence as a repeat.
                if kind=='insistent' and not p['owner_requests']:
                    kind='contact_requested';p['analysis']['first_request_gate']=True
                if kind in ('contact_requested','insistent'):count+=1
                p['facts'].update(analysis['extracted'])
                if kind=='unclear':kind='routine'
            if body.scenario is not None:kind=body.scenario;source='explicit_lab_scenario'
            p['owner_requests']=count
            # Keep urgency through later turns: a polite follow-up must not erase a crisis.
            ranks={'routine':0,'contact_requested':1,'insistent':2,'crisis':3}
            if ranks[kind]>ranks[p['situation']]:p['situation']=kind
            decision=evaluate(policy,at,p['situation']);decision['policy_revision']=pol['revision'];decision['classification_source']=source
            if p['owner_outcome'] is not None:
                decision['eligible_for_owner_contact']=False
                decision['action']='log_and_notify'
                decision['reasons'].append('owner_attempt_completed')
            p['decision']=decision
            if decision['eligible_for_owner_contact']:
                p['state']='owner_pending'
                p['owner_briefing']={'facts':p['facts'],'caller':p['caller'],'reason':p['situation'],'recent_customer_messages':[m['text'] for m in p['messages'] if m['role']=='customer'][-3:]}
                response='Sprawa wymaga kontaktu z właścicielem. W tym laboratorium czekamy na jego decyzję; nie wykonuję połączenia.'
            elif p['situation'] in ('insistent','crisis'):
                self.case(c,ident,p)
                response='Właściciel jest teraz niedostępny według ustalonych zasad. Zapisuję pilną prośbę o kontakt, bez obietnicy godziny oddzwonienia.'
            elif analysis is not None and analysis['needs_clarification']:response='Proszę doprecyzować, co się wydarzyło i jakiej pomocy Pan/Pani potrzebuje. Nie potwierdzam jeszcze pilności ani terminu.'
            elif kind=='contact_requested':response='Proszę krótko powiedzieć, czego dotyczy sprawa. Spróbuję pomóc lub zapisać prośbę o kontakt.'
            else:response='Proszę podać samochód, objawy, preferowany termin i kontakt. Przygotuję zgłoszenie do sprawdzenia, bez potwierdzania ceny ani rezerwacji.'
            if p['situation']=='crisis':response+=' Przy bezpośrednim zagrożeniu życia potrzebna jest pomoc służb ratunkowych; kontakt z warsztatem jej nie zastępuje.'
            p['messages'].append({'role':'assistant','text':response})
        elif body.action=='finish':
            p['state']='ended';self.case(c,ident,p)
            p['messages'].append({'role':'assistant','text':'Zakończono test. Zgłoszenie pozostaje w laboratorium recepcji, bez zapisu do AutoLogiki.'})
        else:
            if p['state']!='owner_pending':raise HTTPException(409,'No pending owner contact')
            # Re-evaluate immediately before accepting; changed policy or elapsed hours prevail.
            decision=evaluate(policy,at,p['situation']);decision['policy_revision']=pol['revision'];p['decision']=decision
            if body.action=='owner_accept' and decision['eligible_for_owner_contact']:
                p['state']='connected_lab';p['owner_outcome']='accepted_in_lab'
                message='Właściciel przyjął rozmowę w symulacji. Nie zestawiono rzeczywistego połączenia.'
            else:
                p['state']='reception';p['owner_outcome']='blocked_by_current_policy' if not decision['eligible_for_owner_contact'] else body.action
                message='Nie udało się przekazać rozmowy. Zapisuję pilną prośbę o oddzwonienie.'
            self.case(c,ident,p);p['messages'].append({'role':'assistant','text':message})
        c.execute('UPDATE reception_calls SET revision=revision+1,payload=?,updated=? WHERE id=?',(json.dumps(p,ensure_ascii=False),time.time(),ident))
        c.execute('INSERT INTO reception_events VALUES(?,?,?)',(ident,str(body.event_id),digest))
        self.audit(c,'reception.lab_event',{'id':ident,'action':body.action,'state':p['state']})
        row=c.execute('SELECT * FROM reception_calls WHERE id=?',(ident,)).fetchone()
        return render(row)
