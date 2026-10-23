"""Independent delta replay: verifies chain, contents, identity and state hashes."""
import hashlib
import json
from pathlib import Path

def raw(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def hash_value(x):return hashlib.sha256(raw(x)).hexdigest()

def verify(root, expected_run, *, require_final=True):
    root=Path(root);previous='0'*64;state=None;states=[];reads=[];sessions=set();last_mono=0;final=False
    for sequence,line in enumerate((root/'mutations.jsonl').read_bytes().splitlines(),1):
        item=json.loads(line);digest=item.pop('record_sha256')
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
            states.append((sequence,json.loads(json.dumps(state))))
        elif kind=='read':
            node=state['nodes'][str(item['inode'])];assert node.get('sha256')==item['content_sha256']
            data=(root/'objects'/node['sha256']).read_bytes()[item['offset']:item['offset']+item['bytes']]
            assert hashlib.sha256(data).hexdigest()==item['returned_sha256'];reads.append(item)
        elif kind in ('checkpoint','final'):
            assert state==item['state'] and hash_value(state)==item['state_sha256']
            if kind=='final':final=True
        elif kind!='rejected_mutation':raise AssertionError('unknown record type')
        for inode,node in state['nodes'].items():
            if node.get('sha256'):
                content=(root/'objects'/node['sha256']).read_bytes()
                assert len(content)==node['size'] and hashlib.sha256(content).hexdigest()==node['sha256'],'content missing/corrupt'
        assert all(str(inode) in state['nodes'] for inode in state['paths'].values())
    assert state is not None
    if require_final:assert final,'missing final closure'
    return dict(passed=True,records=sequence,mutations=len(states),reads=len(reads),
                sessions=sorted(s for s in sessions if s),final_state_sha256=hash_value(state),
                state=state,states=states,read_events=reads)
