"""Audited-schema read bridge over an explicitly prepared immutable snapshot.
No production connection, migrations, HTTP writes or arbitrary SQL are exposed.
"""
from contextlib import contextmanager, closing
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from fastapi import HTTPException
from .autologika import AUDITED_COMMIT

DOMAINS=('calendar','orders','vehicles','parts','customers','diagnostics','finances','reports','notifications')
TOTAL='COALESCE(o.final_price,COALESCE(o.labor_hours,0)*COALESCE(o.labor_rate,0)+COALESCE(o.parts_sale,0)+COALESCE(o.other_sale,0)+COALESCE(o.diagnosis_fee,0)-COALESCE(o.discount,0))'
COST='COALESCE(o.parts_cost,0)+COALESCE(o.other_cost,0)'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def build_snapshot(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if not source.is_file() or source==destination or not destination.name.endswith('.snapshot.sqlite3'):
        raise ValueError('Use an existing source and a different *.snapshot.sqlite3 destination')
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.snapshot-',suffix='.sqlite3',dir=destination.parent);os.close(fd)
    temp=Path(name);started=time.monotonic()
    try:
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=5)) as src:
            if src.execute('PRAGMA user_version').fetchone()[0]!=18:
                raise ValueError('Expected audited AutoLogika schema 18; audit another schema before importing')
            def progress(*args):
                if time.monotonic()-started>30:raise TimeoutError('Snapshot backup exceeded 30 seconds')
            with closing(sqlite3.connect(temp)) as dst:
                src.backup(dst,pages=128,progress=progress,sleep=.05)
                if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Snapshot integrity failed')
        manifest={'kind':'jarvis_autologika_snapshot','schema_version':18,'audited_commit':AUDITED_COMMIT,'created_at':datetime.now(timezone.utc).isoformat(),'sha256':digest(temp),'source_name':source.name}
        os.replace(temp,destination)
        manifest_temp=destination.with_suffix('.json.tmp')
        manifest_temp.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        os.replace(manifest_temp,destination.with_suffix('.json'))
        return manifest
    finally:temp.unlink(missing_ok=True)


