"""Cross-check derived behavior counts against the independent final registries."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

HOME=Path(__file__).resolve().parent
sys.path.insert(0,str(HOME.parent))
from common import save,sha


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def verify(analysis_path,audit_root,output):
    analysis_path=Path(analysis_path).resolve();audit_root=Path(audit_root).resolve()
    derived=read(analysis_path);manifest=read(derived['manifest']);episode=Path(manifest['output'])
    audit=read(audit_root/'assessment/receipt.json');official=read(audit_root/'official-status.json')
    assert official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0
    assert audit['passed'] and sha(audit_root/'assessment/receipt.json')==derived['audit_receipt_sha256']
    assert sha(derived['manifest'])==derived['manifest_sha256']
    identities=read(audit_root/'assessment/input-identities.json')
    assert all(sha(episode/name)==value['sha256'] and (episode/name).stat().st_size==value['bytes']
               for name,value in identities.items())
    checks={'authenticated_source_inputs':True}
    coordinator=read(episode/'receipt.json')
    expected_sessions=[a['session_id'] for a in coordinator['attempted_sessions']]
    assert [s['session_id'] for s in derived['sessions']]==expected_sessions
    assert derived['declared_encounters']==manifest['encounter_limit']
    assert derived['attempted_encounters']==len(expected_sessions)
    assert derived['not_run_encounters']==manifest['encounter_limit']-len(expected_sessions)
    assert derived['accepted_terminals']==len(coordinator['sessions'])
    assert derived['joint_task_outcome']==audit['task_outcome']
    assert derived['qualification_complete']==audit['qualification_complete']
    checks['all_attempted_success_failed_and_unrun_slots']=True
    registry=list(read(episode/'host/command-registry.json').values())
    starts=sorted([r for r in registry if r['kind']=='start-invocation' and r['status']=='completed'],
                  key=lambda r:r['requested_sim_time_s'])
    assert len(starts)==len(expected_sessions)
    evidence=[]
    for index,session in enumerate(derived['sessions']):
        start=starts[index];stop=starts[index+1]['requested_sim_time_s'] if index+1<len(starts) else float('inf')
        assert start['envelope']['invocation_id']==session['session_id']
        commands=[r for r in registry if r.get('actor')=='robot'
                  and start['requested_sim_time_s']<=r['requested_sim_time_s']<stop]
        physical=[r for r in commands if r['kind']=='command']
        assert len(physical)==session['physical_requests']
        statuses=dict(Counter(r['status'] for r in physical))
        assert statuses==session['physical_terminal_statuses'],(session['session_id'],statuses)
        assert sum(r['kind']=='observe' for r in commands)==session['explicit_observe_requests']
        registry_handbacks={r['request_id']:r['status'] for r in commands if r['kind']=='handback'}
        displayed_handbacks={e['request_id']:e['status'] for e in session['handbacks']}
        assert registry_handbacks==displayed_handbacks
        evidence.append(dict(session_id=session['session_id'],physical_requests=len(physical),
            statuses=statuses,handbacks=registry_handbacks))
    checks['per_session_counts_from_final_command_registry']=True
    with (audit_root/'assessment/raw/journal/mutations.jsonl').open(encoding='utf-8') as stream:
        journal=[json.loads(s) for s in stream]
    state=journal[-1]['state'];expected={path:state['nodes'][str(inode)] for path,inode in state['paths'].items()
        if path.startswith(('/notes/','/programs/','/.continuity/'))}
    assert derived['artifacts']['final_inventory']==expected
    assert derived['artifacts']['final_state_sha256']==journal[-1]['state_sha256']==audit['measurements']['journal']['final_state_sha256']
    for event in derived['artifacts']['reads']:
        original=journal[event['sequence']-1]
        assert original['type']=='read'
        for key in ('sequence','session_id','path','bytes','offset','content_sha256','returned_sha256','monotonic_ns','process'):
            assert event[key]==original.get(key),(event['sequence'],key)
    checks['exact_final_inventory_and_content_read_references']=True
    assert all(sha(episode/name)==value['sha256'] for name,value in identities.items())
    checks['original_source_bytes_unchanged']=True
    result=dict(passed=True,model_calls=0,checks=checks,sessions=evidence,
        analysis_sha256=sha(analysis_path),verifier_sha256=sha(__file__),
        scope='Independent registry/denominator/final-inventory readback. Semantic reuse and causal claims still require their separate evidence.')
    save(output,result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('analysis');p.add_argument('audit');p.add_argument('output');a=p.parse_args()
    verify(a.analysis,a.audit,a.output)
