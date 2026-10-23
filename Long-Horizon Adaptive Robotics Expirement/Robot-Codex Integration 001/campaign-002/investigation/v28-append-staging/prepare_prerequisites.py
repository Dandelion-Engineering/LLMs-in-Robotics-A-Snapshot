"""Prepare only the three authorized settled V28 prerequisite rows; never publish."""
import copy
import json
import re
import stage_append as s


def main():
    original = s.HISTORY.read_bytes()
    s.require(s.sha(original) == s.BASELINE_SHA, 'Canonical115 changed')
    history = json.loads(original)
    s.require(len(history['attempts']) == 115, 'Wrong baseline count')
    folder = s.STAGE / 'prerequisites-drafts'
    folder.mkdir()
    gates = folder / 'official-plan-gates'
    gates.mkdir()
    jobs = {}
    allocations = (
        ('raw-preflight-017', 'raw-preflight-018', '20260929T044038276184Z-34689449',
         '32102573e1634dd4d42105fbceaa0594a8fd4d2aa0e58b3b602b2938e990df5f'),
        ('transport-probe-020', 'transport-probe-021', '20260929T044647517233Z-7f498d19',
         '9314ad3092f583e9d7dd9af13c9d61a23aa9c212d7cb5527d02e098339dc8b4c'),
        ('host-probe-027', 'host-probe-028', '20260929T044654743209Z-a1e89599',
         'fe8a27593e4eba4448ce3a9b27c34c61aa8ba8556dd12f04b31ff9972e1de36a'),
    )
    # All three fresh official gates precede output reads and hashes.
    for _, new, job, _ in allocations:
        s.authenticate({'run_id': 'RCI001-C02-' + new, 'status': 'passed', 'queue': {'id': job}}, gates, jobs)
    snapshot_path = s.C.parents[1] / 'Architecture Map/releases/RCI001-C02-dev-087/snapshot.json'
    s.require(s.bind(snapshot_path)['sha256'] ==
              '30c61e444ca566ea25fa292ac21d5b1da394a5032f4aa5919be90b37425ff52a', 'Anchor differs')
    frozen = s.read(snapshot_path)

    def artifact(path, label):
        return {'label': label, **s.bind(path)}

    report = s.module('v28_prerequisite_plan_report', s.I / 'qualification_report.py')
    rows = []
    for old, new, job_id, result_sha in allocations:
        row = copy.deepcopy(next(r for r in history['attempts'] if r['run_id'] == 'RCI001-C02-' + old))
        replacements = {old: new, 'dev-083': 'dev-087', 'dev083': 'dev087',
                        'checks-030': 'checks-031', 'checks030': 'checks031', 'Host027': 'Host028',
                        'v27-source-change-inventory': 'v28-source-change-inventory',
                        'V27 full frozen': 'V28 full frozen'}
        pattern = re.compile('|'.join(map(re.escape, replacements)))

        def replace(value):
            return pattern.sub(lambda m: replacements[m.group()], value)

        row.update(run_id='RCI001-C02-' + new, revision='RCI001-C02-dev-087',
                   queue={k: jobs[job_id][k] for k in ('id', 'state', 'exit_status', 'started_at', 'ended_at')})
        row['artifacts'] = [artifact(replace(a['path']), replace(a['label'])) for a in row['artifacts']]
        method = s.IO / 'PILOT_RETIREMENT_INVENTORY_V1.md'
        row['artifacts'].append(artifact(method, 'Frozen exact versioned pilot retirement inventory method'))
        by_path = {a['path']: a for a in row['artifacts']}
        official_item = next(a for a in row['artifacts'] if a['label'] == 'Official queue receipt')
        official = s.read(official_item['path'])
        official = official.get('job', official)
        s.require(all(official.get(k) == jobs[job_id].get(k) for k in
                      ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd')),
                  'Original official receipt differs from fresh metadata')
        item = by_path[str(method)]
        s.require(frozen['sources'][method.relative_to(s.REPO).as_posix()] ==
                  {k: item[k] for k in ('sha256', 'bytes')}, 'New method not frozen')
        row['details']['pilot_retirement_inventory_method_source_bound'] = True
        # Existing cross-run diagnoses remain unchanged; optional new links are not invented.
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
                row['reason'] = ('Raw018 passed its original no-model option, authenticated owner and isolation/lifecycle '
                    'checks on frozen dev087 and was independently replayed and settled. This is metadata only: no model '
                    'tool-result capture, active model cleanup, task recovery or final qualifier claim.')
            else:
                row['details']['cases'] = report.channel_diagnostic_cases(value)
                row['reason'] = ('Transport021 passed the three fixed no-model, no-physics synthetic cases on frozen dev087 '
                    'and was independently replayed and settled. The multi-channel case passed ordinary transport checks; '
                    'foreign-owner and in-flight-EOF cases prove expected rejection/retirement only and remain '
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
                known_limit='Idle host prerequisite only. V28 readiness and Native027 submission metadata are retained; '
                    'no active qualifier outcome is read for this append. Full qualification and scientific admission remain incomplete.')
            row['reason'] = ('Host028 passed all eight original independent idle-host prerequisite checks on frozen dev087 '
                'after official succeeded/integer-zero authentication. It is settled valid diagnostic evidence with no model '
                'or reference recovery; model-loaded timing and full qualification are not established.')
        s.save(folder / (new + '-row.json'), row)
        rows.append(row)

    readiness_path = s.Q / 'final-qualification-028-readiness.json'
    s.require(s.bind(readiness_path)['sha256'] ==
              '14279de33358b4bd79b9f619db8f6bba190b1f9124a822593aa560b05ae4a55d', 'Readiness changed')
    readiness = artifact(readiness_path, 'V28 source-bound prerequisite readiness')
    preflight = artifact(s.LEDGER / 'preflight.json', 'V28 completed source and prerequisite preflight')
    submit_path = s.LEDGER / 'native-027/submit-receipt.json'
    submission = json.loads(s.read(submit_path)['stdout'])
    submission = submission.get('job', submission)
    s.require(submission['id'] == '20260929T045359983400Z-c5b84ade', 'Wrong Native027 submission metadata')
    status = copy.deepcopy(s.read(s.STAGE / 'prerequisites-plan-template-001.json')['current_status'])
    status.update(as_of=s.now(), summary='V28 Raw018, Transport021 and Host028 passed their original independent '
        'prerequisite checks and settlement. Native027 is active according to retained submission metadata after the '
        '04:53:53.538095 UTC accounting cutoff; its empirical outputs remain unread. Pilot Stock024 remains the latest '
        'settled model and generic qualifier, invalid with unknown task outcome. Smoke025 retains its original pass. '
        'Full qualification and scored admission remain incomplete.')
    status['artifacts'] = copy.deepcopy(history['current_status']['artifacts'])
    existing = {a['path'] for a in status['artifacts']}
    for item in [a for row in rows for a in row['artifacts']] + [readiness, preflight,
                  artifact(submit_path, 'Native027 submission metadata only')]:
        if item['path'] not in existing:
            status['artifacts'].append(item)
            existing.add(item['path'])
    status['active_lineage'].update(state='v28_prerequisites_passed_native027_pending_independent_assessment',
        completed_prerequisites=[r['run_id'] for r in rows], latest_completed_prerequisite='RCI001-C02-host-probe-028',
        readiness=readiness, preflight=preflight,
        active_qualifier={'run_id': 'RCI001-C02-native-027', 'revision': 'RCI001-C02-dev-088',
            'job_id': submission['id'], 'queue_state_at_submission': submission['state'],
            'submitted_at': submission['submitted_at'], 'started_at': submission['started_at'],
            'assessment_state': 'pending_unread', 'empirical_outputs_read': False,
            'queue_submission_receipt': artifact(submit_path, 'Native027 submission metadata only')})
    plan = {'schema': s.PLAN_SCHEMA, 'coordinator': 'run_final_qualification_v28.py',
            'ledger': 'final-qualification-028', 'expected_history_sha256': s.sha(original),
            'expected_rows_before': 115, 'rows': rows, 'current_status': status}
    binding = s.save(s.STAGE / 'prerequisites-plan-001.json', plan)
    s.require(s.HISTORY.read_bytes() == original, 'Concurrent canonical history mutation')
    print(json.dumps({'plan': binding, 'rows': [r['run_id'] for r in rows],
                      'active_outputs_read': False, 'canonical_written': False}, indent=2))


if __name__ == '__main__':
    main()
