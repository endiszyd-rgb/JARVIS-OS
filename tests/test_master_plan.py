"""Master-plan integrity checks use synthetic records, never edit the real journal."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.check_master_plan import PlanError, TASK_IDS, check


@pytest.fixture
def records(tmp_path):
    statuses = {task: 'TODO' for task in TASK_IDS}
    statuses.update({'M0.1': 'VERIFIED', 'M0.2': 'IN_PROGRESS'})
    graph = {'format_version': 1, 'tasks': {
        task: {'requires': [TASK_IDS[index - 1]] if index else [], 'external_gate': None}
        for index, task in enumerate(TASK_IDS)}}

    def write(*, evidence=None, suffix='', counters=None):
        counts = {status: sum(value == status for value in statuses.values()) for status in ('VERIFIED', 'DONE')}
        counts.update(counters or {})
        text = '# Fixture\n## Snapshot\n' + ''.join(f'- Zadania {status}: {count} / 45\n' for status, count in counts.items())
        text += '\n## Zadania\n'
        for task in TASK_IDS:
            tests = (evidence or {}).get(task, 'PASS recorded fixture check' if statuses[task] == 'VERIFIED' else 'NOT_RUN')
            text += f'\n#### {task} — Fixture\n- **Status:** {statuses[task]}\n- **Testy (komenda, wynik):** {tests}\n- **Blokady:** —\n'
        text += suffix
        for name in ('JARVIS_MASTER_PLAN.txt', 'JARVIS_MASTER_PLAN.md'):
            (tmp_path / name).write_bytes(text.encode())
        (tmp_path / 'JARVIS_MASTER_DEPENDENCIES.json').write_text(json.dumps(graph), encoding='utf-8')
        return tmp_path

    return tmp_path, statuses, graph, write


def test_summary_uses_statuses_and_prioritizes_in_progress(records):
    root, statuses, graph, write = records
    graph['tasks']['M0.1']['requires'] = []
    statuses['M0.1'], statuses['M0.2'] = 'TODO', 'TODO'
    statuses['M8.5'] = 'IN_PROGRESS'
    graph['tasks']['M8.5']['requires'] = []
    summary = check(write())
    assert summary['total'] == 45
    assert summary['counts'] == {'TODO': 44, 'IN_PROGRESS': 1, 'BLOCKED': 0, 'DONE': 0, 'VERIFIED': 0}
    assert summary['eligible'] == ['M8.5', 'M0.1']
    assert summary['next_task'] == 'M8.5'


def test_mirror_comparison_detects_newline_drift(records):
    root, _, _, write = records
    write()
    mirror = root / 'JARVIS_MASTER_PLAN.md'
    mirror.write_bytes(mirror.read_bytes().replace(b'\n', b'\r\n'))
    with pytest.raises(PlanError, match='byte-identical'):
        check(root)


@pytest.mark.parametrize('mutation,expected', [
    ('missing', 'Missing task'), ('duplicate', 'Duplicate task'), ('unknown', 'Unknown task'),
    ('bad_status', 'invalid status'), ('duplicate_status', 'exactly one Status'),
    ('duplicate_tests', 'exactly one Testy'),
])
def test_rejects_malformed_task_records(records, mutation, expected):
    root, _, _, write = records
    write()
    source = (root / 'JARVIS_MASTER_PLAN.txt').read_text(encoding='utf-8')
    if mutation == 'missing':
        source = source[:source.index('\n#### M8.5')]
    elif mutation == 'duplicate':
        source += '\n#### M0.1 — duplicate\n- **Status:** TODO\n- **Testy (komenda, wynik):** NOT_RUN\n'
    elif mutation == 'unknown':
        source = source.replace('#### M8.5', '#### M9.1')
    elif mutation == 'bad_status':
        source = source.replace('**Status:** IN_PROGRESS', '**Status:** ALMOST_DONE')
    elif mutation == 'duplicate_status':
        source = source.replace('**Status:** IN_PROGRESS', '**Status:** IN_PROGRESS\n- **Status:** TODO')
    else:
        source = source.replace('**Testy (komenda, wynik):** PASS recorded fixture check', '**Testy (komenda, wynik):** PASS recorded fixture check\n- **Testy (komenda, wynik):** PASS duplicate')
    for name in ('JARVIS_MASTER_PLAN.txt', 'JARVIS_MASTER_PLAN.md'):
        (root / name).write_text(source, encoding='utf-8')
    with pytest.raises(PlanError, match=expected):
        check(root)


@pytest.mark.parametrize('evidence', ['NOT_RUN', 'BYPASS elsewhere', 'NOT_PASS detail', 'PASS'])
def test_verified_needs_positive_evidence_in_its_own_field(records, evidence):
    root, _, _, write = records
    write(evidence={'M0.1': evidence}, suffix='\n## Notes\nPASS this is outside the task test field\n')
    with pytest.raises(PlanError, match='recorded PASS evidence'):
        check(root)


def test_verified_dependency_cannot_be_only_done(records):
    root, statuses, _, write = records
    statuses.update({'M0.1': 'DONE', 'M0.2': 'VERIFIED'})
    with pytest.raises(PlanError, match='M0.2: VERIFIED requires VERIFIED dependencies: M0.1'):
        check(write())


@pytest.mark.parametrize('mutation,expected', [
    ('version', 'format_version'), ('missing', 'same 45'), ('unknown', 'unknown dependency'),
    ('duplicate', 'duplicate dependencies'), ('string', 'requires must be a list'),
    ('gate', 'external_gate'), ('cycle', 'cycle'),
])
def test_rejects_malformed_graph(records, mutation, expected):
    _, _, graph, write = records
    node = graph['tasks']['M0.2']
    if mutation == 'version':
        graph['format_version'] = True
    elif mutation == 'missing':
        del graph['tasks']['M8.5']
    elif mutation == 'unknown':
        node['requires'] = ['M9.1']
    elif mutation == 'duplicate':
        node['requires'] = ['M0.1', 'M0.1']
    elif mutation == 'string':
        node['requires'] = 'M0.1'
    elif mutation == 'gate':
        node['external_gate'] = '  '
    else:
        graph['tasks']['M0.1']['requires'] = ['M0.2']
    with pytest.raises(PlanError, match=expected):
        check(write())


def test_duplicate_json_task_key_is_not_silently_overwritten(records):
    root, _, _, write = records
    write()
    path = root / 'JARVIS_MASTER_DEPENDENCIES.json'
    text = path.read_text(encoding='utf-8')
    path.write_text(text.replace('"tasks": {', '"tasks": {"M0.1": {"requires": [], "external_gate": null},', 1), encoding='utf-8')
    with pytest.raises(PlanError, match='Duplicate JSON key: M0.1'):
        check(root)


@pytest.mark.parametrize('counter', ['VERIFIED', 'DONE'])
def test_snapshot_counters_must_match_actual_task_statuses(records, counter):
    _, _, _, write = records
    with pytest.raises(PlanError, match=f'Snapshot {counter} count'):
        check(write(counters={counter: 23}))


def test_gated_blocked_is_skipped_but_todo_gate_is_preparatory(records):
    _, statuses, graph, write = records
    statuses['M0.2'] = 'BLOCKED'
    graph['tasks']['M0.2']['external_gate'] = 'physical hardware required'
    graph['tasks']['M7.1'] = {'requires': ['M0.1'], 'external_gate': 'account needed for later activation'}
    statuses['M7.2'] = 'BLOCKED'
    graph['tasks']['M7.2']['requires'] = ['M0.1']
    summary = check(write())
    assert summary['next_task'] == 'M7.1'
    assert summary['eligible'] == ['M7.1', 'M7.2']
    assert summary['gated_blocked'] == ['M0.2']


def test_cli_root_success_and_clear_failure(records):
    root, _, _, write = records
    script = Path(__file__).resolve().parents[1] / 'scripts/check_master_plan.py'
    write()
    passed = subprocess.run([sys.executable, str(script), '--root', str(root)], capture_output=True, text=True)
    assert passed.returncode == 0
    assert json.loads(passed.stdout)['next_task'] == 'M0.2'
    (root / 'JARVIS_MASTER_PLAN.md').unlink()
    failed = subprocess.run([sys.executable, str(script), '--root', str(root)], capture_output=True, text=True)
    assert failed.returncode == 1
    assert 'Master plan error: Cannot read plan/dependencies:' in failed.stderr
    assert 'Traceback' not in failed.stderr
