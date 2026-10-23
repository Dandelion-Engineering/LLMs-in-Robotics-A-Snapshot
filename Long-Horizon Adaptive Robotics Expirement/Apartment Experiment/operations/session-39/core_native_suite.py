"""Complete the two remaining core groups on the unchanged frozen release."""
from pathlib import Path
import sys
import traceback
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))
from common import read,save,sha

def main():
    out=HERE/'output';out.mkdir();result=dict(passed=False,checks={},model_calls=0,official_sessions=0)
    try:
        manifest=read(HERE/'manifest.json')
        for n,row in manifest['files'].items():assert sha(HERE/n)==row['sha256'],n
        from run import source_identity
        from environment import identity
        assert source_identity()==manifest['source_identity'] and identity()==manifest['environment']
        import current_native_stream_fixture,bundle_engineering
        for name,module in [('native_stream_bounds_and_failure_cleanup',current_native_stream_fixture),('exact_frozen_bundle_native_preflight',bundle_engineering)]:
            result['checks'][name]=module.run(out/name);save(out/'progress.json',result)
            assert result['checks'][name],name
        result['passed']=True
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(result,flush=True);return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
