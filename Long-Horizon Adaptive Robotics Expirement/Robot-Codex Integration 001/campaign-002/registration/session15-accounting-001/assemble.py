"""One additive S15 accounting refresh using the unchanged authenticated helper."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = HERE.parent
C = REG.parent
REPO = C.parents[2]
OLD = REG / 'session14-accounting.json'
NEW = REG / 'session15-accounting.json'
HELPER = REG / 'refresh_session14_accounting.py'
HELPER_SHA = '5675db9f1454e1db0f45f4bd0ed642dee5c96d63543e787e1d3c05b74e5ac954'
OLD_SHA = 'c0422c911e5a85f9e98497800865c4f4763a00dc18b6778f44cdc3a344bd1ee4'
OBSERVATIONS = (
    ('20260929T172359627310Z-e9b8409e', 'RCI001-C02-shutdown-diagnostic-004', 'succeeded', 0,
     'native004-diagnosis-001/observations.json', '/client/model_started'),
    ('20260929T182650537335Z-49496959', 'RCI001-C02-smoke-027', 'failed', 1,
     'smoke027-queue-failure-diagnosis-001/analysis.json', '/metadata/interrupt\\client\\result.json/metadata/model_started'),
)


def identity(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def add_starts(result, reader, binder):
    """Two exact retained Boolean observations; no raw output or request-count inference."""
    jobs = result['refresh_provenance']['official_statuses']
    existing = set(result.get('diagnostic_observed_model_starts', {}))
    if result.get('session15_diagnostic_model_starts'):
        raise ValueError('Session15 observations already attached')
    records = {}
    literal_before = result['totals']['observed_turn_start_requests_from_assessable_and_diagnostic_receipts']
    for jid, run, state, exit_status, relative, pointer in OBSERVATIONS:
        job = jobs[jid]
        if (jid in existing or job.get('id') != jid or job.get('state') != state
                or type(job.get('exit_status')) is not int or job['exit_status'] != exit_status
                or not job.get('started_at') or not job.get('ended_at')):
            raise ValueError('Exact fresh terminal diagnostic job required, without double counting')
        path = C / 'io-repair' / relative
        document = reader(path)
        if (document.get('job_id', document.get('queue_job_id')) != jid or document.get('run_id') != run
                or document.get('task_outcome') != 'unknown'):
            raise ValueError('Retained diagnosis identity or unknown-outcome scope differs')
        if run.endswith('diagnostic-004'):
            if document.get('diagnostic_only') is not True:
                raise ValueError('Native004 must remain diagnostic only')
        elif document.get('assessment_state') != 'not_assessed' or document.get('scorable') is not False:
            raise ValueError('Smoke027 must remain unassessed and unscorable')
        value = document
        for key in pointer.strip('/').split('/'):
            value = value[key]
        if value is not True:
            raise ValueError('Exact model_started Boolean required')
        item = binder(path)
        record = {'queue_job_id': jid, 'run_id': run, 'observed_model_starts_lower_bound': 1,
            'diagnostic_analysis': item, 'json_pointer': pointer, 'value': True,
            'scope': 'Unassessed diagnostic model-start observation only; no literal request, generation, billing, qualification or task-outcome inference.'}
        matches = [row for row in result['rows'] if row['official_queue']['id'] == jid]
        if len(matches) != 1 or matches[0].get('known_model_invocations_started') not in (None, 0):
            raise ValueError('Missing, duplicate or already counted model job')
        matches[0]['diagnostic_model_start_accounting'] = record
        records[jid] = record
        result['source_bindings'].setdefault(item['path'], item)
        result['refresh_provenance']['current_bindings'][item['path']] = item
    total = result['totals']
    if total['observed_model_starts_lower_bound_from_assessable_and_diagnostic_receipts'] != (
            total['known_qualification_model_invocations_started'] + total['known_scored_model_invocations_started']
            + total['diagnostic_only_observed_model_starts_lower_bound']):
        raise ValueError('Prior lower-bound accounting does not reconcile')
    total['diagnostic_only_observed_model_starts_lower_bound'] += len(records)
    total['observed_model_starts_lower_bound_from_assessable_and_diagnostic_receipts'] += len(records)
    assert total['observed_turn_start_requests_from_assessable_and_diagnostic_receipts'] == literal_before
    result['session15_diagnostic_model_starts'] = records
    result['limitations'].append('Two Session15 model_started observations include Native004 completed diagnostic and failed Smoke027; they increase only the diagnostic start lower bound, never literal request counts, qualification or billing.')
    return records


def main():
    assert identity(HELPER)['sha256'] == HELPER_SHA and identity(OLD)['sha256'] == OLD_SHA
    assert not NEW.exists()
    execution = HERE / 'execution-001'; execution.mkdir()
    prior_bytes = OLD.read_bytes(); prior = json.loads(prior_bytes)
    assert len(prior['rows']) == 115 and len(prior['source_bindings']) == 913
    history = C / 'investigation/qualification-history.json'
    assert identity(history)['sha256'] == 'cc2bc83f1c7b887c3e8f16d0cab65beb509f1f7e55e44310833725000375590e'
    exports = json.loads((C / 'investigation/qualification-history-append-session15-receipt.json').read_bytes())['exports_preserved']
    assert len(exports) == 19 and all(identity(v['path']) == v for v in exports)
    save(execution / 'intent.json', {'source': identity(Path(__file__)), 'unchanged_helper': identity(HELPER),
        'prior_accounting': identity(OLD), 'history': identity(history), 'old_bindings': 913,
        'exports': exports, 'scope': 'New additive Session15 artifact; preserve Session14 bytes and authenticate all discovered jobs before consumption.'})
    spec = importlib.util.spec_from_file_location('session15_unchanged_accounting_core', HELPER)
    core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
    discovered = core.discover(C, prior)
    result = core.build_refresh(prior, discovered, C, REPO)
    assert result['queue_occupancy_at_cutoff']['active_accounted_jobs'] == []
    add_starts(result, core.read, identity)
    for path in (Path(__file__), HERE / 'test_assemble.py', OLD):
        item = identity(path); result['source_bindings'].setdefault(item['path'], item)
        result['refresh_provenance']['current_bindings'][item['path']] = item
    result['session'] = 15
    result['scope'] = 'Campaign002 accounting through the stopped V29/Smoke027 lineage; Session14 is retained separately and unchanged. Not campaign completion.'
    result['refresh_provenance']['session15_assembler'] = identity(Path(__file__))
    result['refresh_provenance']['previous_accounting'] = identity(OLD)
    assert all(result['source_bindings'][k] == v for k,v in prior['source_bindings'].items())
    assert OLD.read_bytes() == prior_bytes and all(identity(v['path']) == v for v in exports)
    assert result['totals']['official_jobs'] == 122
    assert result['totals']['queue_states'] == {'succeeded': 104, 'failed': 18}
    assert result['totals']['observed_model_starts_lower_bound_from_assessable_and_diagnostic_receipts'] == 31
    assert result['totals']['observed_turn_start_requests_from_assessable_and_diagnostic_receipts'] == 20
    save(NEW, result)
    receipt = {'passed': True, 'old_accounting_unchanged': identity(OLD), 'accounting': identity(NEW),
        'prior_source_bindings_preserved': 913, 'current_source_bindings': len(result['source_bindings']),
        'rows': len(result['rows']), 'exports_preserved': exports, 'active_outputs_read': False,
        'new_diagnostic_observations': result['session15_diagnostic_model_starts'], 'totals': result['totals']}
    save(execution / 'receipt.json', receipt)
    print(json.dumps({k:receipt[k] for k in ('passed','accounting','rows','prior_source_bindings_preserved','current_source_bindings','totals')}, indent=2))


if __name__ == '__main__':
    main()
