"""Primary lifecycle accounting, checked on retained engineering traces before official readout.

This does not score throwing skill, timing efficiency, first-window success or a condition effect.
"""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import sys

CODE = Path(__file__).resolve().parents[2]
REPO = CODE.parents[1]
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
FROZEN = PAIR / 'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
sys.path.insert(0, str(FROZEN))
from common import canonical, read, save, sha
from audit import chain


def lifecycle(events):
    starts = [r for r in events if r['kind'] == 'session_started']
    closes = [r for r in events if r['kind'] == 'session_closed']
    identifiers = [r['payload']['session'] for r in starts]
    assert identifiers == list(range(1, len(starts) + 1)), 'Session starts missing or duplicated'
    closed_ids = [r['payload']['session'] for r in closes]
    assert closed_ids == list(range(1, len(closes) + 1)), 'Normal closeouts missing or duplicated'
    assert len(closes) <= len(starts)
    rows = []
    for position in sorted({r['payload']['assignment_position'] for r in starts}):
        members = [r for r in starts if r['payload']['assignment_position'] == position]
        kind = members[0]['payload']['task']
        assert all(r['payload']['task'] == kind for r in members)
        advance = [r for r in closes if r['payload']['assignment_advanced'] and r['payload']['next_position'] == position + 1]
        assert len(advance) <= 1
        if advance:
            assert advance[0]['payload']['session'] == members[-1]['payload']['session']
        rows.append(dict(position=position,task=kind,sessions=len(members),
                         first_session=members[0]['payload']['session'],last_session=members[-1]['payload']['session'],
                         advancing_session=advance[0]['payload']['session'] if advance else None,
                         advancement_sim_time=advance[0]['sim_time'] if advance else None))
    return dict(starts=len(starts),normal_closures=len(closes),unclosed_starts=len(starts)-len(closes),assignments=rows)


def validate_fixtures():
    fixtures = Path('D:/Dandelion-Apartment-Experiment/engineering/APARTMENT-reliability-live002/output')
    evidence = []
    for condition in ('baseline','maps'):
        for branch, expected in (('failed',(2,1,1)),('recovered',(2,2,0))):
            root = fixtures / branch / condition
            events = chain(root / 'events.jsonl')
            got = lifecycle(events)
            assert (got['starts'],got['normal_closures'],got['unclosed_starts']) == expected
            assert got['assignments'][0]['task'] == 'throwing' and got['assignments'][0]['advancing_session'] == 1
            assert got['assignments'][1]['task'] == 'kitchen' and got['assignments'][1]['first_session'] == 2
            malformed = list(events) + [next(r for r in events if r['kind']=='session_started')]
            try: lifecycle(malformed)
            except AssertionError: pass
            else: raise AssertionError('Duplicate session was not rejected')
            evidence.append(dict(root=str(root),event_sha256=sha(root/'events.jsonl'),expected_counts=expected,passed=True))
    return dict(passed=True,fixtures=evidence,duplicate_start_rejected=True,
                scope='Session/assignment lifecycle counting, including retained failed starts; no new simulation/model calls')


