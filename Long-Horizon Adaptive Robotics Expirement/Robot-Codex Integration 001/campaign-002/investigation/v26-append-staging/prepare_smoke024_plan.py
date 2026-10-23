"""Prepare the authorized single Smoke024 history draft; never publish."""
from pathlib import Path
import copy
import hashlib
import json
import subprocess
import sys
import stage_append as s


def main():
    folder = s.STAGE / 'smoke024-drafts'
    # Fresh official metadata precedes all outcome reads and hashes in this run.
    argv = [str(s.PYTHON), '-X', 'utf8', '-B', str(s.QUEUE), 'status',
            '20260929T030751715764Z-8ed12f73']
    start = s.now()
    p = subprocess.run(argv, cwd=s.REPO, capture_output=True, text=True, encoding='utf-8')
    auth = {'schema': 'campaign002-history-fresh-official-1', 'command': argv,
            'started_at': start, 'ended_at': s.now(), 'exit_code': p.returncode,
            'stdout': p.stdout, 'stderr': p.stderr}
    if p.returncode == 0:
        value = json.loads(p.stdout)
        auth['official'] = value.get('job', value)
    s.save(folder / 'official-plan-gate.json', auth)
    s.require(p.returncode == 0, 'Official query failed')
    job = auth['official']
    s.require(job['id'] == argv[-1] and job['state'] == 'succeeded'
              and type(job['exit_status']) is int and job['exit_status'] == 0,
              'No successful genuine-integer queue gate')
    original = s.HISTORY.read_bytes()
    s.require(s.sha(original) == '08c4031a2823ef9a465fe9a7d89fcc9c59b37811c1b61f98ee905a7d7bf32d04',
              'Canonical107 changed')
    history = json.loads(original)
    s.require(len(history['attempts']) == 107, 'Wrong prior row count')
    prior = next(r for r in history['attempts'] if r['run_id'] == 'RCI001-C02-smoke-023')
    assessment_path = s.Q / 'smoke-024-assessment.json'
    disposition_path = s.LEDGER / 'smoke-024/disposition.json'
    s.require(s.bind(assessment_path)['sha256'] ==
              '87896350f7eb8812531146427bd541fe2356efa3f986d437fdcd4e8fa02be013', 'Assessment changed')
    s.require(s.bind(disposition_path)['sha256'] ==
              'bec23fbe9448907767599c5efd1a9fa3a3e933697b2bfb76478ea5880ee34550', 'Disposition changed')
    assessment, disposition = s.read(assessment_path), s.read(disposition_path)
    queue = s.read(s.Q / 'smoke-024-queue.json')
    queue = queue.get('job', queue)
    s.require(all(queue.get(k) == job.get(k) for k in
              ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd')),
              'Original queue receipt differs from fresh official')
    failed = [k for k, v in assessment['checks'].items() if v is not True]
    s.require(assessment['smoke_passed'] is False and disposition['passed'] is False
              and failed == ['both_models_read_fixed_startup_and_initial_continuity_bytes']
              and len(assessment['checks']) == 62, 'Original verdict differs')

    def remap(value):
        return (value.replace('smoke-023', 'smoke-024').replace('dev-078', 'dev-082')
                .replace('dev078', 'dev082').replace('final-qualification-025', 'final-qualification-026')
                .replace('v25', 'v26'))

    def artifact(path, label):
        return {'label': label, **s.bind(path)}

    artifacts = [artifact(remap(item['path']), remap(item['label'])) for item in prior['artifacts']]
    snapshot = s.read(disposition['entry']['snapshot']['path'])
    for name in s.METHODS:
        path = s.IO / name
        item = artifact(path, 'Frozen method: ' + name)
        s.require(snapshot['sources'].get(path.relative_to(s.REPO).as_posix()) ==
                  {k: item[k] for k in ('sha256', 'bytes')}, 'Method not frozen in dev082')
        artifacts.append(item)
    by_path = {item['path']: item for item in artifacts}
    for path, digest in assessment['evidence_sha256'].items():
        s.require(path in by_path and by_path[path]['sha256'] == digest,
                  'Missing or mismatched original smoke evidence: ' + path)
    for invocation, proof in assessment['transport_lifecycle'].items():
        root = Path(disposition['entry']['evidence']) / invocation
        for relative, binding in proof['input_bindings'].items():
            item = by_path.get(str(root / relative))
            s.require(item and all(item[k] == binding[k] for k in ('sha256', 'bytes')),
                      'Original lifecycle input binding differs: ' + relative)
    timing = assessment['campaign_timing']
    details = {
        'raw_smoke_passed': False, 'admission_passed': False,
        'admission_error': disposition['error'], 'failed_checks': failed,
        'checks_passed': 61, 'checks_total': 62,
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
        'downstream_stages_not_launched': ['RCI001-C02-pilot-stock-023', 'RCI001-C02-pilot-home-023'],
        'diagnosis_state': 'separate_infrastructure_investigation',
        'startup_verified': {stage: {name: value['verified'] for name, value in data.items()}
                             for stage, data in assessment['startup_read_evidence'].items()}}
    s.require(all(assessment['checks'][stage + ':actual_model_started'] is True
                  for stage in ('interrupt', 'resume')), 'Two model starts not established')
    row = {'run_id': 'RCI001-C02-smoke-024', 'revision': 'RCI001-C02-dev-082', 'status': 'failed',
           'reason': ('Smoke024 completed through the official queue under dev082, but its original independent '
                      'assessment and final admission failed the fixed-startup/initial-Continuity read criterion. '
                      'The original 61/62 assessment has resume Tasks.md and Robot.md unverified; all interrupt '
                      'startup reads and both initial Continuity reads passed. Transport, lifecycle, canary and '
                      'timing checks passed. No cause is inferred here. V26 stopped with exit1; both pilot023 '
                      'stages were not launched. Qualification remains failed, validity invalid and task outcome unknown.'),
           'scorable': False, 'validity': 'invalid', 'task_outcome': 'unknown', 'model_calls': 2,
           'queue': {k: job[k] for k in ('id', 'state', 'exit_status', 'started_at', 'ended_at')},
           'details': details, 'admission_disposition': by_path[str(disposition_path)], 'artifacts': artifacts}
    stopped = s.read(s.LEDGER / 'coordinator-launch-receipt.json')
    s.require(type(stopped['exit_code']) is int and stopped['exit_code'] == 1, 'Coordinator not stopped')
    absent = [s.LEDGER / 'completed.json']
    for pilot in ('pilot-stock-023', 'pilot-home-023'):
        absent.extend([s.LEDGER / pilot, s.Q / (pilot + '-queue.json'), s.Q / (pilot + '-submit.json'),
                       s.Q / ('RCI001-C02-' + pilot) / 'queue-submit.json'])
    s.require(all(not path.exists() for path in absent), 'Downstream pilot/completion evidence exists')
    status = copy.deepcopy(history['current_status'])
    status.update(state='qualification_failed_blocked', as_of=s.now(), basis_run_id=row['run_id'],
                  basis_assessment_sha256=s.bind(assessment_path)['sha256'],
                  summary=('V26 stopped after Smoke024 failed its original independent qualification: 61/62 checks '
                           'passed and the fixed startup read criterion failed. Smoke024 is the latest completed '
                           'qualifier and model qualifier. Native025 and Boundary026 remain passed. Neither pilot023 '
                           'stage nor a scored attempt was launched.'),
                  engineering_context=('The failed assessment and invalid/unknown registered disposition are retained '
                                       'unchanged. Separate infrastructure diagnosis is pending; queue success is not '
                                       'qualification. Prior lineages and outcomes are preserved.'))
    lineage = status['active_lineage']
    lineage.pop('active_qualifier', None)
    lineage.update(state='v26_stopped_smoke024_failed_pilots023_not_launched',
                   latest_model_qualifier=row['run_id'], final_qualification_completed=False,
                   scientific_admission=False, scored_attempts_started=0,
                   downstream_stages_not_launched=details['downstream_stages_not_launched'])
    lineage['completed_qualifiers'].append({k: row[k] for k in
                                          ('run_id', 'revision', 'queue', 'admission_disposition')})
    lineage['coordinator_terminal_receipt'] = by_path[str(s.LEDGER / 'coordinator-launch-receipt.json')]
    existing = {item['path'] for item in status['artifacts']}
    status['artifacts'].extend(item for item in artifacts if item['path'] not in existing)
    s.save(folder / 'smoke-024-row.json', row)
    s.save(folder / 'preparation-receipt.json', {
        'schema': 'campaign002-history-draft-preparation-1', 'at': s.now(),
        'fresh_official_gate': s.bind(folder / 'official-plan-gate.json'),
        'source': s.bind(Path(__file__)), 'prior_history': s.bind(s.HISTORY),
        'template_run_id': prior['run_id'], 'draft': s.bind(folder / 'smoke-024-row.json'),
        'downstream_metadata_absent': [str(p) for p in absent],
        'outcomes_recomputed': False, 'canonical_history_written': False})
    plan = {'schema': s.PLAN_SCHEMA, 'coordinator': 'run_final_qualification_v26.py',
            'ledger': 'final-qualification-026', 'expected_history_sha256': s.sha(original),
            'expected_rows_before': 107, 'rows': [row], 'current_status': status}
    plan_binding = s.save(s.STAGE / 'smoke024-plan-001.json', plan)
    s.require(s.HISTORY.read_bytes() == original, 'Concurrent canonical mutation')
    print(json.dumps({'plan': plan_binding, 'artifacts': len(artifacts), 'failed_checks': failed,
                      'pilots_have_no_outcome_rows': True}, indent=2))


if __name__ == '__main__':
    main()
