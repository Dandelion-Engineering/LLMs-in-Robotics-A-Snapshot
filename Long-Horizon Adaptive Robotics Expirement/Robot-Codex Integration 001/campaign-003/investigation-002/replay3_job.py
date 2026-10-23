"""Build and independently verify a new offline replay in this derived scope."""
import argparse
import json
from pathlib import Path
import shutil
import sys

HOME=Path(__file__).resolve().parent
sys.path.insert(0,str(HOME.parent))
sys.path.insert(0,str(HOME/'viewer-003'))
import build
import verify
sys.path.insert(0,str(HOME.parent))
from common import save,sha


def run(manifest,audit,output):
    output=Path(output).resolve()
    assert output.is_relative_to(HOME/'replays'), 'Output must stay in the new derived replay scope'
    before=shutil.disk_usage(HOME).free
    # Preserve the existing 100 GiB reserve and 2 GiB headroom, plus admit a
    # conservative 2 GiB for this derived export. No old evidence is removed.
    if before<104*1024**3:raise RuntimeError('Insufficient local capacity for derived replay admission')
    build.build(manifest,audit,output)
    verify.verify(output)
    checked=json.loads((output/'verification.json').read_text(encoding='utf-8'))
    assert checked['passed']
    total=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    after=shutil.disk_usage(HOME).free
    if total>2*1024**3 or after<102*1024**3:
        raise RuntimeError('Derived storage allowance or existing reserve reached; retain all output and stop')
    save(output/'job-receipt.json',dict(passed=True,model_calls=0,source_wrapper_sha256=sha(__file__),
        verification_sha256=sha(output/'verification.json'),retained_bytes=total,
        free_before_bytes=before,free_after_bytes=after,original_evidence_modified=False,
        browser_qa='pending; independent data verification does not establish UI behavior'))
    print(json.dumps(dict(replay=str(output),passed=True,retained_bytes=total)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('audit');p.add_argument('output');a=p.parse_args()
    run(a.manifest,a.audit,a.output)
