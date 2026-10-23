"""Assemble the completed v4 Baseline readback; never operate the experiment."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OPS = Path(__file__).resolve().parent
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
AUDIT = PAIR / 'operator/endpoint-audit-session57-001'
OBS = PAIR / 'operator/observations'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def ref(label, path):
    return dict(label=label, uri=path.resolve().as_posix(),
                sha256=sha256(path.read_bytes()).hexdigest(),
                state='available', access='operator', locator=None)


def create(path, value):
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    with path.open('xb') as handle:
        handle.write(payload)
    return payload


def main():
    paths = {
        'official_queue': AUDIT / 'official-queue-status.json',
        'full_audit': AUDIT / 'output/result.json',
        'full_audit_queue': AUDIT / 'audit-queue-status.json',
        'failed_supplement': AUDIT / 'physical-retirement001/result.json',
        'failed_supplement_queue': AUDIT / 'physical001-queue-status.json',
        'supplement': AUDIT / 'physical-retirement002/result.json',
        'supplement_queue': AUDIT / 'physical002-queue-status.json',
        'wake_observation': OBS / 'session57-heartbeat-b2b26af6b3c14763b66fa24dbf2ff9ab.json',
        'checkpoint_readback': OBS / 'checkpoint-00035-5947342f3bc54f5490e8ab7748dc8d9f.json',
        'native_progress': OBS / 'session57-progress-3d5f1422964a4d2fa7f7977a62f3cd24.json',
        'primary_accounting': OPS / 'primary-accounting.json',
        'lifecycle_validation': OPS / 'lifecycle-reader-validation.json',
        'failed_geometry_fixture': OPS / 'geometry-reader-validation.json',
        'geometry_validation': OPS / 'geometry-reader-validation002.json',
        'checkpoint_state_bindings': OPS / 'checkpoint-state-bindings.json',
        'physical_boundary_diagnosis': OPS / 'physical-boundary-diagnosis.json',
        'reader_revision_verification': OPS / 'reader-revision-verification.json',
        'monitoring_before': OPS / 'monitoring-before.json',
        'monitoring_paused': OPS / 'monitoring-paused.json',
        'full_audit_submission': AUDIT / 'submission-intent.json',
        'failed_supplement_submission': AUDIT / 'physical-submission-intent.json',
        'supplement_submission': AUDIT / 'physical002-submission-intent.json',
        'failed_reader': OPS / 'audit_physical_retirement.py',
        'supplement_reader': OPS / 'audit_physical_retirement_v2.py',
        'full_audit_reader': OPS.parent / 'session-33/audit_terminal.py',
        'aggregate_reader': Path(__file__),
        'frozen_source_manifest': PAIR / 'frozen_repository/source-manifest.json',
        'frozen_certificate': PAIR / 'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json',
        'analysis_freeze': PAIR / 'analysis-freeze.json',
        'analysis_plan': PAIR / 'evaluation/ANALYSIS.md',
        'baseline_lineage': PAIR / 'baseline-lineage.json',
    }
    data = {key: read(path) for key, path in paths.items() if path.suffix == '.json'}
    official, base, supplement = [data[k] for k in ('official_queue', 'full_audit', 'supplement')]
    for key in ('official_queue', 'full_audit_queue', 'supplement_queue'):
        assert data[key]['state'] == 'succeeded'
        assert type(data[key]['exit_status']) is int and data[key]['exit_status'] == 0
        assert data[key]['error'] is None and data[key]['cancel_requested_at'] is None
    assert official['id'] == '20261010T035451057091Z-9b1fda10'
    for result in (base, supplement):
        assert result['passed'] is True and len(result['checks']) == 5 and all(result['checks'].values())
    assert data['failed_supplement_queue']['state'] == 'failed' and data['failed_supplement_queue']['exit_status'] == 1
    assert data['failed_supplement']['passed'] is False
    for key in ('checkpoint_readback', 'lifecycle_validation', 'geometry_validation',
                'checkpoint_state_bindings', 'reader_revision_verification'):
        assert data[key]['passed'] is True
    assert data['failed_geometry_fixture']['passed'] is False
    monitor = data['monitoring_paused']
    assert monitor['monitoring_paused'] and monitor['older_monitors_unchanged']
    assert len(monitor['monitors']) == 4 and all(m['status'] == 'PAUSED' for m in monitor['monitors'])
    primary = data['primary_accounting']['primary_accounting']
    accounting = supplement['accounting']
    assert (primary['starts'], primary['normal_closures'], primary['unclosed_starts']) == (35, 35, 0)
    assert len(primary['assignments']) == 21 and sum(a['sessions'] for a in primary['assignments']) == 35
    assert (accounting['started'], accounting['closed'], accounting['unclosed'], accounting['assignments']) == (35, 35, 0, 21)
    assert base['evidence']['accounting']['branches'] == []
    corroboration = supplement['physical_corroboration']
    assert [corroboration[k] for k in ('trusted_latched_successes', 'first_retained_sample_passes',
                                     'close_boundary_passes', 'corroborated_at_either_observed_time')] == [14, 13, 13, 14]
    native = base['evidence']['native']['sessions']
    journal_counts = dict(sessions=len(native), reads=sum(s['reads'] for s in native),
                          mutations=sum(s['mutations'] for s in native))
    assert journal_counts == dict(sessions=35, reads=13748, mutations=32118)
    assert data['wake_observation']['maps_pristine'] and not data['wake_observation']['running_lock']
    assert len(base['source_identity']) == 253
    assert len(supplement['windows_retirement']) == 70
    assert all(r['observation']['state'] == 'absent' for r in supplement['windows_retirement'])
    linux = supplement['linux_retirement']
    assert not linux['process_matches'] and not linux['mounts'] and not linux['unreadable_cmdlines']
    assert len(linux['identities']) == 70 and not any(r['same_original_process'] for r in linux['identities'])
    references = {key: ref(key.replace('_', ' '), path) for key, path in paths.items()}
    result = dict(
        schema='apartment-v4-baseline-endpoint-1', recorded_utc=datetime.now(timezone.utc).isoformat(),
        development_session=57, heartbeat_utc='2026-10-10T11:56:20.549Z', observational_only=True,
        run_id='APARTMENT-v4-baseline', pair=PAIR.as_posix(), root=(PAIR / 'baseline').as_posix(),
        conclusion='Completed and valid under the frozen endpoint rule: 21 advancements in 35 fresh native sessions. Household success is latched; throwing advancement is timed practice, not mastery.',
        execution_status='completed', validity='valid', outcome='success',
        official_queue=official, full_audit_checks=base['checks'], supplemental_checks=supplement['checks'],
        primary_accounting=primary, lifecycle=accounting, task_summary=supplement['task_summary'],
        checkpoint={**base['evidence']['checkpoint'], 'session': 35, 'reason': 'completed'},
        authenticated_prefix=base['evidence']['prefix'], replay=supplement['replay'],
        physical_event_counts=data['primary_accounting']['physical_event_counts'],
        physical_corroboration=corroboration,
        physical_snapshot_exceptions=[r for r in supplement['physical_household_readback'] if not (r['near_event']['passed'] and r['boundary']['passed'])],
        physical_interpretation=[
            'The frozen controller latches physical success; later predicate persistence is not the frozen completion criterion.',
            'Session 7 kitchen passes at the first post-event sample (+16 ms), but its drawer later closes to 0.109718717143315 m at normal closeout, below the >0.32 m opening criterion.',
            'Session 16 bedroom has green-toy speed 0.21707819903969847 m/s at the first sample (+16 ms), above the <0.08 m/s criterion; its normal closeout state passes.',
            'Eight success events have exact-time replay samples. Six are corroborated with a sample offset up to 16 ms and/or the later closeout state; exact event-time physics is not independently sampled for those six.',
            'Pickup/release flags are verified in all 14 advancing checkpoints, not invented from replay arrays.'
        ],
        journals=journal_counts, frozen_source_entries_verified=len(base['source_identity']),
        model=dict(name='gpt-6-astra', reasoning_effort='max', fresh_threads=35, model_calls=35),
        retirement=dict(normal_native_closeouts=35,
                        fresh_windows_owner_records=dict(Counter(r['observation']['state'] for r in supplement['windows_retirement'])),
                        linux_boot_id=linux['boot_id'], linux_identity_checks=len(linux['identities']),
                        linux_matching_processes=linux['process_matches'], linux_matching_mounts=linux['mounts'],
                        linux_unreadable_cmdlines=linux['unreadable_cmdlines'],
                        host=supplement['host_retirement'], running_lock=False,
                        interpretation='Fresh census establishes absence of the original owners. Normal exit 0 and orderly teardown come from authenticated retained receipts, not from an absent PID.'),
        observation=dict(observed_utc=data['wake_observation']['observed_utc'],
                         free_disk_gib=data['wake_observation']['free_disk_gib'],
                         viewer_responding=data['wake_observation']['viewer_responding']),
        maps=dict(pristine=True, launched=False, comparison_performed=False),
        monitoring=dict(observed_utc=monitor['observed_utc'], paused=True,
                        all_four_statuses=[{'id':m['id'], 'status':m['status']} for m in monitor['monitors']],
                        older_monitors_unchanged=True),
        failed_operator_attempts=[
            dict(kind='supplemental_readback', job=data['failed_supplement_queue']['id'], exit_status=1,
                 result=references['failed_supplement'], explanation=supplement['reader_revision']['reason'],
                 disposition='Preserved unchanged. A distinct corrected operator reader was queued once; no scientific replay execution, retry, reset, recovery or relaunch.'),
            dict(kind='geometry_fixture_validation', result=references['failed_geometry_fixture'],
                 explanation=data['geometry_validation']['qualification'], disposition='Preserved unchanged; matching-scene engineering fixtures and negative checks pass in validation002; geometry predicate AST unchanged.')
        ],
        limits=supplement['limitations'] + [
            'All 35 boundary manifests and state bytes are bound to retained execution pointers. Full filesystem/inode reconstruction is verified at the latest boundary; older checkpoint directories were not each fully rehashed again.',
            'This endpoint handoff does not assess throwing mastery or every throwing attempt, token/cost totals, secondary learning trajectories, or a causal benefit of memory.',
            'Command requested/admitted/terminal counts are distinct; terminal counts do not imply every command physically succeeded.',
            'No new independent replicate or Baseline-versus-Maps comparison. Further scientific launch, resume, recovery, repair or comparison requires direct authority.'
        ],
        evidence=references,
    )
    payload = create(OPS / 'endpoint.json', result)
    with (AUDIT / 'verified-endpoint.json').open('xb') as handle:
        handle.write(payload)
    print(json.dumps({'endpoint':str(OPS / 'endpoint.json'), 'sha256':sha256(payload).hexdigest(),
                      'assignments':len(primary['assignments']), 'sessions':primary['starts'],
                      'evidence_files':len(references), 'external_copy_identical':True}, indent=2))


if __name__ == '__main__':
    main()
