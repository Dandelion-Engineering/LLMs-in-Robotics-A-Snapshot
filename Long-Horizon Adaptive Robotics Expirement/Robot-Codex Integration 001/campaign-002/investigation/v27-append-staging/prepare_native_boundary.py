"""Draft two settled V27 rows after fresh official gates; never publish."""
import copy
import json
import re
from pathlib import Path
import stage_append as s

EXPECTED_HISTORY = '9973018f0347576af7c4598b070fe4d431236d697f8c9614e0c4b3f9613635c2'


def main():
    original = s.HISTORY.read_bytes()
    s.require(s.sha(original) == EXPECTED_HISTORY, 'Canonical111 changed')
    history = json.loads(original)
    s.require(len(history['attempts']) == 111, 'Wrong baseline row count')
    folder = s.STAGE / 'native-boundary-drafts-003'
    folder.mkdir()
    gates = folder / 'official-draft-gates'
    gates.mkdir()
    allocations = [
        ('native-025', 'native-026', '080', '084', '20260929T035108044594Z-0996c06c',
         '0fda2ab792ba2029ba594e155ade925d9e0cac342095b951c3a854aa58a306a7',
         '834681d247e4ae765a570a336f285cc54bcbabc752825acb946e508c981705c1'),
        ('boundary-026', 'boundary-027', '081', '085', '20260929T035938575014Z-eec4e520',
         'ac851bbb37cc6742ab4f5290fd44e35d1388d4d537a6703775e5fae541ba5497',
         'aaf0e3f32db32946082a78ed74c34b57e75d3fef07c9a5fc7fc0c9dc950c656a')]
    jobs = {}
    for _, new, _, _, job, _, _ in allocations:
        s.authenticate({'run_id': 'RCI001-C02-' + new, 'status': 'passed', 'queue': {'id': job}}, gates, jobs)

    def artifact(path, label):
        return {'label': label, **s.bind(path)}

    rows = []
    for old, new, oldrev, newrev, job, disp_sha, assessment_sha in allocations:
        row = copy.deepcopy(next(r for r in history['attempts'] if r['run_id'] == 'RCI001-C02-' + old))
        replacements = {old: new, 'dev-' + oldrev: 'dev-' + newrev,
                        'dev' + oldrev: 'dev' + newrev, 'final-qualification-026': 'final-qualification-027',
                        'V26': 'V27'}
        regex = re.compile('|'.join(map(re.escape, replacements)))
        def replace(value):
            return regex.sub(lambda m: replacements[m.group()], value)
        row.update(run_id='RCI001-C02-' + new, revision='RCI001-C02-dev-' + newrev,
                   queue={k: jobs[job][k] for k in ('id', 'state', 'exit_status', 'started_at', 'ended_at')})
        row['artifacts'] = [artifact(replace(v['path']), replace(v['label'])) for v in row['artifacts']]
        row['artifacts'].append(artifact(s.IO / 'PREPARED_INDEX_LABELS_V1.md',
                                         'Frozen stage method: PREPARED_INDEX_LABELS_V1.md'))
        row['admission_disposition'] = artifact(s.LEDGER / new / 'disposition.json',
                                                row['admission_disposition']['label'])
        s.require(row['admission_disposition']['sha256'] == disp_sha, 'Original disposition changed')
        disposition = s.read(row['admission_disposition']['path'])
        s.require(disposition['passed'] is True and disposition['error'] is None
                  and disposition['run_id'] == row['run_id'], 'Original admission did not pass')
        entry = disposition['entry']
        for item in [*entry.values(), disposition['registered_result']]:
            if isinstance(item, dict) and 'path' in item:
                s.require(s.bind(item['path'])['sha256'] == item['sha256'], 'Disposition entry changed')
        official = s.read(entry['queue']['path'])
        official = official.get('job', official)
        s.require(all(official.get(k) == jobs[job].get(k) for k in
                      ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd')),
                  'Original official receipt differs from fresh status')
        s.require(entry['assessment']['sha256'] == assessment_sha, 'Wrong original assessment')
        assessment = s.read(entry['assessment']['path'])
        frozen = s.read(entry['snapshot']['path'])
        method = s.IO / 'PREPARED_INDEX_LABELS_V1.md'
        method_binding = s.bind(method)
        s.require(frozen['sources'][method.relative_to(s.REPO).as_posix()] ==
                  {k: method_binding[k] for k in ('sha256', 'bytes')}, 'Method absent from stage freeze')
        if new.startswith('native'):
            cases = assessment['rows']
            s.require(assessment['qualification_passed'] is True and len(cases) == 6
                      and all(r['passed'] is True and not r['errors'] and
                              all(v is True for v in r['checks'].values()) for r in cases),
                      'Original native qualification did not pass all six cases')
            details = []
            for case in cases:
                timing = case['timing']
                replay = timing['replayed_timing']
                details.append({'run_id': case['run_id'], 'family': case['family'], 'passed': case['passed'],
                    'observed_reference_task_outcome': case['independent_outcome']['independent_task_outcome'],
                    **{k: replay[k] for k in ('maximum_lag_s', 'maximum_timing_sample_gap_s',
                                             'complete_wall_windows', 'outside_rtf_tolerance_windows')},
                    'resource_integrity_pass': timing['resource_integrity_pass']})
            count = sum(len(r['checks']) for r in cases)
            s.require(count == 66, 'Reference check count differs')
            row['details'] = {'reference_cases': 6, 'checks_passed': count, 'failed_checks': [],
                              'cases': details, 'admission_passed': True}
            row['reason'] = ('All six fresh native reference cases passed the original independent apparatus '
                'assessment and source-bound V27 admission under dev084. All 66 reference checks and resource '
                'gates passed. These no-model controls do not establish model recovery performance, reverse '
                'earlier failures or complete scored campaign admission.')
        else:
            root = Path(entry['evidence'])
            before = s.read(root / 'source-binding-before.json')
            after = s.read(root / 'source-binding-after.json')
            s.require(assessment['qualified'] is True and len(assessment['checks']) == 12
                      and all(v is True for v in assessment['checks'].values()), 'Boundary checks differ')
            s.require(before == after and all(frozen['sources'].get(k, {}).get('sha256') == v
                                             for k, v in before.items()),
                      'Measured boundary source bindings differ')
            row['details'] = {'raw_suite_qualified': True, 'raw_checks_passed': 12, 'admission_passed': True,
                'measured_source_count': len(before), 'before_after_sources_identical': True,
                'snapshot_source_count': len(frozen['sources']), 'all_measured_sources_bound': True}
            row['reason'] = (f'Fresh Boundary027 passed all 12 original isolated boundary/lifecycle checks '
                f'and source-bound V27 admission under dev085. All {len(before)} measured before/after source '
                f'identities matched the {len(frozen["sources"])}-source frozen snapshot. These no-model checks '
                'do not establish a model-stage outcome or full campaign admission. Earlier attempts retain '
                'their original verdicts.')
        s.save(folder / (new + '-row.json'), row)
        rows.append(row)

    status = copy.deepcopy(history['current_status'])
    status.update(as_of=s.now(), basis_run_id=rows[-1]['run_id'],
        basis_assessment_sha256=allocations[-1][-1],
        summary='V27 Native026 passed its six original reference cases and Boundary027 passed its 12 original '
                'boundary checks, each independently admitted after official succeeded/integer-zero authentication. '
                'Smoke025 is active according to retained submission metadata; its outcomes remain unread. '
                'Smoke024 remains the latest completed model qualifier with its unchanged failed verdict. '
                'Full qualification and scored admission remain incomplete.')
    submit_path = s.Q / 'RCI001-C02-smoke-025' / 'queue-submit.json'
    job = s.read(submit_path)
    job = job.get('job', job)
    s.require(job['id'] == '20260929T040035554754Z-4e67aa65', 'Wrong active submission metadata')
    submit_binding = artifact(submit_path, 'Smoke025 submission metadata only')
    status['active_lineage'].update(state='v27_native_boundary_passed_smoke025_pending_independent_assessment',
        completed_qualifiers=[r['run_id'] for r in rows],
        active_qualifier={'run_id': 'RCI001-C02-smoke-025', 'revision': 'RCI001-C02-dev-086',
            'job_id': job['id'], 'queue_state_at_submission': job['state'],
            'submitted_at': job['submitted_at'], 'started_at': job['started_at'],
            'assessment_state': 'pending_unread', 'empirical_outputs_read': False,
            'queue_submission_receipt': submit_binding})
    existing = {v['path'] for v in status['artifacts']}
    for item in [*(a for row in rows for a in row['artifacts']), submit_binding]:
        if item['path'] not in existing:
            status['artifacts'].append(item)
            existing.add(item['path'])
    plan = {'schema': s.PLAN_SCHEMA, 'coordinator': 'run_final_qualification_v27.py',
            'ledger': 'final-qualification-027', 'expected_history_sha256': EXPECTED_HISTORY,
            'expected_rows_before': 111, 'rows': rows, 'current_status': status}
    binding = s.save(s.STAGE / 'native-boundary-plan-001.json', plan)
    s.require(s.HISTORY.read_bytes() == original, 'Canonical changed during staging preparation')
    print(json.dumps({'plan': binding, 'rows': [r['run_id'] for r in rows],
                      'canonical_written': False, 'active_outputs_read': False}, indent=2))


if __name__ == '__main__':
    main()
