"""Draft failed Smoke027 from queue and declared metadata only; never assess."""
import copy
import json
import stage_append as s

EXPECTED_HISTORY = '158d678ae62372579298b5c55677d51d0c6ad63dd7779729e58eb69bd6fa0692'
JOB = '20260929T182650537335Z-49496959'
RUN = 'RCI001-C02-smoke-027'


def main():
    original = s.HISTORY.read_bytes()
    s.require(s.sha(original) == EXPECTED_HISTORY, 'Canonical128 changed')
    history = json.loads(original)
    s.require(len(history['attempts']) == 128, 'Wrong baseline count')
    folder = s.STAGE / 'smoke027-drafts'
    folder.mkdir()
    gates = folder / 'official-draft-gates'
    gates.mkdir()
    job = s.authenticate({'run_id': RUN, 'status': 'failed', 'queue': {'id': JOB},
                          'queue_failure_contract': {}}, gates, {})
    s.require(job['exit_status'] == 1, 'Original integer exit1 differs')

    def artifact(path, label):
        return {'label': label, **s.bind(path)}

    official = artifact(s.Q / RUN / 'official-status.json', 'Official queue receipt')
    frozen_manifest = artifact(s.Q / 'smoke-027-manifest.json', 'Frozen attempt manifest')
    snapshot = artifact(s.C.parents[1] / 'Architecture Map/releases/RCI001-C02-dev-096/snapshot.json',
                        'Frozen source snapshot')
    s.require(snapshot['sha256'] == 'da90fe5b56e7cef8e3f9d0c01ccffb69c0a20e4efc68ee06e270e3a9b931a530',
              'Final source snapshot differs')
    retained = s.read(official['path'])
    retained = retained.get('job', retained)
    s.require(all(retained.get(k) == job.get(k) for k in
                  ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd')),
              'Stored official metadata differs from fresh gate')
    row = {'run_id': RUN, 'revision': 'RCI001-C02-dev-096', 'status': 'failed',
        'reason': 'Official Smoke027 execution failed with genuine integer exit1. V29 coordinator38867 '
            'stopped at its official queue gate before empirical assessment and finished exit1. '
            'No smoke qualification assessment is admitted, model-call count and task outcome remain unknown, '
            'and no pilot026 or scored attempt launched. This row contains official execution metadata only; '
            'it neither diagnoses raw outputs nor promotes or retries the failed attempt.',
        'scorable': False, 'validity': 'unknown', 'assessment_state': 'not_assessed',
        'task_outcome': 'unknown', 'model_calls': None,
        'queue': {k: job[k] for k in ('id', 'state', 'exit_status', 'started_at', 'ended_at')},
        'details': {}, 'queue_failure_contract': {'schema': 'campaign002-failed-queue-diagnostic-1',
            'official_queue_sha256': official['sha256'], 'manifest_sha256': frozen_manifest['sha256'],
            'snapshot_sha256': snapshot['sha256']},
        'artifacts': [official, frozen_manifest, snapshot], 'diagnostic_analyses': []}
    # Both are metadata, not empirical assessment inputs. The row itself keeps the exact three-file contract.
    failure = artifact(s.Q / RUN / 'queue-failure.json', 'Original unassessed Smoke027 queue-failure disposition')
    s.require(failure['sha256'] == '0d09ab084855e67021a5ec58acfab19fd47ccd7af2ed9c785c1307cf17bd1621',
              'Original failed-queue disposition differs')
    coordinator = artifact(s.LEDGER / 'coordinator-launch-receipt.json', 'Stopped V29 coordinator receipt')
    s.require(coordinator['sha256'] == 'abc79d255b77da974c9472d396ac16cadec2554c2e331047f96b9fde4f7ba937',
              'Stopped coordinator identity differs')
    submit = artifact(s.Q / RUN / 'queue-submit.json', 'Original Smoke027 submission metadata')
    submitted = s.read(submit['path'])
    submitted = submitted.get('job', submitted)
    s.require(submitted['id'] == JOB, 'Submission identity differs')
    diagnostics = [artifact(s.IO / 'smoke027-queue-failure-diagnosis-001' / name,
                           'Separate Smoke027 diagnosis; hash-only context, not qualification: ' + name)
                   for name in ('ordered-analysis.json', 'FINDINGS.md')]
    s.require([a['sha256'] for a in diagnostics] == [
        'de6eb89282cd12d2b9084cdd5c93aa7e6cc9dc15e2920023665b0cc043cbe46b',
        '12e8c6e5fbaee8d0b860c86fc824b081f0229023dcb8b09ec0f2af6ac7bf87b3'],
        'Separate diagnostic identity differs')
    status = copy.deepcopy(history['current_status'])
    status.update(state='qualification_failed_blocked', as_of=s.now(), basis_run_id=RUN,
        basis_assessment_sha256=None, basis_queue_sha256=official['sha256'],
        basis_kind='official_terminal_execution_failure_without_assessment',
        summary='V29 stopped at failed Smoke027 execution (official integer exit1). Coordinator38867 finished '
            'exit1 before empirical smoke assessment; no pilot026 or scored slot launched. Smoke027 is the '
            'latest completed qualifier and model qualifier, unassessed with unknown task outcome and model-call '
            'count. Native028 and Boundary029 retain their original separate passes; earlier outcomes remain unchanged.',
        engineering_context='This failed-queue history row uses only official receipt, frozen manifest and source '
            'snapshot metadata. The retained queue-failure disposition and stopped-coordinator receipt are context '
            'only. No raw diagnostic output, timing, canary, lifecycle or model-result assessment is consumed.')
    lineage = status['active_lineage']
    lineage.update(state='v29_smoke027_queue_failed_unassessed', latest_model_qualifier=RUN,
        active_qualifier=None, failed_qualifier={'run_id': RUN, 'revision': 'RCI001-C02-dev-096',
            'job_id': JOB, 'assessment_state': 'not_assessed', 'task_outcome': 'unknown', 'model_calls': None},
        unlaunched_pilots=['RCI001-C02-pilot-stock-026', 'RCI001-C02-pilot-home-026'],
        coordinator_terminal={'exit_code': 1, 'receipt': coordinator},
        final_qualification_completed=False, scientific_admission=False, scored_attempts_started=0)
    known = {a['path'] for a in status['artifacts']}
    for item in [*row['artifacts'], failure, coordinator, submit, *diagnostics]:
        if item['path'] not in known:
            status['artifacts'].append(item)
            known.add(item['path'])
    draft = s.save(folder / 'smoke-027-row.json', row)
    preparation = s.save(folder / 'preparation-receipt.json', {
        'schema': 'campaign002-history-draft-preparation-1', 'at': s.now(),
        'fresh_official_gate': s.bind(next(gates.glob('*.json'))), 'source': s.bind(__file__),
        'prior_history': s.bind(s.HISTORY), 'draft': draft, 'queue_failure_context': failure,
        'coordinator_context': coordinator, 'submission_metadata': submit,
        'hash_only_diagnostic_context': diagnostics,
        'diagnostic_row_links_omitted_reason': 'Existing row-link grammar requires a prefixed -analysis/-diagnosis basename; the unchanged generic packet is linked as current-status parse-false context instead.',
        'empirical_outputs_read': False, 'outcomes_recomputed': False, 'canonical_history_written': False})
    plan = {'schema': s.PLAN_SCHEMA, 'coordinator': 'run_final_qualification_v29.py',
        'ledger': 'final-qualification-029', 'expected_history_sha256': EXPECTED_HISTORY,
        'expected_rows_before': 128, 'rows': [row], 'current_status': status, 'staging_correction': preparation}
    binding = s.save(s.STAGE / 'smoke027-plan-001.json', plan)
    s.require(s.HISTORY.read_bytes() == original, 'Concurrent canonical mutation')
    print(json.dumps({'plan': binding, 'artifacts': 3, 'assessment_state': 'not_assessed',
                      'canonical_written': False, 'empirical_outputs_read': False}, indent=2))


if __name__ == '__main__':
    main()
