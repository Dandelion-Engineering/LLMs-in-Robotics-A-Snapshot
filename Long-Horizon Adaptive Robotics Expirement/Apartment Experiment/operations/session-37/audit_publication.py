"""Independent extraction readback, original preservation, and optional Git blob audit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import traceback

PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
PRIOR=Path('D:/Dandelion-Apartment-Experiment/engineering/cup-physics-session36/history001/output/protected-v2-files.json')
ANCHORS=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-36/protected-anchors.json'
def read(p):return json.loads(p.read_bytes())
def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def run(corpus,git_ref=None):
    manifest=read(corpus/'manifest.json');checks={};counts={}
    # Independent original-file enumeration, comparison to the earlier session guard.
    guard=read(PRIOR);expected={str(Path(x['path'])):x for x in guard}
    actual={str(p) for c in ('baseline','maps') for p in (PAIR/c).rglob('*') if p.is_file()}
    assert actual==set(expected)
    for i,(name,row) in enumerate(expected.items(),1):
        p=Path(name);assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],name
        if i%10000==0:print('Independent preservation',i,flush=True)
    for name,row in read(ANCHORS).items():assert digest(Path(name))==row['sha256'],name
    checks['all_original_files_and_protected_anchors_unchanged']=True
    counts['original_files']=len(guard);counts['original_bytes']=sum(x['bytes'] for x in guard)
    exported={r['path']:r for r in manifest['entries']};assert len(exported)==len(manifest['entries'])
    for name,row in exported.items():
        p=corpus/name;assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],name
        if 'source' in row:assert p.read_bytes()==(PAIR/row['source']).read_bytes(),name
    checks['every_exported_file_matches_manifest_and_direct_source']=True
    views={}
    for view in manifest['parts']:
        raw=bytearray();end=0
        for part in view['parts']:
            b=(corpus/part['path']).read_bytes();assert part['start']==end and sha(b)==part['sha256']
            raw.extend(b);end+=len(b);assert part['end']==end
        assert len(raw)==view['bytes'] and sha(raw)==view['sha256']
        if view['source']:
            assert bytes(raw)==(PAIR/view['source']).read_bytes();views[view['source']]=bytes(raw)
    checks['ordered_parts_reconstruct_exact_sources']=True
    versions=read(corpus/'versions.json')
    for key,row in versions.items():assert digest(corpus/row['path'])==key and (corpus/row['path']).stat().st_size==row['bytes']
    total_records=total_reads=0
    for condition,total in [('baseline',36),('maps',22)]:
        root=PAIR/condition;prior=None
        for number in range(1,total+1):
            sid=f'session-{number:05d}';cp=root/'checkpoints'/sid
            cm=read(cp/'manifest.json')
            for name,row in cm['files'].items():assert digest(cp/name)==row['sha256'] and (cp/name).stat().st_size==row['bytes']
            namespace=read(cp/'filesystem-namespace.json')
            required={name.lstrip('/'):namespace['nodes'][str(inode)] for name,inode in namespace['paths'].items() if stat.S_ISREG(namespace['nodes'][str(inode)]['mode'])}
            target=corpus/condition/'history'/sid/'after'
            assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}==set(required)
            for name,node in required.items():assert digest(target/name)==node['sha256'] and (target/name).stat().st_size==node['size']
            before=corpus/condition/'history'/sid/'before'
            before_map={p.relative_to(before).as_posix():digest(p) for p in before.rglob('*') if p.is_file()}
            if prior is not None:assert before_map==prior
            prior={name:node['sha256'] for name,node in required.items()}
            source=f'{condition}/sessions/{sid}/workspace/journal/mutations.jsonl'
            rows=[json.loads(x) for x in views[source].splitlines()]
            state=None;last='0'*64;finished=False;mono=-1;run_id=rows[0]['run_id']
            for i,row in enumerate(rows,1):
                got=row.pop('record_sha256');assert sha(canonical(row))==got
                assert row['previous_record_sha256']==last and row['sequence']==i and row['run_id']==run_id
                assert not finished and row['monotonic_ns']>=mono and row['clock_source']=='linux-CLOCK_MONOTONIC'
                last=got;mono=row['monotonic_ns'];kind=row['type']
                if kind=='initial':assert i==1;state=row['state'];assert sha(canonical(state))==row['state_sha256']
                elif kind=='mutation':
                    assert sha(canonical(state))==row['before_state_sha256']
                    for area in ('paths','nodes'):
                        for key in row['delta'][area]['remove']:del state[area][key]
                        state[area].update(row['delta'][area]['set'])
                    assert sha(canonical(state))==row['after_state_sha256']
                elif kind=='read':
                    key=state['nodes'][str(row['inode'])]['sha256'];assert key==row['content_sha256']
                    content=(corpus/versions[key]['path']).read_bytes()
                    assert sha(content[row['offset']:row['offset']+row['bytes']])==row['returned_sha256']
                    total_reads+=1
                elif kind in ('checkpoint','final'):
                    assert state==row['state'] and sha(canonical(state))==row['state_sha256']
                    if kind=='final':finished=True
                else:assert kind=='rejected_mutation'
                for node in state['nodes'].values():
                    if 'sha256' in node:assert node['sha256'] in versions and node['size']==versions[node['sha256']]['bytes']
            assert finished and state==namespace
            total_records+=len(rows)
        final=corpus/condition/'final'
        assert {p.relative_to(final).as_posix():digest(p) for p in final.rglob('*') if p.is_file()}==prior
        assert digest(root/'checkpoints'/f'session-{total:05d}'/'manifest.json')==manifest['conditions'][condition]['checkpoint_manifest_sha256']
    checks['all_58_journals_replay_to_verified_checkpoints']=True
    checks['all_106_final_regular_files_complete_and_byte_exact']=True
    checks['consecutive_snapshot_content_continuity']=True
    assert read(corpus/'sensitivity-scan.json')['passed'] is True
    checks['sensitivity_scan_no_unresolved_findings']=True
    if git_ref:
        paths=sorted(p for p in corpus.rglob('*') if p.is_file())
        # cat-file batch reads object bytes without checkout conversion or shell interpolation.
        names=[git_ref+':'+p.relative_to(REPO).as_posix() for p in paths]
        response=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(names)+'\n').encode(),cwd=REPO)
        offset=0
        for p in paths:
            end=response.index(b'\n',offset);head=response[offset:end].split();assert len(head)==3 and head[1]==b'blob',head
            size=int(head[2]);blob=response[end+1:end+1+size];assert blob==p.read_bytes(),str(p)
            assert response[end+1+size:end+2+size]==b'\n';offset=end+size+2
        assert offset==len(response)
        checks['git_object_readback_all_corpus_files']=True;counts['git_files']=len(paths)
    counts.update(journal_records=total_records,read_records=total_reads,unique_content_versions=len(versions),exported_files=len(exported))
    return {'passed':True,'checks':checks,'counts':counts,'git_ref':git_ref,'manifest_sha256':digest(corpus/'manifest.json')}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('corpus',type=Path);parser.add_argument('--git-ref');parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    try:result=run(a.corpus,a.git_ref)
    except Exception as e:result={'passed':False,'error':repr(e),'traceback':traceback.format_exc()}
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result),flush=True);raise SystemExit(0 if result['passed'] else 1)
