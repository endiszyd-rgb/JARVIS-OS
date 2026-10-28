"""Typed laboratory delivery contract. No network, dialling or carrier support."""
from typing import Literal, Protocol
import uuid
from pydantic import Field, model_validator
from .telephony import Strict
from .reception import Facts

class Briefing(Strict):
    facts: Facts
    caller: str = Field(default='',pattern=r'^(?:|\+[1-9][0-9]{6,14})$')
    reason: Literal['insistent','crisis']
    recent_customer_messages: list[str] = Field(max_length=3)
    @model_validator(mode='after')
    def bounded(self):
        if any(len(text)>4000 for text in self.recent_customer_messages):raise ValueError('Briefing is too long')
        return self

class PublicText(Strict):
    text: str = Field(min_length=1,max_length=4000)
class Offer(Strict):
    attempt_id: uuid.UUID
    briefing: Briefing
class Cancel(Strict):
    attempt_id: uuid.UUID
    reason: str = Field(min_length=1,max_length=80)
class Bridge(Strict):
    attempt_id: uuid.UUID
    consent_event_id: uuid.UUID
class Empty(Strict):pass

class Command(Strict):
    id: uuid.UUID
    call_id: uuid.UUID
    channel: Literal['caller','owner','system']
    kind: Literal['say','hold','offer','cancel','bridge','end']
    payload: dict
    @model_validator(mode='after')
    def safe_channel(self):
        schemas={('caller','say'):PublicText,('caller','hold'):PublicText,('caller','end'):PublicText,
                 ('owner','offer'):Offer,('owner','cancel'):Cancel,('system','bridge'):Bridge,('system','end'):Empty}
        schema=schemas.get((self.channel,self.kind))
        if schema is None:raise ValueError('Command is not allowed on this channel')
        self.payload=schema.model_validate(self.payload).model_dump(mode='json')
        return self

class Ack(Strict):
    command_id: uuid.UUID
    source: Literal['lab']='lab'
    accepted: bool=True
    calls_placed: Literal[False]=False

class Adapter(Protocol):
    def deliver(self,command:Command)->Ack: ...

class LabAdapter:
    """Pure acknowledgement; durable idempotency and journals belong to SQLite."""
    def deliver(self,command:Command)->Ack:
        command=Command.model_validate(command.model_dump())
        return Ack(command_id=command.id)
