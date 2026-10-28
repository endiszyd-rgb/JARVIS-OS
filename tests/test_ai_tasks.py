"""Multi-stage read scenarios, authority boundaries and interruption lifecycle."""
import asyncio
import json
import sqlite3
import threading
import time
import uuid
import pytest
from fastapi import HTTPException
from jarvis.ai_tasks import TaskManager
from jarvis import llm_providers as providers
from test_tool_chat import client,answer,alias,transport,REQUEST,KEY,spy_gateway,install_openapi


def plan(**fields):return {'request_id':str(uuid.uuid4()),'steps':['Read status','Summarize verified results'],**{k:v for k,v in REQUEST.items() if k!='message'},**fields}

def start(c,body,headers=None):
    res=c.post('/api/v1/chat/tasks',json=body,**({'headers':headers} if headers else {}))
    assert res.status_code==202,res.text
    return res.json()

def wait(c,ident,expected,headers=None):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        r=c.get('/api/v1/chat/tasks/'+ident,**({'headers':headers} if headers else {}));assert r.status_code==200,r.text
        value=r.json()
        if value['status'] in ('completed','failed','cancelled'):
            assert value['status']==expected,value
            return value
        time.sleep(0.005)
    pytest.fail('AI task did not finish')


def test_real_gateway_multistep_protocol_context_and_idempotent_request(client,monkeypatch):
    body=plan(model='ollama');seen=transport(monkeypatch,lambda p,n:answer(p,[{'name':alias(p)}]) if n%2 else answer(p,text='Verified reply '+str(n)))
    executed=spy_gateway(client,monkeypatch)
    first=start(client,body);value=wait(client,first['id'],'completed')
    assert value['steps_completed']==2 and len(value['results'])==2 and len(executed)==2
    assert [r['provider_turns'] for r in value['results']]==[2,2]
    assert 'Verified reply 2' in json.dumps(seen[2]['messages'])
    assert seen[2]['messages'][1]['role']=='user' and 'untrusted_previous_step_results' in seen[2]['messages'][1]['content']
    assert start(client,body)['id']==first['id'] and len(seen)==4
    assert client.post('/api/chat/tasks',json={**body,'steps':['Changed plan']}).status_code==409
    audit=client.get('/api/audit').text
    assert 'ai_task.completed' in audit and 'Verified reply' not in audit and body['steps'][0] not in audit
    assert client.get('/api/chat/sessions').json()==[] and client.get('/api/proposals').json()==[]
    assert value['restart_resume'] is False and value['cancellation_undoes_reads'] is False


@pytest.mark.parametrize('phase',['model','discovery','read'])
def test_cancel_in_each_phase_stops_following_calls_and_releases_slots(client,monkeypatch,phase):
    entered=threading.Event();seen=[]
    async def block(*args,**kwargs):entered.set();await asyncio.Event().wait()
    if phase=='model':monkeypatch.setattr(providers,'post_json',block)
    else:
        seen=transport(monkeypatch,lambda p,n:answer(p,[{'name':alias(p)}]))
        monkeypatch.setattr(client.app.state.tool_gateway,'discover' if phase=='discovery' else 'execute',block)
    created=start(client,plan(model='ollama'))
    assert entered.wait(3)
    cancelled=client.post('/api/chat/tasks/'+created['id']+'/cancel');assert cancelled.status_code==202
    state=wait(client,created['id'],'cancelled')
    assert state['results']==[] and state['steps_completed']==0
    assert len(seen)==(1 if phase=='read' else 0)
    assert client.app.state.tool_loop._active==0
    again=client.post('/api/chat/tasks/'+created['id']+'/cancel');assert again.json()['status']=='cancelled'


def test_second_step_respects_total_cloud_budget_before_extra_provider_io(client,monkeypatch):
    monkeypatch.setenv('JARVIS_OPENAI_MAX_REQUEST_USD','0.7')
    sent=transport(monkeypatch,lambda p,n:answer(p,[{'name':alias(p)}]) if n==1 else answer(p))
    created=start(client,plan());state=wait(client,created['id'],'failed')
    assert len(sent)==2 and state['steps_completed']==1 and state['results']==[]
    assert state['error_status']==403


