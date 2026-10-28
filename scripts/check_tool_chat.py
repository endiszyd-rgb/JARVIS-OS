"""Actual loopback Core + LLM protocols + OpenAPI/MCP smoke; no inference.

Uses temporary SQLite, synthetic credentials/data and dynamically bound ports.
All real integrations are explicitly disabled. Writes only the requested report.
"""
import argparse
import asyncio
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def verify(folder,*,tasks_mode=False):
    import httpx
    import uvicorn
    from mcp.server.fastmcp import FastMCP

    key, provider_key, plugin_key = (secrets.token_urlsafe(36) for _ in range(3))
    requests, tool_reads, mcp_reads = [], [], []
    cancel_entered,cancel_release=threading.Event(),threading.Event()
    model = 'gpt-5.4-mini-2026-03-17'
    class Remote(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def reply(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            if self.path != '/read?item=7':
                self.reply(404, {}); return
            tool_reads.append({'path': self.path, 'authorized': self.headers.get('Authorization') == 'Bearer ' + plugin_key})
            self.reply(200, {'item': 7, 'source': 'synthetic_openapi', 'value': 'Controlled read result'})
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            is_cloud = self.path == '/v1/chat/completions'
            assert self.path in ('/api/chat', '/v1/chat/completions')
            wire = json.dumps(payload)
            assert all(secret not in wire for secret in (key, provider_key, plugin_key, 'PRIVATE NOTE NOT ATTACHED'))
            assert len(payload['tools']) == 1
            name = payload['tools'][0]['function']['name']
            has_result = any(row['role'] == 'tool' for row in payload['messages'])
            requests.append({'protocol': 'openai' if is_cloud else 'ollama', 'result_attached': has_result,
                             'authorized': not is_cloud or self.headers.get('Authorization') == 'Bearer ' + provider_key})
            if any(row['role']=='user' and row['content']=='fixture_wait' for row in payload['messages']):
                cancel_entered.set();cancel_release.wait(10)
            attack = any(row['role'] == 'user' and row['content'] == 'fixture_attack' for row in payload['messages'])
            message = {'role': 'assistant', 'content': 'Syntetyczny odczyt zakończony.' if has_result else ''}
            if not has_result:
                names = [name, 'open_gate'] if attack else [name]
                if is_cloud:
                    message['tool_calls'] = [{'type': 'function', 'id': 'call_' + str(i),
                        'function': {'name': n, 'arguments': '{"item":7}'}} for i, n in enumerate(names)]
                else:
                    message['tool_calls'] = [{'type': 'function', 'function': {
                        'name': n, 'arguments': {'item': 7}, 'index': i}} for i, n in enumerate(names)]
            else:
                assert 'untrusted_tool_data' in payload['messages'][-1]['content']
                assert payload['messages'][-1]['role'] == 'tool'
            if is_cloud:
                self.reply(200, {'model': model, 'choices': [{'finish_reason': 'stop' if has_result else 'tool_calls', 'message': message}],
                                 'usage': {'prompt_tokens': 100, 'completion_tokens': 10}})
            else:
                self.reply(200, {'model': 'synthetic:local', 'done': True, 'done_reason': 'stop',
                                 'message': message, 'prompt_eval_count': 100, 'eval_count': 10})
    remote = ThreadingHTTPServer(('127.0.0.1', 0), Remote)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{remote.server_port}'
    os.environ.update(
        JARVIS_API_KEY=key, JARVIS_DB=str(Path(folder)/'core.db'), JARVIS_POSTGRES_DSN='',
        JARVIS_VOICE_ENABLED='false', JARVIS_RECEPTION_AI_ENABLED='false',
        JARVIS_EMBEDDINGS_ENABLED='false', TWILIO_WEBHOOK_ENABLED='false', HA_READONLY_ENABLED='false',
        AUTOLOGIKA_READONLY_ENABLED='false', AUTOLOGIKA_SNAPSHOT_ENABLED='false',
        JARVIS_TOOL_CHAT_ENABLED='true', JARVIS_ALLOW_CLOUD_MODELS='true', JARVIS_OPENAI_ENABLED='true',
        JARVIS_OPENAI_API_KEY=provider_key, JARVIS_OPENAI_MODEL=model, JARVIS_OPENAI_URL=origin,
        JARVIS_OPENAI_INPUT_USD_PER_MILLION='0.75', JARVIS_OPENAI_OUTPUT_USD_PER_MILLION='4.5',
        JARVIS_OPENAI_MAX_REQUEST_USD='2' if tasks_mode else '1', JARVIS_LLM_MAX_OUTPUT_TOKENS='1024',
        OLLAMA_URL=origin, OLLAMA_MODEL='synthetic:local', OLLAMA_ALLOWED_MODELS='synthetic:local',
        JARVIS_NETWORK_ALLOWLIST='127.0.0.0/8,::1/128', JARVIS_PLUGIN_SECRET_TOOL_LOOP_LAB=plugin_key,
        JARVIS_CORS_ORIGINS='', JARVIS_API_REQUESTS_PER_MINUTE='1000',
    )
    mcp = FastMCP('Synthetic tool-loop lab', host='127.0.0.1', stateless_http=True, json_response=True, log_level='WARNING')
    @mcp.tool()
    def read_item(item: int) -> dict:
        """Read a synthetic item; no external actions."""
        assert item == 7
        mcp_reads.append(item)
        return {'item': item, 'source': 'synthetic_mcp', 'value': 'Controlled MCP result'}

    servers, sockets, tasks = [], [], []
    def serve(app):
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0)); sock.listen(128); sock.setblocking(False)
        server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False, proxy_headers=False))
        servers.append(server); sockets.append(sock)
        tasks.append(asyncio.create_task(server.serve(sockets=[sock])))
        return f'http://127.0.0.1:{sock.getsockname()[1]}'
    try:
        mcp_origin = serve(mcp.streamable_http_app())
        from jarvis.main import create_app
        core_origin = serve(create_app(Path(folder)/'core.db', key))
        for _ in range(200):
            if all(server.started for server in servers): break
            if any(task.done() for task in tasks): raise RuntimeError('Loopback server failed to start')
            await asyncio.sleep(0.02)
        assert all(server.started for server in servers)
        async with httpx.AsyncClient(base_url=core_origin, headers={'X-Jarvis-Key': key}, trust_env=False, timeout=30) as client:
            async def request(method, route, body=None, expected=200):
                response = await client.request(method, '/api/v1'+route, json=body)
                assert response.status_code == expected, (route, body.get('tool_ids') if isinstance(body, dict) else None, response.status_code, response.text)
                return response.json()
            await request('POST', '/memory', {'text': 'PRIVATE NOTE NOT ATTACHED'}, 201)
            schema = {'openapi': '3.0.3', 'paths': {'/read': {'get': {'operationId': 'read_item', 'parameters': [
                {'name': 'item', 'in': 'query', 'required': True, 'schema': {'type': 'integer', 'minimum': 1}}]}}}}
            for pid, protocol, endpoint in [('loop_http', 'openapi', origin), ('loop_mcp', 'mcp', mcp_origin+'/mcp')]:
                await request('POST', '/plugins', {'id': pid, 'name': 'Synthetic lab', 'protocol': protocol}, 201)
                cfg = {'endpoint': endpoint, 'reviewed_read_tools': ['read_item']}
                if protocol == 'openapi': cfg.update(openapi=schema, secret_env='JARVIS_PLUGIN_SECRET_TOOL_LOOP_LAB')
                await request('PUT', '/plugins/'+pid+'/config', cfg)
                await request('PUT', '/plugins/'+pid, {'enabled': True})
            scenarios = []
            for provider in ('ollama', 'openai'):
                for pid in ('loop_http', 'loop_mcp'):
                    result = await request('POST', '/chat/tools', {'message': 'Odczytaj wskazany rekord demonstracyjny.',
                                             'model': provider, 'tool_ids': [pid+'.read_item']})
                    assert result['provider_turns'] == 2 and len(result['tool_calls']) == 1
                    assert result['tool_calls'][0]['tool_id'] == pid+'.read_item'
                    assert result['reply'] == 'Syntetyczny odczyt zakończony.' and result['history_saved'] is False
                    scenarios.append({'provider': provider, 'plugin_protocol': 'openapi' if pid == 'loop_http' else 'mcp',
                                      'provider_turns': 2, 'tool_calls': 1, 'passed': True})
            before = len(tool_reads)
            await request('POST', '/chat/tools', {'message': 'fixture_attack', 'model': 'openai',
                                                 'tool_ids': ['loop_http.read_item']}, 502)
            assert len(tool_reads) == before
            task_scenarios=[]
            if tasks_mode:
                async def task_state(ident,expected):
                    for _ in range(500):
                        state=await request('GET','/chat/tasks/'+ident)
                        if state['status'] in ('completed','failed','cancelled'):
                            assert state['status']==expected
                            return state
                        await asyncio.sleep(0.01)
                    raise AssertionError('Task did not reach expected terminal status')
                for provider in ('ollama','openai'):
                    for pid in ('loop_http','loop_mcp'):
                        body={'request_id':str(uuid.uuid4()),'steps':['Read selected item','Summarize the previous verified read'],
                              'model':provider,'tool_ids':[pid+'.read_item']}
                        job=await request('POST','/chat/tasks',body,202)
                        state=await task_state(job['id'],'completed')
                        assert state['steps_completed']==2 and len(state['results'])==2
                        assert all(result['provider_turns']==2 and len(result['tool_calls'])==1 for result in state['results'])
                        before_posts=len(requests)
                        replay=await request('POST','/chat/tasks',body,202)
                        assert replay['id']==job['id'] and len(requests)==before_posts
                        task_scenarios.append({'provider':provider,'protocol':pid,'steps':2,'provider_posts':4,'replay':False})
                waiting=await request('POST','/chat/tasks',{'request_id':str(uuid.uuid4()),'steps':['fixture_wait','Never start'],
                    'model':'ollama','tool_ids':['loop_http.read_item']},202)
                for _ in range(500):
                    if cancel_entered.is_set():break
                    await asyncio.sleep(0.01)
                assert cancel_entered.is_set()
                before_reads=len(tool_reads)
                await request('POST','/chat/tasks/'+waiting['id']+'/cancel',expected=202)
                cancelled=await task_state(waiting['id'],'cancelled')
                assert cancelled['results']==[] and cancelled['steps_completed']==0
                cancel_release.set();await asyncio.sleep(0.05)
                assert len(tool_reads)==before_reads
            assert await request('GET', '/chat/sessions') == []
            audit = json.dumps(await request('GET', '/audit'))
            assert all(value not in audit for value in (key, provider_key, plugin_key, 'fixture_attack', 'Controlled read result', 'Controlled MCP result'))
        assert len(requests) == (26 if tasks_mode else 9) and all(row['authorized'] for row in requests)
        assert len(tool_reads) == (6 if tasks_mode else 2) and all(row['authorized'] for row in tool_reads) and len(mcp_reads) == (6 if tasks_mode else 2)
        return {'task': 'M3.5' if tasks_mode else 'M3.2', 'task_scenarios':task_scenarios, 'task_cancel_before_dispatch':tasks_mode, 'passed': True, 'checked_utc': datetime.now(timezone.utc).isoformat(),
                'transport': 'genuine_loopback_TCP_Core_OpenAI_Ollama_OpenAPI_MCP_SDK',
                'scenarios': scenarios, 'provider_posts':len(requests), 'openapi_reads':len(tool_reads), 'mcp_reads':len(mcp_reads),
                'unselected_call_refused_before_batch_dispatch': True, 'audit_privacy': True,
                'private_memory_attached': False, 'history_saved': False,
                'real_inference': False, 'real_provider_account': False, 'production_modified': False}
    finally:
        for server in servers: server.should_exit = True
        if tasks:
            try: await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)
            except TimeoutError:
                for task in tasks: task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        for sock in sockets: sock.close()
        cancel_release.set()
        remote.shutdown(); remote.server_close(); thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks',action='store_true',help='Also verify M3.5 multistep tasks and cancellation')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='jarvis-tool-loop-') as folder:
        report = asyncio.run(verify(folder,tasks_mode=args.tasks))
    text = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
