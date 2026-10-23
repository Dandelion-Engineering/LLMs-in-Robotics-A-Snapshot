"""Streaming independent journal replay; every unique content hash is checked."""
import copy
import hashlib
import json
from pathlib import Path
from content_store import Store

def raw(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def hash_value(x):return hashlib.sha256(raw(x)).hexdigest()

def verify(root,expected_run,*,require_final=True,retain_states=False,retain_reads=False):
    root=Path(root);previous='0'*64;state=None;states=[];reads=[];sessions=set();last_mono=0;final=False
    verified=set();store=Store(root);mutations=read_count=sequence=0
    for sequence,line in enumerate((root/'mutations.jsonl').open('rb'),1):
        assert line.endswith(b'\n'),'partial journal tail'
        item=json.loads(line);digest=item.pop('record_sha256')
        assert not final,'record after final'
        assert hash_value(item)==digest,'record hash'
        assert item['previous_record_sha256']==previous and item['sequence']==sequence,'chain gap'
        assert item['run_id']==expected_run,'wrong run'
        assert item['clock_source']=='linux-CLOCK_MONOTONIC' and item['monotonic_ns']>=last_mono,'clock regression'
        last_mono=item['monotonic_ns'];previous=digest;sessions.add(item.get('session_id'))
        kind=item['type']
        if kind=='initial':
            assert state is None and sequence==1
            state=item['state'];assert hash_value(state)==item['state_sha256']
        elif kind=='mutation':
            assert hash_value(state)==item['before_state_sha256'],'before mismatch'
            for area in ('paths','nodes'):
                for key in item['delta'][area]['remove']:del state[area][key]
                state[area].update(item['delta'][area]['set'])
            assert hash_value(state)==item['after_state_sha256'],'after mismatch'
            assert item['started_monotonic_ns']<=item['monotonic_ns']
            mutations+=1
            if retain_states:states.append((sequence,copy.deepcopy(state)))
        elif kind=='read':
            node=state['nodes'][str(item['inode'])];assert node.get('sha256')==item['content_sha256']
            data=store.get(node['sha256'])[item['offset']:item['offset']+item['bytes']]
            assert hashlib.sha256(data).hexdigest()==item['returned_sha256'];read_count+=1
            if retain_states or retain_reads:reads.append(item)
        elif kind in ('checkpoint','final'):
            assert state==item['state'] and hash_value(state)==item['state_sha256']
            if kind=='final':final=True
        elif kind!='rejected_mutation':raise AssertionError('unknown record type')
        for node in state['nodes'].values():
            key=node.get('sha256')
            if key and key not in verified:
                content=store.get(key)
                assert len(content)==node['size'] and hashlib.sha256(content).hexdigest()==key,'content missing/corrupt'
                verified.add(key)
        assert all(str(inode) in state['nodes'] for inode in state['paths'].values())
    assert state is not None
    if require_final:assert final,'missing final closure'
    return dict(passed=True,records=sequence,mutations=mutations,reads=read_count,
                sessions=sorted(s for s in sessions if s),final_state_sha256=hash_value(state),
                state=state,states=states,read_events=reads,verified_content_versions=len(verified))
