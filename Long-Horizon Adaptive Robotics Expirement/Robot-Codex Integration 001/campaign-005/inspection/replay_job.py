"""Build and independently verify an inert Campaign 005 replay on D."""
import argparse
import json
from pathlib import Path
import shutil
import sys
HOME=Path(__file__).resolve().parent
sys.path.insert(0,str(HOME.parent));sys.path.insert(0,str(HOME/'viewer'))
import build
import verify
from common import save,sha
from archive_location import PUBLIC_EXPORT_ROOT

def run(manifest,audit,output):
    output=Path(output).resolve();assert output.is_relative_to(PUBLIC_EXPORT_ROOT/'inspection')
    assert shutil.disk_usage(PUBLIC_EXPORT_ROOT).free>12*1024**3
    build.build(manifest,audit,output);verify.verify(output)
    checked=json.loads((output/'verification.json').read_text());assert checked['passed']
    total=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    assert total<=12*1024**3,'Derived export exceeded prospective storage admission'
    save(output/'job-receipt.json',dict(passed=True,model_calls=0,verification_sha256=sha(output/'verification.json'),
        retained_bytes=total,source_sha256=sha(__file__),browser_qa='pending',original_evidence_modified=False))
    print(json.dumps(dict(passed=True,replay=str(output),bytes=total)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('audit');p.add_argument('output');a=p.parse_args();run(a.manifest,a.audit,a.output)