def main():
    op = PAIR / 'operator/endpoint-audit-session34-001'
    out = Path(__file__).parent
    validation = validate_fixtures()
    save(op/'lifecycle-reader-validation.json',validation)
    queue = REPO.parent/'tools/compute_queue/compute_queue.py'
    status = json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(queue),'status',read(op/'queue-submission.json')['id']],text=True,encoding='utf-8'))
    assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
    save(op/'queue-status.json',status)
    audit = read(op/'output/result.json')
    assert audit['passed'] is True and all(v is True for v in audit['checks'].values())
    root = Path(read(PAIR/'baseline-lineage.json')['active_root'])
    assert read(PAIR/'baseline-lineage.json')['history'] == [], 'This summary expects the observed no-recovery lineage'
    checkpoint = Path(read(root/'latest-checkpoint.json')['path'])
    state = read(checkpoint/'state.json')
    events = chain(root/'events.jsonl')
    counted = lifecycle(events)
    assert counted['starts']==counted['normal_closures']==36 and counted['unclosed_starts']==0
    assert len(counted['assignments'])==state['position']==21
    for row, completed in zip(counted['assignments'],state['completed']):
        assert (row['position'],row['task'],row['advancing_session'],row['advancement_sim_time']) == (completed['position'],completed['kind'],completed['session'],completed['sim_time'])
    native = [read(p/'native/client/result.json') for p in sorted((root/'sessions').iterdir())]
    assert len(native)==len({r['thread_id'] for r in native})==counted['starts']
    assert all(r['success'] is True and r['turn_status']=='completed' for r in native)
    task_summary = {}
    for task in ('bedroom','kitchen','throwing'):
        counts = [r['sessions'] for r in counted['assignments'] if r['task']==task]
        assert len(counts)==7
        task_summary[task] = dict(assignments=7,sessions=sum(counts),median_sessions=statistics.median(counts),range_sessions=[min(counts),max(counts)],recurrence_sessions=counts)
    result = dict(recorded_utc=datetime.now(timezone.utc).isoformat(),passed=True,condition='baseline',
        endpoint_complete=True,endpoint_session_count=36,normal_closed_sessions=36,abandoned_started_sessions=0,
        recovery_branches=0,condition_histories=1,accepted_native_turns=36,failed_native_turns=0,
        assignments_completed=21,household_successes=14,throwing_windows_completed=7,
        clean_hibernations=1,clean_resumes=1,checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint/'manifest.json'),
        simulation_time=state['world']['sim_time'],official_queue=read(op/'official-queue-status.json'),audit_queue=status,
        task_summary=task_summary,assignment_table=counted['assignments'],physical_event_counts=dict(Counter(r['kind'] for r in events)),
        maps_status='pristine and unlaunched; no condition comparison',
        secondary_analysis_status='Not assessed in this terminal closeout: first-window/timing efficiency, observed throwing-feedback series, action outcome breakdown and learned-artifact causal effect.',
        limitations=['One dependent condition history; no independent replicates or Maps comparison.','Completed throwing windows are not evidence of throwing mastery.','Baseline may create its own maps; these were not supplied or added by Development Codex.'],
        evidence=dict(independent_audit=str(op/'output/result.json'),independent_audit_sha256=sha(op/'output/result.json'),
                      lifecycle_reader_validation=str(op/'lifecycle-reader-validation.json'),event_sha256=sha(root/'events.jsonl'),
                      final_state_sha256=sha(checkpoint/'state.json')))
    save(op/'verified-endpoint.json',result)
    save(out/'endpoint.json',result)
    lines=['# Apartment v2 Baseline — verified endpoint','',
        'Baseline completed all 21 assignments in **36 fresh Robot Codex sessions**. All 36 closed normally; there were no abandoned starts, failed native turns or recovery branches. The run includes one clean overnight hibernation/resume.',
        '', 'The trusted controller recorded success on all 14 household assignments and completion of seven throwing-practice windows. This does not establish throwing mastery. Maps remains pristine and unlaunched; no condition comparison is available.',
        '', 'The official worker ended at '+result['official_queue']['ended_at']+' with integer exit 0. Independent audit '+status['id']+' passed all five gates, authenticating the endpoint checkpoint, native identity/retirement, inode journals, sensors, replay/transport history and frozen source. The final checkpoint is session 36 with manifest SHA-256 `'+result['checkpoint_sha256']+'`.',
        '', '## Session accounting','', '| Task | Assignments | Sessions | Median | Range |','|---|---:|---:|---:|---:|']
    for task, values in task_summary.items():
        lines.append(f"| {task.title()} | 7 | {values['sessions']} | {values['median_sessions']:g} | {values['range_sessions'][0]}–{values['range_sessions'][1]} |")
    lines += ['', '## Retained assignment order','', 'Positions below are one-based. Sessions span successful and incomplete attempts; no unfavorable normal session was removed.', '',
              '| Position | Task | Sessions | First session | Advancing session |','|---:|---|---:|---:|---:|']
    for row in counted['assignments']:
        lines.append(f"| {row['position']+1} | {row['task']} | {row['sessions']} | {row['first_session']} | {row['advancing_session']} |")
    lines += ['', '## Evidence and limits','',
              '`endpoint.json` binds the machine-readable table and original hashes. Full independent readback is at `D:/Dandelion-Apartment-Experiment/official/apartment-v2/operator/endpoint-audit-session34-001/`. The lifecycle reader passed four retained engineering-trace checks, including failed versus recovered starts and duplicate rejection, before the official readout.',
              '', result['secondary_analysis_status'],
              '', 'The experimental unit is one complete condition history. Sessions and recurrences are dependent observations. Neither this baseline nor spontaneous map creation establishes a causal memory benefit, condition superiority or real-robot capability. Full paired analysis remains unavailable while Maps is unrun. Token use/cost and complete throwing-attempt census are unknown.',
              '', 'Six Session 34 observations, five intermediate checkpoint readbacks, original pre-resume proof and terminal audit remain preserved. No coaching, reset, reroll, fallback, source/task modification or infrastructure recovery occurred. Monitoring is paused; a later Maps launch requires explicit human authority.','']
    (out/'RESULT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(canonical(dict(passed=True,endpoint_sessions=36,task_summary=task_summary,ended_at=result['official_queue']['ended_at'],evidence=str(op/'verified-endpoint.json'))).decode())


if __name__=='__main__': main()
