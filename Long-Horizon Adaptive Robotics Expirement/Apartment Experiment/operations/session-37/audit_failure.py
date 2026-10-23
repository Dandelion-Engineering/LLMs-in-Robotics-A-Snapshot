"""Independent queued readback of the failed v3 history and operator retirement.

An audit pass authenticates an incomplete failed history; it never makes the
official execution successful. Completed native sessions and the unstarted
session-15 workspace are accounted separately, without moving condition files.
"""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3')
ROOT=PAIR/'baseline';OP=PAIR/'operator/failure-audit-session37-001'
CODE=PAIR/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
sys.path.insert(0,str(CODE))
from common import canonical,inventory,read,save,sha
from run import verify_run,source_identity
from recording import verify_checkpoint,verify_prefix
from recovery import terminal
from audit import native,chain
from repair_validation import transport_readback

class CompletedSessions:
    def __init__(self,sessions):self.sessions=sessions
    def iterdir(self):return iter(self.sessions)

class CompletedPrefixView:
    """Only selects the proven 14 closed sessions for the unchanged native reader.

    All condition event/sensor/replay reads still address the original root.
    The one excluded startup directory is required and audited independently.
    This creates no filesystem view, link, copy, or changed frozen module.
    """
    name='baseline'
    def __init__(self,sessions):self.sessions=sessions
    def __truediv__(self,name):return CompletedSessions(self.sessions) if name=='sessions' else ROOT/name

def original_v2_preservation():
    original=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
    protected=Path('D:/Dandelion-Apartment-Experiment/engineering/cup-physics-session36/history001/output/protected-v2-files.json')
    records=read(protected)
    actual={str(p) for condition in ('baseline','maps') for p in (original/condition).rglob('*') if p.is_file()}
    assert actual=={r['path'] for r in records}
    for row in records:
        path=Path(row['path']);assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],path
    frozen=original/'frozen_repository';expected=read(frozen/'source-manifest.json')
    actual=inventory(frozen);actual.pop('source-manifest.json');assert actual==expected
    return dict(files=len(records),bytes=sum(r['bytes'] for r in records),protected_manifest_sha256=sha(protected),
                baseline_checkpoint_manifest_sha256=sha(original/'baseline/checkpoints/session-00036/manifest.json'),
                maps_checkpoint_manifest_sha256=sha(original/'maps/checkpoints/session-00022/manifest.json'),
                frozen_source_files=len(expected))