def test_disable_plugin_between_steps_blocks_new_transport(client,monkeypatch):
    def handler(p,n):
        if n==2:
            with sqlite3.connect(client.app.state.runtime_config.database_path) as db:db.execute("UPDATE plugins SET enabled=0 WHERE id='mqtt'")
        return answer(p,[{'name':alias(p)}]) if n==1 else answer(p)
    sent=transport(monkeypatch,handler)
    created=start(client,plan(model='ollama'));state=wait(client,created['id'],'failed')
    assert len(sent)==2 and state['steps_completed']==1 and state['error_status']==409


def test_foreign_owners_and_revoked_sessions_cannot_access_tasks(client,monkeypatch):
    password='Synthetic-task-owner-password-32chars'
    def account(name):
        row=client.post('/api/security/users',json={'username':name,'password':password,'role':'owner'});assert row.status_code==201
        login=client.post('/api/auth/login',json={'username':name,'password':password});return {'X-Jarvis-Key':login.json()['token']}
    a,b=account('task.alice'),account('task.bob')
    transport(monkeypatch,lambda p,n:answer(p))
    body=plan(model='ollama');created=start(client,body,a);wait(client,created['id'],'completed',a)
    assert client.get('/api/chat/tasks/'+created['id'],headers=b).status_code==404
    assert client.post('/api/chat/tasks/'+created['id']+'/cancel',headers=b).status_code==404
    assert start(client,body,b)['id']!=created['id']
    assert client.post('/api/auth/logout',headers=a).status_code==200
    assert client.get('/api/chat/tasks/'+created['id'],headers=a).status_code==401


@pytest.mark.parametrize('body',[
 plan(steps=[]),plan(steps=['x']*5),plan(steps=[' ']),plan(steps=['x'*8001]),
 plan(steps=['x'*8000]*3),plan(tool_ids=['mqtt.status']*2),plan(role='owner'),
 plan(steps=['\ud800']),plan(session_id=str(uuid.uuid4())),plan(message='Not a step'),plan(request_id='invalid')])
def test_invalid_task_plan_refused_without_provider_or_discovery(client,monkeypatch,body):
    sent=transport(monkeypatch,lambda *args:pytest.fail('No I/O'))
    assert client.post('/api/chat/tasks',content=json.dumps(body),headers={'Content-Type':'application/json'}).status_code==422
    assert sent==[]


def test_owner_and_feature_flags_are_required_before_start(client,monkeypatch):
    sent=transport(monkeypatch,lambda *args:pytest.fail('No I/O'))
    assert client.post('/api/chat/tasks',headers={'X-Jarvis-Key':'invalid'},json=plan()).status_code==401
    monkeypatch.setenv('JARVIS_TOOL_CHAT_ENABLED','false')
    assert client.post('/api/chat/tasks',json=plan()).status_code==403 and sent==[]


def test_registry_capacity_ttl_queued_cancel_timeout_and_shutdown(monkeypatch):
    from types import SimpleNamespace
    from jarvis import ai_tasks
    offset = [0.0]
    # Only the task registry clock is controlled; asyncio keeps its real clock.
    monkeypatch.setattr(ai_tasks, 'time', SimpleNamespace(
        time=time.time, monotonic=lambda: time.monotonic() + offset[0]))
    async def scenario():
        events=[];manager=TaskManager(max_active=1,max_records=2,ttl=60,timeout=0.02)
        async def block(*args):await asyncio.Event().wait()
        payload={'steps':['Step']}
        first=manager.submit('owner','req1',payload,block,lambda:None,lambda state,job:events.append(state))
        with pytest.raises(HTTPException) as full:manager.submit('owner','req2',payload,block,lambda:None)
        assert full.value.status_code==429
        assert (await manager.cancel('owner',first['id']))['status']=='cancelled'
        assert events==['created','cancelled']
        second=manager.submit('owner','req2',payload,block,lambda:None)
        await asyncio.wait_for(manager.jobs[second['id']].task, timeout=2)
        assert manager.get('owner',second['id'])['error_status']==504
        offset[0] += 61
        with pytest.raises(HTTPException) as expired:manager.get('owner',first['id'])
        assert expired.value.status_code == 404
        third=manager.submit('owner','req3',payload,block,lambda:None,lambda state,job:events.append(state))
        await manager.close()
        assert events[-1]=='cancelled'
        assert manager.jobs=={} and manager.closing
    asyncio.run(scenario())


