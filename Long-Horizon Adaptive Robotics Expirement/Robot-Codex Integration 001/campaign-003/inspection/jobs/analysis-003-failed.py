"""Evidence-only encounter accounting and observable artifact inventory."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

HOME=Path(__file__).resolve().parent
sys.path.insert(0,str(HOME.parent))
from common import save,sha

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8').splitlines()]

def analyze(episode,audit):
    episode=Path(episode);audit=Path(audit);r=read(episode/'receipt.json')
    a=read(audit/'assessment/receipt.json');queue=read(audit/'official-status.json')
    manifest=read(read(audit/'declaration.json')['source_manifest'])
    declared=manifest['encounter_limit']
    assert queue['state']=='succeeded' and type(queue['exit_status']) is int and queue['exit_status']==0 and a['passed']
    expected=read(audit/'assessment/input-identities.json')
    for name,value in expected.items():assert sha(episode/name)==value['sha256']
    public=rows(episode/'host/public-history.jsonl');events=Counter(e['type'] for e in public)
    commands=[e for e in public if e['type']=='command_requested' and e['payload']['actor']=='robot']
    physical=[e for e in commands if e['payload']['kind']=='command']
    rejected=[e for e in public if e['type']=='command_rejected']
    terminal=[e for e in public if e['type']=='command_terminal' and e['payload']['request_id'] in {c['payload']['request_id'] for c in physical}]
    journal=rows(audit/'assessment/raw/journal/mutations.jsonl');final=journal[-1]['state']
    persistent={p:final['nodes'][str(i)] for p,i in final['paths'].items() if p.startswith(('/notes/','/programs/','/.continuity/'))}
    sessions=[]
    for attempt in r['attempted_sessions']:
        root=episode/attempt['session_id'];client=read(root/'client/result.json');capture=rows(root/'client/events.jsonl')
        items=[dict(line=i,item=e['params']['item'],wall_ns=e['capture_wall_unix_ns']) for i,e in enumerate(capture,1) if e.get('method')=='item/completed']
        shell=[x for x in items if x['item']['type']=='commandExecution']
        by_command=Counter()
        for x in shell:
            c=x['item']['command']
            for key in ('status','query','history','observe','handback','manual','continuity'):
                if 'robot.py '+key in c:by_command[key]+=1;break
            else:by_command['other']+=1
        sessions.append(dict(session_id=attempt['session_id'],thread_id=client['thread_id'],model=client['model_effective'],
            effort=client['effort_effective'],auth=client['auth_type'],model_termination=attempt.get('model_termination','bounded_deadline'),
            public_item_counts=dict(Counter(x['item']['type'] for x in items)),shell_command_kinds=dict(by_command),
            shell_exit_codes=dict(Counter(str(x['item'].get('exitCode')) for x in shell)),
            messages=[dict(source=attempt['session_id']+'/client/events.jsonl:'+str(x['line']),wall_ns=x['wall_ns'],text=x['item']['text']) for x in items if x['item']['type']=='agentMessage'],
            commands=[dict(source=attempt['session_id']+'/client/events.jsonl:'+str(x['line']),wall_ns=x['wall_ns'],command=x['item']['command'],exit_code=x['item'].get('exitCode')) for x in shell]))
    handbacks=[]
    for e in rejected:
        if e['payload'].get('kind')!='handback':continue
        ob=next(x for x in reversed(public[:e['event_id']-1]) if x['type']=='observation')
        p=ob['payload'];d=next((d for d in p['detections'] if d['id']=='C1'),None);pad=p['workcell_geometry']['C_pad']
        margins=[pad['half_extent_xy_m'][i]-abs(d['pos'][i]-pad['center_xy_m'][i])-.021-d['uncertainty_m'] for i in (0,1)] if d else None
        handbacks.append(dict(event_id=e['event_id'],sim_time_s=e['sim_time_s'],error=e['payload']['error'],
            preceding_observation_event_id=ob['event_id'],observation_sequence=p['sequence'],
            public_containment_margin_m=margins,
            boundary='Derived from the nearest preceding retained public observation; exact internal packet is not separately frozen at handback. No threshold change.'))
    return dict(run_id=episode.name,joint_task_outcome='failure' if not r['sessions'] else 'see_sessions',
        source_coordinator_error_kind=r.get('error_kind'),original_auditor_task_outcome=a['task_outcome'],
        audit_passed=True,qualification_complete=a['qualification_complete'],declared_encounters=declared,
        attempted_encounters=len(r['attempted_sessions']),not_run_encounters=declared-len(r['attempted_sessions']),
        protected_C_outcome=a['measurements']['protected_C_outcome'],accepted_handbacks=len(r['sessions']),
        public_host_counts=dict(events),physical_requests=len(physical),physical_terminal_statuses=dict(Counter(e['payload'].get('feedback',{}).get('status') or e['payload'].get('status','unknown') for e in terminal)),
        explicit_observe_requests=sum(e['payload']['kind']=='observe' for e in commands),actual_image_deliveries=a['measurements']['actual_image_deliveries'],
        handback_rejections=handbacks,persistent_final_inventory=persistent,
        final_continuity_equals_initial=a['measurements'].get('canonical_continuity_equals_initial'),
        journal=dict(records=len(journal),mutations=sum(e['type']=='mutation' for e in journal),reads=sum(e['type']=='read' for e in journal),
            read_paths=dict(Counter(e['path'] for e in journal if e['type']=='read')),final_state_sha256=journal[-1]['state_sha256']),
        wall_elapsed_s=r['wall_elapsed_s'],retained_windows_bytes=r['retained_windows_bytes'],
        timing={k:v for k,v in r['independent_timing_replay'].items() if k!='timing'},sessions=sessions,
        claims=dict(task_related_saved_programs='none observed',task_related_saved_notes='none observed; executor-canary.txt is preflight apparatus content',
            continuity='empty and unchanged; no false machine terminal appended',reuse='not assessable: later conversations did not run',
            causal_artifact_contribution='unknown; no intervention or successful later invocation',
            comparative_efficiency='not assessed from two different unscored stages'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();c=HOME.parent
    values=[analyze(c/'live-evidence'/run,c/'qualification'/audit) for run,audit in (
        ('RCI001-C03-live-001-attempt','live-audit-003'),('RCI001-C03-pilot-001-attempt','pilot-audit-001'))]
    save(Path(a.output),dict(schema='campaign003-observable-investigation-1',model_calls=0,cases=values))
    print(json.dumps([dict(run=v['run_id'],physical_requests=v['physical_requests'],handbacks=v['accepted_handbacks'],files=list(v['persistent_final_inventory'])) for v in values]),flush=True)
