"""Independent original-byte and cross-clock boundary checks for the observer."""
import argparse
import bisect
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import traceback
from common import DEFAULT_ROOT,REPO,read,save,sha,canonical
from recording import Replay
from viewer import Files

def fails(fn):
    try:fn()
    except (AssertionError,ValueError,KeyError):return True
    return False

def run(out):
    out.mkdir(parents=True,exist_ok=False);r=dict(passed=False,checks={},official_sessions=0,model_calls=0,stage='independent-replay-boundaries')
    replay=None
    try:
        root=DEFAULT_ROOT/'engineering/APARTMENT-live003/output/baseline'
        work=root/'sessions/session-00001/workspace';journal=work/'journal'
        spec=importlib.util.spec_from_file_location('separate_journal_reader',REPO/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-005/verify_journal.py')
        reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
        run_id=read(work/'location.json')['run_id'];proof=reader.verify(journal,run_id)
        records=[json.loads(x) for x in (journal/'mutations.jsonl').read_bytes().splitlines()]
        clocks=[json.loads(x)['payload'] for x in (work/'clock-bridge.jsonl').read_bytes().splitlines()]
        states={records[0]['sequence']:records[0]['state'],**dict(proof['states'])}
        rows=[x for x in records if x['type'] in ('initial','mutation')]
        bounds={}
        for row in rows:
            later=next((c for c in clocks if c['linux']['linux_monotonic_ns']>=row['monotonic_ns']),None)
            if later:bounds[row['sequence']]=later['after']['sim_time']
        times=sorted(set(bounds.values()));checked=0;files=Files(root)
        for boundary in times:
            for t in (boundary-1e-7,boundary,boundary+1e-7):
                eligible=[s for s in states if s in bounds and bounds[s]<=t]
                expected=states[max(eligible)] if eligible else {'paths':{},'nodes':{}}
                current=files.material(t)[0]
                wanted=sorted(p for p,i in expected['paths'].items() if expected['nodes'][str(i)].get('sha256'))
                if current!=wanted:raise ValueError('Namespace differs before/at/after measured boundary')
                for path in wanted:
                    node=expected['nodes'][str(expected['paths'][path])]
                    content=files.file(path,t)['content']
                    if node['size']<256*1024:
                        original=(journal/'objects'/node['sha256']).read_bytes().decode('utf-8',errors='replace')
                        if content!=original:raise ValueError('Displayed file content differs from independently replayed bytes')
                checked+=1
        r['checks']['before_at_after_every_mutation_bound']=checked==3*len(times) and len(times)>1
        r['checks']['initial_before_state_labeled']='No earlier retained version' in files.file('/RobotAgentPrompt.md',1e9)['diff']
        r['checks']['post_stop_final_namespace']=files.material(1e9)[0]==sorted(p for p,i in proof['state']['paths'].items() if proof['state']['nodes'][str(i)].get('sha256'))
        replica=out/'damaged';target=replica/'sessions/session-00001/workspace';shutil.copytree(journal,target/'journal')
        r['checks']['missing_clocks_withhold_files']=not Files(replica).listing(1e9)['files']
        item=next(n for n in proof['state']['nodes'].values() if n.get('sha256'))
        (target/'journal/objects'/item['sha256']).write_bytes(b'CORRUPTED')
        r['checks']['independent_reader_rejects_corrupt_content']=fails(lambda:reader.verify(target/'journal',run_id))
        index=read(root/'replay/index.json');replay=Replay(root);frame=replay.frame(200)
        r['checks']['sample_age_under_50ms']=0<=frame['sample_age']<.05
        r['checks']['original_sample_identity']=sha(Path(frame['provenance']['file']))==frame['provenance']['sha256']
        replay.close();replay=None
        p=replica/'replay';p.mkdir();save(p/'index.json',[index[0]])
        (p/index[0]['file']).write_bytes(b'CORRUPTED');replay=Replay(replica)
        r['checks']['replay_rejects_corrupt_state']=fails(lambda:replay.frame(0))
        r['measurements']=dict(boundary_queries=checked,journal_records=proof['records'],mutations=proof['mutations'],source_journal_sha256=sha(journal/'mutations.jsonl'),source_replay_index_sha256=sha(root/'replay/index.json'))
        r['passed']=all(r['checks'].values())
    except BaseException as e:r.update(error=repr(e),traceback=traceback.format_exc())
    finally:
        if replay:replay.close()
        save(out/'result.json',r)
    print(canonical(r).decode());return r['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
