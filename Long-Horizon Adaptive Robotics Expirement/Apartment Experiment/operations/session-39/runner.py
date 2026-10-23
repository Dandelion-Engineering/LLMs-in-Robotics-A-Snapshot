"""Invoke one immutable test suite against the exact prospective release."""
import hashlib
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))

def main():
    manifest=json.loads((HERE/'manifest.json').read_bytes())
    for n,row in manifest['files'].items():
        assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==row['sha256'],n
    from run import source_identity
    from environment import identity
    assert source_identity()==manifest['source_identity']
    assert identity()==manifest['environment']
    mode=manifest['cases'][0]['mode']
    if mode=='offline':
        import reliability_engineering
        return 0 if reliability_engineering.run(HERE/'output') else 1
    if mode=='native':
        import revision_model_engineering
        return 0 if revision_model_engineering.run(HERE/'output') else 1
    if mode=='workspace':
        import qualify_workspace
        return qualify_workspace.main()
    if mode=='physics':
        import verify_candidate
        return verify_candidate.main()
    if mode=='recorder':
        import test_recorder
        return test_recorder.main()
    raise ValueError(mode)

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        out=HERE/'output';out.mkdir(exist_ok=True)
        if not (out/'result.json').exists():
            (out/'result.json').write_text(json.dumps(dict(passed=False,error=repr(error),traceback=traceback.format_exc()),indent=2)+'\n',encoding='utf-8')
        raise
