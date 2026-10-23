"""Read-only evidence audit. Never imports a live runtime or submits model work.

Run through the shared compute queue. Output must be outside protected inputs.
The two full SHA256 inventories bracket all evidence reads. Native notification
analysis retains protocol facts only, not assistant reasoning or image payloads.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v1-restart001')
ORIGINAL = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v1')
PRESERVED = Path('D:/Dandelion-Apartment-Experiment/failed-launches/APARTMENT-v1-baseline-launch-001')
FROZEN = PAIR/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'

def read(p): return json.loads(Path(p).read_bytes())
def canonical(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
def digest(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def save(p, x):
    with Path(p).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(x, f, ensure_ascii=False, indent=2, sort_keys=True); f.write('\n')
def inventory(root):
    rows={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink(): raise ValueError('Unexpected symlink: '+str(p))
        if p.is_file():
            s=p.stat(); h=digest(p); t=p.stat()
            assert (s.st_size,s.st_mtime_ns)==(t.st_size,t.st_mtime_ns), str(p)
            rows[p.relative_to(root).as_posix()]={'bytes':s.st_size,'sha256':h,'mtime_ns':s.st_mtime_ns}
    return rows
def compact_inventory(root):
    return {k:{'bytes':v['bytes'],'sha256':v['sha256']} for k,v in inventory(root).items()}
def select(d, names): return {k:d.get(k) for k in names.split()}
def lines(p):
    with p.open('rb') as f:
        for n,line in enumerate(f,1):
            assert line.endswith(b'\n'), (p,n,'partial tail')
            yield n,json.loads(line),len(line)

def journal_stats(j):
    kinds=Counter(); ops=Counter(); writes=defaultdict(lambda:{'writes':0,'input_bytes':0,'full_version_bytes_counterfactual':0})
    rejected=[]; initial=final=None; max_file=max_namespace=0
    for n,d,_ in lines(j/'mutations.jsonl'):
        kinds[d['type']]+=1
        if d['type']=='initial': initial=d['state']; state=json.loads(json.dumps(initial))
        if d['type']=='mutation':
            ops[d['operation']]+=1
            for area in ('paths','nodes'):
                for k in d['delta'][area]['remove']: del state[area][k]
                state[area].update(d['delta'][area]['set'])
            if d['operation']=='write':
                a=d['arguments']; row=writes[a.get('path','<unlinked>')]
                row['writes']+=1;row['input_bytes']+=a['bytes']
                row['full_version_bytes_counterfactual']+=state['nodes'][str(a['inode'])]['size']
        if d['type']=='rejected_mutation': rejected.append({'line':n,**d})
        if d['type']=='final': final=d['state']
        sizes=[x['size'] for x in state['nodes'].values() if x.get('sha256')]
        max_file=max(max_file,max(sizes,default=0));max_namespace=max(max_namespace,sum(sizes))
    sizes={name:sum(p.stat().st_size for p in (j/name).rglob('*') if p.is_file()) for name in ['objects','chunks']}
    return dict(records=sum(kinds.values()),kinds=dict(kinds),operations=dict(ops),rejected=rejected,
        writes=dict(sorted(writes.items(),key=lambda kv:kv[1]['input_bytes'],reverse=True)),
        write_input_bytes=sum(x['input_bytes'] for x in writes.values()),content_bytes=sum(sizes.values()),
        content_breakdown=sizes,metadata_bytes=(j/'mutations.jsonl').stat().st_size,
        max_file_bytes=max_file,max_namespace_bytes=max_namespace,
        initial_state_sha256=hashlib.sha256(canonical(initial)).hexdigest(),
        final_state_sha256=hashlib.sha256(canonical(final)).hexdigest() if final else None,
        final_namespace_equal_initial=final==initial)

def native_facts(p):
    methods=Counter();items=Counter();errors=[];terminal=[];rate=[];timeline=[]
    image_record_bytes=0;item_bytes=Counter();first=last=None
    for n,d,size in lines(p/'client/events.jsonl'):
        first=first or d.get('capture_wall_unix_ns');last=d.get('capture_wall_unix_ns')
        method=d.get('method');methods[method or d.get('kind')]+=1
        if d.get('kind')!='notification': continue
        q=d.get('params',{});it=q.get('item',{})
        if method=='item/completed':
            kind=it.get('type','unknown');items[kind]+=1;item_bytes[kind]+=size
            if kind=='imageToolCall': image_record_bytes+=size
        if method=='error': errors.append({'line':n,'capture_wall_unix_ns':d.get('capture_wall_unix_ns'),'params':q})
        if method in ('turn/started','turn/completed'):
            t=q['turn'];x={'line':n,'method':method,'capture_wall_unix_ns':d.get('capture_wall_unix_ns'),
                **select(t,'id status error startedAt completedAt durationMs')};timeline.append(x)
            if method=='turn/completed': terminal.append(x)
        if method=='account/rateLimits/updated':
            r=q['rateLimits']; rate.append({'line':n,**select(r,'limitId primary secondary rateLimitReachedType spendControlReached')})
    return dict(method_counts=dict(methods),completed_item_counts=dict(items),completed_item_record_bytes=dict(item_bytes),
        errors=errors,terminal=terminal,timeline=timeline,rate_notifications=rate,
        first_capture_ns=first,last_capture_ns=last,event_bytes=(p/'client/events.jsonl').stat().st_size)

def main(out):
    out=out.resolve()
    assert not any(out==p or p in out.parents for p in (PAIR,ORIGINAL,PRESERVED))
    out.mkdir(parents=True,exist_ok=False)
    roots={'restart001':PAIR,'original':ORIGINAL,'original_preservation':PRESERVED}
    before={}
    for name,root in roots.items():
        print('Hashing protected input:',name,flush=True);before[name]=inventory(root);save(out/(name+'-before.json'),before[name])
    result={'schema':'apartment-second-failure-investigation-1','started_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Read-only analysis; no live model, no repair, no simulator execution, no official mutations',
        'script_sha256':digest(Path(__file__)),'disk_free':{d:shutil.disk_usage(d+':/').free for d in ('C','D')},'sessions':[]}
    save(out/'audit-start.json',result)
    sys.path.insert(0,str(FROZEN))
    import journal_reader
    import h2_readback
    import run
    base=PAIR/'baseline'
    result['source_identity_matches']=run.source_identity()==read(base/'run.json')['source_identity']
    result['source_identity_files']=len(read(base/'run.json')['source_identity'])
    result['execution_result']=read(next(base.glob('execution-result-*.json')))
    result['maps']={'launched':read(PAIR/'maps/run.json')['launched'],
        'filesystem_matches_initial':compact_inventory(PAIR/'maps/filesystem')==read(PAIR/'maps/initial-filesystem.json'),
        'session_directory_exists':(PAIR/'maps/sessions').exists()}
    result['checkpoint_state']={x:(base/x).exists() for x in ['latest-checkpoint.json','checkpoints','completed.json','running.lock','hibernate-requested.json']}
    b=read(base/'boundary-state.json');result['boundary']=select(b,'sessions phase position completed event_sequence event_chain')
    result['boundary'].update(sim_time=b['world']['physics'][0],docked=b['world']['docked'])
    state_events=[];previous='0'*64;event_counts=Counter();samples=[]
    for n,d,_ in lines(base/'events.jsonl'):
        h=d.pop('sha256');assert hashlib.sha256(canonical(d)).hexdigest()==h
        assert d['previous']==previous and d['sequence']==n;previous=h;event_counts[d['kind']]+=1
        if d['kind'] in ['session_started','session_closed','battery_warning','docked','invalid_stop','boundary_checkpoint']:state_events.append(d)
        if d['kind']=='sensor_capture':
            f=base/'sensors'/('frame-'+str(d['payload']['sequence']).zfill(7)+'.png')
            assert digest(f)==d['payload']['image_sha256'];samples.append(str(f))
    result['events']={'records':n,'last_hash':previous,'counts':dict(event_counts),'lifecycle':state_events,'verified_sensor_images':len(samples),'chain_passed':True}
    runtime_ids=[]
    for s in sorted((base/'sessions').iterdir()):
        print('Auditing',s.name,flush=True);w=s/'workspace';native=s/'native';j=w/'journal'
        location=read(w/'location.json');jr=journal_reader.verify(j,location['run_id'])
        client=read(native/'client/result.json');br=read(native/'codehost-owner-bridge-v3.json');ret=read(w/'retirement.json')
        audit={'session':s.name,'journal_verification':select(jr,'passed records mutations reads verified_content_versions final_state_sha256'),
            'journal':journal_stats(j),'native':native_facts(native),
            'client':select(client,'success model_started preflight_passed thread_id model_effective effort_effective turn_status error finished_utc'),
            'native_quiescence':select(client['native_quiescence'],'qualified handshake_qualified forced_job_close native_exit_code start_monotonic_s completed_monotonic_s failures'),
            'native_stream':read(native/'client/native-stream.json'),
            'bridge':select(br,'qualified exit_code attempts accepted denied queue_maximum_bytes queued_bytes_at_close framing_headroom_bytes queue_with_headroom_maximum_bytes failures drain'),
            'parent_metadata_bytes':(native/'codehost-transport-v3.jsonl').stat().st_size,
            'namespace_metadata_bytes':sum(len(canonical(x))+1 for x in br['namespace_records']),
            'executor_capture_bytes':sum(x.stat().st_size for x in native.glob('executor-*-capture.jsonl')),
            'workspace_retirement':select(ret,'passed native_exit records mutations reads verified_content_versions'),
            'guest_cleanup':read(native/'cleanup.json'),'closeout_exists':(s/'closeout.json').exists(),'channels':[]}
        for c in br['channels']:
            paired=h2_readback.paired(c['h2'],c['namespace_closed']['h2'])
            meters=c['meters'];ns=c['namespace_closed']
            equal=meters['upload']==meters['client_read']==ns['upload'] and meters['download']==meters['client_written']==ns['download']
            assert equal
            audit['channels'].append({'id':c['channel_id'],'paired':paired,'byte_commitments_match':equal,'meters':meters,
                'h2':select(c['h2'],'last_stream_id open_streams closed_streams reset_streams frames bytes max_streams error')})
        if (s/'closeout.json').exists(): audit['closeout']=select(read(s/'closeout.json'),'passed report')
        assert jr['state']==read(w/'final-namespace.json')
        assert compact_inventory(w/'final-filesystem')==ret['filesystem']
        audit['final_export_matches_receipt']=True
        runtime_ids.append({'session':s.name,'service':read(j/'service-identity.json'),'location':location,
            'native':select(read(native/'client/native-owner.json'),'pid process_creation_filetime')})
        result['sessions'].append(audit);save(out/(s.name+'.json'),audit)
    result['last_export_matches_persistent_filesystem']=compact_inventory(base/'sessions/session-00006/workspace/final-filesystem')==compact_inventory(base/'filesystem')
    result['session5_namespace_equals_session6_initial']=read(base/'filesystem-namespace.json')==next(lines(base/'sessions/session-00006/workspace/journal/mutations.jsonl'))[1]['state']
    import numpy as np
    ix=read(base/'replay/index.json');last_t=last_wall=last_mono=-1;total=0;replay_bytes=0;wall_regressions=[]
    for row in ix:
        f=base/'replay'/row['file'];assert digest(f)==row['sha256'];replay_bytes+=f.stat().st_size
        with np.load(f,allow_pickle=False) as a:
            t=a['t'];wall=a['wall_ns'];mono=a['monotonic_ns'];cnt=row['samples']
            assert len(t)==cnt and len(a['qpos'])==cnt and len(a['qvel'])==cnt
            assert float(t[0])==row['first'] and float(t[-1])==row['last']
            assert np.all(np.diff(t)>=0) and t[0]>=last_t
            for k in range(len(wall)):
                prior=int(wall[k-1]) if k else last_wall
                if int(wall[k])<prior:
                    wall_regressions.append({'file':row['file'],'sample':k,'prior_wall_ns':prior,
                        'wall_ns':int(wall[k]),'delta_ns':int(wall[k])-prior,'sim_time':float(t[k]),
                        'monotonic_delta_ns':int(mono[k])-(int(mono[k-1]) if k else last_mono)})
            assert np.all(np.diff(mono)>=0) and mono[0]>=last_mono
            assert np.isfinite(a['qpos']).all() and np.isfinite(a['qvel']).all()
            last_t=float(t[-1]);last_wall=int(wall[-1]);last_mono=int(mono[-1]);total+=cnt
    result['replay']={'hash_physics_monotonic_checks_passed':True,'wall_clock_monotone':not wall_regressions,
        'wall_clock_regressions':wall_regressions,'chunks':len(ix),'samples':total,'bytes':replay_bytes,'first':ix[0],'last':ix[-1],
        'last_wall_ns':last_wall,'last_monotonic_ns':last_mono,'extra_unindexed_npz':sorted(set(p.name for p in (base/'replay').glob('*.npz'))-{r['file'] for r in ix})}
    result['original_diagnosis']=read(PRESERVED/'failed-launch-diagnosis.json')
    oldj=ORIGINAL/'baseline/sessions/session-00001/workspace/journal'
    result['original_journal']=journal_stats(oldj)
    result['original_result']=read(next((ORIGINAL/'baseline').glob('execution-result-*.json')))
    save(out/'runtime-identities.json',runtime_ids)
    save(out/'findings.json',result)
    for name,root in roots.items():
        print('Rehashing protected input:',name,flush=True);after=inventory(root);save(out/(name+'-after.json'),after)
        assert before[name]==after, 'Input changed: '+name
    result['preservation']={name:{'files':len(v),'bytes':sum(x['bytes'] for x in v.values()),'before_after_equal':True,
        'before_manifest_sha256':digest(out/(name+'-before.json')),'after_manifest_sha256':digest(out/(name+'-after.json'))} for name,v in before.items()}
    result['completed_utc']=datetime.now(timezone.utc).isoformat();result['audit_passed']=True
    save(out/'result.json',result);print(json.dumps({'audit_passed':True,'output':str(out),'sessions':len(result['sessions'])}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    try: main(args.output)
    except BaseException as e:
        if args.output.is_dir():save(args.output/'audit-error.json',{'error':repr(e),'traceback':traceback.format_exc()})
        raise
