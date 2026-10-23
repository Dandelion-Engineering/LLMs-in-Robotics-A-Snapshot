"""Append only authenticated Native024 and Boundary025 history metadata."""
from pathlib import Path
import copy
import datetime
import hashlib
import importlib.util
import json
import os
import sys
import zipfile

S = Path(__file__).resolve().parent
I = S.parent
C = I.parent
Q = C / 'qualification'
IO = C / 'io-repair'
REPO = C.parents[2]
HISTORY = I / 'qualification-history.json'
EXPECTED = 'f4914439b7697d41ac182a681e7c1605e893380b3361dee2c055c6a51c8ba6ac'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


helper = load_module('v25_append_prior_helpers', I / 'v25-append-staging/stage_append.py')
bind, raw_rows, read, sha = helper.bind, helper.raw_rows, helper.read, helper.sha


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as file:
        json.dump(value, file, indent=2, ensure_ascii=False, allow_nan=False)
        file.write('\n')
    return bind(path)


def main():
    prior = HISTORY.read_bytes()
    assert sha(prior) == EXPECTED
    history = json.loads(prior)
    text, spans, _ = raw_rows(prior)
    assert len(spans) == 99
    with (S / 'prior-history.json').open('xb') as file:
        file.write(prior)
    exports = read(I / 'qualification-history-append-v25-prerequisites-receipt.json')['exports_before_and_after']
    assert len(exports) == 19 and [bind(value['path']) for value in exports] == exports
    save(S / 'intent.json', {'schema': 'campaign002-history-append-intent-1', 'at': NOW,
        'prior_history': bind(HISTORY), 'prior_raw_row_sha256': [{'run_id': rid, 'sha256': sha(raw)} for rid, raw, *_ in spans],
        'append_only': ['RCI001-C02-native-024', 'RCI001-C02-boundary-025'],
        'scope': 'Two terminal qualification rows only; no active Smoke023 output access, report build, accounting or map mutation.',
        'exports_before': exports,
        'fresh_official_authentication': [bind(S / (name + '-official.json')) for name in ('native024', 'boundary025')]})

    rows = []
    assessments = []
    for old_short, short, old_rev, rev, auth in [
        ('native-023', 'native-024', '072', '076', 'native024'),
        ('boundary-024', 'boundary-025', '073', '077', 'boundary025'),
    ]:
        job = read(S / (auth + '-official.json'))['official']
        assert job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
        rid = 'RCI001-C02-' + short
        disposition_path = Q / 'final-qualification-025' / short / 'disposition.json'
        disposition = read(disposition_path)
        assert disposition['run_id'] == rid and disposition['passed'] is True and disposition['error'] is None
        for value in list(disposition['entry'].values()) + [disposition['registered_result']]:
            if isinstance(value, dict) and {'path', 'sha256'} <= set(value):
                assert bind(value['path'])['sha256'] == value['sha256']
        snapshot = read(disposition['entry']['snapshot']['path'])
        assert snapshot['revision'] == 'RCI001-C02-dev-' + rev
        stored = read(disposition['entry']['queue']['path']); stored = stored.get('job', stored)
        assert all(stored[key] == job[key] for key in ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd'))
        row = copy.deepcopy(next(value for value in history['attempts'] if value['run_id'] == 'RCI001-C02-' + old_short))
        row['run_id'] = rid
        row['revision'] = snapshot['revision']
        row['queue'] = {key: job[key] for key in ('id', 'state', 'exit_status', 'started_at', 'ended_at')}
        replacements = [(old_short, short), ('RCI001-C02-dev-' + old_rev, row['revision']),
                        ('dev' + old_rev, 'dev' + rev), ('final-qualification-024', 'final-qualification-025'), ('V24', 'V25')]
        artifacts = []
        for item in row['artifacts']:
            path, label = item['path'], item['label']
            for old, new in replacements:
                path, label = path.replace(old, new), label.replace(old, new)
            artifacts.append(bind(path, label))
        artifacts.append(bind(IO / 'PREPARED_STARTUP_SEGMENTS_V1.md', 'Frozen stage method: PREPARED_STARTUP_SEGMENTS_V1.md'))
        with zipfile.ZipFile(Path(disposition['entry']['snapshot']['path']).with_name('code.zip')) as archive:
            for item in artifacts:
                path = Path(item['path'])
                if path.suffix == '.md' and path.parent == IO:
                    name = path.relative_to(REPO).as_posix()
                    frozen = snapshot['sources'].get(name)
                    item['label'] = ('Frozen stage method: ' if frozen else 'Context outside this stage snapshot: ') + path.name
                    if frozen:
                        assert all(frozen[key] == item[key] for key in ('sha256', 'bytes'))
                        assert sha(archive.read(name)) == item['sha256']
        assert len({value['path'] for value in artifacts}) == len(artifacts)
        row['artifacts'] = artifacts
        row['admission_disposition'] = bind(disposition_path, row['admission_disposition']['label'])
        assessment = read(disposition['entry']['assessment']['path'])
        if short.startswith('native'):
            assert disposition['entry']['assessment']['sha256'] == '2a1eb913c1d90f05aa41bfccdff7262119ab94d1f4a8bb934ff7a6965ba15772'
            assert assessment['qualification_passed'] is True and len(assessment['rows']) == 6
            cases = []
            for case in assessment['rows']:
                assert case['passed'] is True and case['errors'] == {} and all(v is True for v in case['checks'].values())
                timing = case['timing']['replayed_timing']
                cases.append({'run_id': case['run_id'], 'family': case['family'], 'passed': True,
                    'observed_reference_task_outcome': case['independent_outcome']['independent_task_outcome'],
                    **{key: timing[key] for key in ('maximum_lag_s', 'maximum_timing_sample_gap_s', 'complete_wall_windows', 'outside_rtf_tolerance_windows')},
                    'resource_integrity_pass': case['timing']['resource_integrity_pass']})
            checks = sum(len(case['checks']) for case in assessment['rows'])
            row['details'] = {'reference_cases': 6, 'checks_passed': checks, 'failed_checks': [], 'cases': cases, 'admission_passed': True}
            row['reason'] = (f'All six fresh native reference cases passed the original independent apparatus assessment and source-bound V25 admission under dev{rev}. '
                             f'All {checks} reference checks and resource gates passed. These no-model controls do not establish model recovery performance, reverse earlier failures or complete scored campaign admission.')
        else:
            assert assessment['qualified'] is True and len(assessment['checks']) == 12 and all(v is True for v in assessment['checks'].values())
            before = read(Path(disposition['entry']['evidence']) / 'source-binding-before.json')
            after = read(Path(disposition['entry']['evidence']) / 'source-binding-after.json')
            assert before == after
            assert all(snapshot['sources'][path]['sha256'] == value for path, value in before.items())
            row['details'] = {'raw_suite_qualified': True, 'raw_checks_passed': 12, 'admission_passed': True,
                'measured_source_count': len(before), 'before_after_sources_identical': True,
                'snapshot_source_count': len(snapshot['sources']), 'all_measured_sources_bound': True}
            row['reason'] = (f'Fresh Boundary025 passed all 12 original isolated boundary/lifecycle checks and source-bound V25 admission under dev{rev}. '
                             f'All {len(before)} measured before/after source identities matched the {len(snapshot["sources"])}-source frozen snapshot. '
                             'These no-model checks do not establish a model-stage outcome or full campaign admission. Earlier attempts retain their original verdicts.')
        save(S / (short + '-row.json'), row)
        rows.append(row)
        assessments.append(disposition['entry']['assessment'])

    status = copy.deepcopy(history['current_status'])
    status['as_of'] = NOW
    status['basis_run_id'] = rows[-1]['run_id']
    status['basis_assessment_sha256'] = assessments[-1]['sha256']
    status['summary'] = ('V25 Native024 and Boundary025 passed their original independent checks and source-bound admission after the three no-model prerequisites. '
                         'Smoke023 is active according to its retained submission metadata; its empirical outputs remain unopened. Smoke022 remains the latest completed model qualifier with its original failed verdict. '
                         'Both pilot022 stages and scored admission remain pending.')
    lineage = status['active_lineage']
    lineage['state'] = 'v25_native024_boundary025_passed_smoke023_pending_independent_assessment'
    lineage['completed_qualifiers'] = [{key: row[key] for key in ('run_id', 'revision', 'queue', 'admission_disposition')} for row in rows]
    submitted_path = Q / 'RCI001-C02-smoke-023/queue-submit.json'
    active = read(submitted_path); active = active.get('job', active)
    assert active['id'] == '20260929T014234165833Z-cba1e8b0' and active['state'] == 'running'
    lineage['active_qualifier'] = {'run_id': 'RCI001-C02-smoke-023', 'revision': 'RCI001-C02-dev-078',
        'job_id': active['id'], 'queue_state_at_submission': active['state'], 'submitted_at': active['submitted_at'],
        'started_at': active['started_at'], 'assessment_state': 'pending_unread', 'empirical_outputs_read': False,
        'queue_submission_receipt': bind(submitted_path, 'Smoke023 submission metadata only')}
    lineage['latest_model_qualifier'] = 'RCI001-C02-smoke-022'
    for row in rows:
        status['artifacts'].append(row['admission_disposition'])

    insertion = ',\n' + ',\n'.join('    ' + json.dumps(row, indent=2, ensure_ascii=False).replace('\n', '\n    ') for row in rows)
    candidate = text[:spans[-1][3]] + insertion + text[spans[-1][3]:]
    old_time = '"updated_at": ' + json.dumps(history['updated_at'])
    assert candidate.count(old_time) == 1
    candidate = candidate.replace(old_time, '"updated_at": ' + json.dumps(NOW), 1)
    marker = '"current_status": '
    assert candidate.count(marker) == 1
    start = candidate.index(marker) + len(marker)
    _, end = json.JSONDecoder().raw_decode(candidate, start)
    candidate = (candidate[:start] + json.dumps(status, indent=2, ensure_ascii=False).replace('\n', '\n  ') + candidate[end:]).encode('utf-8')
    new_history = json.loads(candidate)
    _, new_spans, _ = raw_rows(candidate)
    assert len(new_spans) == 101 and [(rid, raw) for rid, raw, *_ in spans] == [(rid, raw) for rid, raw, *_ in new_spans[:99]]
    with (S / 'candidate-history.json').open('xb') as file:
        file.write(candidate)

    report = load_module('v25_final_history_report', I / 'qualification_report.py')
    qa = load_module('v25_final_history_qa', I / 'qualification_qa.py')
    rendered = [report.qualification_row(row, I) for row in new_history['attempts']]
    for row in rendered:
        if row.get('diagnostic_result') is not None:
            qa.no_model_diagnostic_guard(row, I)
        elif row.get('host_prerequisite') is not None:
            qa.host_prerequisite_guard(row, I)
        elif row.get('queue_failure') is not None:
            qa.failed_queue_guard(row, I)
    inventory = report.launch_inventory(C, I)
    current = report.current_status_detail(status, rendered, new_history, inventory, C, I)
    assert current['basis_run_id'] == report.latest_completed_qualifier(rendered)['run_id'] == 'RCI001-C02-boundary-025'
    assert inventory['entries'] == [] and inventory['registration'] is None
    assert all('RCI001-C02-smoke-023' not in value['path'] for value in report.READS)
    assert HISTORY.read_bytes() == prior and [bind(value['path']) for value in exports] == exports
    old96 = read(I / 'v25-append-staging/prior-history.json')
    def counts(index, rendered_rows):
        return {'history_rows': len(index['attempts']),
            'indexed_artifact_occurrences': sum(len(row.get('artifacts', [])) for row in index['attempts']),
            'indexed_diagnostic_link_occurrences': sum(len(row.get('diagnostic_analyses', [])) for row in index['attempts']),
            'rendered_row_link_occurrences': sum(len(row['links']) + len(row.get('diagnostic_links', [])) for row in rendered_rows),
            'current_status_artifact_occurrences': len(index['current_status']['artifacts']),
            'preserved_export_file_bindings': len(exports)}
    comparison = {'prior96': counts(old96, rendered[:96]), 'prerequisite99': counts(history, rendered[:99]),
                  'current101': counts(new_history, rendered),
                  'definitions': {'rendered_row_link_occurrences': 'Per-history-row links plus diagnostic_links, counted by occurrence; excludes current-status context and retained exports; not a unique-path count.',
                                  'historical_2027_reconciliation': '96-row rendered links + current-status artifact occurrences + 19 preserved export bindings; the old receipt is not rewritten.'}}
    prior_count = comparison['prior96']
    assert prior_count['rendered_row_link_occurrences'] + prior_count['current_status_artifact_occurrences'] + 19 == 2027
    assert comparison['prerequisite99']['rendered_row_link_occurrences'] == 1954
    comparison['prior_smoke022_qa'] = bind(I / 'qualification-history-append-smoke022-qa.json')
    comparison['prerequisite99_qa'] = bind(I / 'qualification-history-append-v25-prerequisites-qa.json')
    count_binding = save(S / 'link-count-reconciliation.json', comparison)
    validation = {'schema': 'campaign002-history-current-status-qa-1', 'at': NOW, 'passed': True,
        'candidate_history': bind(S / 'candidate-history.json'), 'history_rows': 101, 'prior_raw_rows_preserved': 99,
        'new_rows_verified': [row['run_id'] for row in rows], 'current_qualification_basis': current['basis_run_id'],
        'latest_model_qualifier': 'RCI001-C02-smoke-022', 'active_qualifier_metadata_only': lineage['active_qualifier'],
        'scored_launch_inventory': inventory, 'link_counts': comparison['current101'], 'count_reconciliation': count_binding,
        'active_outputs_read': False, 'outcomes_recomputed': False, 'exports_rebuilt': False,
        'preserved_exports': exports, 'source_helpers': [bind(I / 'qualification_report.py'), bind(I / 'qualification_qa.py')],
        'authenticated_reader_inputs': report.READS}
    save(S / 'qa.json', validation)
    save(S / 'publish-intent.json', {'prior_history': bind(HISTORY), 'candidate_history': bind(S / 'candidate-history.json'), 'qa': bind(S / 'qa.json')})
    temp = I / 'qualification-history-v25-final-stages-publish.tmp'
    with temp.open('xb') as file:
        file.write(candidate); file.flush(); os.fsync(file.fileno())
    assert HISTORY.read_bytes() == prior
    os.replace(temp, HISTORY)
    assert HISTORY.read_bytes() == candidate and [bind(value['path']) for value in exports] == exports
    validation['history'] = bind(HISTORY)
    validation['canonical_history_matches_validated_candidate'] = True
    qa_binding = save(I / 'qualification-history-append-v25-native-boundary-qa.json', validation)
    receipt = {'schema': 'campaign002-history-append-receipt-1', 'at': NOW, 'history_before': bind(S / 'prior-history.json'),
        'history_after': bind(HISTORY), 'rows_before': 99, 'rows_after': 101, 'prior_raw_rows_preserved': 99,
        'appended': [{'run_id': rid, 'sha256': sha(raw), 'bytes': len(raw)} for rid, raw, *_ in new_spans[99:]],
        'qa': qa_binding, 'link_count_reconciliation': count_binding, 'exports_before_and_after': exports,
        'fresh_official_authentication': [bind(S / (name + '-official.json')) for name in ('native024', 'boundary025')],
        'source': bind(Path(__file__)), 'current_qualification_basis': current['basis_run_id'],
        'latest_model_qualifier': 'RCI001-C02-smoke-022', 'active_qualifier_metadata_only': lineage['active_qualifier'],
        'active_outputs_read': False, 'exports_rebuilt': False, 'accounting_mutated': False, 'map_mutated': False}
    receipt_binding = save(I / 'qualification-history-append-v25-native-boundary-receipt.json', receipt)
    print(json.dumps({'history': bind(HISTORY), 'receipt': receipt_binding, 'qa': qa_binding, 'counts': comparison}, indent=2))


if __name__ == '__main__':
    main()
