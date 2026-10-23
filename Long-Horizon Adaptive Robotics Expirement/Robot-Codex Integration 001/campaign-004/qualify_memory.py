"""Bounded startup-allocation diagnostic; no model or measured experiment."""
import argparse
import native_environment
import gc
import json
from pathlib import Path
import traceback
from common import save,inherited_paths
inherited_paths()
from runtime_limits import apply_limits
from scheduler import Schedule
from memory_guard import MemoryGuard

def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);rows=[];adapter=None;memory=None
    result={'passed':False,'model_calls':0,'rows':rows}
    try:
        m=apply_limits(dict(run_id=out.name,seed=173,noise_seed=44001,schedule_seed=440031,encounters=3,
             initial_order=Schedule(440031).current,mode='serve'),'development')
        memory=MemoryGuard(m['wall_cap_s']);memory.apply()
        def sample(label):rows.append({'label':label,'read':memory.read(),'memory_buffer_bytes':len(memory.values)*8})
        sample('after_declared_memory_buffer')
        from adapter import Adapter
        sample('after_imports')
        adapter=Adapter(m,out/'host',out/'public',m['run_id']);sample('after_adapter_warmup')
        from array import array
        memory.values=array('d',[0.])*8192*7
        sample('after_memory_buffer_8192_rows')
        collected=gc.collect();sample('after_preloop_collect')
        result['collected']=collected
        result['passed']=True
    except Exception as e:result.update(error=str(e),traceback=traceback.format_exc())
    finally:
        if adapter:
            try:adapter.close()
            except Exception as e:result['cleanup_error']=str(e);result['passed']=False
        if memory:memory.close()
        save(out/'receipt.json',result)
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();raise SystemExit(run(a.output))
