"""Derived, inert inspection of retained attempts. Never invokes the robot."""
import argparse
import base64
import bisect
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

HOME = Path(__file__).resolve().parent
sys.path.insert(0, str(HOME.parent))
from common import HERE, REPO, sha, save, inherited_paths
inherited_paths()
from recorder import Reader
sys.path.insert(0, str(REPO / 'Tools/synchronized_replay'))
from core import clock_bracket, validate_anchors, script_json


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p): return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines()]
def safe_numbers(v):
    if type(v) is int and abs(v) > 2**53: return str(v)
    if isinstance(v, dict): return {k: safe_numbers(x) for k, x in v.items()}
    if isinstance(v, list): return [safe_numbers(x) for x in v]
    return v


def build(manifest_path, audit_path, destination):
    manifest_path=Path(manifest_path).resolve(); audit_path=Path(audit_path).resolve()
    manifest=read(manifest_path); audit=read(audit_path/'assessment/receipt.json')
    official=read(audit_path/'official-status.json')
    assert official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0
    assert audit['passed'] and audit['source_manifest_sha256']==sha(manifest_path)
    episode=Path(manifest['output']); out=Path(destination).resolve(); out.mkdir(parents=True,exist_ok=False)
    expected=read(audit_path/'assessment/input-identities.json')
    for rel, ident in expected.items():
        p=episode/rel
        assert p.stat().st_size==ident['bytes'] and sha(p)==ident['sha256'], rel
    save(out/'inputs.json',dict(manifest=str(manifest_path),manifest_sha256=sha(manifest_path),
        audit=str(audit_path),audit_receipt_sha256=sha(audit_path/'assessment/receipt.json'),
        official_status_sha256=sha(audit_path/'official-status.json'),episode=str(episode),files=expected))
    public=rows(episode/'host/public-history.jsonl')
    anchors=[dict(id=e['event_id'],line=i,wall=e['wall_unix_s'],sim=e['sim_time_s'])
             for i,e in enumerate(public,1) if e['type']=='observation']
    validate_anchors(anchors)
    start=public[0]['sim_time_s']; end=public[-1]['sim_time_s']
    events=[]; observations=[]; published={}
    for line,e in enumerate(public,1):
        typ=e['type']; source='host/public-history.jsonl:'+str(line)
        if typ=='observation':
            p=copy.deepcopy(e['payload']);p.update(sim=e['sim_time_s'],source=source)
            observations.append(p);published.setdefault(p['capture_sim_time_s'],e)
        else:
            events.append(dict(id='host:'+str(e['event_id']),kind=typ,at=e['sim_time_s'],
                timing=dict(kind='recorded-simulation',sim_min=e['sim_time_s'],sim_max=e['sim_time_s']),
                source=source,detail=e))
    counts={}; client_rows=0
    for session in sorted(episode.glob('robot-session-*')):
        path=session/'client/events.jsonl'
        if not path.exists():continue
        for line,e in enumerate(rows(path),1):
            client_rows+=1
            method=e.get('method',''); counts[method]=counts.get(method,0)+1
            item=e.get('params',{}).get('item',{})
            # Completed public items are complete text/output, so streaming
            # fragments are not duplicated. The original inventory remains bound.
            if method not in ('item/completed','turn/completed','turn/started','turn/start','thread/start'):
                continue
            if method == 'item/completed' and item.get('type') not in (
                'userMessage', 'agentMessage', 'commandExecution', 'dynamicToolCall', 'fileChange'):
                continue
            assert 'reasoning' not in method.lower() and item.get('type','').lower() not in ('reasoning','reasoningsummary')
            detail=copy.deepcopy(e)
            for part in detail.get('params',{}).get('item',{}).get('contentItems',[]):
                if part.get('type')=='inputImage':
                    raw=base64.b64decode(part.pop('imageUrl').split(',',1)[1])
                    part.update(retained_pixel_sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            wall=e.get('capture_wall_unix_ns',0)/1e9
            bracket=clock_bracket(anchors,wall)
            at=bracket.get('sim_max')
            events.append(dict(id=session.name+':'+str(line),kind=item.get('type',method),
                at=at,timing=bracket,source=session.name+'/client/events.jsonl:'+str(line),detail=detail))
    events.sort(key=lambda e:(end+1 if e['at'] is None else e['at'],e['id']))
    frames=[]; images=out/'images';images.mkdir()
    import recorder
    recorder.MAX_CONTAINER_BYTES=manifest['apparatus_manifest']['native_container_cap_bytes']
    reader=Reader(episode/'host/native-recording')
    try:
        for entry in reader.images():
            if entry['status']!='available':continue
            p=published.get(entry['capture_time_s'])
            assert p is not None,'No original publication for frame'
            raw=reader.image(entry['id'])['rgb'];digest=hashlib.sha256(raw).hexdigest()
            assert digest==entry['rgb_sha256']
            file=images/(digest+'.png')
            if not file.exists():file.write_bytes(raw)
            frames.append(dict(id=entry['id'],capture=entry['capture_time_s'],at=p['sim_time_s'],
                source='host/public-history.jsonl:'+str(p['event_id']),sha256=digest,href='images/'+file.name))
    finally:reader.db.close()
    for e in public:
        if e['type']!='requested_image_available':continue
        p=e['payload'];original=episode/'public/live/observations'/('overhead-'+str(p['observation_sequence'])+'.png')
        assert sha(original)==p['sha256']
        file=images/(p['sha256']+'.png')
        if not file.exists():shutil.copyfile(original,file)
        # Capture time is joined to the published observation, never inferred
        # from frame number or delivery time.
        matches=[o for o in observations if o.get('sequence')==p['observation_sequence']]
        assert len(matches)==1, ('image observation identity',p.keys())
        frames.append(dict(id='requested-'+str(p['observation_sequence']),capture=matches[0]['capture_sim_time_s'],
            at=e['sim_time_s'],source='host/public-history.jsonl:'+str(e['event_id']),sha256=p['sha256'],href='images/'+file.name))
    frames.sort(key=lambda f:(f['at'],f['capture']))
    journal_root=audit_path/'assessment/raw/journal'
    journal=rows(journal_root/'mutations.jsonl')
    assert journal[-1]['state_sha256']==audit['measurements']['journal']['final_state_sha256']
    brackets=rows(episode/'workspace-block/clock-brackets.jsonl')
    checkpoints=[]
    for b in brackets:
        before=clock_bracket(anchors,b['before']['windows_wall_unix_ns']/1e9)
        after=clock_bracket(anchors,b['after']['windows_wall_unix_ns']/1e9)
        checkpoints.append(dict(sequence=b['linux']['sequence'],label=b['label'],
            wall_min=b['before']['windows_wall_unix_ns']/1e9,wall_max=b['after']['windows_wall_unix_ns']/1e9,
            sim_min=before.get('sim_min'),sim_max=after.get('sim_max'),
            source='workspace-block/clock-brackets.jsonl',original=b))
    # Every persistent path and metadata delta is retained. Endpoint and canary
    # contents are deliberately never read or exported to the inspection view.
    state=copy.deepcopy(journal[0]['state']); objects={}; excluded=set(); all_objects=set()
    for e in journal:
        if e['type']=='mutation':
            for area in ('paths','nodes'):
                for k in e['delta'][area]['remove']:state[area].pop(k)
                state[area].update(e['delta'][area]['set'])
        for path,inode in state['paths'].items():
            node=state['nodes'][str(inode)];digest=node.get('sha256')
            if not digest:continue
            all_objects.add(digest)
            if path.startswith(('/live/endpoint.json','/live/canaries.json')) and node['size']:
                excluded.add(digest);continue
            if digest not in objects:
                raw=(journal_root/'objects'/digest).read_bytes()
                assert hashlib.sha256(raw).hexdigest()==digest
                try:text=raw.decode('utf-8');encoding='utf-8'
                except UnicodeDecodeError:text=base64.b64encode(raw).decode();encoding='base64'
                objects[digest]=dict(text=text,encoding=encoding,bytes=len(raw))
    for digest in excluded:objects.pop(digest,None)
    # Unlinked open inode content remains available even without a current path.
    # It is metadata-only in the UI if it has never had a safe exportable path.
    coordinator=read(episode/'receipt.json');session_boundaries=[]
    for attempt in coordinator['attempted_sessions']:
        sid=attempt['session_id'];ending=read(episode/sid/'model-ending-state.json')
        begin=next(e for e in public if e['type']=='invocation_start-invocation' and e['payload']['invocation']['invocation_id']==sid)
        session_boundaries.append(dict(at=begin['sim_time_s'],attempt=attempt,model_ending=ending,
            ending_source=sid+'/model-ending-state.json',scope='Protected analyst-only snapshot, never delivered to Robot-Codex.'))
    data=dict(meta=dict(run_id=manifest['run_id'],stage=manifest['stage'],start=start,end=end,
        outcome=('failure' if read(episode/'receipt.json').get('error_kind')=='task_failure' else audit['task_outcome']),
        original_auditor_task_outcome=audit['task_outcome'],qualification_complete=audit['qualification_complete'],
        measurements=audit['measurements'],client_records=client_rows,client_methods=counts,
        excluded_content_objects=sorted(excluded),exported_objects=len(objects),all_path_objects=len(all_objects),
        source_boundaries='Public completed items and host events; exact workspace journal. Streaming deltas remain in original evidence. No private reasoning.'),
        anchors=anchors,events=events,observations=observations,frames=frames,
        journal=journal,checkpoints=checkpoints,session_boundaries=session_boundaries)
    (out/'data.js').write_text('window.INSPECTION='+script_json(safe_numbers(data))+';\n',encoding='utf-8')
    (out/'objects.js').write_text('window.OBJECTS='+script_json(objects)+';\n',encoding='utf-8')
    for name in ('index.html','versions.js','viewer.js','viewer.css'):shutil.copyfile(HOME/name,out/name)
    save(out/'build.json',dict(schema='campaign004-inspection-build-1',model_calls=0,
        sources={str(p.relative_to(REPO)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in (HOME/'build.py',HOME/'index.html',HOME/'versions.js',HOME/'viewer.js',HOME/'viewer.css')},
        outputs={str(p.relative_to(out)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in out.rglob('*') if p.is_file()},
        frame_count=len(frames),events=len(events),observations=len(observations),journal_records=len(journal),
        exact_final_state_sha256=journal[-1]['state_sha256'],credential_content_excluded=True))
    print(json.dumps(dict(output=str(out),frames=len(frames),events=len(events),journal_records=len(journal))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('audit');p.add_argument('output');a=p.parse_args()
    build(a.manifest,a.audit,a.output)
