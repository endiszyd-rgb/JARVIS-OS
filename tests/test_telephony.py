from datetime import datetime
import sqlite3
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from jarvis.main import create_app
from jarvis.telephony import Policy,evaluate

KEY='telephony-owner-key-32-characters-long'

def configured(**kwargs):
    data={'enabled':True,'owner_number':'+48500111222','workshop_number':'+48500333444',
          'weekly':[{'weekday':i,'windows':[{'start':'08:00','end':'18:00'}]} for i in range(5)]}
    data.update(kwargs);return Policy(**data)

def decision(policy,at,situation='crisis'):return evaluate(policy,datetime.fromisoformat(at),situation)

@pytest.fixture
def client(tmp_path):
    c=TestClient(create_app(tmp_path/'core.db',KEY),headers={'X-Jarvis-Key':KEY});c.path=tmp_path/'core.db';return c

def test_schedule_edges_and_escalation():
    p=configured()
    assert decision(p,'2026-10-28T07:59:59+01:00')['eligible_for_owner_contact'] is False
    for situation in ['crisis','insistent']:
        result=decision(p,'2026-10-28T08:00:00+01:00',situation)
        assert result['eligible_for_owner_contact'] and result['action']=='request_owner_acceptance'
        assert result['executed'] is False and result['carrier_connected'] is False
    for situation in ['routine','contact_requested']:
        assert decision(p,'2026-10-28T12:00:00+01:00',situation)['action']=='continue_reception'
    assert 'outside_hours' in decision(p,'2026-10-28T18:00:00+01:00')['reasons']
    assert 'outside_hours' in decision(p,'2026-10-31T12:00:00+01:00')['reasons']

def test_breaks_and_end_of_day():
    p=configured(weekly=[{'weekday':2,'windows':[{'start':'08:00','end':'12:00'},{'start':'13:00','end':'24:00'}]}])
    assert 'outside_hours' in decision(p,'2026-10-28T12:30:00+01:00')['reasons']
    assert decision(p,'2026-10-28T23:59:59+01:00')['eligible_for_owner_contact']
    assert 'outside_hours' in decision(p,'2026-10-29T00:00:00+01:00')['reasons']

def test_dst_uses_warsaw_not_machine_zone():
    p=configured(weekly=[{'weekday':6,'windows':[{'start':'02:00','end':'03:00'}]}])
    first=decision(p,'2026-10-25T00:30:00+00:00');second=decision(p,'2026-10-25T01:30:00+00:00')
    assert first['eligible_for_owner_contact'] and second['eligible_for_owner_contact']
    assert first['local_time'].endswith('+02:00') and second['local_time'].endswith('+01:00')
    assert 'outside_hours' in decision(p,'2026-03-29T01:30:00+00:00')['reasons']

def test_holidays_vacation_dnd_and_expiry():
    p=configured(exceptions=[{'start':'2026-10-28','end':'2026-10-30','label':'Urlop'}])
    assert 'date_exception' in decision(p,'2026-10-30T10:00:00+01:00')['reasons']
    p=configured(dnd=True)
    assert 'do_not_disturb' in decision(p,'2026-10-28T10:00:00+01:00')['reasons']
    p=configured(dnd_until='2026-10-28T10:00:00+01:00')
    assert 'do_not_disturb' in decision(p,'2026-10-28T08:59:59+00:00')['reasons']
    assert decision(p,'2026-10-28T09:00:00+00:00')['eligible_for_owner_contact']

@pytest.mark.parametrize('values',[
 {'owner_number':'+48500333444'}, {'owner_number':'500111222'}, {'timezone':'UTC'},
 {'weekly':[{'weekday':0,'windows':[{'start':'18:00','end':'08:00'}]}]},
 {'weekly':[{'weekday':0,'windows':[{'start':'08:00','end':'12:00'},{'start':'11:00','end':'13:00'}]}]},
 {'weekly':[{'weekday':0},{'weekday':0}]},{'weekly':[]}, {'dnd_until':'2026-10-28T12:00:00'},
 {'exceptions':[{'start':'2026-12-25','end':'2026-12-24'}]}
])
def test_invalid_configuration(values):
    with pytest.raises(ValidationError):configured(**values)

def test_api_persistence_revision_preview_and_audit_privacy(client):
    initial=client.get('/api/telephony/settings').json()
    assert initial['revision']==0 and initial['policy']['enabled'] is False
    saved=client.put('/api/telephony/settings',json={'revision':0,'policy':configured().model_dump(mode='json')})
    assert saved.status_code==200
    assert client.put('/api/telephony/settings',json={'revision':0,'policy':{}}).status_code==409
    restarted=TestClient(create_app(client.path,KEY),headers={'X-Jarvis-Key':KEY})
    assert restarted.get('/api/telephony/settings').json()['policy']['owner_number']=='+48500111222'
    r=client.post('/api/telephony/preview',json={'at':'2026-10-28T12:00:00+01:00','situation':'insistent'})
    assert r.status_code==200 and r.json()['eligible_for_owner_contact']
    assert r.json()['notifications_sent'] is False
    with sqlite3.connect(client.path) as c:
        assert '+48500111222' not in str(c.execute("SELECT detail FROM audit WHERE event='telephony.policy_updated'").fetchall())
        assert c.execute('PRAGMA user_version').fetchone()[0]==12

@pytest.mark.parametrize('body',[{'at':'2026-10-28T12:00:00'},{'situation':'urgent'},{'at':'bad'}])
def test_preview_validation(client,body):
    assert client.post('/api/telephony/preview',json=body).status_code==422

def test_no_owner_authority_from_service_token(client):
    token=client.post('/api/security/tokens',json={'name':'reader','scopes':['status:read']}).json()['token']
    headers={'X-Jarvis-Key':token}
    assert client.get('/api/telephony/settings',headers=headers).status_code==403
    assert client.put('/api/telephony/settings',json={'revision':0,'policy':{}},headers=headers).status_code==403
    assert client.post('/api/telephony/preview',json={},headers=headers).status_code==403
    assert client.get('/api/telephony/settings',headers={'X-Jarvis-Key':'wrong'}).status_code==401

def test_upgrade_from_v05_preserves_policy_and_pre_migration_backup(tmp_path):
    path=tmp_path/'old.db'
    create_app(path,KEY)
    with sqlite3.connect(path) as db:
        db.execute('DROP TABLE telephony_policy')
        db.execute("INSERT INTO memory VALUES('old','existing note',0)")
        db.execute('PRAGMA user_version=5')
    c=TestClient(create_app(path,KEY),headers={'X-Jarvis-Key':KEY})
    assert c.get('/api/memory').json()[0]['text']=='existing note'
    assert c.get('/api/telephony/settings').json()['revision']==0
    copies=list((tmp_path/'backups').glob('before-schema12-*'))
    assert len(copies)==1
    with sqlite3.connect(copies[0]) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==5
        assert db.execute('SELECT text FROM memory').fetchone()[0]=='existing note'
