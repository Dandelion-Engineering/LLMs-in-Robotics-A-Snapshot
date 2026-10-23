"""Native preflight, FUSE inode continuation and failed-service retirement."""
import argparse
from pathlib import Path
import traceback
from common import save,canonical

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='throwaway-repaired-lifecycle',official_sessions=0,model_calls=0,checks={})
    space=None
    try:
        import integration_engineering,lifecycle_engineering
        result['checks']['two_condition_transport_preflight']=integration_engineering.run(out/'preflight')
        if not result['checks']['two_condition_transport_preflight']:raise ValueError('Native preflight failed')
        result['checks']['controller_and_inode_continuation']=lifecycle_engineering.run(out/'lifecycle')
        if not result['checks']['controller_and_inode_continuation']:raise ValueError('Lifecycle failed')
        from native_runtime import Workspace,linux
        from deployment import instantiate
        root=out/'write-patterns';instantiate('baseline',root/'filesystem')
        space=Workspace(root/'workspace',root/'filesystem','sparse-overwrite-truncate')
        measured=linux("""import hashlib,json,pathlib,random,sys
p=pathlib.Path(sys.argv[1])/'patterns.bin';expected=b'';rng=random.Random(841)
with p.open('w+b',buffering=0) as f:
 for i in range(96):
  at=rng.randrange(0,max(1,len(expected)+4096));data=rng.randbytes(1000+i)
  f.seek(at);assert f.write(data)==len(data)
  expected=expected[:at].ljust(at,b'\\0')+data+expected[at+len(data):]
  if i%7==0:
   size=rng.randrange(0,131072);f.truncate(size);expected=expected[:size].ljust(size,b'\\0')
  f.seek(0);assert f.read()==expected
print(json.dumps({'sha256':hashlib.sha256(expected).hexdigest(),'bytes':len(expected)}))
""",space.workspace)
        final,proof=space.close();space=None
        import json
        from common import sha
        expected=json.loads(measured)
        result['checks']['sparse_overwrite_truncate_readback']=proof['passed'] and sha(final/'patterns.bin')==expected['sha256'] and (final/'patterns.bin').stat().st_size==expected['bytes']
        root=out/'abnormal';instantiate('baseline',root/'filesystem')
        space=Workspace(root/'workspace',root/'filesystem','injected-size-failure')
        linux("import pathlib,sys;p=pathlib.Path(sys.argv[1])/'oversize';f=p.open('wb');f.seek(16*1024**2);\ntry:f.write(b'x');f.flush()\nexcept OSError:pass\ntry:f.close()\nexcept OSError:pass",space.workspace)
        refused=False
        try:space.close()
        except Exception:refused=True
        result['checks']['poisoned_filesystem_not_promoted']=refused
        space.abort();result['checks']['failed_service_retired']=space.process.poll() is not None
        result['checks']['failed_mount_absent']=linux("import os,sys;print(os.path.ismount(sys.argv[1]))",space.workspace).strip()=='False'
        space=None
        result['passed']=all(result['checks'].values())
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    finally:
        if space:
            try:space.abort()
            except BaseException as e:result['abort_error']=repr(e)
    save(out/'result.json',result);print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
