import json
from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient
from examples.workshop_fixture import create_fixture
from jarvis.main import create_app
from jarvis.workshop import build_snapshot,Snapshot,DOMAINS,digest

KEY='workshop-test-key-32-characters-long'

@pytest.fixture
def setup(tmp_path,monkeypatch):
    source=create_fixture(tmp_path/'source.db')
    dest=tmp_path/'workshop.snapshot.sqlite3'
    before=digest(source)
    manifest=build_snapshot(source,dest)
    assert digest(source)==before
    monkeypatch.setenv('AUTOLOGIKA_SNAPSHOT_ENABLED','true')
    monkeypatch.setenv('AUTOLOGIKA_SNAPSHOT_PATH',str(dest))
    client=TestClient(create_app(tmp_path/'core.db',KEY),headers={'X-Jarvis-Key':KEY})
    return client,source,dest,manifest


@pytest.mark.parametrize('domain',DOMAINS)
def test_all_eight_domains_use_readonly_snapshot(setup,domain):
    client,source,dest,manifest=setup
    before=(digest(source),digest(dest))
    r=client.get('/api/autologika/snapshot/'+domain+'?month=2026-10')
    assert r.status_code==200,r.text
    assert r.json()['mode']=='snapshot_readonly'
    assert r.json()['sha256']==manifest['sha256']
    assert before==(digest(source),digest(dest))


def test_financial_final_price_zero_no_double_counting_and_payment_period(setup):
    client,_,_,_=setup
    result=client.get('/api/autologika/snapshot/finances?month=2026-10').json()['data']
    assert result['orders_count']==2
    assert result['orders_value']==610
    assert result['contribution']==490
    assert result['paid_in_month']==170
    assert result['receivables']==510
    assert result['accounting_profit'] is False


def test_notifs_all_families_and_tombstones(setup):
    client,_,_,_=setup
    rows=client.get('/api/autologika/snapshot/notifications').json()['data']['items']
    assert {r['kind'] for r in rows}=={'WAIT','REPLY','PART_LATE','APPROVAL','VEHICLE_FINDING'}
    orders=client.get('/api/autologika/snapshot/orders?limit=1').json()['data']
    assert orders['has_more'] and len(orders['items'])==1
    all_orders=client.get('/api/autologika/snapshot/orders').json()['data']['items']
    assert len(all_orders)==3 and not any(r['id']==4 for r in all_orders)


def test_checksum_mismatch_and_unknown_domain_fail_closed(setup):
    client,_,dest,_=setup
    assert client.get('/api/autologika/snapshot/unknown').status_code==422
    assert client.get('/api/autologika/snapshot/orders?month=2026-99').status_code==422
    with sqlite3.connect(dest) as c:c.execute("UPDATE orders SET title='tampered' WHERE id=1")
    assert client.get('/api/autologika/snapshot/orders').status_code==503


def test_snapshot_read_connection_rejects_writes(setup):
    _,_,dest,_=setup
    with Snapshot(dest).connect() as c:
        with pytest.raises(sqlite3.OperationalError):c.execute('DELETE FROM orders')


def test_unsupported_schema_never_overwrites_valid_snapshot(setup):
    _,source,dest,_=setup
    before=digest(dest)
    with sqlite3.connect(source) as c:c.execute('PRAGMA user_version=19')
    with pytest.raises(ValueError):build_snapshot(source,dest)
    assert digest(dest)==before
    assert not list(dest.parent.glob('.snapshot-*'))


def test_snapshot_is_explicitly_off_by_default(tmp_path,monkeypatch):
    monkeypatch.delenv('AUTOLOGIKA_SNAPSHOT_ENABLED',raising=False)
    c=TestClient(create_app(tmp_path/'core.db',KEY),headers={'X-Jarvis-Key':KEY})
    assert c.get('/api/autologika/snapshot').status_code==503


