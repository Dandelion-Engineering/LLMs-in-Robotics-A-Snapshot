"""Independent retained-evidence audit and read-only review artifact generation."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import traceback
import xml.etree.ElementTree as ET
from common import HERE,REPO,QUEUE,MAP,inherited_paths,save,sha,canonical
inherited_paths()
from verify_journal import verify

def run(episode,job_id,output):
    episode=Path(episode).resolve();out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    result={'passed':False,'model_calls':0,'checks':{}};checks=result['checks']
    try:
        job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',job_id],text=True,encoding='utf-8'))
        assert job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0
        save(out/'source-job.json',job);checks['official_success_int_zero']=True
        receipt=json.loads((episode/'receipt.json').read_text());assert receipt['passed'] and receipt['model_calls']==0
        assert len(receipt['sessions'])==3 and all(s['actions']==12 and s['clean_retirement'] for s in receipt['sessions'])
        checks['three_successful_no_model_sessions']=True
        raw=out/'raw';raw.mkdir();archive=episode/'workspace-block/evidence.tar.gz'
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar.getmembers():
                dest=(raw/member.name).resolve()
                assert dest.is_relative_to(raw.resolve()) and not member.issym() and not member.islnk()
                assert member.isfile() or member.isdir()
            tar.extractall(raw,filter='data')
        journal=raw/'journal';replay=verify(journal,episode.name)
        assert {k:v for k,v in replay.items() if k not in ('state','states','read_events')}==receipt['filesystem']
        rows=[json.loads(s) for s in (journal/'mutations.jsonl').read_text().splitlines()]
        checks['independent_complete_reconstruction']=True
        source=Path(job['cwd'])/job['argv'][-1]
        declaration=json.loads(source.read_text());snapshot=declaration['source_snapshot_sha256']
        assert all(r['source_revision']==declaration['revision_id'] and r['source_snapshot_sha256']==snapshot for r in rows)
        assert all(r['run_id']==episode.name for r in rows)
        checks['every_record_source_run_session_bound']=True
        mutations=[r for r in rows if r['type']=='mutation']
        assert all('process' in r for r in mutations)
        assert any(r['process'].get('namespace_role')=='isolated-runtime' for r in mutations)
        assert any(r['process'].get('namespace_role')=='outer-runtime' for r in mutations)
        result['unavailable_process_identities']=sum(r.get('process',{}).get('identity_unavailable',False) for r in rows)
        checks['caller_namespace_attribution_retained']=True
        # A disappearing file and overwritten bytes must exist in actual old states.
        transient=[s for _,s in replay['states'] if '/notes/transient' in s['paths']]
        assert transient and '/notes/transient' not in replay['state']['paths']
        state=transient[-1];node=state['nodes'][str(state['paths']['/notes/transient'])]
        assert (journal/'objects'/node['sha256']).read_bytes()==b'exact short-lived bytes'
        final=replay['state'];note_node=final['nodes'][str(final['paths']['/.continuity/Continuity.md'])]
        note=(journal/'objects'/note_node['sha256']).read_bytes()
        assert note.startswith(b'Agent-authored test continuity.\n') and note.count(b'Machine-authored terminal record')==3
        assert (episode/'public/Continuity.md').read_bytes()==note
        checks['transient_and_terminal_bytes_exact']=True
        brackets=[json.loads(s) for s in (episode/'workspace-block/clock-brackets.jsonl').read_text().splitlines()]
        indexed={r['sequence']:r for r in rows}
        for b in brackets:
            row=indexed[b['linux']['sequence']]
            assert row['run_id']==b['run_id'] and row['session_id']==b['session_id']
            assert row['state_sha256']==b['linux']['state_sha256'] and row['monotonic_ns']==b['linux']['linux_monotonic_ns']
            assert b['before']['windows_perf_ns']<=b['after']['windows_perf_ns']
        result['clock_brackets']={'count':len(brackets),'maximum_width_ms':max((b['after']['windows_perf_ns']-b['before']['windows_perf_ns'])/1e6 for b in brackets)}
        assert result['clock_brackets']['maximum_width_ms']<=150
        checks['cross_clock_brackets_bound']=True
        from timing import verify_timing
        timing=verify_timing(episode/'host');assert timing['actual_host_timing_pass']
        result['timing']={k:v for k,v in timing.items() if k!='timing'};checks['strict_timing_independently_replayed']=True
        events=[json.loads(s) for s in (episode/'host/public-history.jsonl').read_text().splitlines()]
        assert [e['event_id'] for e in events]==list(range(1,len(events)+1))
        assert all(e['run_id']==episode.name for e in events)
        assert not any(e['type']=='operator_plant_reload' for e in events)
        assert not any('schedule_seed' in json.dumps(e) for e in events)
        jobs=[e['payload']['order'] for e in events if e['type']=='job_released']
        assert sum(j['kind']=='AB-transfer' for j in jobs)==5 and sum(j['kind']=='C-placement' for j in jobs)==2
        checks['separated_jobs_and_public_truth_boundary']=True
        for session in receipt['sessions']:
            sid=session['session_id'];rid=session['accepted_handback'];append=session['terminal_append']
            handbacks=[e for e in events if e['type']=='control_owner_changed' and e['payload'].get('request_id')==rid]
            resumes=[e for e in events if e['type']=='conventional_resumed' and e['payload']['handback_request_id']==rid]
            assert len(handbacks)==len(resumes)==1 and handbacks[0]['event_id']<resumes[0]['event_id']
            assert append['record']['accepted_event_id']==handbacks[0]['event_id']
            assert append['record']['resumption_event_id']==resumes[0]['event_id']
            assert append['record']['retirement_evidence_sha256']==json.loads((episode/sid/'retirement-bound.json').read_text())['evidence_sha256']
            for path in (episode/sid).glob('executor-*-retirement.json'):
                retirement=json.loads(path.read_text());assert retirement['qualified']
                assert sid in retirement['identity_path']
            views=[json.loads(s) for s in (episode/'host'/('image-views-'+sid+'.jsonl')).read_text().splitlines()]
            assert len(views)==1 and views[0]['sha256']==sha(episode/sid/'model-interface-image.png')
            published=next(e for e in events if e['event_id']==views[0]['publication_event_id'])
            assert published['payload']['sha256']==views[0]['sha256'] and published['authority_epoch']==views[0]['authority_epoch']
        checks['image_and_terminal_identity_chains']=True
        from protocol_check import validate
        from image_sensor import TOOL
        schema=json.loads((HERE/'protocol/ThreadStartParams.json').read_text())
        validate(TOOL,schema['definitions']['DynamicToolSpec'],schema)
        checks['registered_dynamic_tool_schema']=True
        from coordinator import approved_manifest
        try:approved_manifest(None)
        except RuntimeError:checks['coordinator_requires_human_review']=True
        else:raise AssertionError('Default launch authority')
        coordinator=(HERE/'coordinator.py').read_text()
        assert not any(s in coordinator for s in ('points=','qualify_system','fs_guest_probe','reference_actions'))
        for p in HERE.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
        checks['production_coordinator_has_no_developer_motion']=True
        # Exact original scene after removing only the declared C additions.
        from cell_c import build_scene,original_scene,base,BASE_ZONES
        xml,_=build_scene(3,173);root=ET.fromstring(xml)
        root.find('worldbody').remove(root.find("worldbody/body[@name='C1']"));root.find('worldbody').remove(root.find("worldbody/geom[@name='zone_C_pad']"))
        root.find('asset').remove(root.find("asset/material[@name='tagmat_C1']"))
        zones=base.ZONES
        try:base.ZONES=BASE_ZONES;original,_=original_scene(3,173)
        finally:base.ZONES=zones
        assert ET.tostring(root)==ET.tostring(ET.fromstring(original));checks['final_scene_original_hardware_physics_exact']=True
        from preservation import verify as preserve
        preserve(HERE/'preservation-baseline.json',out/'preservation.json');checks['campaign002_and_frozen_sources_unchanged']=True
        from build_viewer import build
        result['viewer']=build(episode,replay,rows,journal)
        assert result['viewer']['last_frame_sim_time_s']>=receipt['sessions'][-1]['resumption']['sim_time_s']-3
        checks['late_camera_evidence_retained']=True
        inputs={str(p.relative_to(HERE)).replace('\\','/'):sha(p) for p in episode.rglob('*') if p.is_file()}
        save(out/'input-identities.json',inputs);result['input_file_count']=len(inputs)
        result['filesystem']={k:v for k,v in replay.items() if k not in ('state','states','read_events')}
        result['passed']=all(checks.values())
    except Exception as error:result.update(error=str(error),traceback=traceback.format_exc())
    save(out/'receipt.json',result);print(json.dumps(result),flush=True);return 0 if result['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('job');p.add_argument('output');a=p.parse_args();raise SystemExit(run(a.episode,a.job,a.output))
