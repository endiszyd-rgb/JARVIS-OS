import asyncio
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

import pytest
from jarvis import reception_eval as ev

SUITE = Path(__file__).resolve().parents[1]/'evals/reception-pl-v1.json'

@contextmanager
def server(monkeypatch, response, status=200):
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        def log_message(self,*args):pass
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    monkeypatch.setenv('OLLAMA_RECEPTION_URL',f'http://127.0.0.1:{http.server_port}')
    monkeypatch.setenv('OLLAMA_RECEPTION_MODEL','test:local')
    monkeypatch.setenv('OLLAMA_ALLOWED_MODELS','test:local')
    monkeypatch.setenv('JARVIS_RECEPTION_AI_ENABLED','true')
    monkeypatch.setenv('JARVIS_NETWORK_ALLOWLIST','127.0.0.1/32')
    try:yield requests
    finally:http.shutdown();http.server_close();thread.join()


def single():
    suite=ev.load_suite(SUITE)
    # Use one selected case for bounded transport tests; full dataset is validated separately.
    suite.cases=[next(c for c in suite.cases if c.id=='no-failure')]
    return suite


def outer(**changes):
    answer={'kind':'routine','confidence':'high','evidence':[],'facts':[]}
    answer.update(changes)
    return {'done':True,'message':{'content':json.dumps(answer)}}


def test_versioned_dataset_and_no_model_validation(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('Validation must not run inference')
    monkeypatch.setattr(ev,'analyze',forbidden)
    suite=ev.load_suite(SUITE)
    assert len(suite.cases)>=25
    assert {'negacja','cytat','hipoteza','prompt-injection','bledny-telefon'} <= {t for c in suite.cases for t in c.tags}
    data=suite.model_dump();data['cases'][1]['id']=data['cases'][0]['id']
    with pytest.raises(ValueError):ev.Suite.model_validate(data)
    data=suite.model_dump();data['cases'][0]['expected']['facts']['name']=['Invented']
    with pytest.raises(ValueError):ev.Suite.model_validate(data)


def test_real_http_success_report_and_no_actions(monkeypatch,tmp_path):
    from jarvis.main import create_app
    from fastapi.testclient import TestClient
    key='test-eval-owner-key-32-characters'
    app=TestClient(create_app(tmp_path/'core.db',key),headers={'X-Jarvis-Key':key})
    before={path:app.get(path).json() for path in ['/api/memory','/api/reception/calls','/api/reception/cases']}
    with server(monkeypatch,outer()) as requests:
        report=asyncio.run(ev.evaluate(single(),'test:local','controlled_http'))
    assert report['counts']=={'passed':1}
    assert report['real_ai_passed']==0 and report['real_model_quality']=='unverified'
    assert len(requests)==1 and requests[0][0]=='/api/chat'
    assert 'tools' not in requests[0][1]
    assert requests[0][1]['model']=='test:local'
    assert before=={path:app.get(path).json() for path in before}
    ev.write_report(report,tmp_path/'eval')
    saved=json.loads((tmp_path/'eval.json').read_text())
    assert saved['source']=='controlled_http'
    assert 'no-failure | passed' in (tmp_path/'eval.md').read_text()


@pytest.mark.parametrize('response,status,error',[
    ({'error':'model missing'},404,'environment_error'),
    ({'done':True,'message':{'content':'not json'}},200,'invalid_schema'),
    (outer(kind='crisis',evidence=[{'message_index':0,'quote':'invented crisis'}]),200,'fabricated_evidence_or_fact'),
    (outer(facts=[{'field':'vehicle','value':'BMW','message_index':0,'quote':'Po naprawie hamulce'}]),200,'fabricated_evidence_or_fact'),
    (outer(execute='open_gate'),200,'invalid_schema'),
])
def test_failures_are_distinct(monkeypatch,response,status,error):
    with server(monkeypatch,response,status):
        report=asyncio.run(ev.evaluate(single(),'test:local','controlled_http'))
    assert report['cases'][0]['errors']==[error]
    assert report['real_ai_passed']==0
    assert report['cases'][0]['status']==('environment_error' if status==404 else 'failed')


def test_semantic_over_escalation_and_uncertainty(monkeypatch):
    with server(monkeypatch,outer(kind='crisis',evidence=[{'message_index':0,'quote':'hamulce działają świetnie'}])):
        report=asyncio.run(ev.evaluate(single(),'test:local','controlled_http'))
    assert set(report['cases'][0]['errors'])=={'wrong_intent','unsafe_over_escalation'}
    with server(monkeypatch,outer(confidence='low')):
        report=asyncio.run(ev.evaluate(single(),'test:local','controlled_http'))
    assert set(report['cases'][0]['errors'])=={'wrong_intent','uncertainty'}


def test_fact_semantics_and_network_denied(monkeypatch):
    with server(monkeypatch,outer(facts=[{'field':'name','value':'hamulce','message_index':0,'quote':'hamulce działają świetnie'}])):
        report=asyncio.run(ev.evaluate(single(),'test:local','controlled_http'))
    assert report['cases'][0]['errors']==['forbidden_fact:name']
    with server(monkeypatch,outer()) as requests:
        monkeypatch.setenv('JARVIS_NETWORK_ALLOWLIST','192.0.2.0/24')
        report=asyncio.run(ev.evaluate(single(),'test:local','controlled_http'))
        assert requests==[]
    assert report['cases'][0]['status']=='environment_error'
