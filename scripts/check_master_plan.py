#!/usr/bin/env python3
"""Validate the master-plan records, not the truth/adequacy of recorded tests."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys


TASK_IDS = tuple(f'M{stage}.{task}' for stage in range(9) for task in range(1, 6))
STATUSES = ('TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE', 'VERIFIED')
HEADINGS = re.compile(r'^####[ \t]+(M\d+\.\d+)\b[^\n]*$', re.MULTILINE)


class PlanError(ValueError):
    """A malformed or inconsistent plan/dependency record."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PlanError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _field(block, label, task):
    pattern = re.compile(r'^- \*\*' + re.escape(label) + r':\*\*[ \t]*(.*)$', re.MULTILINE)
    matches = list(pattern.finditer(block))
    if len(matches) != 1:
        raise PlanError(f'{task}: expected exactly one {label} field')
    match = matches[0]
    tail = block[match.end():]
    end = re.search(r'^(?:- \*\*|#{1,4} )', tail, re.MULTILINE)
    return (match.group(1) + tail[:end.start() if end else len(tail)]).strip()


def _parse_tasks(plan):
    headings = list(HEADINGS.finditer(plan))
    tasks = {}
    for index, heading in enumerate(headings):
        task = heading.group(1)
        if task not in TASK_IDS:
            raise PlanError(f'Unknown task ID: {task}')
        if task in tasks:
            raise PlanError(f'Duplicate task heading: {task}')
        block = plan[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(plan)]
        status = _field(block, 'Status', task)
        if status not in STATUSES:
            raise PlanError(f'{task}: invalid status {status!r}')
        evidence = _field(block, 'Testy (komenda, wynik)', task)
        if status == 'VERIFIED' and not re.search(r'\bPASS\b\s+\S', evidence):
            raise PlanError(f'{task}: VERIFIED requires recorded PASS evidence in its Testy field')
        tasks[task] = status
    missing = set(TASK_IDS) - tasks.keys()
    if missing:
        raise PlanError('Missing task headings: ' + ', '.join(sorted(missing)))
    return tasks


def _validate_graph(graph):
    if not isinstance(graph, dict) or type(graph.get('format_version')) is not int or graph['format_version'] != 1:
        raise PlanError('Dependency graph requires format_version: 1')
    nodes = graph.get('tasks')
    if not isinstance(nodes, dict) or set(nodes) != set(TASK_IDS):
        raise PlanError('Dependency graph must contain exactly the same 45 known task IDs')
    for task, spec in nodes.items():
        if not isinstance(spec, dict):
            raise PlanError(f'{task}: dependency entry must be an object')
        requires = spec.get('requires')
        if not isinstance(requires, list) or any(not isinstance(dep, str) for dep in requires):
            raise PlanError(f'{task}: requires must be a list of task IDs')
        if len(requires) != len(set(requires)):
            raise PlanError(f'{task}: duplicate dependencies')
        for dep in requires:
            if dep not in nodes:
                raise PlanError(f'{task}: unknown dependency {dep}')
        if 'external_gate' not in spec or (spec['external_gate'] is not None and
                (not isinstance(spec['external_gate'], str) or not spec['external_gate'].strip())):
            raise PlanError(f'{task}: external_gate must be null or nonempty text')
    visiting, visited = set(), set()

    def visit(task):
        if task in visiting:
            raise PlanError(f'Dependency cycle involving {task}')
        if task in visited:
            return
        visiting.add(task)
        for dep in nodes[task]['requires']:
            visit(dep)
        visiting.remove(task)
        visited.add(task)

    for task in TASK_IDS:
        visit(task)
    return nodes


def _validate_snapshot(plan, counts):
    sections = list(re.finditer(r'^## Snapshot[^\n]*\n(.*?)(?=^## |\Z)', plan, re.MULTILINE | re.DOTALL))
    if len(sections) != 1:
        raise PlanError('Expected exactly one Snapshot section')
    for status in ('VERIFIED', 'DONE'):
        values = re.findall(r'^- Zadania ' + status + r':[ \t]*(\d+)[ \t]*/[ \t]*(\d+)[ \t]*$', sections[0].group(1), re.MULTILINE)
        if len(values) != 1 or tuple(map(int, values[0])) != (counts[status], len(TASK_IDS)):
            raise PlanError(f'Snapshot {status} count must equal {counts[status]} / {len(TASK_IDS)}')


def check(root):
    """Return counts and ordered eligible tasks; raise PlanError on invalid records."""
    root = Path(root)
    try:
        source = (root / 'JARVIS_MASTER_PLAN.txt').read_bytes()
        mirror = (root / 'JARVIS_MASTER_PLAN.md').read_bytes()
        if source != mirror:
            raise PlanError('JARVIS_MASTER_PLAN.txt and .md must be byte-identical')
        plan = source.decode('utf-8')
        graph = json.loads((root / 'JARVIS_MASTER_DEPENDENCIES.json').read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f'Cannot read plan/dependencies: {exc}') from exc
    tasks = _parse_tasks(plan)
    nodes = _validate_graph(graph)
    counts = {status: Counter(tasks.values())[status] for status in STATUSES}
    _validate_snapshot(plan, counts)
    for task in TASK_IDS:
        if tasks[task] == 'VERIFIED':
            pending = [dep for dep in nodes[task]['requires'] if tasks[dep] != 'VERIFIED']
            if pending:
                raise PlanError(f'{task}: VERIFIED requires VERIFIED dependencies: {", ".join(pending)}')
    gated = [task for task in TASK_IDS if tasks[task] == 'BLOCKED' and nodes[task]['external_gate']]
    eligible = [task for status_group in (('IN_PROGRESS',), ('TODO', 'BLOCKED')) for task in TASK_IDS
                if tasks[task] in status_group and task not in gated and
                all(tasks[dep] == 'VERIFIED' for dep in nodes[task]['requires'])]
    return {'total': len(tasks), 'counts': counts, 'eligible': eligible,
            'next_task': eligible[0] if eligible else None, 'gated_blocked': gated}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        summary = check(args.root)
    except PlanError as exc:
        print(f'Master plan error: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
