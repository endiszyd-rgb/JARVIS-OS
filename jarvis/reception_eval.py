"""Read-only evaluation of synthetic reception cases; no call or database services."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import Field, model_validator
from .reception_ai import Strict, analyze, inputs

KINDS = Literal['routine','contact_requested','insistent','crisis','unclear']
FIELDS = Literal['name','phone','vehicle','issue','preferred_time']

class Message(Strict):
    role: Literal['customer','assistant']
    text: str = Field(min_length=1, max_length=4000)

class Expected(Strict):
    kinds: list[KINDS] = Field(min_length=1)
    facts: dict[FIELDS, list[str]]
    forbidden_facts: list[FIELDS] = []
    clarification: bool = False

class Case(Strict):
    id: str = Field(min_length=1)
    tags: list[str] = Field(min_length=1)
    history: list[Message] = Field(max_length=10)
    text: str = Field(min_length=1, max_length=4000)
    expected: Expected

    @model_validator(mode='after')
    def grounded_expectations(self):
        _, customers = inputs({'messages':[m.model_dump() for m in self.history]}, self.text)
        for field, values in self.expected.facts.items():
            if field in self.expected.forbidden_facts or not values:
                raise ValueError('Contradictory or empty expected fact')
            for value in values:
                texts = customers
                if field == 'phone':
                    import re
                    texts = [re.sub(r'[\s()\-]', '', t) for t in texts]
                if not value or not any(value in t for t in texts):
                    raise ValueError('Expected fact absent from customer input')
        return self

class Suite(Strict):
    version: str = Field(min_length=1)
    synthetic: Literal[True]
    cases: list[Case] = Field(min_length=25)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({c.id for c in self.cases}) != len(self.cases):
            raise ValueError('Duplicate case IDs')
        return self


def load_suite(path):
    return Suite.model_validate_json(Path(path).read_text(encoding='utf-8'))


def score(case, result):
    errors = []
    exp = case.expected
    kind = result['effective_kind']
    if kind not in exp.kinds:
        errors.append('wrong_intent')
    if kind in ('crisis','insistent') and kind not in exp.kinds:
        errors.append('unsafe_over_escalation')
    if result['needs_clarification'] != exp.clarification:
        errors.append('uncertainty')
    actual = result['extracted']
    for field, values in exp.facts.items():
        if actual.get(field) not in values:
            errors.append('missing_or_wrong_fact:' + field)
    for field in exp.forbidden_facts:
        if field in actual:
            errors.append('forbidden_fact:' + field)
    # Literal grounding alone does not establish the correct semantic field.
    for field in actual:
        if field not in exp.facts and field not in exp.forbidden_facts:
            errors.append('unexpected_fact:' + field)
    return errors


async def evaluate(suite, model, source):
    rows = []
    for case in suite.cases:
        try:
            result = await analyze({'messages':[m.model_dump() for m in case.history]}, case.text)
            errors = score(case, result)
            row = {'id':case.id, 'source':source, 'response_source':result['source'],
                   'errors':errors, 'result':result, 'status':'failed' if errors else 'passed'}
        except HTTPException as exc:
            category = getattr(exc, 'evaluation_category', 'environment_error')
            row = {'id':case.id, 'source':source, 'status':'environment_error' if category=='environment_error' else 'failed',
                   'errors':[category], 'http_status':exc.status_code}
        rows.append(row)
    counts = Counter(r['status'] for r in rows)
    return {'suite_version':suite.version, 'model':model, 'source':source,
            'created_at':datetime.now(timezone.utc).isoformat(),
            'real_model_quality':'measured' if source=='ollama' and counts['environment_error']==0 else 'unverified',
            'real_ai_passed':counts['passed'] if source=='ollama' else 0,
            'quality_evaluated':sum(r['status']!='environment_error' for r in rows),
            'quality_pass_rate':(counts['passed']/sum(r['status']!='environment_error' for r in rows)) if source=='ollama' and any(r['status']!='environment_error' for r in rows) else None,
            'counts':dict(counts), 'error_counts':dict(Counter(e for r in rows for e in r['errors'])),
            'side_effects':'analysis only; no calls, notifications, customer records or database writes', 'cases':rows}


def write_report(report, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    lines = ['# Ewaluacja recepcji', '', f"Zestaw: {report['suite_version']}; model: {report['model']}; źródło: {report['source']}.",
             f"Jakość rzeczywistego modelu: {report['real_model_quality']}.", '',
             f"Liczniki: {json.dumps(report['counts'],ensure_ascii=False)}", '', report['side_effects'], '',
             '| Przypadek | Wynik | Błędy |','|---|---|---|']
    lines += [f"| {r['id']} | {r['status']} | {', '.join(r['errors'])} |" for r in report['cases']]
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',default=str(Path(__file__).resolve().parents[1]/'evals/reception-pl-v1.json'))
    parser.add_argument('--validate-only',action='store_true')
    parser.add_argument('--model')
    parser.add_argument('--source',choices=['ollama','controlled_http'],default='ollama')
    parser.add_argument('--output',default='data/evals/reception')
    args = parser.parse_args()
    suite = load_suite(args.suite)
    if args.validate_only:
        print(f'Validated {len(suite.cases)} synthetic cases: {suite.version}; no inference')
        return 0
    if not args.model:
        parser.error('--model must explicitly select an installed, allowlisted model')
    os.environ['OLLAMA_RECEPTION_MODEL'] = args.model
    report = asyncio.run(evaluate(suite,args.model,args.source))
    write_report(report,args.output)
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False))
    return 2 if report['counts'].get('environment_error') else int(bool(report['counts'].get('failed')))

if __name__ == '__main__':
    raise SystemExit(main())
