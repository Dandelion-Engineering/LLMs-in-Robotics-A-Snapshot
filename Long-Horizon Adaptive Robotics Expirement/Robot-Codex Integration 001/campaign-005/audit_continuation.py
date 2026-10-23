"""Independent session/occurrence accounting from retained public and protected bytes."""
import hashlib
import json
from common import canonical,sha
from continuation import assess

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def audit(episode,receipt,events,rows,manifest):
    attempts=receipt['attempted_sessions'];counts={};summaries=[];previous=None
    commands=read(episode/'host/command-registry.json')
    indexed={r['sequence']:r for r in rows}
    accepted_ids={s['session_id'] for s in receipt['sessions']}
    for attempt in attempts:
        sid=attempt['session_id'];root=episode/sid;version=attempt['order_version']
        counts[version]=counts.get(version,0)+1
        assert counts[version]==attempt['session_within_occurrence']
        assert counts[version]<=3 and attempt['occurrence']==len(counts)
        started=[e for e in events if e['type']=='invocation_start-invocation' and e['payload']['invocation']['invocation_id']==sid]
        retired=[e for e in events if e['type']=='invocation_retire-invocation' and e['payload']['invocation']['invocation_id']==sid]
        assert len(started)==len(retired)==1 and retired[0]['event_id']>started[0]['event_id']
        end=read(root/'model-ending-state.json');assert end['session_id']==sid
        assert end['public']['order_version']==version==end['physical']['order_version']
        epoch=started[0]['payload']['invocation']['authority_epoch']
        requests=[c for c in commands.values() if c.get('envelope',{}).get('authority_epoch')==epoch and c.get('actor')=='robot']
        handbacks=[c for c in requests if c['kind']=='handback']
        if previous:
            if previous['order_version']==version:
                assert previous['ending']['safe_unresolved'] and previous['ending']['admitted']
                assert started[0]['sim_time_s']>=previous['ending']['physical']['sim_time_s']
                assert not any(e['type']=='job_released' and previous['retired_event']<e['event_id']<started[0]['event_id'] for e in events)
            else:
                assert previous['session_id'] in accepted_ids
                jobs=[e['payload']['order'] for e in events if e['type']=='job_released' and previous['retired_event']<e['event_id']<started[0]['event_id']]
                assert len([j for j in jobs if j['kind']=='AB-transfer']) in (2,3)
                assert len([j for j in jobs if j['kind']=='C-placement'])==1
        sources=[*sorted(root.glob('executor-*-retirement.json')),root/'cleanup.json',root/'client/result.json']
        bound=read(root/'retirement-bound.json')
        assert bound['all_namespaces_retired'] and bound['session_id']==sid
        assert hashlib.sha256(canonical({p.name:sha(p) for p in sources})).hexdigest()==bound['evidence_sha256']
        ending=None
        if sid not in accepted_ids:
            ending=read(root/'ending.json');assert ending==read(episode/'host'/('continuation-'+sid+'.json'))|{'ok':True}
            prefix=read(root/'continuation-journal-audit.json');proof=ending['evidence']
            assert sha(root/'continuation-journal-audit.json')==proof['journal_audit_sha256']
            assert proof['retirement_evidence_sha256']==bound['evidence_sha256'] and proof['client_result_sha256']==sha(root/'client/result.json')
            assert prefix['verified']['passed'] and proof['journal_verified']
            assert prefix['before']['linux']['sequence']+1==prefix['after']['linux']['sequence']
            for bracket in (prefix['before'],prefix['after']):
                row=indexed[bracket['linux']['sequence']]
                assert row['state_sha256']==bracket['linux']['state_sha256']==proof['journal_state_sha256']
                assert row['session_id']==sid and bracket['linux']['open_handles']==0
            status={**end['public'],**retired[0]['payload']}
            recomputed=assess(status,commands,ending['physical'],proof)
            assert all(ending[k]==v for k,v in recomputed.items())
            assert ending['safe_unresolved']==all(ending['checks'].values())
            assert ending['admitted']==(ending['safe_unresolved'] and counts[version]<3)
            assert not any(e['type']=='framework_terminal_appended' and e['payload']['receipt']['record']['session_id']==sid for e in events)
        else:
            assert len([c for c in handbacks if c['status']=='completed'])==1
        summaries.append(dict(session_id=sid,occurrence=attempt['occurrence'],session_within_occurrence=counts[version],
            model_termination=attempt['model_termination'],task_outcome=attempt['task_outcome'],
            physical_placement_at_end=end['physical']['protected_placement'],
            handback_statuses=[c['status'] for c in handbacks],
            public_action_budget_at_end=end['public'].get('robot_action_budget'),
            safe_unresolved=None if ending is None else ending['safe_unresolved'],
            successor_admitted=None if ending is None else ending['admitted']))
        previous=dict(session_id=sid,order_version=version,ending=ending,retired_event=retired[0]['event_id'])
    assert len(counts)<=3 and len(attempts)<=9
    if len(accepted_ids)<3:
        assert previous['ending'] and not previous['ending']['admitted'], 'Premature block stop while qualified continuation remained'
    return dict(sessions=summaries,attempted_occurrences=len(counts),not_run_occurrences=3-len(counts),
                accepted_occurrences=len(accepted_ids),unlaunched_session_slots=9-len(attempts),
                scope='Observable state/readback accounting; no hidden reasoning or causal transfer inference.')
