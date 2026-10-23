"""Stage the original failed pilot admission without reassessment or publication."""
from pathlib import Path
import copy
import json
import stage_append as s


def main():
    folder = s.STAGE / 'pilot-stock024-drafts'
    gates = folder / 'official-draft-gates'
    gates.mkdir()
    jobs = {}
    job = s.authenticate({'run_id': 'RCI001-C02-pilot-stock-024', 'status': 'failed',
        'queue': {'id': '20260929T041418803542Z-2f3b6425'}}, gates, jobs)
    original = s.HISTORY.read_bytes()
    s.require(s.sha(original) == '6e1b3f07bca6357e19ac4f817f159806980b9f560e77fca73df7f0438095d3dd',
              'Canonical114 changed')
    history = json.loads(original)
    s.require(len(history['attempts']) == 114, 'Wrong prior row count')
    run = 'RCI001-C02-pilot-stock-024'
    assessment_path = s.Q / 'pilot-stock-024-assessment.json'
    disposition_path = s.LEDGER / 'pilot-stock-024/disposition.json'
    s.require(s.bind(assessment_path)['sha256'] ==
              'a87dc3025fb1212b3969640eeaf185701b201ed0bf8613d443f7332697d6f126', 'Assessment changed')
    s.require(s.bind(disposition_path)['sha256'] ==
              'fc47a1e0c41bfea7eb912327432583352e9095e8887fec5242e77bbf589a439b', 'Disposition changed')
    assessment, disposition = s.read(assessment_path), s.read(disposition_path)
    failed = ['all_namespace_retirements_observed', 'qualified_lifecycle_end_observed']
    s.require(assessment['run_id'] == disposition['run_id'] == run
              and assessment['framework_revision'] == 'RCI001-C02-dev-086'
              and assessment['validity'] == 'invalid' and assessment['task_outcome'] == 'unknown'
              and assessment['task_evidence_valid'] is False and assessment['scorable'] is False
              and assessment['failed_checks'] == failed
              and [k for k,v in assessment['checks'].items() if v is not True] == failed
              and len(assessment['checks']) == 38 and disposition['passed'] is False,
              'Original pilot failure differs')
    entry = disposition['entry']
    queue = s.read(entry['queue']['path'])
    queue = queue.get('job', queue)
    s.require(all(queue.get(k) == job.get(k) for k in
              ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd')),
              'Original queue receipt differs from fresh official')
    artifacts, by_path = [], {}
    def artifact(path, label, expected=None):
        item = {'label': label, **s.bind(path)}
        if expected:
            s.require(all(item[k] == expected[k] for k in ('sha256', 'bytes') if k in expected),
                      'Original artifact binding differs: ' + item['path'])
        if item['path'] not in by_path:
            artifacts.append(item)
            by_path[item['path']] = item
        return by_path[item['path']]
    labels = {'queue': 'Official queue receipt', 'manifest': 'Frozen one-invocation pilot manifest',
              'snapshot': 'Frozen dev086 source snapshot', 'assessment': 'Original invalid pilot assessment'}
    for name, label in labels.items():
        artifact(entry[name]['path'], label, entry[name])
    disp = artifact(disposition_path, 'Original failed pilot admission disposition')
    artifact(disposition['registered_result']['path'], 'Registered invalid/unknown pilot qualification result',
             disposition['registered_result'])
    frozen = s.read(entry['snapshot']['path'])
    artifact(Path(entry['snapshot']['path']).with_name('code.zip'), 'Frozen dev086 source archive',
             {'sha256': assessment['bindings']['framework_archive_sha256']})
    preflight = artifact(s.LEDGER / 'preflight.json', 'Original V27 coordinator preflight')
    verifier = artifact(s.C / 'admission.py', 'Original pilot admission verifier')
    assessor = artifact(s.C / 'assessment/assess.py', 'Frozen original pilot base assessor',
                        {'sha256': assessment['bindings']['assessment_sha256']})
    s.require(frozen['sources'][Path(assessor['path']).relative_to(s.REPO).as_posix()] ==
              {k: assessor[k] for k in ('sha256','bytes')}, 'Assessor is not exactly frozen')
    for name in s.METHODS:
        path = s.IO / name
        item = artifact(path, 'Frozen method: ' + name)
        s.require(frozen['sources'].get(path.relative_to(s.REPO).as_posix()) ==
                  {k: item[k] for k in ('sha256','bytes')}, 'Method is not frozen')
    roots = {'orchestrator': Path(entry['evidence']), 'protected_host': Path(entry['host_evidence'])}
    for binding in assessment['evidence_inventory']:
        root = roots[binding['root']]
        path = (root / binding['path']).resolve()
        s.require(path.is_relative_to(root.resolve()), 'Original inventory escapes its root')
        artifact(path, 'Original assessed pilot input: ' + binding['root'] + '/' + binding['path'], binding)
    proof = assessment['transport_lifecycle']
    for relative, binding in proof['input_bindings'].items():
        artifact(roots['orchestrator'] / 'pilot' / relative,
                 'Pilot source-bound transport proof input: ' + relative, binding)
    timing = assessment['campaign_timing']
    details = {'original_validity': assessment['validity'], 'task_evidence_valid': False,
        'admission_passed': False, 'admission_error': disposition['error'],
        'failed_checks': failed, 'checks_passed': 36, 'checks_total': 38,
        'verification_errors': assessment['verification_errors'],
        'timing': {k: timing['replayed_timing'][k] for k in
                   ('maximum_lag_s', 'maximum_timing_sample_gap_s', 'complete_wall_windows',
                    'outside_rtf_tolerance_windows', 'outside_rtf_tolerance_fraction')},
        'resource_gates': {k: timing[k] for k in
                           ('passed','resource_integrity_pass','garbage_collection_pass','host_memory_pass')},
        'transport_passed': assessment['transport']['passed'],
        'transport_lifecycle_passed': proof['passed'],
        'qualified_lifecycle': assessment['lifecycle'],
        'downstream_stages_not_launched': ['RCI001-C02-pilot-home-024'],
        'diagnosis_state': 'not_interpreted_in_history_append'}
    # Keep only the original validity outcome; no observed physical outcome promotes this invalid evidence.
    details['qualified_lifecycle'] = {k: v for k, v in assessment['lifecycle'].items()
        if k in ('valid','branch','explicit_retirement_receipt_observed','late_old_token_http403_observed',
                 'all_namespaces_retired','missing_receipts','limitation')}
    s.require(assessment['checks']['actual_model_started'] is True, 'Model start not established')
    row = {'run_id': run, 'revision': 'RCI001-C02-dev-086', 'status': 'failed',
        'reason': 'Pilot Stock024 completed through the official queue but failed its original independent '
                  'assessment and one-invocation family admission. The original assessment has 36/38 checks true; '
                  'all_namespace_retirements_observed and qualified_lifecycle_end_observed are false. Validity '
                  'remains invalid, task evidence invalid and task outcome unknown. No cause or task result is '
                  'inferred here. V27 stopped with exit1; Home024 and scored attempts were not launched. '
                  'Smoke025 retains its separate 62/62 passed smoke verdict.',
        'scorable': False, 'validity': 'invalid', 'task_outcome': 'unknown', 'model_calls': 1,
        'queue': {k: job[k] for k in ('id','state','exit_status','started_at','ended_at')},
        'details': details,
        'pilot_admission': {'schema': 'campaign002-pilot-history-binding-1', 'disposition': disp,
                            'verifier': verifier, 'base_assessor': assessor, 'preflight': preflight},
        'artifacts': artifacts}
    stopped_path = s.LEDGER / 'coordinator-launch-receipt.json'
    stopped = artifact(stopped_path, 'Original stopped V27 coordinator receipt',
        {'sha256': '3e8979c7f4e99662f4b9fd3a8f0f718d445a5f8c8100b8120fc3d052dda7becb'})
    terminal = s.read(stopped_path)
    s.require(type(terminal['exit_code']) is int and terminal['exit_code'] == 1, 'Coordinator not stopped')
    absent = [s.LEDGER/'completed.json', s.LEDGER/'pilot-home-024', s.Q/'pilot-home-024-queue.json',
              s.Q/'pilot-home-024-submit.json', s.Q/'RCI001-C02-pilot-home-024/queue-submit.json',
              s.C.parent/'local-evidence/campaign002/qualification/RCI001-C02-pilot-home-024']
    s.require(all(not p.exists() for p in absent), 'Home/completed output exists')
    status = copy.deepcopy(history['current_status'])
    status.update(state='qualification_failed_blocked', as_of=s.now(), basis_run_id=run,
        basis_assessment_sha256=s.bind(assessment_path)['sha256'],
        summary='V27 stopped after Pilot Stock024 failed its original independent assessment and family '
                'admission: 36/38 checks passed, with namespace-retirement and qualified-lifecycle checks false. '
                'Pilot Stock024 is the latest completed qualifier and model qualifier, invalid with task outcome '
                'unknown. Smoke025 remains a separate passed 62/62 smoke. Home024 and scored attempts were not launched.',
        engineering_context='Original assessments and dispositions remain unchanged. This history append does '
                            'not diagnose the lifecycle failure, rerun qualification, infer task performance or '
                            'promote queue success to valid evidence.')
    lineage = status['active_lineage']
    lineage.pop('active_qualifier', None)
    lineage.update(state='v27_stopped_pilot_stock024_failed_home024_not_launched', latest_model_qualifier=run,
        completed_qualifiers=['RCI001-C02-native-026','RCI001-C02-boundary-027','RCI001-C02-smoke-025',run],
        final_qualification_completed=False, scientific_admission=False, scored_attempts_started=0,
        downstream_stages_not_launched=details['downstream_stages_not_launched'],
        coordinator_terminal_receipt=stopped)
    existing = {a['path'] for a in status['artifacts']}
    for item in artifacts:
        if item['path'] not in existing:
            status['artifacts'].append(item)
            existing.add(item['path'])
    draft = s.save(folder/'pilot-stock-024-row.json', row)
    prep = s.save(folder/'preparation-receipt.json', {
        'schema':'campaign002-history-draft-preparation-1','at':s.now(),
        'fresh_official_gate':s.bind(next(gates.glob('*.json'))),'source':s.bind(__file__),
        'prior_history':s.bind(s.HISTORY),'draft':draft,'downstream_metadata_absent':[str(p) for p in absent],
        'existing_pilot_binding_schema_used':True,'generic_raw_qualification_flag_invented':False,
        'outcomes_recomputed':False,'canonical_history_written':False})
    plan={'schema':s.PLAN_SCHEMA,'coordinator':'run_final_qualification_v27.py',
        'ledger':'final-qualification-027','expected_history_sha256':s.sha(original),
        'expected_rows_before':114,'rows':[row],'current_status':status,'staging_correction':prep}
    plan_binding=s.save(s.STAGE/'pilot-stock024-plan-001.json',plan)
    s.require(s.HISTORY.read_bytes()==original,'Concurrent canonical mutation')
    print(json.dumps({'plan':plan_binding,'artifacts':len(artifacts),'failed_checks':failed,
                      'outcomes_recomputed':False,'canonical_written':False},indent=2))


if __name__ == '__main__':
    main()
