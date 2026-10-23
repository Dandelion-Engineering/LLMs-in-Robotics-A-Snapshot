"""Reproduce original ownership and unmount race using throwaway state only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ORIGINAL=Path('D:/Dandelion-Apartment-Experiment/engineering/workspace-session38/profile001/source')
sys.path.insert(0,str(ORIGINAL))
import native_runtime as nr
from common import read,save
from deployment import instantiate

def main():
    out=HERE/'output/original-reproductions';out.mkdir();result=dict(passed=False,cases=[])
    original_popen=subprocess.Popen
    for fault in ('original_timeout','race'):
        root=out/fault;instantiate('baseline',root/'filesystem');captures=[];space=None
        def injected(argv,*args,**kwargs):
            argv=list(argv)
            matches=[i for i,v in enumerate(argv) if str(v).endswith('/journal_service.py')]
            if matches:
                argv[matches[0]]=nr.wsl(HERE/'fault_service.py')
                # WSL does not automatically forward arbitrary Windows env.
                index=argv.index('python3');argv[index:index]=['env','S38_SOURCE='+nr.wsl(ORIGINAL),'S38_FAULT='+fault]
                child=original_popen(argv,*args,**kwargs)
                captures.append((child,argv[argv.index('--mount')+1]));return child
            return original_popen(argv,*args,**kwargs)
        case=dict(fault=fault,passed=False);begin=time.perf_counter()
        try:
            with patch.object(subprocess,'Popen',injected):
                try:
                    space=nr.Workspace(root/'workspace',root/'filesystem',fault)
                    if fault=='race':space.close()
                except Exception as e:case['expected_error']=repr(e)
            case['elapsed_s']=time.perf_counter()-begin
            child,mount=captures[0];run=str(Path(mount).parent).replace('\\','/')
            if fault=='original_timeout':
                case['constructor_never_returned']=space is None
                case['orphan_present']=child.poll() is None
                case['passed']=case['constructor_never_returned'] and case['orphan_present'] and 'FUSE mount deadline' in case.get('expected_error','')
            else:case['passed']='I/O operation on closed file' in case.get('expected_error','')
        finally:
            if captures:
                child,mount=captures[0];run=mount.rsplit('/',1)[0]
                cleanup=nr.linux("import json,sys;sys.path.insert(0,sys.argv[1]);from workspace_lifecycle import retire;print(json.dumps(retire(sys.argv[2],sys.argv[3],sys.argv[4])))",
                    nr.wsl(HERE/'source'),run+'/injected-owner.json',read(root/'workspace/location.json')['run_id'] if (root/'workspace/location.json').exists() else json.loads(nr.linux("import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_text())",run+'/identity.json'))['run_id'],mount)
                case['cleanup']=json.loads(cleanup);case['exit_status']=child.wait(10)
                if space and space.log:space.log.close()
                assert case['cleanup']['retired'],case
            save(root/'result.json',case)
        result['cases'].append(case)
        if not case['passed']:break
    result['passed']=len(result['cases'])==2 and all(x['passed'] for x in result['cases'])
    save(out/'result.json',result);print(json.dumps(result));return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
