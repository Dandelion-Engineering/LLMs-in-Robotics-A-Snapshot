"""Queued Maps terminal readback using the unchanged frozen runtime readers."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import traceback


def audit(root,code,status_path,out,expect,baseline_identity_path=None):
    sys.path.insert(0,str(code.resolve()))
    from common import canonical,inventory,read,save,sha
    from run import verify_run,source_identity
    from recording import verify_checkpoint,verify_prefix
    from recovery import terminal
    from audit import native,chain
    from repair_validation import transport_readback
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,expectation=expect,root=str(root),checks={},evidence={})
    try:
        status=read(status_path)
        assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
        result['checks']['queue_execution']=True
        run=verify_run(root,official_allowed=True);assert run['condition']=='maps'
        execution=terminal(root)
        assert execution['passed'] is True and execution['retirement']['all_retired'] is True
        assert not (root/'running.lock').exists() and not (root/'controller-failure.json').exists()
        checkpoint=Path(read(root/'latest-checkpoint.json')['path'])
        assert checkpoint.resolve().is_relative_to(root.resolve())
        result['evidence']['checkpoint']=verify_checkpoint(checkpoint)
        result['evidence']['prefix']=verify_prefix(root,checkpoint)
        state=read(checkpoint/'state.json');events=chain(root/'events.jsonl')
        assert len(events)==state['event_sequence'] and events[-1]['sha256']==state['event_chain']
        assert inventory(root/'filesystem')==inventory(checkpoint/'filesystem')
        assert sha(root/'filesystem-namespace.json')==sha(checkpoint/'filesystem-namespace.json')
        assert sha(root/'replay/index.json')==state['replay_index_sha256']
        if expect=='completed':
            completed=read(root/'completed.json')
            assert completed['assignments']==state['position']==21 and len(state['completed'])==21
            assert [r['position'] for r in state['completed']]==list(range(21))
        else:
            assert state['position']<21 and (root/'hibernate-requested.json').exists()
            assert any(s['ending'].get('hibernated') for s in execution['sessions']) or execution.get('boundary_pause',{}).get('hibernated')
        result['checks']['exact_clean_terminal_boundary']=True
        result['evidence']['native']=native(root)
        result['evidence']['transport']={s.name:transport_readback(s/'native') for s in sorted((root/'sessions').iterdir())}
        starts=[r for r in events if r['kind']=='session_started'];closed=[r for r in events if r['kind']=='session_closed']
        assert len(starts)==len(closed)==state['sessions']
        for row in starts:
            assert row['payload']['work_s']==(600 if row['payload']['task']=='throwing' else 360)
        result['checks']['native_inode_sensor_replay_transport']=True
        abandoned=0;branches=[];cursor=root;seen=set()
        while (cursor/'recovery-ready.json').exists():
            recovery=read(cursor/'recovery-ready.json');parent=Path(recovery['source']).resolve()
            assert str(parent) not in seen;seen.add(str(parent))
            assert inventory(parent)==recovery['parent_inventory']
            parent_events=chain(parent/'events.jsonl');parent_state=read(Path(recovery['checkpoint'])/'state.json')
            tail=[r for r in parent_events if r['sequence']>parent_state['event_sequence']]
            count=sum(r['kind']=='session_started' for r in tail)
            assert count==recovery['interrupted_sessions_in_parent_tail']
            abandoned+=count;branches.append(dict(parent=str(parent),abandoned_starts=count,parent_unchanged=True))
            cursor=parent
        result['evidence']['accounting']=dict(assignments=state['position'],retained_normal_sessions=state['sessions'],
            abandoned_started_sessions=abandoned,total_started_sessions=len(starts)+abandoned,branches=branches,
            physical_event_counts=dict(Counter(r['kind'] for r in events)),endpoint_session_count=len(starts)+abandoned if expect=='completed' else None)
        result['checks']['failed_tails_preserved_and_counted']=True
        if run['stage']=='official':
            pair=Path(run['official_pair_root']);prepared=read(pair/'prepared.json');frozen=pair/'frozen_repository'
            assert sha(frozen/'source-manifest.json')==prepared['source_manifest_sha256']
            expected=read(frozen/'source-manifest.json');actual=inventory(frozen);actual.pop('source-manifest.json')
            assert actual==expected
            assert baseline_identity_path is not None
            expected_baseline=read(baseline_identity_path)['baseline_identity']
            assert all(sha(pair/'baseline'/name)==digest for name,digest in expected_baseline.items())
            assert sha(root/'schedule.json')==sha(pair/'hidden-schedule.json')==prepared['schedule_sha256']
            assert sha(code/'commissioning.json')==prepared['certificate_sha256']
            result['checks']['frozen_pair_and_unchanged_baseline']=True
        result['source_identity']=source_identity();result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result)
    print(canonical({k:v for k,v in result.items() if k not in ('source_identity','evidence')}).decode())
    return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--code',type=Path,required=True)
    p.add_argument('--queue-status',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--expect',choices=('completed','hibernated'),required=True);p.add_argument('--baseline-identity',type=Path);a=p.parse_args()
    raise SystemExit(0 if audit(a.root.resolve(),a.code,a.queue_status,a.output,a.expect,a.baseline_identity) else 1)
