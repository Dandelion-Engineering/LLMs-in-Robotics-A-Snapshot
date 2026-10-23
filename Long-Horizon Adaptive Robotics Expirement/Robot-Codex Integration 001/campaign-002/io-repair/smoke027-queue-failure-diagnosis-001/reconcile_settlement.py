"""Reconcile the retained pre-mutation registry import error; never rerun a job."""
import importlib.util
import json
from pathlib import Path
import settle as s


def main():
    c = s.c
    records = s.C / 'qualification' / s.RUN
    intent_path = records / 'failure-settle-intent.json'
    result_path = records / 'queue-failure.json'
    target = c.MAP / 'releases/RCI001-C02-dev-096' / ('result-' + s.RUN)
    job = c.official(s.JOB)
    c.require(job == c.read(records / 'official-status.json') and job['state'] == 'failed'
              and type(job['exit_status']) is int and job['exit_status'] == 1, 'Exact fresh failure required')
    intent = c.read(intent_path)
    c.require(intent['result'] == c.identity(result_path) and intent['run_id'] == s.RUN, 'Retained intent changed')
    rows = [json.loads(line) for line in (c.MAP / 'results.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    c.require(not target.exists() and not any(row.get('run_id') == s.RUN for row in rows)
              and not (records / 'failure-settle-receipt.json').exists(), 'Existing mutation requires separate reconciliation')
    c.save_exact(s.HERE / 'settlement-reconciliation.json', {
        'error': 'AttributeError: registry_session15.py has no importable finish; its substitution is CLI-only.',
        'failed_operator': c.identity(s.HERE / 'settle.py'), 'original_intent': c.identity(intent_path),
        'original_result': c.identity(result_path), 'map_result_count_before': 0, 'result_directory_existed': False,
        'action': 'Use original registry callable with only common author changed to Session15; preserve original intent and result.'})
    spec = importlib.util.spec_from_file_location('smoke027_reconciled_registry', s.C / 'registry.py')
    registry = importlib.util.module_from_spec(spec); spec.loader.exec_module(registry)
    original = registry.common
    def common(identifier):
        value = original(identifier); value['author'] = 'Codex session 15'; return value
    registry.common = registry.prior.common = common
    result = registry.finish(s.RUN, result_path, records / 'official-status.json', 'invalid', 'unknown', c.read(result_path)['reason'], 'failed')
    c.save_exact(records / 'failure-settle-receipt.json', {'result': result,
        'record': c.identity(target / 'result-record.json'), 'reconciliation': c.identity(s.HERE / 'settlement-reconciliation.json')})
    print(json.dumps(result))


if __name__ == '__main__':
    main()
