"""Fixed bounded no-model startup/lifecycle matrix. Failures remain recorded."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))
import native_runtime as nr
from common import read,save,sha
from deployment import instantiate
from workspace_lifecycle import Gate
import journal_reader

PROFILE=Path('D:/Dandelion-Apartment-Experiment/engineering/workspace-session38/profile001/output')

def runtime_snapshot(space):
    return json.loads(nr.linux("""import json,pathlib,sys
sys.path.insert(0,sys.argv[1]);from workspace_lifecycle import mounted,process
owner=pathlib.Path(sys.argv[2]);x=json.loads(owner.read_text()) if owner.exists() else None
print(json.dumps({'mounted':mounted(sys.argv[3]),'process':None if x is None else process(x),'owner':x,'process_fd_count':len(list((pathlib.Path('/proc')/str(x['pid'])/'fd').iterdir())) if x and (pathlib.Path('/proc')/str(x['pid'])/'fd').exists() else 0}))
""",nr.wsl(HERE/'source'),space.owner,space.workspace))

def case(out,name,fixture='small',fault=None,expected=None,policy=None):
    root=out/name;root.mkdir();space=None
    result=dict(name=name,fault=fault,expected=expected,passed=False)
    source=PROFILE/('fixture-'+fixture)
    # Reuse immutable throwaway inputs; nothing writes into them.
    begin=time.perf_counter();original_popen=subprocess.Popen
    def injected(argv,*args,**kwargs):
        argv=list(argv)
        if fault and '--service' in argv:
            argv[argv.index('--service')+1]=nr.wsl(HERE/'fault_service.py')
            index=argv.index('python3');argv[index:index]=['env','S38_SOURCE='+nr.wsl(HERE/'source'),'S38_FAULT='+fault]
        return original_popen(argv,*args,**kwargs)
    try:
        space=nr.Workspace(root/'workspace',source/'filesystem',name,start=False)
        if policy:space.policy=policy
        with patch.object(subprocess,'Popen',injected):
            try:space.start()
            except Exception as e:result['startup_error']=repr(e)
        result['startup_s']=time.perf_counter()-begin
        if expected:
            readiness=read(space.evidence/'readiness.json')
            assert not space.ready and readiness['reason']==expected,readiness
            assert space.closed and space.log.closed
            assert not (space.evidence/'retirement.json').exists()
            assert not (space.evidence/'journal/native-exit.json').exists()
            result['readiness']=readiness;result['repeat_abort']=space.abort()
        else:
            assert space.ready,result
            if fault=='race':
                race=json.loads(nr.linux("""import subprocess,time,pathlib,json,sys
sys.path.insert(0,sys.argv[1]);from workspace_lifecycle import request
subprocess.run(['fusermount3','-u',sys.argv[2]],check=True,timeout=5)
end=time.monotonic()+2
while not pathlib.Path(sys.argv[3]).exists():
 if time.monotonic()>end:raise RuntimeError('Destroy barrier timeout')
 time.sleep(.01)
