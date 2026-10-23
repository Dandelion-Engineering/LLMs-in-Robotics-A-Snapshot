"""No-model qualification of envelope, exact bounded history and full C/A/B sequence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import traceback
from common import HERE,save,sha,inherited_paths
inherited_paths()


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    result={'passed':False,'model_calls':0,'full_duration_soak':False,
            'scope':'Boundary tests, full-duration-size history replay, and actual deterministic three-C sequence; no model or claim of full-duration timing qualification.'}
    try:
        tests=subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'test_runtime_limits.py')],capture_output=True,text=True,encoding='utf-8')
        (out/'tests.log').write_text(tests.stdout+tests.stderr,encoding='utf-8')
        result['test_exit_code']=tests.returncode
        if tests.returncode:raise RuntimeError('Envelope/authority tests failed')
        from journal_c import DiskEvents
        from supervisor import canonical
        # 132,000 exact rows cover the 13,200-second block's nominal 10 Hz
        # observation count. The actual interval is still qualified by timing.
        path=out/'history-stress.jsonl';events=DiskEvents(path)
        with path.open('wb') as stream:
            for i in range(1,132001):
                item={'event_id':i,'type':'synthetic-observation','payload':{'sequence':i,'text':'x'*1024}}
                stream.write(canonical(item)+b'\n');stream.flush();events.append(item)
        assert len(events)==132000
        for i in (0,1,100,6000,36000,100000,131999):
            assert events[i]['event_id']==i+1 and events[i]['payload']['sequence']==i+1
        assert [e['event_id'] for e in events[120000:120200]]==list(range(120001,120201))
        result['history_stress']={'rows':len(events),'bytes':path.stat().st_size,'sha256':sha(path),
            'index_bytes':sys.getsizeof(events.offsets)+sys.getsizeof(events.hashes)+sum(sys.getsizeof(v) for v in events.hashes)}
        from qualify_system import run as system
        code=system(out/'system',extended_envelope=True)
        result['system_exit_code']=code
        receipt=json.loads((out/'system/receipt.json').read_text())
        result['system_receipt_sha256']=sha(out/'system/receipt.json')
        assert code==0 and receipt['passed'] and len(receipt['sessions'])==3
        result['passed']=True
    except Exception as error:result.update(error=str(error),traceback=traceback.format_exc())
    save(out/'receipt.json',result)
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();raise SystemExit(run(a.output))
