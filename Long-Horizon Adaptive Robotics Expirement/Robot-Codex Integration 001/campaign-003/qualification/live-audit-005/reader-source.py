"""Read retained live evidence independently; never starts a model or plant."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import traceback
from common import HERE, REPO, QUEUE, save, sha, canonical, inherited_paths
inherited_paths()
from verify_journal import verify

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def lines(path):return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]
def require(value,reason):
    if not value:raise AssertionError(reason)

def audit(manifest_path,job_id,output):
    manifest_path=Path(manifest_path).resolve();manifest=read(manifest_path)
    episode=Path(manifest['output']);out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    result={'passed':False,'model_calls':0,'checks':{},'measurements':{},'source_manifest_sha256':sha(manifest_path)}
    checks=result['checks'];measure=result['measurements'];context={}
    def check(name,action):
        try:action();checks[name]={'passed':True}
        except Exception as error:checks[name]={'passed':False,'error':str(error),'type':type(error).__name__}

    def official():
        job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',job_id],text=True,encoding='utf-8'))
        save(out/'source-job.json',job);context['job']=job
        require(job['state'] in ('succeeded','failed') and type(job['exit_status']) is int,'Official terminal queue receipt required')
        # A failed worker is diagnostic input, never a successful-run claim.
        # The separately queued reader must itself succeed before its audit is used.
        measure['original_queue_state']=job['state'];measure['original_queue_exit_status']=job['exit_status']
        require((Path(job['cwd'])/job['argv'][-1]).resolve()==manifest_path,'Queue command declaration mismatch')
    check('official_source_job',official)

    def source():
        snapshot=manifest_path.parent/manifest['source_snapshot_path'];require(sha(snapshot)==manifest['source_snapshot_sha256'],'Snapshot identity')
        import zipfile
        identities=read(snapshot)
        with zipfile.ZipFile(manifest_path.parent/'source.zip') as archive:
            require(set(archive.namelist())==set(identities['source']),'Source archive membership')
            for name,value in identities['source'].items():
                content=archive.read(name);require(hashlib.sha256(content).hexdigest()==value['sha256'] and len(content)==value['bytes'],'Archived source '+name)
                require(sha(REPO/name)==value['sha256'],'Executed source drift '+name)
        for name,value in identities['inherited'].items():require(sha(REPO/name)==value['sha256'],'Inherited source changed '+name)
        authority=manifest['authority']
        with (REPO/authority['path']).open('rb') as stream:prefix=stream.read(authority['bytes'])
        require(hashlib.sha256(prefix).hexdigest()==authority['sha256'],'Authorization prefix identity')
        measure['source_file_count']=len(identities['source']);measure['inherited_source_count']=len(identities['inherited'])
    check('source_archive_and_inherited_identity',source)

    def host():
        receipt=read(episode/'receipt.json');context['receipt']=receipt
        require(receipt['manifest_sha256']==sha(manifest_path),'Coordinator manifest identity')
        require(receipt['stage']==manifest['stage'],'Stage identity')
        require(1<=receipt['model_calls_requested']==len(receipt['attempted_sessions'])<=manifest['encounter_limit'],'Invocation denominator')
        measure['declared_encounters']=manifest['encounter_limit'];measure['attempted_encounters']=len(receipt['attempted_sessions'])
        measure['not_run_encounters']=manifest['encounter_limit']-len(receipt['attempted_sessions'])
        events=lines(episode/'host/public-history.jsonl');context['events']=events
        require([e['event_id'] for e in events]==list(range(1,len(events)+1)),'Public event gaps')
        require(all(e['run_id']==manifest['run_id'] for e in events),'Public run identities')
        require(not any(e['type']=='operator_plant_reload' or 'schedule_seed' in json.dumps(e) for e in events),'Protected plant/schedule leak')
        declared=manifest['apparatus_manifest'];require(read(episode/'host/manifest.json')==declared,'Host manifest identity')
        from timing import verify_timing
        timing=verify_timing(episode/'host');save(out/'timing-replay.json',timing)
        require(timing['actual_host_timing_pass'],'Original strict physical timing failed')
        host=read(episode/'host/result.json');require(host['execution_completed'] and host['error'] is None,'Host infrastructure failure')
        require(host['continuous_physics']['owner_finished'] and host['continuous_physics']['metrics']['owner_closed'],'Physics owner did not retire')
        require(host['continuous_physics']['metrics']['published']==host['continuous_physics']['metrics']['drained'],'Lost physics evidence')
        require(receipt.get('failed_session_cleanup',True) is True and not any(k in receipt for k in ('cleanup_error','host_forced_stop','block_cleanup_error')),'Coordinator retirement failure')
        measure['host_timing']=host['timing_v2'];measure['protected_C_outcome']=host['independent_outcome']
        measure['wall_elapsed_s']=receipt['wall_elapsed_s'];measure['retained_windows_bytes']=receipt['retained_windows_bytes']
    check('host_sequence_timing_and_truth_boundary',host)

    def journal():
        raw=out/'raw';raw.mkdir();archive=episode/'workspace-block/evidence.tar.gz'
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar.getmembers():
                require((raw/member.name).resolve().is_relative_to(raw),'Archive path escape')
                require(not member.issym() and not member.islnk() and (member.isfile() or member.isdir()),'Archive special member')
            tar.extractall(raw,filter='data')
        journal=raw/'journal';replay=verify(journal,manifest['run_id']);rows=lines(journal/'mutations.jsonl')
        native_exit=read(journal/'native-exit.json');lifetime=read(episode/'workspace-block/close-lifetime.json')
        require(lifetime['completed'] and lifetime['error'] is None,'Incomplete workspace lifetime')
        require(native_exit['run_id']==manifest['run_id'],'Native journal exit identity')
        require(rows[-1]['type']=='final' and sum(r['type']=='final' for r in rows)==1,'Unique final closure')
        require(native_exit['final_sequence']==rows[-1]['sequence'] and native_exit['final_state_sha256']==rows[-1]['state_sha256'],'Native exit final-state binding')
        requests=[r for r in rows if r.get('label')=='retirement-requested']
        if native_exit['requested_sigterm']:
            require(native_exit['libfuse_main_return'] in (0,8) and len(requests)==1,'Expected native signal-exit path')
            require(requests[0]['sequence']+1==rows[-1]['sequence'] and requests[0]['state_sha256']==rows[-1]['state_sha256'],'Mutation after retirement request')
            require(lifetime['retirement_request']['sequence']==requests[0]['sequence'],'Retirement request receipt join')
        else:
            require(native_exit['libfuse_main_return']==0 and not requests,'Unexpected native exit')
        measure['native_journal_exit']=native_exit
        context.update(journal=journal,replay=replay,rows=rows)
        summary={k:v for k,v in replay.items() if k not in ('state','states','read_events')}
        save(out/'journal-replay.json',summary);measure['journal']=summary
        require(all(r['source_revision']==manifest['revision_id'] and r['source_snapshot_sha256']==manifest['source_snapshot_sha256'] for r in rows),'Journal source binding')
        brackets=lines(episode/'workspace-block/clock-brackets.jsonl');indexed={r['sequence']:r for r in rows}
        widths=[]
        for b in brackets:
            row=indexed[b['linux']['sequence']]
            require(row['run_id']==b['run_id'] and row['session_id']==b['session_id'],'Clock identity')
            require(row['state_sha256']==b['linux']['state_sha256'] and row['monotonic_ns']==b['linux']['linux_monotonic_ns'],'Clock journal join')
            width=(b['after']['windows_perf_ns']-b['before']['windows_perf_ns'])/1e6
            require(0<=width<=150,'Clock bracket outside unchanged 150 ms limit');widths.append(width)
        measure['clock_brackets']={'count':len(widths),'maximum_width_ms':max(widths)}
    check('independent_complete_journal_and_clocks',journal)

    def models():
        receipt=context.get('receipt',read(episode/'receipt.json'));thread_ids=[];details=[];total_images=0
        events=context.get('events') or lines(episode/'host/public-history.jsonl')
        for attempt in receipt['attempted_sessions']:
            sid=attempt['session_id'];root=episode/sid;client=read(root/'client/result.json');launch=read(root/'client/launch.json')
            deadline=(client.get('error')=='Bounded app-server deadline exceeded' and client.get('model_started') is True
                and client.get('native_quiescence',{}).get('terminal_turn',{}).get('status')=='interrupted')
            require((client['success'] or deadline) and client['native_quiescence']['qualified'],'Unexpected client failure or native retirement failed')
            require(client['auth_type']=='chatgpt' and client['model_effective']=='gpt-6-astra' and client['effort_effective']=='max','Wrong auth/model/effort')
            require(client['model_started'] and (client.get('turn_status')=='completed' or deadline),'No completed or bounded-interrupted live invocation')
            require(launch['timeout_seconds']==manifest['apparatus_manifest'].get('model_timeout_s',600),'Declared model deadline changed')
            if deadline:
                require(read(episode/'host/result.json')['handbacks']==len(receipt['sessions']),'Deadline handback needs separate reconciliation')
            require(client['instruction_sources']==[] and client['mcp_active_servers']==[],'Unexpected instruction/tool sources')
            public=lines(root/'client/events.jsonl')
            starts=[e for e in public if e.get('kind')=='request' and e.get('method')=='thread/start']
            turns=[e for e in public if e.get('kind')=='request' and e.get('method')=='turn/start']
            require(len(starts)==len(turns)==1,'One fresh thread and sole initial turn required')
            require(starts[0]['params']['ephemeral'] is True and starts[0]['params']['allowProviderModelFallback'] is False,'Fresh/fallback flags')
            require(not any(e.get('method') in ('thread/resume','thread/fork') for e in public),'Conversation context was resumed')
            require(turns[0]['params']['input']==[{'type':'text','text':'Follow the instructions in RobotAgentPrompt.md.','text_elements':[]}],'Sole bootstrap changed')
            require(turns[0]['params']['model']=='gpt-6-astra' and turns[0]['params']['effort']=='max','Turn identity')
            require(launch['experimental_raw_events_requested'] is False,'Raw/private provider events requested')
            require(not any('reasoning' in e.get('method','').lower() or e.get('params',{}).get('item',{}).get('type','').lower() in ('reasoning','reasoningsummary') for e in public),'Private reasoning retained')
            for mode in ('canary','codehost-canary'):
                canary=read(root/(mode+'-stdout.json'));require(canary.get('qualified',canary.get('host_qualified')) is True,'Live namespace canary failed')
            retirement=list(root.glob('executor-*-retirement.json'));require(retirement,'Missing executor retirement')
            for path in retirement:require(read(path)['qualified'] is True,'Executor retirement unqualified')
            require(read(root/'cleanup.json')['clean'],'Runtime cleanup failed')
            views_path=episode/'host'/('image-views-'+sid+'.jsonl');views=lines(views_path) if views_path.exists() else []
            items=[e['params']['item'] for e in public if e.get('method')=='item/completed']
            for view in views:
                require(view['run_id']==manifest['run_id'] and view['session_id']==sid and view['thread_id']==client['thread_id'],'Image call identity')
                event=next(e for e in events if e['event_id']==view['publication_event_id'])
                require(event['type']=='requested_image_available' and event['payload']['sha256']==view['sha256'],'Image publication join')
                require(event['authority_epoch']==view['authority_epoch'],'Image authority epoch')
                image=episode/'public/live/observations'/('overhead-'+str(view['observation_sequence'])+'.png')
                require(sha(image)==view['sha256'] and image.stat().st_size==view['bytes'],'Image pixels identity')
                completed=[it for it in items if it.get('type')=='dynamicToolCall' and it.get('id')==view['call_id']]
                # The native completion is the independent readback that the
                # app-server accepted the result, not just a client-side send.
                require(len(completed)==1 and completed[0].get('success') is True,'Native image completion missing')
                pixels=[c for c in completed[0]['contentItems'] if c.get('type')=='inputImage']
                require(len(pixels)==1,'Native image payload missing')
                require(hashlib.sha256(base64.b64decode(pixels[0]['imageUrl'].split(',',1)[1])).hexdigest()==view['sha256'],'Native returned pixels differ')
            total_images+=len(views);thread_ids.append(client['thread_id'])
            details.append({'session_id':sid,'thread_id':client['thread_id'],'image_deliveries':len(views),
                'completed_public_items':len(items),'model':client['model_effective'],'effort':client['effort_effective'],
                'bounded_deadline':deadline,'native_retirement_qualified':True})
        require(len(thread_ids)==len(set(thread_ids))==len(receipt['attempted_sessions']),'Fresh conversation denominator')
        measure['model_sessions']=details;measure['actual_image_deliveries']=total_images
        require(total_images>0,'No actual image delivery observed; vision integration remains unqualified')
    check('real_model_isolation_retirement_and_rendered_image_delivery',models)

    def terminal():
        receipt=context.get('receipt',read(episode/'receipt.json'));events=context.get('events') or lines(episode/'host/public-history.jsonl')
        journal=context['journal'];replay=context['replay']
        if not receipt['sessions']:
            require(read(episode/'host/result.json')['handbacks']==0,'Unreconciled accepted handback')
            require(not any(e['type']=='framework_terminal_appended' for e in events),'False terminal append')
            measure['accepted_terminal_live_qualification']='not exercised; no accepted handback'
        for session in receipt['sessions']:
            sid=session['session_id'];rid=session['accepted_handback'];append=session['terminal_append'];record=append['record']
            accepted=[e for e in events if e['type']=='control_owner_changed' and e['payload'].get('request_id')==rid]
            resumed=[e for e in events if e['type']=='conventional_resumed' and e['payload']['handback_request_id']==rid]
            require(len(accepted)==len(resumed)==1,'Unique handback/resumption chain')
            require(accepted[0]['event_id']==record['accepted_event_id']<record['resumption_event_id']==resumed[0]['event_id'],'Terminal event order')
            require(record['resumption_evidence_sha256']==hashlib.sha256(canonical(session['resumption'])).hexdigest(),'Resumption hash')
            binding=read(episode/sid/'retirement-bound.json');require(binding['all_namespaces_retired'] is True,'Terminal before retirement')
            sources=[*sorted((episode/sid).glob('executor-*-retirement.json')),episode/sid/'cleanup.json',episode/sid/'client/result.json']
            require(hashlib.sha256(canonical({p.name:sha(p) for p in sources})).hexdigest()==binding['evidence_sha256']==record['retirement_evidence_sha256'],'Retirement bytes identity')
            before=(journal/'objects'/append['before_sha256']).read_bytes();after=(journal/'objects'/append['after_sha256']).read_bytes()
            require(after.startswith(before) and len(before)==append['original_bytes'],'Agent continuity prefix was altered')
            require(canonical(record) in after[len(before):],'Exact terminal content missing')
        note=replay['state']['nodes'][str(replay['state']['paths']['/.continuity/Continuity.md'])]
        note_content=(journal/'objects'/note['sha256']).read_bytes()
        mirror=episode/'public/Continuity.md'
        if mirror.exists():require(mirror.read_bytes()==note_content,'Final canonical continuity mirror differs')
        else:
            initial=context['rows'][0]['state'];initial_note=initial['nodes'][str(initial['paths']['/.continuity/Continuity.md'])]
            require(not receipt['sessions'],'Missing mirror after successful terminal append')
            measure['host_continuity_mirror']='not created: no protected commit or accepted terminal; exact canonical FUSE bytes retained'
            measure['canonical_continuity_equals_initial']=note['sha256']==initial_note['sha256']
        if not receipt['sessions']:require(b'Machine-authored terminal record' not in note_content,'Incomplete task falsely marked complete')
        measure['terminal_appends']=len(receipt['sessions'])
    check('terminal_acceptance_resumption_retirement_and_prefix',terminal)

    def preserved():
        from preservation import verify as preserve
        preserve(HERE/'preservation-baseline.json',out/'preservation.json')
    check('historical_campaigns_unchanged',preserved)
    identities={str(p.relative_to(episode)).replace('\\','/'):dict(sha256=sha(p),bytes=p.stat().st_size) for p in episode.rglob('*') if p.is_file()}
    save(out/'input-identities.json',identities);measure['input_files']=len(identities)
    result['passed']=all(c['passed'] for c in checks.values())
    result['qualification_complete']=result['passed'] and measure.get('terminal_appends',0)==manifest['encounter_limit']
    result['task_outcome']='success' if result['qualification_complete'] else 'failure' if result['passed'] and measure.get('terminal_appends',0)<manifest['encounter_limit'] else 'unknown'
    result['scope']='Read-only evidence audit; audit success is not task success or completed qualification.'
    save(out/'receipt.json',result)
    print(json.dumps({'passed':result['passed'],'checks':checks,'measurements':{k:v for k,v in measure.items() if k!='host_timing'}}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('job');p.add_argument('output');a=p.parse_args()
    raise SystemExit(audit(a.manifest,a.job,a.output))
