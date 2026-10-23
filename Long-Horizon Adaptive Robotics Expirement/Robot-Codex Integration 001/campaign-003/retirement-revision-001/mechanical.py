"""No-model qualification of native journal retirement with a retained mount."""
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import HERE,save,sha
from workspace_block import WorkspaceBlock,linux,wsl
from verify_journal import verify

CONTROL="""import socket,sys,json
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect(sys.argv[1]);s.sendall((json.dumps({'command':'retire','run_id':sys.argv[2]})+'\\n').encode());print(s.makefile().readline(8193));s.close()
"""
HOLDER="""import pathlib,sys,json,os
w=pathlib.Path(sys.argv[1]);assert os.path.ismount(w)
print(json.dumps({'ready':True,'pid':os.getpid(),'mounts':[l for l in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if str(w) in l]}),flush=True)
for line in sys.stdin:
 if line.strip()=='quit':break
 try:value={'content':(w/'notes/persist.txt').read_text()}
 except OSError as e:value={'errno':e.errno,'error':str(e)}
 print(json.dumps(value),flush=True)
"""

def case(root,retained_mount):
    run_id=root.name;block=WorkspaceBlock(root/'raw',{'Continuity.md':'fixture only'},run_id,'retirement-mechanical',sha(HERE/'workspace_block.py'))
    results={};holder=None
    try:
        for index in range(3):
            block.begin_session('fixture-'+str(index),{'Robot.md':'fixture '+str(index)})
            result=linux("import pathlib,sys; p=pathlib.Path(sys.argv[1])/'notes/persist.txt'; prior=p.read_text() if p.exists() else ''; p.write_text(prior+sys.argv[2]);print(p.read_text())",block.workspace,str(index))
            assert result.strip()==''.join(str(n) for n in range(index+1))
        for identity,expected in [('wrong-run','identity mismatch'),(run_id,'outer unmount')]:
            response=json.loads(linux(CONTROL,block.run+'/journal/control.sock',identity))
            assert expected in response['error'];results[expected]=response
        if retained_mount:
            holder=subprocess.Popen(['wsl.exe','-d','Ubuntu-24.04','--','unshare','-Ur','-m','--propagation','private',
                'python3','-B','-u','-c',HOLDER,block.workspace],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            ready=json.loads(holder.stdout.readline());assert ready['ready'] and len(ready['mounts'])==1;results['holder']=ready
        start=time.monotonic();receipt=block.close();results['close_elapsed_s']=time.monotonic()-start
        assert receipt['passed'] and block.process.returncode==0
        assert block.close()==receipt,'Second close must return same receipt without new activity'
        if holder:
            holder.stdin.write('probe\n');holder.stdin.flush();unavailable=json.loads(holder.stdout.readline())
            assert 'errno' in unavailable and 'content' not in unavailable;results['retained_mount_after_shutdown']=unavailable
            assert block.retirement_request.get('retirement_requested'),block.retirement_request
        extraction=root/'raw/extracted';extraction.mkdir()
        with tarfile.open(root/'raw/evidence.tar.gz') as archive:archive.extractall(extraction,filter='data')
        independent=verify(extraction/'journal',run_id)
        assert independent['state']['nodes'][str(independent['state']['paths']['/notes/persist.txt'])]['sha256']==__import__('hashlib').sha256(b'012').hexdigest()
        results['independent_replay']={k:v for k,v in independent.items() if k not in ('state','states','read_events')}
        rows=[json.loads(s) for s in (extraction/'journal/mutations.jsonl').read_text().splitlines()]
        assert rows[-1]['type']=='final' and sum(r['type']=='final' for r in rows)==1
        results['retirement_request']=block.retirement_request;results['native_exit_status']=block.process.returncode
        results['passed']=True
    finally:
        if holder:
            holder.stdin.write('quit\n');holder.stdin.flush();holder.stdin.close()
            code=holder.wait(timeout=10);assert code==0,holder.stderr.read()
        if not getattr(block,'close_attempted',False):block.close()
    save(root/'receipt.json',results)
    return results

if __name__=='__main__':
    root=Path(sys.argv[1]);root.mkdir(exist_ok=False)
    save(root/'declaration.json',dict(model_calls=0,scope=__doc__,sources={str(p.relative_to(HERE)):sha(p) for p in [HERE/'workspace_block.py',HERE/'journal_fs.py',Path(__file__)]}))
    result={'ordinary':case(root/'ordinary',False),'retained_mount':case(root/'retained-mount',True)}
    save(root/'receipt.json',dict(passed=all(v['passed'] for v in result.values()),model_calls=0,cases=result))
    print(json.dumps({k:{'passed':v['passed'],'close_elapsed_s':v['close_elapsed_s'],'native_exit_status':v['native_exit_status'],'retirement_request':v['retirement_request']} for k,v in result.items()}),flush=True)