def test_active_task_api_capacity_cancel_and_next_admission(client,monkeypatch):
    entered=threading.Event()
    async def block(*args,**kwargs):entered.set();await asyncio.Event().wait()
    monkeypatch.setattr(providers,'post_json',block)
    first=start(client,plan(model='ollama'));assert entered.wait(2)
    second=start(client,plan(model='ollama'))
    assert client.post('/api/chat/tasks',json=plan(model='ollama')).status_code==429
    for job in [first,second]:
        assert client.post('/api/chat/tasks/'+job['id']+'/cancel').status_code==202
        wait(client,job['id'],'cancelled')
    third=start(client,plan(model='ollama'))
    assert client.post('/api/chat/tasks/'+third['id']+'/cancel').status_code==202
    assert client.app.state.tool_loop._active==0


def test_revoked_owner_during_provider_response_prevents_next_read(client,monkeypatch):
    password='Synthetic-task-owner-password-32chars'
    account=client.post('/api/security/users',json={'username':'task.revoked','password':password,'role':'owner'}).json()
    login=client.post('/api/auth/login',json={'username':'task.revoked','password':password}).json()
    headers={'X-Jarvis-Key':login['token']}
    def handler(p,n):
        with sqlite3.connect(client.app.state.runtime_config.database_path) as db:db.execute('UPDATE identity_sessions SET revoked=1 WHERE user_id=?',(account['id'],))
        return answer(p,[{'name':alias(p)}])
    sent=transport(monkeypatch,handler);executed=spy_gateway(client,monkeypatch)
    job=start(client,plan(model='ollama'),headers)
    deadline=time.monotonic()+3
    while client.app.state.ai_tasks.jobs[job['id']].status not in ('failed','completed') and time.monotonic()<deadline:time.sleep(0.005)
    stored=client.app.state.ai_tasks.jobs[job['id']]
    assert stored.status=='failed' and stored.error_status==401 and stored.results==[]
    assert len(sent)==1 and executed==[]
    assert client.get('/api/chat/tasks/'+job['id'],headers=headers).status_code==401


@pytest.mark.parametrize('reason',['context_limit','result_limit','internal_error'])
def test_registry_bounds_results_and_hides_internal_failures(reason):
    async def scenario():
        manager=TaskManager();calls=[]
        async def runner(*args):
            calls.append(args)
            if reason=='internal_error':raise RuntimeError('SYNTHETIC INTERNAL SECRET')
            return {'reply':'x'*(16001 if reason=='context_limit' else 131073),'usage':{'reserved_cost_usd':None}}
        job=manager.submit('owner','req',{'steps':['First','Next']},runner,lambda:None)
        await manager.jobs[job['id']].task
        result=manager.get('owner',job['id'])
        assert result['status']=='failed' and result['results']==[] and len(calls)==1
        assert result['error_status']==(500 if reason=='internal_error' else 413)
        assert 'SYNTHETIC INTERNAL SECRET' not in json.dumps(result)
        await manager.close()
    asyncio.run(scenario())


def test_cancel_still_blocks_dispatch_when_provider_suppresses_cancellation(client,monkeypatch):
    entered=threading.Event();sent=[]
    async def stubborn(origin,path,payload,headers=None):
        sent.append(payload);entered.set()
        try:await asyncio.Event().wait()
        except asyncio.CancelledError:return answer(payload,[{'name':alias(payload)}])
    monkeypatch.setattr(providers,'post_json',stubborn);executed=spy_gateway(client,monkeypatch)
    job=start(client,plan(model='ollama'));assert entered.wait(2)
    assert client.post('/api/chat/tasks/'+job['id']+'/cancel').status_code==202
    assert wait(client,job['id'],'cancelled')['results']==[] and executed==[] and len(sent)==1
