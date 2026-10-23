"""Append the authenticated infrastructure failure without changing old records."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common import read
from register import append, base, ref

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3')
OP = PAIR / 'operator/failure-audit-session37-001'
CODE = PAIR / 'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'

def main():
    official = read(HERE / 'official-terminal.json')
    status = read(HERE / 'failure-audit-terminal.json')
    audit = read(HERE / 'failure-audit-result.json')
    summary = read(HERE / 'terminal-summary.json')
    assert official['state'] == 'failed' and official['exit_status'] == 1
    assert status['state'] == 'succeeded' and type(status['exit_status']) is int and status['exit_status'] == 0
    assert audit['passed'] and len(audit['checks']) == 11 and all(audit['checks'].values())
    assert summary['later_runtime_retirement_verified'] and summary['maps_pristine_unlaunched']
    proof = ref('Independent failed-history and retirement audit', HERE / 'failure-audit-result.json')

    def metric(name, value, unit, denominator=None, description='Count within this retained failed execution; no rate denominator.'):
        return dict(name=name, value=value, unit=unit, denominator=denominator,
                    denominator_description=description, missing_reason=None, evidence=[proof])

    result_id = 'APARTMENT-v3-baseline-infrastructure-stop-result'
    append('result', {
        **base(result_id), 'tags': ['apartment', 'official', 'baseline', 'infrastructure-failure', 'incomplete'],
        'run_id': 'APARTMENT-v3-baseline', 'supersedes_result_id': None,
        'execution_status': 'failed', 'validity': 'invalid', 'outcome': 'not_assessed',
        'validity_reason': 'The fixed 21-assignment condition ended at 9 advancements after 14 normal native sessions. Workspace construction for session 15 exceeded the FUSE mount deadline before any native/model turn. No completed endpoint exists. Independent audit authenticates the failed history, checkpoint 14, original evidence and later operator retirement, without converting execution failure into scientific completion.',
        'ended_at': official['ended_at'],
        'termination_reason': 'FUSE mount deadline during session-00015 workspace-startup; no automatic repair, retry, recovery, resume or Maps launch.',
        'metrics': [metric('assignment_advancements', 9, 'assignments', 21, 'The fixed matched schedule has 21 assignments; advancement is not a throwing-mastery measure.'),
                    metric('normal_closed_sessions', 14, 'sessions'),
                    metric('actual_native_turns', 14, 'turns'),
                    metric('failed_workspace_startups', 1, 'startup_attempts')],
        'details': dict(queue_id=official['id'], exit_status=1, failed_workspace_session=15,
                        audit_queue_id=status['id'], audit_exit_status=0, audit_checks=audit['checks'],
                        completed_by_task=audit['evidence']['lifecycle_and_unstarted_attempt_accounting']['completed_by_task'],
                        failed_native_turns=0, checkpoint='session-00014',
                        official_recorded_retirement_complete=False, operator_retirement_command_passed=False,
                        later_runtime_retirement_verified=True, original_failure_unchanged=True,
                        maps_pristine_unlaunched=True, monitors_paused=True,
                        condition_comparison_performed=False, recovery_or_resume_authorized=False),
        'evidence': [ref('Official terminal queue failure', HERE / 'official-terminal.json'),
                     ref('Original failed execution, retirement still false', HERE / 'failed-execution.json'),
                     ref('Independent audit terminal queue success', HERE / 'failure-audit-terminal.json'), proof,
                     ref('Authenticated checkpoint 14 manifest', PAIR / 'baseline/checkpoints/session-00014/manifest.json'),
                     ref('Full pre-cleanup Baseline inventory', OP / 'preservation/output/baseline-before.json'),
                     ref('Immutable partial-startup copy inventory', OP / 'preservation/output/partial-before.json'),
                     ref('Separate operator follow-up failure', HERE / 'operator-retirement-failed.json'),
                     ref('Final independent runtime retirement', HERE / 'runtime-final.json'),
                     ref('Paused monitoring and final evidence references', HERE / 'terminal-summary.json'),
                     ref('Terminal decision and scope limits', HERE / 'DECISION.md')]
    }, HERE)
    append('note', {
        **base('APARTMENT-v3-workspace-startup-interpretation-s37'),
        'tags': ['apartment', 'filesystem', 'startup', 'retirement', 'source-interpretation'],
        'target_ids': ['APARTMENT-v3-baseline', result_id], 'claim_type': 'interpretation',
        'supersedes_note_id': None,
        'body': 'Frozen native_runtime.py gives mounting 20 seconds. Retained service process-start and first-journal monotonic clocks span approximately 22.450884 seconds, consistent with restore exceeding that gate; no performance reproduction or attribution to a particular disk/content item was performed. Workspace starts the service inside its constructor, then raises before run.py assigns the object; the caller cleanup therefore retains workspace=None and cannot retire the partial service. The observed orphan and original false filesystem-retirement flag agree with this source control flow. Normal operator unmount later exited the service, while its subsequent retirement request raced the closed journal and failed; preserve both facts. Future isolated engineering should qualify progress-aware bounded readiness, constructor-safe ownership and retirement races with checkpoint-sized throwaway state. No repair was made and no recovery is authorized: the frozen recovery guard rejects the original all_retired=false receipt.',
        'evidence': [proof, ref('Frozen workspace construction and retirement source', CODE / 'native_runtime.py'),
                     ref('Frozen execution ownership and cleanup source', CODE / 'run.py'),
                     ref('Frozen recovery admission guard', CODE / 'recovery.py'),
                     ref('Preserved failed operator receipt', HERE / 'operator-retirement-failed.json'),
                     ref('Decision and limitations', HERE / 'DECISION.md')]
    }, HERE)
    print('Registered failed/invalid/not_assessed result and source-supported interpretation; no old record replaced.')

if __name__ == '__main__':
    main()
