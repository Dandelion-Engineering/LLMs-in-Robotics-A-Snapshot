"""Stage the original passed Smoke025 evidence only; no assessment or publication."""
from pathlib import Path
import copy
import json
import re
import stage_append as s


def main():
    folder = s.STAGE / 'smoke025-drafts'
    gates = folder / 'official-draft-gates'
    gates.mkdir()
    jobs = {}
    job = s.authenticate({'run_id': 'RCI001-C02-smoke-025', 'status': 'passed',
        'queue': {'id': '20260929T040035554754Z-4e67aa65'}}, gates, jobs)
    original = s.HISTORY.read_bytes()
    s.require(s.sha(original) == 'bed5a7900692eaf4cb1c2dd9978a9de6947360182998a75b620a5059b19daf45',
              'Canonical113 changed')
    history = json.loads(original)
    s.require(len(history['attempts']) == 113, 'Wrong prior row count')
    prior = next(r for r in history['attempts'] if r['run_id'] == 'RCI001-C02-smoke-024')
    assessment_path = s.Q / 'smoke-025-assessment.json'
    disposition_path = s.LEDGER / 'smoke-025/disposition.json'
    s.require(s.bind(assessment_path)['sha256'] ==
              '5426faaa4de68d59923772d2c4bf8cfee5b1d846c4ef296e4fafa77118d988c7', 'Assessment changed')
    s.require(s.bind(disposition_path)['sha256'] ==
              '63adbaf688de543220ef80a896ff8de9069e3a860e5524c9cc46f0a67b33d04e', 'Disposition changed')
    assessment, disposition = s.read(assessment_path), s.read(disposition_path)
    s.require(assessment['run_id'] == disposition['run_id'] == 'RCI001-C02-smoke-025'
              and assessment['framework_revision'] == 'RCI001-C02-dev-086'
              and assessment['smoke_passed'] is True and disposition['passed'] is True
              and disposition['error'] is None and assessment['verification_errors'] == {}
              and len(assessment['checks']) == 62
              and all(v is True for v in assessment['checks'].values()), 'Original Smoke025 pass differs')
    for item in [*disposition['entry'].values(), disposition['registered_result']]:
        if isinstance(item, dict) and 'path' in item:
            s.require(s.bind(item['path'])['sha256'] == item['sha256'], 'Disposition entry changed')
    queue = s.read(disposition['entry']['queue']['path'])
    queue = queue.get('job', queue)
    s.require(all(queue.get(k) == job.get(k) for k in
              ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd')),
              'Original receipt differs from fresh official metadata')

    replacements = {'smoke-024': 'smoke-025', 'dev-082': 'dev-086', 'dev082': 'dev086',
                    'final-qualification-026': 'final-qualification-027', 'v26': 'v27',
                    'failed': 'passed', 'invalid': 'valid'}
    pattern = re.compile('|'.join(map(re.escape, replacements)))
    def remap(text):
        return pattern.sub(lambda m: replacements[m.group()], text)
    def artifact(path, label):
        return {'label': label, **s.bind(path)}
    # A running coordinator has no terminal receipt. Prior failed-row evidence is not reused as a pass.
    omitted = [a for a in prior['artifacts'] if Path(a['path']).name == 'coordinator-launch-receipt.json']
    s.require(len(omitted) == 1, 'Expected one historical stopped-coordinator artifact')
    artifacts = [artifact(remap(a['path']), remap(a['label'])) for a in prior['artifacts'] if a not in omitted]
    by_path = {a['path']: a for a in artifacts}
    frozen = s.read(disposition['entry']['snapshot']['path'])
    for name in s.METHODS:
        path = s.IO / name
        item = artifact(path, 'Frozen method: ' + name)
        s.require(frozen['sources'].get(path.relative_to(s.REPO).as_posix()) ==
                  {k: item[k] for k in ('sha256', 'bytes')}, 'Method is not frozen')
        if item['path'] not in by_path:
            artifacts.append(item)
            by_path[item['path']] = item
    for path, digest in assessment['evidence_sha256'].items():
        if path not in by_path:
            item = artifact(path, 'Original smoke assessment input: ' + Path(path).name)
            artifacts.append(item)
            by_path[path] = item
        s.require(by_path[path]['sha256'] == digest, 'Original assessed input changed')
    for invocation, proof in assessment['transport_lifecycle'].items():
        root = Path(disposition['entry']['evidence']) / invocation
        s.require(proof['passed'] is True, 'Lifecycle proof did not pass')
        for relative, binding in proof['input_bindings'].items():
            path = str(root / relative)
            if path not in by_path:
                item = artifact(path, invocation + ' source-bound transport proof input: ' + relative)
                artifacts.append(item)
                by_path[path] = item
            s.require(all(by_path[path][k] == binding[k] for k in ('sha256', 'bytes')),
                      'Original lifecycle input binding differs')
    timing = assessment['campaign_timing']
    details = {'raw_smoke_passed': True, 'admission_passed': True, 'admission_error': None,
        'failed_checks': [], 'checks_passed': 62, 'checks_total': 62,
        'timing': {k: timing['replayed_timing'][k] for k in
                   ('maximum_lag_s', 'maximum_timing_sample_gap_s', 'complete_wall_windows',
                    'outside_rtf_tolerance_windows', 'outside_rtf_tolerance_fraction')},
        'resource_gates': {k: timing[k] for k in
                           ('passed', 'resource_integrity_pass', 'garbage_collection_pass', 'host_memory_pass')},
        'transport_passed_by_invocation': {k: v['passed'] for k, v in assessment['transport'].items()},
        'transport_lifecycle_passed_by_invocation':
            {k: v['passed'] for k, v in assessment['transport_lifecycle'].items()},
        'verification_errors': assessment['verification_errors'],
        'original_assessor_source_bindings': {
            (s.C / 'assessment/assess.py').relative_to(s.REPO).as_posix(): assessment['base_assessment_sha256'],
            (s.C / 'assessment/assess_smoke_v2.py').relative_to(s.REPO).as_posix(): assessment['assessment_code_sha256']},
        'startup_verified': {stage: {name: value['verified'] for name, value in data.items()}
                             for stage, data in assessment['startup_read_evidence'].items()},
        'scope': assessment['scope']}
    s.require(all(assessment['checks'][stage + ':actual_model_started'] is True
                  for stage in ('interrupt', 'resume')), 'Two model starts not established')
    row = {'run_id': 'RCI001-C02-smoke-025', 'revision': 'RCI001-C02-dev-086', 'status': 'passed',
        'reason': 'Smoke025 passed all 62 original independent smoke checks and source-bound V27 admission under '
                  'dev086, with no verification errors. Both fresh model invocations passed startup/read, canary, '
                  'transport, lifecycle, timing and cleanup checks. This is the declared safe-action interruption '
                  'and continuity smoke; stock recovery was intentionally unattempted. It is not scored recovery '
                  'performance or complete campaign admission. Every earlier verdict remains unchanged.',
        'scorable': False, 'validity': 'apparatus_checks_passed', 'task_outcome': 'unknown', 'model_calls': 2,
        'queue': {k: job[k] for k in ('id', 'state', 'exit_status', 'started_at', 'ended_at')},
        'details': details, 'admission_disposition': by_path[str(disposition_path)], 'artifacts': artifacts}
    status = copy.deepcopy(history['current_status'])
    status.update(state='qualification_in_progress', as_of=s.now(), basis_run_id=row['run_id'],
        basis_assessment_sha256=s.bind(assessment_path)['sha256'],
        summary='V27 Smoke025 passed its original independent 62/62 smoke checks and final stage admission. '
                'It is the latest completed model and generic qualifier. Native026 and Boundary027 remain passed. '
                'Pilot Stock024 is active according to retained submission metadata; its empirical outputs are '
                'unread. Both pilots and full scored campaign admission remain incomplete.',
        engineering_context='The source-bound smoke pass is retained in its declared safe-action/interruption '
                            'scope. It does not establish stock recovery performance or reinterpret earlier failed '
                            'lineages. No scored attempt has started.')
    submit_path = s.Q / 'RCI001-C02-pilot-stock-024/queue-submit.json'
    active = s.read(submit_path)
    active = active.get('job', active)
    s.require(active['id'] == '20260929T041418803542Z-2f3b6425', 'Wrong pilot submission metadata')
    submit = artifact(submit_path, 'Pilot Stock024 submission metadata only')
    lineage = status['active_lineage']
    lineage.update(state='v27_smoke025_passed_pilot_stock024_pending_independent_assessment',
        latest_model_qualifier=row['run_id'], completed_qualifiers=[
            'RCI001-C02-native-026', 'RCI001-C02-boundary-027', row['run_id']],
        active_qualifier={'run_id': 'RCI001-C02-pilot-stock-024', 'revision': 'RCI001-C02-dev-086',
            'job_id': active['id'], 'queue_state_at_submission': active['state'],
            'submitted_at': active['submitted_at'], 'started_at': active['started_at'],
            'assessment_state': 'pending_unread', 'empirical_outputs_read': False,
            'queue_submission_receipt': submit})
    existing = {item['path'] for item in status['artifacts']}
    for item in [*artifacts, submit]:
        if item['path'] not in existing:
            status['artifacts'].append(item)
            existing.add(item['path'])
    draft = s.save(folder / 'smoke-025-row.json', row)
    prep = s.save(folder / 'preparation-receipt.json', {
        'schema': 'campaign002-history-draft-preparation-1', 'at': s.now(),
        'fresh_official_gate': s.bind(next(gates.glob('*.json'))), 'source': s.bind(__file__),
        'prior_history': s.bind(s.HISTORY), 'template_run_id': prior['run_id'], 'draft': draft,
        'historical_stopped_coordinator_not_applicable': omitted,
        'active_submission_only': submit, 'active_outputs_read': False,
        'outcomes_recomputed': False, 'canonical_history_written': False})
    plan = {'schema': s.PLAN_SCHEMA, 'coordinator': 'run_final_qualification_v27.py',
        'ledger': 'final-qualification-027', 'expected_history_sha256': s.sha(original),
        'expected_rows_before': 113, 'rows': [row], 'current_status': status,
        'staging_correction': prep}
    binding = s.save(s.STAGE / 'smoke025-plan-001.json', plan)
    s.require(s.HISTORY.read_bytes() == original, 'Concurrent canonical mutation')
    print(json.dumps({'plan': binding, 'artifacts': len(artifacts), 'checks_passed': 62,
                      'canonical_written': False, 'active_outputs_read': False}, indent=2))


if __name__ == '__main__':
    main()
