"""Owner-configured call escalation policy. Preview only: no carrier or dial actions."""
from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator

WARSAW=ZoneInfo('Europe/Warsaw')
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Window(Strict):
    start:str=Field(pattern=r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$')
    end:str=Field(pattern=r'^(?:(?:[01][0-9]|2[0-3]):[0-5][0-9]|24:00)$')
    @model_validator(mode='after')
    def ordered(self):
        if self.start>=self.end:raise ValueError('Start must precede end; split overnight hours into separate days')
        return self

class Day(Strict):
    weekday:int=Field(ge=0,le=6)
    windows:list[Window]=Field(default_factory=list,max_length=8)
    @field_validator('windows')
    @classmethod
    def non_overlapping(cls,windows):
        ordered=sorted(windows,key=lambda w:w.start)
        if any(a.end>b.start for a,b in zip(ordered,ordered[1:])):raise ValueError('Hours must not overlap')
        return ordered

class ExceptionDays(Strict):
    start:date
    end:date
    label:str=Field(default='',max_length=100)
    @model_validator(mode='after')
    def ordered(self):
        if self.end<self.start:raise ValueError('Vacation end precedes start')
        return self

class Policy(Strict):
    enabled:bool=False
    owner_number:str=Field(default='',pattern=r'^(?:|\+[1-9][0-9]{6,14})$')
    workshop_number:str=Field(default='',pattern=r'^(?:|\+[1-9][0-9]{6,14})$')
    timezone:Literal['Europe/Warsaw']='Europe/Warsaw'
    weekly:list[Day]=Field(default_factory=list,max_length=7)
    exceptions:list[ExceptionDays]=Field(default_factory=list,max_length=100)
    dnd:bool=False
    dnd_until:datetime|None=None
    outside_hours:Literal['log_and_notify']='log_and_notify'
    no_answer:Literal['callback_request']='callback_request'
    @field_validator('dnd_until')
    @classmethod
    def aware(cls,value):
        if value is not None and value.utcoffset() is None:raise ValueError('DND expiry requires timezone offset')
        return value
    @model_validator(mode='after')
    def consistent(self):
        if len({day.weekday for day in self.weekly})!=len(self.weekly):raise ValueError('Duplicate weekday')
        if self.owner_number and self.owner_number==self.workshop_number:raise ValueError('Owner and forwarded workshop number must differ')
        if self.enabled and (not self.owner_number or not self.workshop_number or not any(day.windows for day in self.weekly)):
            raise ValueError('Enable only after setting both numbers and at least one window')
        return self

class Save(Strict):
    revision:int=Field(ge=0)
    policy:Policy

class Preview(Strict):
    at:datetime|None=None
    situation:Literal['routine','contact_requested','insistent','crisis']='routine'
    @field_validator('at')
    @classmethod
    def aware(cls,value):
        if value is not None and value.utcoffset() is None:raise ValueError('Preview needs an explicit timezone offset')
        return value


def evaluate(policy:Policy,at:datetime,situation:str):
    if at.utcoffset() is None:raise ValueError('Aware time required')
    local=at.astimezone(WARSAW)
    clock=local.strftime('%H:%M')
    reasons=[]
    if not policy.enabled:reasons.append('disabled')
    if policy.dnd or (policy.dnd_until is not None and at<policy.dnd_until):reasons.append('do_not_disturb')
    if any(e.start<=local.date()<=e.end for e in policy.exceptions):reasons.append('date_exception')
    if not any(d.weekday==local.weekday() and any(w.start<=clock<w.end for w in d.windows) for d in policy.weekly):reasons.append('outside_hours')
    if situation not in ('insistent','crisis'):reasons.append('escalation_not_justified')
    permitted=not reasons
    return {'preview_only':True,'executed':False,'local_time':local.isoformat(),'situation':situation,
            'eligible_for_owner_contact':permitted,'action':'request_owner_acceptance' if permitted else 'log_and_notify' if situation in ('crisis','insistent') else 'continue_reception',
            'reasons':reasons or ['escalation_within_hours'],'owner_must_accept':True,
            'emergency_services_notice':situation=='crisis','fallback':'callback_request',
            'notifications_sent':False,'carrier_connected':False}