a=request(sys.argv[4],{'command':'retire','run_id':sys.argv[5]})
b=request(sys.argv[4],{'label':'after-final-must-not-append'})
print(json.dumps({'retire':a,'checkpoint':b}))
""",nr.wsl(HERE/'source'),space.workspace,space.run+'/destroy-complete',space.control,space.run_id))
                assert race['retire']['finalized'] is True and 'closed' in race['checkpoint']['error']
                result['race']=race
                space.process.wait(10);space.log.close();space.abort()
                proof=journal_reader.verify(space.evidence/'journal',space.run_id)
            else:
                _,proof=space.close();assert space.close()==space.normal_result
                assert proof['passed']
            state=journal_reader.verify(space.evidence/'journal',space.run_id)['state']
            assert state==read(source/'filesystem-namespace.json')
            result['namespace_exact']=True
            result['readiness']=read(space.evidence/'readiness.json')
            if fault=='slow':assert result['startup_s']>20
        result['runtime']=runtime_snapshot(space)
        assert not result['runtime']['mounted'] and (result['runtime']['process'] is None or not result['runtime']['process']['alive'])
        assert result['runtime']['process_fd_count']==0
        result['passed']=True
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    finally:
        if space and not space.closed:
            try:space.abort()
            except BaseException as e:result['abort_error']=repr(e)
        result['elapsed_s']=time.perf_counter()-begin
        save(root/'result.json',result)
    print(json.dumps(dict(name=name,passed=result['passed'],startup_s=result.get('startup_s'),error=result.get('error'))),flush=True)
    if not result['passed']:raise RuntimeError('Qualification case failed: '+name)
    return {k:v for k,v in result.items() if k not in ('readiness','repeat_abort')}

def gates():
    def value(phase,files=0,bytes=0,run_id='x'):return dict(phase=phase,files=files,bytes=bytes,run_id=run_id)
    checks={};policy=dict(stall_s=2,total_s=5,poll_s=.05)
    g=Gate('x',0,policy);g.observe(0,value('bootstrap'));g.observe(1,value('restoring',1,20))
    checks['heartbeat_does_not_reset']=g.observe(3,value('restoring',1,20))=='no_progress_deadline'
    g=Gate('x',0,policy)
    for t in range(5):g.observe(t,value('restoring',t,20*t))
    checks['absolute_cannot_extend']=g.observe(5,value('restoring',5,100))=='absolute_deadline'
    for name,v in [('identity',value('restoring',run_id='wrong')),('regression',value('inputs'))]:
        try:g.observe(5.1,v);checks[name+'_rejected']=False
        except ValueError:checks[name+'_rejected']=True
    assert all(checks.values());return checks

def isolation(out):
    root=out/'isolation';instantiate('baseline',root/'filesystem');space=nr.Workspace(root/'workspace',root/'filesystem','isolation')
    try:
        # An inert native Unix socket satisfies the namespace canary's mount;
        # no broker, model, robot controller or credentials are involved.
        result=json.loads(nr.linux("""import socket,subprocess,json,sys
s=socket.socket(socket.AF_UNIX);s.bind(sys.argv[1])
try:
 r=subprocess.run(['python3','-B',sys.argv[2],'canary','--repo',sys.argv[3],'--workspace',sys.argv[4],'--socket',sys.argv[1],'--codex',sys.argv[5],'--codehost',sys.argv[6]],capture_output=True,text=True,timeout=30)
 print(json.dumps({'exit_status':r.returncode,'stdout':r.stdout,'stderr':r.stderr}))
