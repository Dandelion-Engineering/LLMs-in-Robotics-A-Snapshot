"""Private failed-prefix reconstruction, long append stress and metadata proof."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import shutil
import sys
import threading
import traceback
from common import save,read,inventory,canonical,REPO
from content_store import Store
from failure_audit import FAILED

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='throwaway-storage-and-transport-stress',official_sessions=0,model_calls=0,checks={})
    try:
        original=FAILED/'baseline/sessions/session-00001/workspace/journal'
        target=out/'exact-failed-prefix';(target/'objects').mkdir(parents=True)
        charged=[0]
        def charge(n):charged[0]+=n
        store=Store(target,charge);store.create();state=None;versions={}
        for line in (original/'mutations.jsonl').open('rb'):
            row=json.loads(line)
            if row['type']=='initial':state=row['state']
            elif row['type']=='mutation':
                for area in ('paths','nodes'):
                    for key in row['delta'][area]['remove']:del state[area][key]
                    state[area].update(row['delta'][area]['set'])
            else:continue
            for inode,node in state['nodes'].items():
                key=node.get('sha256')
                if not key:continue
                if (target/'objects'/key).exists():
                    versions[inode]=key;continue
                raw=(original/'objects'/key).read_bytes();patch=None;args=row.get('arguments',{})
                if row.get('operation')=='write' and str(args['inode'])==inode and inode in versions:
                    old=versions[inode];at=args['offset'];data=raw[at:at+args['bytes']]
                    assert hashlib.sha256(data).hexdigest()==args['input_sha256']
                    before=store.get(old);patch=(old,min(at,len(before)),min(len(data),max(0,len(before)-at)),b'\0'*max(0,at-len(before))+data)
                assert store.put(raw,patch)==key;versions[inode]=key
        store=Store(target)
        for path in (target/'objects').iterdir():assert store.get(path.name)==(original/'objects'/path.name).read_bytes()
        result['checks']['every_original_content_version_exact']=True
        result['failed_prefix']=dict(new_store_bytes=charged[0],old_objects_bytes=sum(p.stat().st_size for p in (original/'objects').iterdir()),versions=len(list((target/'objects').iterdir())))
        stress=out/'append-stress';(stress/'objects').mkdir(parents=True)
        store=Store(stress);store.create();raw=b'';key=store.put(raw);rng=random.Random(9018);old_equivalent=0
        for i in range(8192):
            data=rng.randbytes(1024);next_raw=raw+data
            key=store.put(next_raw,(key,len(raw),0,data));raw=next_raw;old_equivalent+=len(raw)
        assert Store(stress).get(key)==raw
        size=sum(p.stat().st_size for p in stress.rglob('*') if p.is_file())
        result['append_stress']=dict(writes=8192,input_bytes=len(raw),stored_bytes=size,old_full_copy_bytes=old_equivalent)
        result['checks']['beyond_old_quota_exact']=old_equivalent>10*3*1024**3 and size<32*1024**2
        # Deliberate content damage is visible to a fresh independent reader.
        leaf=next((stress/'chunks').iterdir());prior=leaf.read_bytes();leaf.write_bytes(b'corrupt')
        rejected=False
        try:
            for p in (stress/'objects').iterdir():Store(stress).get(p.name)
        except Exception:rejected=True
        leaf.write_bytes(prior);result['checks']['corruption_rejected']=rejected
        import native_runtime
        import transport
        from frame_digest import projection
        class Fixture:
            evidence=out/'transport';abort_event=threading.Event()
        Fixture.evidence.mkdir();ledger=transport.Ledger(Fixture())
        spec=importlib.util.spec_from_file_location('inherited_inside',native_runtime.INTEGRATION/'campaign-002/harness/codehost_inside_v3.py')
        inside=importlib.util.module_from_spec(spec);sys.modules['inherited_inside']=inside;spec.loader.exec_module(inside)
        import transport_inside
        stream=io.StringIO();meta=transport_inside.Metadata(stream)
        ledger.emit('open');meta.emit('open')
        for i in range(1000000):
            fields=dict(frame_type=3,channel_id=1,payload_bytes=1024,payload_sha256=hashlib.sha256(str(i).encode()).hexdigest())
            direction='incoming' if i%2 else 'outgoing'
            ledger.emit('frame',direction=direction,**fields)
            meta.emit('frame',direction='outgoing' if i%2 else 'incoming',**fields)
        ledger.emit('namespace_output_closed');meta.emit('closed')
        rows=[json.loads(line[len(inside.PREFIX):]) for line in stream.getvalue().splitlines()]
        result['checks']['million_frame_endpoint_equality']=all(projection(ledger.events,d)==projection(rows,'outgoing' if d=='incoming' else 'incoming') for d in ('incoming','outgoing'))
        result['transport_stress']=dict(frames=1000000,payload_bytes=1024*1000000,parent_metadata_bytes=ledger.bytes,namespace_metadata_bytes=len(stream.getvalue().encode()),retained_parent_events=len(ledger.events))
        result['checks']['constant_space_metadata']=ledger.bytes<8192 and len(stream.getvalue())<8192
        rows[1]['summary']['sha256']='0'*64
        result['checks']['frame_mismatch_detected']=projection(ledger.events,'outgoing')!=projection(rows,'incoming')
        save(out/'namespace-metadata.json',rows)
        # Real evidence-write failure must set abort and permit teardown without
        # turning missing records into a qualified transport.
        class Broken:
            evidence=out/'broken-ledger';abort_event=threading.Event()
        Broken.evidence.mkdir();broken=transport.Ledger(Broken());failures=[]
        broken.on_failure=lambda:failures.append('metadata_recording_failed')
        bound=transport.inherited.MAX_LEDGER_BYTES
        transport.inherited.MAX_LEDGER_BYTES=1
        try:
            failure=broken.emit('open');teardown=broken.emit('closed')
        finally:transport.inherited.MAX_LEDGER_BYTES=bound
        result['checks']['metadata_failure_allows_unqualified_teardown']=bool(broken.integrity_error and Broken.abort_event.is_set() and failures==['metadata_recording_failed'] and failure['evidence_unavailable'] and teardown['evidence_unavailable'])
        result['passed']=all(result['checks'].values())
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