class Snapshot:
    def __init__(self,path):
        self.path=Path(path)
        if not self.path.name.endswith('.snapshot.sqlite3') or not self.path.is_file():raise ValueError('Snapshot missing')
        self.manifest=json.loads(self.path.with_suffix('.json').read_text(encoding='utf-8'))
        if self.manifest.get('kind')!='jarvis_autologika_snapshot' or self.manifest.get('schema_version')!=18 or self.manifest.get('audited_commit')!=AUDITED_COMMIT:
            raise ValueError('Snapshot manifest does not match audited contract')
        if digest(self.path)!=self.manifest.get('sha256'):raise ValueError('Snapshot checksum mismatch')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True,timeout=3)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA query_only=ON')
        c.execute('PRAGMA trusted_schema=OFF')
        # Bound expensive queries on large snapshots; no caller can provide SQL.
        until=time.monotonic()+5
        c.set_progress_handler(lambda:1 if time.monotonic()>until else 0,1000)
        try:
            if c.execute('PRAGMA user_version').fetchone()[0]!=18:raise ValueError('Unexpected schema version')
            yield c
        finally:c.close()

    def columns(self,c,table):
        row=c.execute('SELECT type,sql FROM sqlite_master WHERE name=?',(table,)).fetchone()
        if not row or row['type']!='table' or 'VIRTUAL TABLE' in row['sql'].upper():raise ValueError('Expected regular audited table: '+table)
        return {r['name'] for r in c.execute('PRAGMA table_info("'+table+'")')}

    def require(self,c,table,columns):
        existing=self.columns(c,table)
        if not set(columns)<=existing:raise ValueError('Missing audited columns in '+table)
        return existing

    def active(self,c,table,alias=''):
        return (alias+'.' if alias else '')+'deleted_at IS NULL' if 'deleted_at' in self.columns(c,table) else '1=1'

    def read(self,domain,limit=50,offset=0,month=None):
        if domain not in DOMAINS or not 1<=limit<=200 or not 0<=offset<=100000:raise ValueError('Invalid domain or page')
        month=month or datetime.now().strftime('%Y-%m')
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month):raise ValueError('Invalid month')
        with self.connect() as c:
            self.require(c,'orders',['id','vehicle_id','title','status','opened_at','due_at','final_price','labor_hours','labor_rate','parts_sale','other_sale','diagnosis_fee','discount','parts_cost','other_cost','wait_state'])
            if domain in ('customers','vehicles','calendar'):
                table={'customers':'customers','vehicles':'vehicles','calendar':'appointments'}[domain]
                cols={'customers':'id,name,phone,email,company,created_at','vehicles':'id,customer_id,plate,vin,make,model,year,engine,mileage,created_at','calendar':'id,order_id,vehicle_id,title,start_at,end_at,bay,status'}[domain]
                self.require(c,table,cols.split(','))
                where=self.active(c,table)
                items=[dict(r) for r in c.execute(f'SELECT {cols} FROM {table} WHERE {where} ORDER BY id LIMIT ? OFFSET ?',(limit+1,offset))]
                data={'items':items[:limit],'has_more':len(items)>limit}
            elif domain=='orders':
                items=[dict(r) for r in c.execute(f'SELECT o.id,o.vehicle_id,o.title,o.status,o.wait_state,o.opened_at,o.due_at,ROUND({TOTAL},2) total,ROUND({COST},2) variable_cost FROM orders o WHERE {self.active(c,"orders","o")} ORDER BY o.id LIMIT ? OFFSET ?',(limit+1,offset))]
                data={'items':items[:limit],'has_more':len(items)>limit}
            elif domain=='parts':
                data={}
                collections={'job_part_orders':'id,order_id,part_no,name,qty,unit_cost,unit_price,status,expected_at','inventory_parts':'id,part_no,name,stock,min_stock,unit_cost,sell_price','repair_parts':'id,order_id,part_no,name,qty,reserved_qty,issued_qty,returned_qty,installed_qty,status'}
                for table,cols in collections.items():
                    self.require(c,table,cols.split(','))
                    rows=[dict(r) for r in c.execute(f'SELECT {cols} FROM {table} WHERE {self.active(c,table)} ORDER BY id LIMIT ? OFFSET ?',(limit+1,offset))]
                    data[table]={'items':rows[:limit],'has_more':len(rows)>limit}
            elif domain=='diagnostics':
                cols='id,order_id,symptom_confirmed,dtcs,measurements,hypothesis,conclusion,recommendation,time_hours,updated_at'
                self.require(c,'diagnostics',cols.split(','))
                fields=','.join('d.'+col for col in cols.split(','))
                rows=[dict(r) for r in c.execute(f'SELECT {fields} FROM diagnostics d JOIN orders o ON o.id=d.order_id WHERE {self.active(c,"diagnostics","d")} AND {self.active(c,"orders","o")} ORDER BY d.id LIMIT ? OFFSET ?',(limit+1,offset))]
                data={'items':rows[:limit],'has_more':len(rows)>limit}
            elif domain=='finances':
                self.require(c,'payments',['id','order_id','amount','paid_at'])
                active=self.active(c,'orders','o');pay_active=self.active(c,'payments','p')
                row=c.execute(f"SELECT COUNT(*) orders_count,ROUND(COALESCE(SUM({TOTAL}),0),2) orders_value,ROUND(COALESCE(SUM(({TOTAL})-({COST})),0),2) contribution,ROUND(COALESCE(SUM(MAX(0,({TOTAL})-COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.order_id=o.id AND {pay_active}),0))),0),2) receivables FROM orders o WHERE {active} AND strftime('%Y-%m',o.opened_at)=?",(month,)).fetchone()
                paid=c.execute(f"SELECT ROUND(COALESCE(SUM(p.amount),0),2) FROM payments p WHERE {pay_active} AND strftime('%Y-%m',p.paid_at)=?",(month,)).fetchone()[0]
                data=dict(row,month=month,paid_in_month=paid,currency='PLN',accounting_profit=False)
            elif domain=='reports':
                data={'status_counts':[dict(r) for r in c.execute(f'SELECT status,COUNT(*) count FROM orders WHERE {self.active(c,"orders")} GROUP BY status ORDER BY status')],'scope':'all non-deleted orders including released; not a full copy of dashboard/analytics'}
            else:
                data=self.notifications(c,limit,offset)
        return {'mode':'snapshot_readonly','domain':domain,'snapshot_created_at':self.manifest['created_at'],'sha256':self.manifest['sha256'],'audited_commit':AUDITED_COMMIT,'limit':limit,'offset':offset,'data':data,'limitations':'Offline snapshot; source data and domain rules may change after snapshot creation. No writes or live sync.'}

    def notifications(self,c,limit,offset):
        items=[];n=limit+offset+1
        def collect(kind,sql,params=()):
            for row in c.execute(sql+' LIMIT ?',(*params,n)):items.append(dict(row,kind=kind))
        self.require(c,'communications',['id','order_id','message','needs_reply','resolved','reply_due_at','created_at'])
        self.require(c,'job_part_orders',['id','order_id','name','expected_at','status'])
        self.require(c,'approvals',['id','order_id','status','created_at','decided_at'])
        self.require(c,'vehicle_findings',['id','vehicle_id','title','severity','status','due_date','due_mileage','created_at'])
        self.require(c,'vehicles',['id','mileage'])
        collect('WAIT',f"SELECT id order_id,title,wait_state text,opened_at created_at FROM orders WHERE {self.active(c,'orders')} AND status!='WYDANE' AND COALESCE(wait_state,'BRAK')!='BRAK' ORDER BY opened_at,id")
        collect('REPLY',f"SELECT id communication_id,order_id,message text,COALESCE(reply_due_at,created_at) created_at FROM communications WHERE {self.active(c,'communications')} AND needs_reply=1 AND resolved=0 AND (reply_due_at IS NULL OR datetime(reply_due_at)<=datetime('now')) ORDER BY COALESCE(reply_due_at,created_at),id")
        collect('PART_LATE',f"SELECT id part_id,order_id,name text,expected_at created_at FROM job_part_orders WHERE {self.active(c,'job_part_orders')} AND datetime(expected_at)<datetime('now') AND status NOT IN ('ODEBRANE','ZAMONTOWANE','ZWROT_ZAKONCZONY','ANULOWANE') ORDER BY expected_at,id")
        collect('APPROVAL',f"SELECT a.id approval_id,a.order_id,a.status text,COALESCE(a.decided_at,a.created_at) created_at FROM approvals a JOIN orders o ON o.id=a.order_id WHERE {self.active(c,'approvals','a')} AND {self.active(c,'orders','o')} AND a.status IN ('APPROVED','DECLINED') AND o.status='AKCEPTACJA' ORDER BY COALESCE(a.decided_at,a.created_at),a.id")
        collect('VEHICLE_FINDING',f"SELECT f.id finding_id,f.vehicle_id,f.title text,f.created_at FROM vehicle_findings f JOIN vehicles v ON v.id=f.vehicle_id WHERE {self.active(c,'vehicle_findings','f')} AND f.status!='RESOLVED' AND (f.severity IN ('CRITICAL','HIGH') OR date(f.due_date)<=date('now','+14 days') OR v.mileage>=f.due_mileage) ORDER BY f.created_at,f.id")
        items.sort(key=lambda r:(r.get('created_at') or '',r['kind'],json.dumps(r,sort_keys=True)))
        return {'items':items[offset:offset+limit],'has_more':len(items)>offset+limit,'derived_at':datetime.now(timezone.utc).isoformat(),'rules':'5 notification families derived from snapshot; time comparisons use SQLite UTC now'}


def configured_snapshot():
    if os.getenv('AUTOLOGIKA_SNAPSHOT_ENABLED','false').lower()!='true':raise HTTPException(503,'Snapshot integration disabled')
    try:return Snapshot(os.getenv('AUTOLOGIKA_SNAPSHOT_PATH','data/autologika/workshop.snapshot.sqlite3'))
    except (ValueError,OSError,KeyError):raise HTTPException(503,'Prepare a valid schema-18 snapshot and manifest first')
