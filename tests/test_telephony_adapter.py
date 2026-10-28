import uuid
import pytest
from pydantic import ValidationError
from jarvis.telephony_adapter import Ack,Command,LabAdapter


def command(channel='caller',kind='say',payload=None):
    return dict(id=str(uuid.uuid4()),call_id=str(uuid.uuid4()),channel=channel,kind=kind,payload=payload or {'text':'Wiadomość testowa'})


def offer():
    return {'attempt_id':str(uuid.uuid4()),'briefing':{'facts':{'issue':'PRIVATE BRIEFING'},'caller':'','reason':'crisis','recent_customer_messages':['Po naprawie nie działają hamulce.']}}


def test_lab_contract_acknowledges_data_without_network_or_calls():
    item=Command(**command())
    ack=LabAdapter().deliver(item)
    assert ack.command_id==item.id and ack.accepted is True
    assert ack.source=='lab' and ack.calls_placed is False
    assert item.payload=={'text':'Wiadomość testowa'}


@pytest.mark.parametrize('channel,kind,payload',[
    ('caller','offer',offer()),
    ('caller','bridge',{'attempt_id':str(uuid.uuid4()),'consent_event_id':str(uuid.uuid4())}),
    ('owner','say',{'text':'Hello'}),
    ('system','hold',{'text':'Hello'}),
    ('caller','say',{'text':'Hello','briefing':{'secret':'PRIVATE'}}),
    ('owner','offer',{**offer(),'execute':'open_gate'}),
    ('system','end',{'execute':'dial_number'}),
])
def test_commands_cannot_cross_private_public_channels_or_execute_fields(channel,kind,payload):
    with pytest.raises(ValidationError):Command(**command(channel,kind,payload))


def test_private_briefing_is_bounded_and_payload_is_canonical():
    item=Command(**command('owner','offer',offer()))
    assert item.payload['briefing']['facts']['issue']=='PRIVATE BRIEFING'
    assert item.payload['briefing']['facts']['name']==''
    assert isinstance(item.payload['attempt_id'],str)
    assert LabAdapter().deliver(item).calls_placed is False
    bad=offer();bad['briefing']['recent_customer_messages']=['x']*4
    with pytest.raises(ValidationError):Command(**command('owner','offer',bad))
    bad=offer();bad['briefing']['facts']['owner_number']='+48500111222'
    with pytest.raises(ValidationError):Command(**command('owner','offer',bad))
    with pytest.raises(ValidationError):Command(**{**command(),'id':'bad'})
    with pytest.raises(ValidationError):Ack(command_id=uuid.uuid4(),calls_placed=True)
