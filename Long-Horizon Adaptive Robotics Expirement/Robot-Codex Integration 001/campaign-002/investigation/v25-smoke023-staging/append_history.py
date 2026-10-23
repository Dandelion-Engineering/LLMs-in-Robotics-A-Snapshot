"""Retain Smoke023's original failed qualification; never rerun its assessor."""
from pathlib import Path
import copy
import datetime
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
EXPECTED_HISTORY = '52b46149fc076cd145f0dfe1253eb29af1b255c12a409c94a8518de5e14a75c2'
EXPECTED_ASSESSMENT = 'aa0b4ceb104e4cefd6d8bac1d0fca424ae555401e7d8a3dcd2846ab0b745c733'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


helper = module('smoke023_append_helpers', I / 'v25-append-staging/stage_append.py')
bind, read, sha, raw_rows = helper.bind, helper.read, helper.sha, helper.raw_rows


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as file:
        json.dump(value, file, indent=2, ensure_ascii=False, allow_nan=False)
        file.write('\n')
    return bind(path)


def main():
    prior = HISTORY.read_bytes()
    assert sha(prior) == EXPECTED_HISTORY
    history = json.loads(prior)
    text, spans, _ = raw_rows(prior)
    assert len(spans) == 101
    with (S / 'prior-history.json').open('xb') as file:
        file.write(prior)
    exports = read(I / 'qualification-history-append-v25-native-boundary-receipt.json')['exports_before_and_after']
    assert len(exports) == 19 and [bind(value['path']) for value in exports] == exports
    auth = read(S / 'official-auth.json')
    job = auth['official']
    assert auth['exit_code'] == 0 and job['id'] == '20260929T014234165833Z-cba1e8b0'
    assert job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
    assessment_path = Q / 'smoke-023-assessment.json'
    assert bind(assessment_path)['sha256'] == EXPECTED_ASSESSMENT
    assessment = read(assessment_path)
    failed = [key for key, value in assessment['checks'].items() if value is not True]
    assert assessment['smoke_passed'] is False and len(assessment['checks']) == 62
    assert failed == ['transport_revocation_and_reply_provenance', 'both_models_read_fixed_startup_and_initial_continuity_bytes', 'resume:all_45_model_canaries_saved']
    assert assessment['checks']['two_fresh_model_threads'] is True
    assert assessment['checks']['interrupt:actual_model_started'] is True and assessment['checks']['resume:actual_model_started'] is True
    disposition_path = Q / 'final-qualification-025/smoke-023/disposition.json'
    disposition = read(disposition_path)
    assert disposition['run_id'] == 'RCI001-C02-smoke-023' and disposition['passed'] is False
    for value in list(disposition['entry'].values()) + [disposition['registered_result']]:
        if isinstance(value, dict) and {'path', 'sha256'} <= set(value):
            assert bind(value['path'])['sha256'] == value['sha256']
    stored = read(disposition['entry']['queue']['path']); stored = stored.get('job', stored)
    assert all(stored[key] == job[key] for key in ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd'))
    snapshot = read(disposition['entry']['snapshot']['path'])
    assert snapshot['revision'] == 'RCI001-C02-dev-078'
    coordinator_path = Q / 'final-qualification-025/coordinator-launch-receipt.json'
    assert read(coordinator_path)['exit_code'] == 1
    pilots = ['RCI001-C02-pilot-stock-022', 'RCI001-C02-pilot-home-022']
    assert all(not (Q / rid / 'queue-submit.json').exists() for rid in pilots)
    save(S / 'intent.json', {'schema': 'campaign002-history-append-intent-1', 'at': NOW,
        'prior_history': bind(HISTORY), 'fresh_official_authentication': bind(S / 'official-auth.json'),
        'original_assessment': bind(assessment_path), 'original_disposition': bind(disposition_path),
        'prior_raw_row_sha256': [{'run_id': rid, 'sha256': sha(raw)} for rid, raw, *_ in spans],
        'exports_before': exports,
        'scope': 'One original failed assessed smoke row only; no assessment replay, coordinator restart, pilots, scoring or export rebuild.'})

    row = copy.deepcopy(next(value for value in history['attempts'] if value['run_id'] == 'RCI001-C02-smoke-022'))
    row['run_id'] = 'RCI001-C02-smoke-023'
    row['revision'] = 'RCI001-C02-dev-078'
    row['queue'] = {key: job[key] for key in ('id', 'state', 'exit_status', 'started_at', 'ended_at')}
    row['reason'] = ('Smoke023 completed through the official queue under dev078, but its original independent assessment and final admission failed three of 62 checks: transport revocation/reply provenance, fixed startup/initial Continuity read evidence, and all 45 retained resume canaries. '
                     'Both initial Continuity reads and all interrupt startup reads passed; resume Tasks.md and Robot.md remained unverified while Tools.md passed. '
                     'The original transport error is "Unresolved transport failure: mirror-error.json" for interrupt. Its cause is not inferred here. '
                     'The original 59/62 verdict remains failed, validity invalid and task outcome unknown. V25 stopped with exit1; both pilot022 stages were not launched.')
    timing = assessment['campaign_timing']
    row['details'] = {
        'raw_smoke_passed': False, 'admission_passed': False, 'admission_error': disposition['error'],
        'failed_checks': failed, 'checks_passed': 59, 'checks_total': 62,
        'timing': {key: timing['replayed_timing'][key] for key in ('maximum_lag_s', 'maximum_timing_sample_gap_s', 'complete_wall_windows', 'outside_rtf_tolerance_windows', 'outside_rtf_tolerance_fraction')},
        'resource_gates': {key: timing[key] for key in ('passed', 'resource_integrity_pass', 'garbage_collection_pass', 'host_memory_pass')},
        'transport_passed_by_invocation': {name: None if value is None else value['passed'] for name, value in assessment['transport'].items()},
        'transport_lifecycle_passed_by_invocation': {name: value['passed'] for name, value in assessment['transport_lifecycle'].items()},
        'verification_errors': assessment['verification_errors'],
        'original_assessor_source_bindings': {name: value['sha256'] for name, value in snapshot['sources'].items() if name.endswith('/assessment/assess.py') or name.endswith('/assessment/assess_smoke_v2.py')},
        'downstream_stages_not_launched': pilots, 'diagnosis_state': 'separate_infrastructure_investigation',
        'startup_verified': {name: {path: proof['verified'] for path, proof in values.items()} for name, values in assessment['startup_read_evidence'].items()},
    }
    artifacts = []
    replacements = [('smoke-022', 'smoke-023'), ('dev-074', 'dev-078'), ('dev074', 'dev078'),
                    ('final-qualification-024', 'final-qualification-025'), ('v24', 'v25'), ('V24', 'V25')]
    for item in row['artifacts']:
        path, label = item['path'], item['label']
        for old, new in replacements:
            path, label = path.replace(old, new), label.replace(old, new)
        artifacts.append(bind(path, label))
    artifacts.append(bind(IO / 'PREPARED_STARTUP_SEGMENTS_V1.md', 'Frozen method: PREPARED_STARTUP_SEGMENTS_V1.md'))
    with zipfile.ZipFile(Path(disposition['entry']['snapshot']['path']).with_name('code.zip')) as archive:
        for item in artifacts:
            path = Path(item['path'])
            if path.suffix == '.md' and path.parent == IO:
                name = path.relative_to(REPO).as_posix(); frozen = snapshot['sources'][name]
                assert all(frozen[key] == item[key] for key in ('sha256', 'bytes'))
                assert sha(archive.read(name)) == item['sha256']
    assert len({item['path'] for item in artifacts}) == len(artifacts)
    row['artifacts'] = artifacts
    row['admission_disposition'] = bind(disposition_path, 'Original failed final smoke admission disposition')
    save(S / 'row.json', row)

    status = copy.deepcopy(history['current_status'])
    status.update(state='qualification_failed_blocked', as_of=NOW, basis_run_id=row['run_id'], basis_assessment_sha256=EXPECTED_ASSESSMENT)
    status['summary'] = ('V25 stopped after Smoke023 completed through the official queue but failed its original independent assessment and admission (59 of 62 checks passed). '
                         'The failed checks concern interrupt transport provenance, fixed startup-read evidence and retained resume canaries. Native024 and Boundary025 retain their passing reference verdicts. '
                         'Both pilot022 stages were not launched; full qualification and scored admission remain incomplete. Smoke023 is invalid with task outcome unknown.')
    status['engineering_context'] = ('Both initial Continuity reads and all interrupt startup reads passed. Resume Tasks.md and Robot.md remained unverified; Tools.md passed. '
                                     'The interrupt transport verifier retained an unresolved mirror-error.json failure. Timing and lifecycle checks that passed do not override these failures. '
                                     'Further diagnosis is separate from the original verdict; no restart or retroactive upgrade occurred.')
    lineage = status['active_lineage']
    lineage.update(state='v25_failed_smoke023_independent_assessment_settled', latest_model_qualifier=row['run_id'], active_qualifier=None,
                   final_qualification_completed=False, scientific_admission=False, scored_attempts_started=0,
                   unlaunched_pilot_allocations=pilots, downstream_not_launched=pilots, coordinator_exit_status_reported=1)
    lineage['failed_qualifier'] = {'run_id': row['run_id'], 'revision': row['revision'], 'queue': row['queue'],
        'assessment_state': 'assessed_failed', 'assessment': bind(assessment_path, 'Original failed Smoke023 assessment'),
        'admission_disposition': row['admission_disposition'], 'task_outcome': 'unknown'}
    lineage['coordinator_receipt'] = bind(coordinator_path, 'Original stopped V25 coordinator receipt')
    lineage['smoke_resume_invocation_attempted'] = True
    lineage['coordinator_restart_attempted'] = False
    for item in [row['admission_disposition'], bind(assessment_path, 'Original failed Smoke023 assessment'), lineage['coordinator_receipt']]:
        assert not any(value['path'] == item['path'] for value in status['artifacts'])
        status['artifacts'].append(item)
    insertion = ',\n    ' + json.dumps(row, indent=2, ensure_ascii=False).replace('\n', '\n    ')
    candidate = text[:spans[-1][3]] + insertion + text[spans[-1][3]:]
    old_time = '"updated_at": ' + json.dumps(history['updated_at'])
    assert candidate.count(old_time) == 1
    candidate = candidate.replace(old_time, '"updated_at": ' + json.dumps(NOW), 1)
    marker = '"current_status": '; assert candidate.count(marker) == 1
    start = candidate.index(marker) + len(marker); _, end = json.JSONDecoder().raw_decode(candidate, start)
    candidate = (candidate[:start] + json.dumps(status, indent=2, ensure_ascii=False).replace('\n', '\n  ') + candidate[end:]).encode('utf-8')
    new_history = json.loads(candidate)
    _, new_spans, _ = raw_rows(candidate)
    assert len(new_spans) == 102 and [(rid, raw) for rid, raw, *_ in new_spans[:101]] == [(rid, raw) for rid, raw, *_ in spans]
    with (S / 'candidate-history.json').open('xb') as file:
        file.write(candidate)

    report = module('smoke023_history_report', I / 'qualification_report.py')
    qa = module('smoke023_history_qa', I / 'qualification_qa.py')
    rendered = [report.qualification_row(value, I) for value in new_history['attempts']]
    for value in rendered:
        if value.get('diagnostic_result') is not None: qa.no_model_diagnostic_guard(value, I)
        elif value.get('host_prerequisite') is not None: qa.host_prerequisite_guard(value, I)
        elif value.get('queue_failure') is not None: qa.failed_queue_guard(value, I)
    inventory = report.launch_inventory(C, I)
    current = report.current_status_detail(status, rendered, new_history, inventory, C, I)
    assert current['basis_run_id'] == report.latest_completed_qualifier(rendered)['run_id'] == row['run_id']
    assert rendered[-1]['failed_checks'] == failed and rendered[-1]['assessment_errors'] == assessment['verification_errors']
    assert inventory['entries'] == [] and inventory['registration'] is None
    assert HISTORY.read_bytes() == prior and [bind(value['path']) for value in exports] == exports
    validation = {'schema': 'campaign002-history-current-status-qa-1', 'at': NOW, 'passed': True,
        'candidate_history': bind(S / 'candidate-history.json'), 'history_rows': 102, 'prior_raw_rows_preserved': 101,
        'new_rows_verified': [row['run_id']], 'current_qualification_basis': row['run_id'], 'latest_model_qualifier': row['run_id'],
        'scored_launch_inventory': inventory, 'active_qualifier': None,
        'link_counts': {'rendered_row_link_occurrences': sum(len(value['links']) + len(value.get('diagnostic_links', [])) for value in rendered),
                        'current_status_artifact_occurrences': len(status['artifacts']), 'preserved_export_file_bindings': 19,
                        'definition': 'Occurrence counts in separate scopes; not unique paths. Row links exclude current-status context and export bindings.'},
        'outcomes_recomputed': False, 'exports_rebuilt': False, 'preserved_exports': exports,
        'source_helpers': [bind(I / 'qualification_report.py'), bind(I / 'qualification_qa.py')], 'authenticated_reader_inputs': report.READS}
    save(S / 'qa.json', validation)
    save(S / 'publish-intent.json', {'prior_history': bind(HISTORY), 'candidate_history': bind(S / 'candidate-history.json'), 'qa': bind(S / 'qa.json')})
    temp = I / 'qualification-history-v25-smoke023-publish.tmp'
    with temp.open('xb') as file:
        file.write(candidate); file.flush(); os.fsync(file.fileno())
    assert HISTORY.read_bytes() == prior
    os.replace(temp, HISTORY)
    assert HISTORY.read_bytes() == candidate and [bind(value['path']) for value in exports] == exports
    validation['history'] = bind(HISTORY); validation['canonical_history_matches_validated_candidate'] = True
    qa_binding = save(I / 'qualification-history-append-smoke023-qa.json', validation)
    receipt = {'schema': 'campaign002-history-append-receipt-1', 'at': NOW,
        'history_before': bind(S / 'prior-history.json'), 'history_after': bind(HISTORY), 'rows_before': 101, 'rows_after': 102,
        'prior_raw_rows_preserved': 101, 'appended': [{'run_id': rid, 'sha256': sha(raw), 'bytes': len(raw)} for rid, raw, *_ in new_spans[101:]],
        'official_authentication': bind(S / 'official-auth.json'), 'qa': qa_binding, 'source': bind(Path(__file__)),
        'exports_before_and_after': exports, 'link_counts': validation['link_counts'], 'original_assessment_sha256': EXPECTED_ASSESSMENT,
        'latest_model_qualifier': row['run_id'], 'current_qualification_basis': row['run_id'],
        'outcomes_recomputed': False, 'exports_rebuilt': False, 'accounting_mutated': False, 'map_mutated': False}
    receipt_binding = save(I / 'qualification-history-append-smoke023-receipt.json', receipt)
    print(json.dumps({'history': bind(HISTORY), 'receipt': receipt_binding, 'qa': qa_binding, 'counts': validation['link_counts']}, indent=2))


if __name__ == '__main__':
    main()
