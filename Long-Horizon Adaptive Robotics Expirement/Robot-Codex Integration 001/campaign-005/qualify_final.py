"""Independent complete system readback including unresolved session boundaries."""
import argparse
import json
from pathlib import Path
import traceback
from common import HERE,REPO,MAP,save,sha

def run(episode,job,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);episode=Path(episode)
    result={'passed':False,'model_calls':0,'checks':{}}
    try:
        from qualify_audit import run as inherited
        assert inherited(episode,job,out/'system-audit')==0
        checks=result['checks'];checks['inherited_sixteen_system_checks']=True
        r=json.loads((episode/'receipt.json').read_text());assert r['passed']
        assert len(r['safe_unresolved_fixtures'])==2 and len(r['sessions'])==3
        namespaces=[]
        for fixture in r['safe_unresolved_fixtures']:
            sid=fixture['session_id'];root=episode/sid
            ending=json.loads((root/'ending.json').read_text())
            assert ending['safe_unresolved'] and ending['admitted'] and all(ending['checks'].values())
            assert ending==json.loads((episode/'host'/('continuation-'+sid+'.json')).read_text())|{'ok':True}
            before=json.loads((episode/(sid+'-before-world.json')).read_text())
            assert before==fixture['before'] and before['order_version']==ending['order_version']
            prefix=json.loads((root/'continuation-journal-audit.json').read_text())
            assert prefix['verified']['passed'] and prefix['verified']['final_state_sha256']==ending['evidence']['journal_state_sha256']
            assert sha(root/'continuation-journal-audit.json')==ending['evidence']['journal_audit_sha256']
            probe=json.loads((root/'neutral-probe.json').read_text());namespaces.append((probe['pid_namespace'],probe['process_start_ticks']))
            assert probe['scratch_initially_absent']
        assert len(set(namespaces))==2
        assert r['safe_unresolved_fixtures'][1]['probe']['read_prior']=='neutral durable bytes 1'
        assert json.loads((episode/'continuation-session-2/rejected-handback.json').read_text())['command']['status']=='rejected'
        assert r['fourth_session_refused'] and json.loads((episode/'fourth-session-refusal.json').read_text())['error']['code']=='admission_unavailable'
        checks['same_occurrence_world_files_fresh_processes_and_hard_ceiling']=True
        from qualify_continuation import negative_tests
        assert negative_tests()['passed'];checks['adverse_endings_fail_closed']=True
        events=[json.loads(l) for l in (episode/'host/public-history.jsonl').read_text().splitlines()]
        assert sum(e['type']=='framework_terminal_appended' for e in events)==3
        assert not any('max_sessions_per_occurrence' in json.dumps(e) or 'session_within_occurrence' in json.dumps(e) for e in events)
        assert not any('invocation_count' in json.dumps(e) for e in events)
        checks['no_false_success_append_or_hidden_counter_exposure']=True
        c4=HERE.parent/'campaign-004'
        for name in ('Tasks.md','Robot.md','robot.py'):
            assert sha(HERE/'template'/name)==sha(c4/'template'/name)
        for name in ('bootstrap_client.py','executor_capture.py'):assert sha(HERE/name)==sha(c4/name)
        prompt=(HERE/'template/RobotAgentPrompt.md').read_text()
        tools=(HERE/'template/Tools.md').read_text()
        assert all(s in prompt for s in ('read Continuity.md','path, purpose','limitations','ArtifactInventory.json','no future invocation is guaranteed'))
        assert all(s not in prompt+tools for s in ('No particular artifact or memory strategy','three sessions','nine sessions','max_sessions_per_occurrence','format_label.py','c_step.py'))
        checks['domain_general_memory_contract_and_unchanged_task_model_interface']=True
        from audit_inventory import verify_inventory
        journal=out/'system-audit/raw/journal'
        inventories=verify_inventory(journal);save(out/'inventory-audit.json',inventories)
        assert inventories['count']==5
        for number in (1,2):
            probe=json.loads((episode/f'continuation-session-{number}/memory-probe.json').read_text())
            assert all(probe['checks'].values())
            rows=[json.loads(l) for l in (journal/'mutations.jsonl').read_bytes().splitlines()]
            actual=[r for r in rows if r['session_id']==f'continuation-session-{number}' and r.get('process',{}).get('pid_namespace')==probe['pid_namespace']]
            reads=[r for r in actual if r['type']=='read' and r['bytes']>0]
            assert any(r['path']=='/ArtifactInventory.json' for r in reads)
            if number==2:
                assert any(r['path']=='/.continuity/Continuity.md' for r in reads)
                assert any(r['path']=='/programs/format_label.py' for r in reads)
        checks['durable_handoff_inventory_artifact_read_execute_update_and_replay']=True
        identity=json.loads((c4/'qualification/identity-001/receipt.json').read_text());assert identity['passed'] and len(identity['cases'])==432
        prior=json.loads((MAP/'releases/RCI001-C04-dev/RCI001-C04-dev-001/snapshot.json').read_text())
        for name in ('cell_c.py','sensor_c.py','controller.py','evaluate_c.py'):
            path=c4/name;assert sha(HERE/name)==sha(path)==prior['source'][path.relative_to(REPO).as_posix()]['sha256']
        checks['qualified_identity_sources_unchanged']=True
        result['passed']=all(checks.values())
        result['runtime_sources']={p.name:sha(p) for p in HERE.glob('*.py')}
        official=json.loads((out/'system-audit/source-job.json').read_text())
        executed=Path(official['cwd'])/official['argv'][-1]
        execution_snapshot=json.loads(executed.with_name('snapshot.json').read_text())
        reader_repairs={}
        for p in HERE.glob('*.py'):
            prior_sha=execution_snapshot['source'][p.relative_to(REPO).as_posix()]['sha256']
            if sha(p)!=prior_sha:
                assert p.name in ('preservation.py','qualify_final.py'), 'Post-execution runtime drift: '+p.name
                reader_repairs[p.name]={'executed_declaration_sha256':prior_sha,'current_reader_sha256':sha(p),
                    'scope':'Independent read-only audit repair, never imported by the running apparatus or model.'}
        result['independent_reader_repairs']=reader_repairs
        result['qualified_system_snapshot_sha256']=sha(executed.with_name('snapshot.json'))
        checks['qualification_uses_exact_executed_sources']=True
        result['template_sources']={p.relative_to(HERE).as_posix():sha(p) for p in (HERE/'template').rglob('*') if p.is_file()}
        result['scope']='Deterministic apparatus and independent evidence qualification; no model performance result.'
    except Exception as e:result.update(passed=False,error=str(e),traceback=traceback.format_exc())
    save(out/'receipt.json',result);print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('job');p.add_argument('output');a=p.parse_args();raise SystemExit(run(a.episode,a.job,a.output))
