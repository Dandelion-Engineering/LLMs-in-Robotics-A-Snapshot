"""Independent verification of inert derived inspection against retained inputs."""
import argparse
import base64
import bisect
import copy
import hashlib
import json
from pathlib import Path
import sys

HOME=Path(__file__).resolve().parent
sys.path.insert(0,str(HOME.parent))
from common import sha,save

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def lines(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines()]
def normalize(v):
    if isinstance(v,list):return [normalize(x) for x in v]
    if isinstance(v,dict):return {k:normalize(x) for k,x in v.items()}
    return str(v) if type(v) is int and abs(v)>9007199254740991 else v
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def script(p,prefix):
    s=p.read_text(encoding='utf-8');assert s.startswith(prefix) and s.endswith(';\n')
    return json.loads(s[len(prefix):-2])

def verify(out):
    out=Path(out).resolve();inputs=read(out/'inputs.json');episode=Path(inputs['episode']);audit=Path(inputs['audit'])
    checks={};d=script(out/'data.js','window.INSPECTION=');objects=script(out/'objects.js','window.OBJECTS=')
    for name,value in inputs['files'].items():assert (episode/name).stat().st_size==value['bytes'] and sha(episode/name)==value['sha256'],name
    assert sha(inputs['manifest'])==inputs['manifest_sha256']
    assert sha(audit/'assessment/receipt.json')==inputs['audit_receipt_sha256']
    assert sha(audit/'official-status.json')==inputs['official_status_sha256']
    q=read(audit/'official-status.json');assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
    checks['original_inputs_and_successful_independent_audit']=True
    build=read(out/'build.json')
    for name,value in build['outputs'].items():assert (out/name).stat().st_size==value['bytes'] and sha(out/name)==value['sha256'],name
    checks['all_derived_output_bytes']=True
    public=lines(episode/'host/public-history.jsonl')
    observations=[e for e in public if e['type']=='observation']
    assert len(observations)==len(d['observations'])
    for raw,shown in zip(observations,d['observations']):
        expected=copy.deepcopy(raw['payload']);expected.update(sim=raw['sim_time_s'],source='host/public-history.jsonl:'+str(raw['event_id']))
        assert normalize(expected)==shown
    anchors=d['anchors'];walls=[a['wall'] for a in anchors]
    assert len(anchors)==len(observations) and all(b>a for a,b in zip(walls,walls[1:]))
    assert all(a['sim']<=b['sim'] for a,b in zip(anchors,anchors[1:]))
    for a,e in zip(anchors,observations):assert (a['wall'],a['sim'],a['id'])==(e['wall_unix_s'],e['sim_time_s'],e['event_id'])
    caches={};widths=[]
    for event in d['events']:
        file,line=event['source'].rsplit(':',1)
        if file not in caches:caches[file]=lines(episode/file)
        raw=copy.deepcopy(caches[file][int(line)-1])
        if file=='host/public-history.jsonl':assert event['at']==raw['sim_time_s'] and event['timing']['kind']=='recorded-simulation'
        else:
            assert raw.get('params',{}).get('item',{}).get('type','').lower() not in ('reasoning','reasoningsummary')
            for item in raw.get('params',{}).get('item',{}).get('contentItems',[]):
                if item.get('type')=='inputImage':
                    pixels=base64.b64decode(item.pop('imageUrl').split(',',1)[1]);item.update(retained_pixel_sha256=hashlib.sha256(pixels).hexdigest(),bytes=len(pixels))
            wall=raw['capture_wall_unix_ns']/1e9;i=bisect.bisect_right(walls,wall)
            if i==0 or i==len(walls) and wall!=walls[-1]:assert event['at'] is None
            elif walls[i-1]==wall:assert event['at']==anchors[i-1]['sim']
            else:
                lo,hi=anchors[i-1],anchors[i]
                assert event['at']==event['timing']['sim_max']==hi['sim'] and event['timing']['sim_min']==lo['sim']
                widths.append(hi['sim']-lo['sim'])
                assert not (event['at']<=lo['sim']) and event['at']<=hi['sim'] # no premature reveal
        assert normalize(raw)==event['detail'],event['source']
    checks['exact_public_items_and_no_future_receipts']=True
    for frame in d['frames']:
        assert sha(out/frame['href'])==frame['sha256']
        event=public[int(frame['source'].rsplit(':',1)[1])-1]
        assert event['sim_time_s']==frame['at']
        assert event['payload']['capture_sim_time_s']==frame['capture']
        if event['type']=='requested_image_available':assert event['payload']['sha256']==frame['sha256']
        else:assert event['type']=='observation'
    # Join all recorder-derived frames independently through the immutable RGB
    # index as well, so the builder cannot substitute another original frame.
    sys.path.insert(0,str(HOME.parent))
    from common import inherited_paths
    inherited_paths();from recorder import Reader
    reader=Reader(episode/'host/native-recording')
    try:
        indexed={e['id']:e for e in reader.images() if e['status']=='available'}
        for f in d['frames']:
            if not str(f['id']).startswith('requested-'):
                source=indexed[f['id']];assert (f['capture'],f['sha256'])==(source['capture_time_s'],source['rgb_sha256'])
    finally:reader.db.close()
    checks['original_pixels_capture_and_publication_identity']=True
    journal=lines(audit/'assessment/raw/journal/mutations.jsonl');assert normalize(journal)==d['journal']
    state=copy.deepcopy(journal[0]['state']);previous='0'*64
    for record in journal:
        r=copy.deepcopy(record);digest=r.pop('record_sha256');assert hashlib.sha256(canonical(r)).hexdigest()==digest
        assert r['previous_record_sha256']==previous;previous=digest
        if r['type']=='mutation':
            assert hashlib.sha256(canonical(state)).hexdigest()==r['before_state_sha256']
            for area in ('paths','nodes'):
                for k in r['delta'][area]['remove']:del state[area][k]
                state[area].update(r['delta'][area]['set'])
            assert hashlib.sha256(canonical(state)).hexdigest()==r['after_state_sha256']
        elif r['type'] in ('checkpoint','final'):assert state==r['state']
    assert state==journal[-1]['state'] and hashlib.sha256(canonical(state)).hexdigest()==build['exact_final_state_sha256']
    for digest,value in objects.items():
        raw=value['text'].encode('utf-8') if value['encoding']=='utf-8' else base64.b64decode(value['text'])
        assert len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==digest
        assert sha(audit/'assessment/raw/journal/objects'/digest)==digest
    assert not set(objects).intersection(d['meta']['excluded_content_objects'])
    checks['complete_exact_journal_final_tree_and_exported_bytes']=True
    raw_brackets=lines(episode/'workspace-block/clock-brackets.jsonl')
    assert len(raw_brackets)==len(d['checkpoints'])
    for b,c in zip(raw_brackets,d['checkpoints']):
        assert normalize(b)==c['original'] and journal[c['sequence']-1]['state_sha256']==b['linux']['state_sha256']
    checks['separate_clock_checkpoints_without_linux_clock_equivalence']=True
    # In-memory corruption checks leave original evidence untouched.
    original=next(iter(objects));v=objects[original];raw=v['text'].encode() if v['encoding']=='utf-8' else base64.b64decode(v['text'])
    assert hashlib.sha256(raw+b'corrupt').hexdigest()!=original
    altered=copy.deepcopy(journal[-1]);altered['sequence']+=1;digest=altered.pop('record_sha256');assert hashlib.sha256(canonical(altered)).hexdigest()!=digest
    checks['negative_content_and_record_corruption_detected']=True
    checks['source_bytes_still_unchanged_after_verification']=all(sha(episode/name)==v['sha256'] for name,v in inputs['files'].items())
    receipt=dict(passed=all(checks.values()),model_calls=0,checks=checks,frames=len(d['frames']),public_events=len(d['events']),
        observations=len(d['observations']),journal_records=len(journal),exported_content_objects=len(objects),
        maximum_public_receipt_bracket_sim_s=max(widths),linux_checkpoint_count=len(raw_brackets),
        boundary='Exact byte history at journal records; sparse cross-clock intervals remain explicit. No scored or causal claims.',
        source_manifest_sha256=inputs['manifest_sha256'],build_sha256=sha(out/'build.json'))
    save(out/'verification.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();verify(a.output)
