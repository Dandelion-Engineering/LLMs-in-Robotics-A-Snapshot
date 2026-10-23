"""Frozen read-only auditor; does not start a model or plant."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from common import save,sha
from live_audit import audit

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('job');p.add_argument('output');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    save(out/'declaration.json',dict(source_manifest=str(Path(a.manifest).resolve()),manifest_sha256=sha(a.manifest),
        source_job=a.job,reader_sha256=sha(Path(__file__).resolve().parent.parent/'live_audit.py'),model_calls=0))
    raise SystemExit(audit(a.manifest,a.job,out/'assessment'))
