"""Bounded, account-private, process-local read tasks; no restart replay.

The trusted caller provides the runner. Neither the model nor task input can
supply callbacks, executable code, permissions, persistence or a schedule.
"""
import asyncio
from dataclasses import dataclass,field
from decimal import Decimal
import hashlib
import json
import time
import uuid
from fastapi import HTTPException

TERMINAL={'completed','failed','cancelled'}

@dataclass(repr=False)
class Job:
    id:str
    owner:str
    request_id:str
    fingerprint:str
    total:int
    created_at:float=field(default_factory=time.time)
    status:str='queued'
    completed_steps:int=0
    phase:dict=field(default_factory=dict)
    results:list=field(default_factory=list,repr=False)
    error_status:int|None=None
    expires:float|None=None
    task:asyncio.Task|None=field(default=None,repr=False)
    cancel_requested:bool=False
    event:object=field(default=None,repr=False)

class TaskManager:
    def __init__(self,*,max_active=2,max_records=32,ttl=900,timeout=180):
        self.max_active=max_active;self.max_records=max_records;self.ttl=ttl;self.timeout=timeout
        self.jobs={};self.closing=False

    def _prune(self):
        now=time.monotonic()
        for ident,job in list(self.jobs.items()):
            if job.expires is not None and job.expires<=now:
                job.results.clear();del self.jobs[ident]

    def _get(self,owner,ident):
        self._prune();job=self.jobs.get(str(ident))
        if job is None or job.owner!=owner:raise HTTPException(404,'AI task missing or expired')
        return job

    @staticmethod
    def public(job):
        return {'id':job.id,'request_id':job.request_id,'status':job.status,'steps_total':job.total,
                'steps_completed':job.completed_steps,'progress':dict(job.phase),'results':list(job.results),
                'error_status':job.error_status,'created_at':job.created_at,
                'retention_seconds':max(0,int(job.expires-time.monotonic())) if job.expires is not None else None,
                'storage':'process_memory','restart_resume':False,'cancellation_undoes_reads':False}

    def get(self,owner,ident):return self.public(self._get(owner,ident))

    def submit(self,owner,request_id,payload,runner,authorize,event=lambda *args:None):
        self._prune()
        encoded=json.dumps(payload,sort_keys=True,ensure_ascii=False,allow_nan=False)
        fingerprint=hashlib.sha256(encoded.encode()).hexdigest();request_id=str(request_id)
        for job in self.jobs.values():
            if job.owner==owner and job.request_id==request_id:
                if job.fingerprint!=fingerprint:raise HTTPException(409,'Task request_id was used for a different plan')
                return self.public(job)
        if self.closing:raise HTTPException(503,'AI tasks are shutting down')
        if len(self.jobs)>=self.max_records or sum(j.status not in TERMINAL for j in self.jobs.values())>=self.max_active:
            raise HTTPException(429,'AI task capacity reached')
        job=Job(str(uuid.uuid4()),owner,request_id,fingerprint,len(payload['steps']),event=event)
        event('created',job)
        self.jobs[job.id]=job
        job.task=asyncio.create_task(self._run(job,payload,runner,authorize,event),name='jarvis-read-task')
        # Consume unexpected exceptions too; no task input/output in logs.
        job.task.add_done_callback(lambda task:None if task.cancelled() else task.exception())
        return self.public(job)

    async def _run(self,job,payload,runner,authorize,event):
        reserved='0'
        def progress(value):
            if job.cancel_requested:raise asyncio.CancelledError()
            authorize()
            if value:job.phase={key:value[key] for key in ('phase','provider_turns','tool_calls') if key in value}
        try:
            if job.cancel_requested:raise asyncio.CancelledError()
            job.status='running'
            async with asyncio.timeout(self.timeout):
                for index,message in enumerate(payload['steps']):
                    authorize();progress({'phase':'step_started','provider_turns':0,'tool_calls':0})
                    previous=[{'step':i+1,'reply':item['reply']} for i,item in enumerate(job.results)]
                    context=json.dumps({'untrusted_previous_step_results':previous},ensure_ascii=False)
                    if len(context.encode('utf-8'))>16000:raise HTTPException(413,'Prior task context limit exceeded')
                    result=await runner(message,context if previous else None,reserved,progress)
                    authorize()
                    if job.cancel_requested:raise asyncio.CancelledError()
                    total=json.dumps(job.results+[result],ensure_ascii=False,allow_nan=False)
                    if len(total.encode('utf-8'))>131072:raise HTTPException(413,'Task result size limit exceeded')
                    reserved=result['usage']['reserved_cost_usd'] or '0'
                    if not Decimal(reserved).is_finite():raise ValueError('Invalid internal reservation')
                    job.results.append(result);job.completed_steps=index+1
                authorize();job.status='completed';job.phase={'phase':'completed'}
        except asyncio.CancelledError:
            job.status='cancelled';job.results.clear();job.phase={'phase':'cancelled'}
        except Exception as exc:
            job.status='failed';job.results.clear();job.phase={'phase':'failed'}
            job.error_status=exc.status_code if isinstance(exc,HTTPException) else 504 if isinstance(exc,TimeoutError) else 500
        finally:self._terminal(job)

    def _terminal(self,job):
        job.expires=time.monotonic()+self.ttl;job.task=None
        try:
            if job.event is not None:job.event(job.status,job)
        except Exception:
            job.status='failed';job.phase={'phase':'failed'};job.results.clear();job.error_status=503
        finally:job.event=None

    async def cancel(self,owner,ident):
        job=self._get(owner,ident)
        if job.status in TERMINAL:
            # Acknowledge already-finished work honestly; no replay or rollback.
            return self.public(job)
        job.cancel_requested=True;job.status='cancelling';job.results.clear()
        task=job.task
        if task is not None:
            task.cancel()
            try:await asyncio.wait_for(asyncio.shield(task),timeout=2)
            except (TimeoutError,asyncio.CancelledError):pass
        # A task cancelled before its coroutine first ran never executes finally.
        if task is not None and task.done() and job.status=='cancelling':
            job.status='cancelled';job.phase={'phase':'cancelled'};self._terminal(job)
        return self.public(job)

    async def close(self):
        self.closing=True
        pending=[j.task for j in self.jobs.values() if j.task is not None]
        for job in self.jobs.values():job.cancel_requested=True;job.results.clear()
        for task in pending:task.cancel()
        if pending:
            try:await asyncio.wait_for(asyncio.gather(*pending,return_exceptions=True),timeout=5)
            except TimeoutError:pass
        for job in self.jobs.values():
            if job.status not in TERMINAL:
                job.status="cancelled";job.phase={"phase":"cancelled"};self._terminal(job)
        self.jobs.clear()
