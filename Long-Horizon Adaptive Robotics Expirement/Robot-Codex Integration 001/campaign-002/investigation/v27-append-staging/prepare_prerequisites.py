"""Build the specifically authorized V27 prerequisite plan, without publishing."""
from pathlib import Path
import copy
import json
import re
import stage_append as s


def main():
    original = s.HISTORY.read_bytes()
    s.require(s.sha(original) == 'dd4dc9414c705c20d102544ebee6a1093f3bb1b390e6b3346124d287d9319576',
              'Canonical108 changed')
    history = json.loads(original)
    s.require(len(history['attempts']) == 108, 'Wrong baseline count')
    folder = s.STAGE / 'prerequisites-drafts'
    # Repeat live gates before any new prerequisite output binding or parsing.
    gates = folder / 'official-plan-gates'
    gates.mkdir()
    jobs = {}
    allocations = [
        ('raw-preflight-016', 'raw-preflight-017', '20260929T034323669949Z-0aaecfd3',
         'ad5e1c3dfff361453dd1927c07ee2e11233b4d04a46c0ee9f85d281b0df1a193'),
        ('transport-probe-019', 'transport-probe-020', '20260929T034412110339Z-63c8c977',
         '8441cc9f1d5391975d4266c17694475b70e5e8f3569ff3e2ff3b1dde22518006'),
        ('host-probe-026', 'host-probe-027', '20260929T034414579360Z-9403fd69',
         '80e341263f6202520bbd49836a2006f3514316ee2948cc56edc8b676eaa5d35f')]
    for _, new, job, _ in allocations:
        s.authenticate({'run_id': 'RCI001-C02-' + new, 'status': 'passed', 'queue': {'id': job}}, gates, jobs)
    snapshot_path = s.C.parents[1] / 'Architecture Map/releases/RCI001-C02-dev-083/snapshot.json'
    frozen = s.read(snapshot_path)
    s.require(s.bind(snapshot_path)['sha256'] ==
              '0a3216313d429237bee614a7c91b24dac5be4d8e9143ec9cb4dedb1cb0a44d2e', 'Anchor differs')

    def artifact(path, label):
        return {'label': label, **s.bind(path)}

    rows = []
    report = s.module('v27_prerequisite_plan_report', s.I / 'qualification_report.py')
    for old, new, job_id, result_sha in allocations:
        row = copy.deepcopy(next(r for r in history['attempts'] if r['run_id'] == 'RCI001-C02-' + old))
        replacements = {old: new, 'dev-079': 'dev-083', 'dev079': 'dev083',
                        'checks-029': 'checks-030', 'checks029': 'checks030', 'Host026': 'Host027'}
        pattern = re.compile('|'.join(map(re.escape, replacements)))
        def replace(value):
            return pattern.sub(lambda match: replacements[match.group()], value)
        row.update(run_id='RCI001-C02-' + new, revision='RCI001-C02-dev-083',
                   queue={k: jobs[job_id][k] for k in ('id', 'state', 'exit_status', 'started_at', 'ended_at')})
        row['artifacts'] = [artifact(replace(a['path']), replace(a['label'])) for a in row['artifacts']]
        row['artifacts'].append(artifact(s.IO / 'PREPARED_INDEX_LABELS_V1.md', 'Frozen literal prepared-result index-label method'))
        row['artifacts'].append(artifact(s.IO / 'v27-source-change-inventory-001.json', 'V27 full frozen source comparison'))
        by_path = {a['path']: a for a in row['artifacts']}
        official_item = next(a for a in row['artifacts'] if a['label'] == 'Official queue receipt')
        official = s.read(official_item['path'])
        official = official.get('job', official)
        s.require(all(official.get(k) == jobs[job_id].get(k) for k in
                      ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd')),
                  'Original official receipt differs from fresh metadata')
        method = s.IO / 'PREPARED_INDEX_LABELS_V1.md'
        item = by_path[str(method)]
        s.require(frozen['sources'][method.relative_to(s.REPO).as_posix()] ==
                  {k: item[k] for k in ('sha256', 'bytes')}, 'New method not frozen')
        row['details']['prepared_index_labels_method_source_bound'] = True
        # Earlier diagnoses remain explicitly cross-run context, never current outcomes.
        row['diagnostic_analyses'].extend(artifact(s.IO / 'smoke-024-read-diagnosis-001' / name,
            'Prior Smoke024 separate read diagnosis; unchanged original verdict: ' + name)
            for name in ('analysis.json', 'analysis.md'))
        if 'diagnostic_contract' in row:
            contract = row['diagnostic_contract']
            for key in ('result', 'verified_readiness_entry'):
                contract[key] = by_path[replace(contract[key]['path'])]
            s.require(contract['result']['sha256'] == result_sha, 'Diagnostic result changed')
            value = s.read(contract['result']['path'])
            s.require(value['passed'] is True and value['run_id'] == row['run_id']
                      and value['framework_revision'] == row['revision']
                      and type(value['model_calls']) is int and value['model_calls'] == 0
                      and value['physical_simulation'] is False and not value['errors'],
                      'No-model diagnostic scope or pass differs')
            row['details']['checks'] = value['checks']
            s.require(all(v is True for v in value['checks'].values()), 'Diagnostic check failed')
            if new.startswith('raw'):
                row['reason'] = ('Raw017 passed its original no-model option, authenticated owner and isolation/lifecycle '
                                 'checks on frozen dev083 and was independently replayed and settled. This is metadata '
                                 'only: no model tool-result capture, active model cleanup, task recovery or final qualifier claim.')
            else:
                row['details']['cases'] = report.channel_diagnostic_cases(value)
                row['reason'] = ('Transport020 passed the three fixed no-model, no-physics synthetic cases on frozen dev083 '
                                 'and was independently replayed and settled. The multi-channel case passed ordinary transport '
                                 'checks; foreign-owner and in-flight-EOF cases prove expected rejection/retirement only and remain '
                                 'production-unqualified. No model, task or final-qualifier claim.')
        else:
            assessment = s.Q / (new + '-assessment.json')
            item = by_path[str(assessment)]
            s.require(item['sha256'] == result_sha, 'Host assessment changed')
            value = s.read(assessment)
            s.require(value['diagnostic_passed'] is True and len(value['checks']) == 8
                      and all(v is True for v in value['checks'].values()), 'Host prerequisite checks differ')
            row['host_prerequisite_contract'].update(assessment_sha256=item['sha256'],
                official_queue_sha256=official_item['sha256'],
                manifest_sha256=by_path[str(s.Q / (new + '-manifest.json'))]['sha256'],
                snapshot_sha256=s.bind(snapshot_path)['sha256'])
            row['details'].update(failed_checks=[], checks_passed=8,
                known_limit='Idle host prerequisite only. V27 readiness and Native026 submission metadata are retained; '
                            'no active qualifier outcome is read for this append. Full qualification and scientific admission remain incomplete.')
            row['reason'] = ('Host027 passed all eight original independent idle-host prerequisite checks on frozen dev083 '
                             'after official succeeded/integer-zero authentication. It is settled valid diagnostic evidence '
                             'with no model or reference recovery; model-loaded timing and full qualification are not established.')
        s.save(folder / (new + '-row.json'), row)
        rows.append(row)
    readiness_path = s.Q / 'final-qualification-027-readiness.json'
    s.require(s.bind(readiness_path)['sha256'] ==
              'd98eaff0f58f460011f7084c2a3c1e48cee5b9b7639998ea25a425e92df32ad8', 'Readiness changed')
    readiness = artifact(readiness_path, 'V27 source-bound prerequisite readiness')
    preflight = artifact(s.LEDGER / 'preflight.json', 'V27 completed source and prerequisite preflight')
    submit_path = s.LEDGER / 'native-026/submit-receipt.json'
    submission_receipt = s.read(submit_path)
    submission = json.loads(submission_receipt['stdout'])
    submission = submission.get('job', submission)
    s.require(submission['id'] == '20260929T035108044594Z-0996c06c', 'Wrong active Native026 metadata')
    # This is retained submission metadata, not a query or an empirical read of the active job.
    status = copy.deepcopy(s.read(s.STAGE / 'prerequisites-plan-template-001.json')['current_status'])
    status.update(as_of=s.now(), summary='V27 Raw017, Transport020 and Host027 passed their original independent '
        'prerequisite checks and settlement. Native026 is active according to retained submission metadata; its empirical '
        'outputs remain unread. Smoke024 remains the latest settled model and generic qualifier, with its original failed '
        'verdict. Full qualification and scored admission remain incomplete.')
    status['artifacts'] = copy.deepcopy(history['current_status']['artifacts'])
    existing = {a['path'] for a in status['artifacts']}
    additions = [a for row in rows for a in row['artifacts']] + [readiness, preflight,
        artifact(submit_path, 'Native026 submission metadata only')]
    for item in additions:
        if item['path'] not in existing:
            status['artifacts'].append(item)
            existing.add(item['path'])
    status['active_lineage'].update(state='v27_prerequisites_passed_native026_pending_independent_assessment',
        completed_prerequisites=[r['run_id'] for r in rows], latest_completed_prerequisite='RCI001-C02-host-probe-027',
        readiness=readiness, preflight=preflight,
        active_qualifier={'run_id': 'RCI001-C02-native-026', 'revision': 'RCI001-C02-dev-084',
            'job_id': submission['id'], 'queue_state_at_submission': submission['state'],
            'submitted_at': submission['submitted_at'], 'started_at': submission['started_at'],
            'assessment_state': 'pending_unread', 'empirical_outputs_read': False,
            'queue_submission_receipt': artifact(submit_path, 'Native026 submission metadata only')})
    plan = {'schema': s.PLAN_SCHEMA, 'coordinator': 'run_final_qualification_v27.py',
            'ledger': 'final-qualification-027', 'expected_history_sha256': s.sha(original),
            'expected_rows_before': 108, 'rows': rows, 'current_status': status}
    binding = s.save(s.STAGE / 'prerequisites-plan-001.json', plan)
    s.require(s.HISTORY.read_bytes() == original, 'Concurrent canonical history mutation')
    print(json.dumps({'plan': binding, 'rows': [r['run_id'] for r in rows],
                      'active_outputs_read': False, 'canonical_written': False}, indent=2))


if __name__ == '__main__':
    main()