def test_narrow_workshop_service_token_can_read_then_is_revoked(setup):
    client,_,_,_=setup
    issued=client.post('/api/v1/security/tokens',json={
        'name':'OpenClaw workshop reader','scopes':['workshop:read'],'hours':1,
    })
    assert issued.status_code==201,issued.text
    body=issued.json();headers={'X-Jarvis-Key':body['token']}
    result=client.get('/api/v1/autologika/snapshot/orders?limit=1',headers=headers)
    assert result.status_code==200,result.text
    assert len(result.json()['data']['items'])==1
    assert client.get('/api/v1/status',headers=headers).status_code==403
    assert client.get('/api/v1/home/states/sensor.workshop_temperature',headers=headers).status_code==403
    assert client.post('/api/v1/security/tokens',json={
        'name':'forbidden','scopes':['workshop:read']},headers=headers).status_code==403
    assert body['token'] not in client.get('/api/v1/security/tokens').text
    assert client.delete('/api/v1/security/tokens/'+body['id']).status_code==200
    assert client.get('/api/v1/autologika/snapshot/orders',headers=headers).status_code==401


def test_source_wal_is_copied_consistently_without_checkpoint(tmp_path):
    source=create_fixture(tmp_path/'source.db')
    with sqlite3.connect(source) as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.execute("UPDATE orders SET title='From WAL' WHERE id=1");c.commit()
        dest=tmp_path/'copy.snapshot.sqlite3'
        build_snapshot(source,dest)
        assert Snapshot(dest).read('orders')['data']['items'][0]['title']=='From WAL'


def test_explicit_workshop_summary_in_chat_is_offline_and_no_customer_list(setup,monkeypatch):
    client,_,_,_=setup
    r=client.post('/api/chat',json={'message':'Podsumowanie','include_workshop_summary':True,'workshop_month':'2026-10'})
    assert r.status_code==200,r.text
    assert '610' in r.json()['reply'] and r.json()['workshop_context'] is True
    assert 'Klient demonstracyjny' not in r.text
    assert 'SYNTHETIC' not in r.text


def test_snapshot_summary_only_attached_when_requested_and_no_customer_pii(setup,monkeypatch):
    import httpx
    from jarvis import main
    client,_,_,_=setup
    original=httpx.AsyncClient;requests=[]
    def handler(req):
        requests.append(json.loads(req.content));return httpx.Response(200,json={'message':{'content':'Odpowiedź testowa'}})
    monkeypatch.setattr(main.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    for attach in [False,True]:
        assert client.post('/api/chat',json={'message':'Podsumuj','model':'ollama','include_workshop_summary':attach,'workshop_month':'2026-10'}).status_code==200
    assert 'snapshot_created_at' not in requests[0]['messages'][0]['content']
    context=requests[1]['messages'][0]['content']
    assert 'snapshot_created_at' in context and '610' in context
    assert 'Klient demonstracyjny' not in context and 'SYNTHETIC' not in context


def test_import_closes_database_handles_before_atomic_replace(tmp_path,monkeypatch):
    from jarvis import workshop
    source=create_fixture(tmp_path/'source.db')
    destination=tmp_path/'windows-safe.snapshot.sqlite3'
    original_connect=sqlite3.connect;original_replace=workshop.os.replace;connections=[]
    class TrackedConnection(sqlite3.Connection):
        closed=False
        def close(self):
            self.closed=True
            return super().close()
    def connect(*args,**kwargs):
        con=original_connect(*args,**dict(kwargs,factory=TrackedConnection));connections.append(con);return con
    def replace(src,dst):
        assert connections and all(con.closed for con in connections)
        return original_replace(src,dst)
    monkeypatch.setattr(workshop.sqlite3,'connect',connect)
    monkeypatch.setattr(workshop.os,'replace',replace)
    build_snapshot(source,destination)
    assert destination.exists()

def test_diagnostics_filters_deleted_parents_and_paginates(setup):
    client,source,dest,_=setup
    with sqlite3.connect(source) as db:
        db.execute("INSERT INTO diagnostics VALUES(3,1,'Second','','','','','',1,'2026-10-29')")
    build_snapshot(source,dest)
    first=client.get('/api/v1/autologika/snapshot/diagnostics?limit=1').json()['data']
    second=client.get('/api/v1/autologika/snapshot/diagnostics?limit=1&offset=1').json()['data']
    assert first['items'][0]['id']==1 and first['has_more']
    assert second['items'][0]['id']==3 and not second['has_more']
    assert 'Usuniety rodzic' not in str(first)+str(second)


def test_missing_diagnostics_table_fails_explicitly(setup):
    client,source,dest,_=setup
    with sqlite3.connect(source) as db: db.execute('DROP TABLE diagnostics')
    build_snapshot(source,dest)
    assert client.get('/api/v1/autologika/snapshot/diagnostics').status_code==503
    assert client.get('/api/v1/autologika/snapshot/orders').status_code==200