finally:s.close()
""",space.run+'/dummy.sock',nr.wsl(HERE/'source/guest_entry.py'),nr.wsl(nr.REPO),space.workspace,nr.old.prior.LINUX_CODEX,nr.old.prior.LINUX_CODEHOST))
        assert result['exit_status']==0 and json.loads(result['stdout'])['qualified'],result
        space.close();result['runtime']=runtime_snapshot(space);save(root/'result.json',result);return result
    finally:
        if not space.closed:space.abort()

def prelaunch_failures(out):
    results={}
    root=out/'corrupt-input';root.mkdir();shutil.copytree(PROFILE/'fixture-small',root/'input')
    state=read(root/'input/filesystem-namespace.json')
    key=next(n['sha256'] for n in state['nodes'].values() if n.get('sha256'))
    (root/'input/filesystem-objects'/key).write_bytes(b'CORRUPTED THROWAWAY INPUT')
    try:nr.Workspace(root/'workspace',root/'input/filesystem','corrupt-input')
    except Exception as error:
        space=error.workspace
        results['corrupt_input']=dict(error=repr(error),owned=True,retired=space.closed,
            preparer_exit=space.preparer.poll(),log_closed=space.prepare_log.closed,native_started=space.process is not None)
    else:raise AssertionError('Corrupt namespace accepted')
    assert results['corrupt_input']['retired'] and not results['corrupt_input']['native_started']
    root=out/'spawn-failure';root.mkdir();original=subprocess.Popen
    def broken(argv,*args,**kwargs):
        if any(str(v).endswith('workspace_restore.py') for v in argv):raise OSError('Injected spawn failure')
        return original(argv,*args,**kwargs)
    with patch.object(subprocess,'Popen',broken):
        try:nr.Workspace(root/'workspace',PROFILE/'fixture-small/filesystem','spawn-failure')
        except Exception as error:
            space=error.workspace
            results['spawn_failure']=dict(error=repr(error),owned=True,retired=space.closed,log_closed=space.prepare_log.closed,native_started=space.process is not None)
        else:raise AssertionError('Injected spawn failure did not fail')
    assert results['spawn_failure']['retired'] and results['spawn_failure']['log_closed']
    # A receipt write can fail after FUSE is already mounted. It must be inside
    # the same ownership/cleanup guard, including legacy constructor callers.
    root=out/'admission-write-failure';root.mkdir();original_save=nr.save
    def broken_save(path,value):
        if Path(path).name=='startup-outcome.json':raise OSError('Injected admission receipt write failure')
        return original_save(path,value)
    with patch.object(nr,'save',broken_save):
        try:nr.Workspace(root/'workspace',PROFILE/'fixture-small/filesystem','admission-write-failure')
        except Exception as error:
            space=error.workspace
            results['admission_write_failure']=dict(error=repr(error),owned=True,retired=space.closed,log_closed=space.log.closed,
                native_started=space.process is not None,native_exit=space.process.poll(),runtime=runtime_snapshot(space))
        else:raise AssertionError('Injected admission write failure accepted')
    assert results['admission_write_failure']['retired'] and not results['admission_write_failure']['runtime']['mounted']
    root=out/'late-preparation';instantiate('baseline',root/'filesystem')
    space=nr.Workspace(root/'workspace',root/'filesystem','late-preparation',start=False)
    space.policy=dict(stall_s=1,total_s=1,poll_s=.05);original_linux=nr.linux
    def delayed_setup(*args,**kwargs):
        time.sleep(1.1);return original_linux(*args,**kwargs)
    with patch.object(nr,'linux',delayed_setup):
        try:space.start()
        except Exception as error:
            assert space.closed and not space.ready and space.process is None
            results['late_preparation']=dict(error=repr(error),owned=error.workspace is space,retired=space.closed,
                log_closed=space.log is None or space.log.closed,native_started=False)
        else:raise AssertionError('Setup overrun admitted')
    save(out/'prelaunch-failures.json',results);return results

def main():
    out=HERE/'output';out.mkdir();result=dict(passed=False,model_calls=0,official_sessions=0,cases=[])
    try:
        result['gates']=gates()
        old=subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'original_reproductions.py')],capture_output=True,text=True,timeout=100)
        save(out/'original-command.json',dict(exit_status=old.returncode,stdout=old.stdout,stderr=old.stderr))
        assert old.returncode==0,old.stderr
        for size in ('small','checkpoint14','large'):
            for cache in ('advised-cold','warm'):
                advice=nr.linux("import os,pathlib,sys\nfor p in pathlib.Path(sys.argv[1]).iterdir():\n with p.open('rb') as f:\n  if sys.argv[2]=='advised-cold':os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)\n  else:f.read()",nr.wsl(PROFILE/('fixture-'+size)/'filesystem-objects'),cache,timeout=90)
                result['cases'].append(case(out,size+'-'+cache,size))
        result['cases'].append(case(out,'slow-progress',fault='slow'))
        short=dict(stall_s=2,total_s=6,poll_s=.05)
        for name,reason in [('hang','no_progress_deadline'),('heartbeat','no_progress_deadline'),('early_exit','child_exited'),('partial_failure','child_exited'),('seed_flush','child_exited')]:
            result['cases'].append(case(out,name,fault=name,expected=reason,policy=short))
        result['cases'].append(case(out,'absolute',fault='absolute',expected='absolute_deadline',policy=dict(stall_s=2,total_s=3,poll_s=.05)))
        result['cases'].append(case(out,'retirement-race',fault='race'))
        result['prelaunch_failures']=prelaunch_failures(out)
        result['isolation']=isolation(out)
        result['passed']=True
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
