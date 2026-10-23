"""Retained source-only inventory, coordinator and admission development checks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

IO = Path(__file__).resolve().parent
C = IO.parent
REPO = IO.parents[3]
NAMES = (
    'qualification/prepare_model_v15.py', 'qualification/test_prepare_model_v15.py',
    'qualification/prepare_native.py', 'qualification/test_prepare_native.py',
    'qualification/host_probe.py', 'qualification/boundary_suite_v3.py',
    'harness/raw_event_preflight_v2.py', 'harness/test_raw_event_preflight_v2.py',
    'qualification/run_final_qualification_v23.py', 'qualification/test_run_final_qualification_v23.py',
    'admission/prepare_certificate.py', 'admission/test_prepare_admission.py',
    'qualification/prepare_model_v14.py', 'qualification/run_final_qualification_v22.py',
    'io-repair/NATIVE_CLEANUP_CANCELLATION_V1.md')


def binding(path):
    raw=path.read_bytes()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=False)
    bindings={name:binding(C/name) for name in NAMES}
    retained={'qualification/prepare_model_v14.py':'02a83aaef2465a58dc6f8e859e52faab5a50aa659091c32bce4ec5a43ccd6562',
              'qualification/run_final_qualification_v22.py':'9f34af4b25e33848b844e3dde5a9f55a73bc1f79b57a8b294e37c67e3e860af4'}
    preserved=all(bindings[name]['sha256']==digest for name,digest in retained.items())
    checks=[]
    for directory,module in [('qualification','test_prepare_model_v15'),('qualification','test_prepare_native'),
                             ('qualification','test_run_final_qualification_v23'),('admission','test_prepare_admission')]:
        command=[sys.executable,'-X','utf8','-B','-m','unittest',module,'-v']
        started=time.time();completed=subprocess.run(command,cwd=C/directory,capture_output=True,timeout=90)
        for field in ('stdout','stderr'):
            (args.directory/(module+'.'+field+'.txt')).write_bytes(getattr(completed,field))
        checks.append({'module':module,'argv':command,'cwd':str(C/directory),'started_unix_s':started,
                       'ended_unix_s':time.time(),'exit_code':completed.returncode})
    unchanged=all(binding(C/name)==value for name,value in bindings.items())
    receipt={'schema':'campaign002-cleanup-lineage-checks-1','source_bindings':bindings,
             'preserved_prior_sources':preserved,'sources_unchanged':unchanged,'checks':checks,
             'scope':'Temporary source fixtures only; no queue, native process, model or scored launch.',
             'passed':preserved and unchanged and all(row['exit_code']==0 for row in checks)}
    (args.directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':receipt['passed'],'exit_codes':[r['exit_code'] for r in checks]}))
    return 0 if receipt['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