def main():
    out=OP/'audit/output';out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,official_outcome='failed',endpoint_complete=False,observational_only=True,
                started_utc=datetime.now(timezone.utc).isoformat(),checks={},evidence={})
    def checked(name,value):
        result['evidence'][name]=value;result['checks'][name]=True
        print('PASS '+name,flush=True)
    try:
        official=read(OP/'official-queue-status.json')
        assert official['state']=='failed' and type(official['exit_status']) is int and official['exit_status']==1
        execution=terminal(ROOT)
        assert execution['passed'] is False and execution['failure_phase']=='workspace-startup'
        assert execution['current_session']=='session-00015' and 'FUSE mount deadline' in execution['error']
        assert execution['model_calls']==execution['official_sessions']==len(execution['sessions'])==14
        assert execution['retirement']==dict(all_retired=False,components=dict(controller=True,filesystem=False,native=True,viewer=True))
        assert not (ROOT/'running.lock').exists() and not (ROOT/'completed.json').exists()
        checked('failed_execution_authenticated',dict(queue=official,execution_pointer=read(ROOT/'latest-execution.json'),
                failure_phase=execution['failure_phase'],error=execution['error'],recorded_retirement=execution['retirement']))

        run=verify_run(ROOT,official_allowed=True)
        assert run['condition']=='baseline' and run['stage']=='official'
        prepared=read(PAIR/'prepared.json');frozen=PAIR/'frozen_repository'
        assert sha(frozen/'source-manifest.json')==prepared['source_manifest_sha256']
        expected=read(frozen/'source-manifest.json');actual=inventory(frozen);actual.pop('source-manifest.json')
        assert actual==expected
        assert source_identity()==run['source_identity']
        assert read(PAIR/'baseline-lineage.json')['history']==[]
        checked('frozen_source_environment_and_lineage',dict(source_manifest_sha256=sha(frozen/'source-manifest.json'),files=len(expected),
                source_identity=source_identity(),recovery_branches=0))

        pointer=read(ROOT/'latest-checkpoint.json');checkpoint=Path(pointer['path'])
        assert checkpoint==ROOT/'checkpoints/session-00014'
        assert sha(checkpoint/'manifest.json')==pointer['manifest_sha256']
        cp=verify_checkpoint(checkpoint);prefix=verify_prefix(ROOT,checkpoint);state=read(checkpoint/'state.json')
        assert state['sessions']==14 and state['position']==9 and len(state['completed'])==9
        assert inventory(ROOT/'filesystem')==inventory(checkpoint/'filesystem')
        assert sha(ROOT/'filesystem-namespace.json')==sha(checkpoint/'filesystem-namespace.json')
        sessions=[ROOT/'sessions'/('session-'+str(n).zfill(5)) for n in range(1,15)]
        checkpoint_receipts=[]
        for recorded,session in zip(execution['sessions'],sessions):
            assert recorded['session']==session.name
            historical=Path(recorded['ending']['checkpoint']['path'])
            receipt=verify_checkpoint(historical)
            assert receipt['manifest_sha256']==recorded['ending']['checkpoint']['manifest_sha256']
            assert sha(session/'native/client/result.json')==recorded['client_result_sha256']
            checkpoint_receipts.append(dict(session=session.name,**receipt))
        checked('checkpoint_and_all_normal_boundaries',dict(latest=cp,prefix=prefix,all_checkpoints=checkpoint_receipts,
                assignments_completed=9,normal_closed_sessions=14,simulation_time=state['world']['sim_time']))

        all_sessions=sorted((ROOT/'sessions').iterdir())
        assert all_sessions==sessions+[ROOT/'sessions/session-00015']
        checked('completed_native_journal_sensor_replay_history',native(CompletedPrefixView(sessions)))
        checked('completed_transport_history',{session.name:transport_readback(session/'native') for session in sessions})

        # Reuse exactly the existing lifecycle reader functions, without importing
        # that script's old pair configuration or executing its main routine.
        reader_path=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-34/summarize_endpoint.py'
        tree=ast.parse(reader_path.read_text(encoding='utf-8'))
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('lifecycle','validate_fixtures')]
        assert len(functions)==2
        namespace=dict(Path=Path,chain=chain,sha=sha)
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),str(reader_path),'exec'),namespace)
        fixtures=namespace['validate_fixtures']();assert fixtures['passed']
        events=chain(ROOT/'events.jsonl');counted=namespace['lifecycle'](events)
        assert counted['starts']==counted['normal_closures']==14 and counted['unclosed_starts']==0
        assert len(counted['assignments'])==9
        for row,completed in zip(counted['assignments'],state['completed']):
            assert (row['position'],row['task'],row['advancing_session'],row['advancement_sim_time'])==(completed['position'],completed['kind'],completed['session'],completed['sim_time'])
        failed=ROOT/'sessions/session-00015';assert not (failed/'native').exists()
        assert not any(row['kind']=='session_started' and row['payload']['session']==15 for row in events)
        tail=[row for row in events if row['sequence']>state['event_sequence']]
        assert not any(row['kind'] in ('session_started','session_closed','task_success') for row in tail)
        replay=read(ROOT/'replay/index.json')
        checked('lifecycle_and_unstarted_attempt_accounting',dict(reader_sha256=sha(reader_path),fixture_validation=fixtures,
                **counted,completed_by_task=dict(Counter(row['kind'] for row in state['completed'])),
                failed_workspace_startups=1,failed_workspace_session=15,native_calls=14,failed_native_turns=0,
                event_counts=dict(Counter(row['kind'] for row in events)),post_checkpoint_event_count=len(tail),
                post_checkpoint_replay_seconds=replay[-1]['last']-state['world']['sim_time']))

        preserved=OP/'preservation/output';before=read(preserved/'baseline-before.json')
        assert read(preserved/'result.json')['passed']
        partial=failed/'workspace';copy=preserved/'session-00015-before-cleanup'
        assert inventory(copy)==read(preserved/'partial-before.json')
        initial_raw=(copy/'journal/mutations.jsonl').read_bytes()
        old_rows=[json.loads(line) for line in initial_raw.splitlines()]
        assert len(old_rows)==1 and old_rows[0]['type']=='initial'
        row=dict(old_rows[0]);digest=row.pop('record_sha256')
        assert hashlib.sha256(canonical(row)).hexdigest()==digest and row['previous_record_sha256']=='0'*64
        assert row['state']==read(checkpoint/'filesystem-namespace.json')
        from content_store import Store
        content=Store(copy/'journal')
        for node in row['state']['nodes'].values():
            if node.get('sha256'):
                raw=content.get(node['sha256']);assert len(raw)==node['size'] and hashlib.sha256(raw).hexdigest()==node['sha256']
        assert (partial/'journal/mutations.jsonl').read_bytes().startswith(initial_raw)
        rows=[json.loads(line) for line in (partial/'journal/mutations.jsonl').read_bytes().splitlines()]
        assert [r['type'] for r in rows]==['initial','checkpoint','final']
        assert rows[1]['label']=='operator-retirement-session37-preflight'
        assert all(r['state']==row['state'] for r in rows)
        identity=read(partial/'journal/service-identity.json')
        import journal_reader
        proof=journal_reader.verify(partial/'journal',identity['run_id'])
        assert proof['passed'] and proof['state']==row['state']
        native_exit=read(partial/'journal/native-exit.json')
        assert native_exit['libfuse_main_return']==0 and native_exit['final_sequence']==3 and native_exit['requested_sigterm'] is False
        cleanup=read(OP/'operator-retirement.json')
        assert cleanup['passed'] is False and cleanup['exit_status']==1
        assert cleanup['cleanup']['unmount']['returncode']==0
        assert cleanup['cleanup']['error']=="RuntimeError('I/O operation on closed file')"
        runtime=read(OP/'runtime-after-cleanup.json')
        assert runtime['all_runtime_retired'] is True and runtime['active_pair_queue']==[]
        hz=int(subprocess.check_output(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',"import os;print(os.sysconf('SC_CLK_TCK'))"],text=True,encoding='utf-8').strip())
        checked('partial_startup_and_separate_operator_retirement',dict(precleanup_records=1,postcleanup_record_types=[r['type'] for r in rows],
                no_guest_mutations=True,no_native_session15=True,namespace_unchanged=True,native_exit=native_exit,
                operator_command_passed=False,operator_followup_error=cleanup['cleanup']['error'],normal_unmount_returncode=0,
                independent_runtime_retired=True,precleanup_identity=identity,
                service_start_ticks_hz=hz,service_start_to_initial_record_seconds=row['monotonic_ns']/1e9-int(identity['start_ticks'])/hz,
                limitation='The normal unmount closed the journal and service. The subsequent retirement request raced that close and returned an error; its failed receipt remains failed. Independent native-exit, final journal, process and mount evidence establish later retirement, not normal official completion.'))

        after=inventory(ROOT);save(out/'baseline-after-cleanup.json',after)
        changed={name for name in before if name in after and before[name]!=after[name]}
        added=set(after)-set(before);removed=set(before)-set(after)
        assert changed=={'sessions/session-00015/workspace/journal/mutations.jsonl'},changed
        assert added=={'sessions/session-00015/workspace/journal/native-exit.json'},added
        assert not removed,removed
        assert sha(Path(read(ROOT/'latest-execution.json')['path']))==read(preserved/'result.json')['execution_result_sha256']
        checked('preserved_failure_and_exact_operator_delta',dict(original_files=len(before),original_bytes=sum(v['bytes'] for v in before.values()),
                original_manifest_sha256=sha(preserved/'baseline-before.json'),changed=sorted(changed),added=sorted(added),removed=[],
                failed_workspace_copy=str(copy),failed_execution_receipt_unchanged=True))
        checked('original_v2_histories_unchanged',original_v2_preservation())
        maps=PAIR/'maps'
        assert read(maps/'run.json')['launched'] is False
        assert inventory(maps/'filesystem')==read(maps/'initial-filesystem.json')
        assert not (maps/'sessions').exists() and not (maps/'events.jsonl').exists() and not (maps/'latest-checkpoint.json').exists()
        checked('maps_pristine_and_unlaunched',dict(passed=True))
        assert inventory(ROOT)==after,'Official evidence changed during read-only audit'
        checked('read_only_audit_preservation',dict(passed=True,after_manifest_sha256=sha(out/'baseline-after-cleanup.json')))
        result.update(passed=True,assignments_completed=9,normal_closed_sessions=14,accepted_native_turns=14,
                      failed_workspace_startups=1,checkpoint=str(checkpoint),checkpoint_manifest_sha256=cp['manifest_sha256'],
                      later_operator_retirement_verified=True,official_recorded_retirement_complete=False,
                      recovery_or_resume_authorized=False,condition_comparison_performed=False)
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    result['finished_utc']=datetime.now(timezone.utc).isoformat();save(out/'result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='evidence'}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
