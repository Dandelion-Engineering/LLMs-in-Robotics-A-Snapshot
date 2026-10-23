"""Separately implemented readback plus adversarial workspace-only checks.

Uses the unchanged pre-repair journal/checkpoint readers, raw queue receipts,
source hashes and complete official inventories. No model or run.launch call.
"""
import ctypes
import importlib.util
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
BASE=HERE.parent
QUALIFIED=BASE/'qualification008'
QUALIFICATIONS=sorted(BASE.glob('qualification[0-9]*'))
PROFILE=BASE/'profile001'
OFFICIAL=Path('D:/Dandelion-Apartment-Experiment/official')
sys.path.insert(0,str(HERE/'source'))
import native_runtime as nr
from common import read,save,sha,inventory
from deployment import instantiate

spec=importlib.util.spec_from_file_location('independent_old_reader',PROFILE/'source/journal_reader.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)

def check_sources():
    manifests={}
    for root in (PROFILE,*QUALIFICATIONS,*sorted(BASE.glob('audit[0-9]*'))):
        manifest=read(root/'manifest.json')
        for relative,row in manifest['files'].items():
            p=root/relative;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],p
        for relative,key in manifest['inherited_python'].items():assert sha(Path(manifest['repository'])/relative)==key,relative
        manifests[root.name]=sha(root/'manifest.json')
    changed=[]
    for p in (PROFILE/'source').glob('*.py'):
        if sha(p)!=sha(QUALIFIED/'source'/p.name):changed.append(p.name)
    assert sorted(changed)==['journal_service.py','native_runtime.py','run.py'],changed
    for p in (QUALIFIED/'source').glob('*.py'):
        assert sha(p)==sha(HERE/'source'/p.name),p.name
        assert sha(p)==sha(nr.REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'/p.name),p.name
    from environment import identity
    return dict(manifests=manifests,changed_existing_app_files=changed,unchanged_readers=True,environment=identity())

def check_receipts():
    queue=nr.REPO.parent/'tools/compute_queue/compute_queue.py';rows={}
    operations=nr.REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-38'
    previous_audits=[p for p in sorted(BASE.glob('audit[0-9]*')) if p!=HERE]
    for root in (PROFILE,*QUALIFICATIONS,*previous_audits):
        name=root.name;expected=root in (PROFILE,BASE/'qualification006',BASE/'qualification007',QUALIFIED,*previous_audits)
        q=read(operations/(name+'-queue.json'))
        terminal=json.loads(subprocess.check_output([sys.executable,'-B',str(queue),'status',q['id']],text=True,encoding='utf-8'))
        assert terminal['cwd']==str(BASE/name)
        assert terminal['state']==('succeeded' if expected else 'failed') and type(terminal['exit_status']) is int and terminal['exit_status']==(0 if expected else 1)
        outcome=read(BASE/name/'output/result.json');assert outcome['passed'] is expected
        rows[name]=dict(id=q['id'],state=terminal['state'],exit_status=terminal['exit_status'],output_sha256=sha(BASE/name/'output/result.json'))
    return rows

def read_matrix():
    result=read(QUALIFIED/'output/result.json');assert result['model_calls']==0 and result['official_sessions']==0
    expected={'hang':'no_progress_deadline','heartbeat':'no_progress_deadline','early_exit':'child_exited','partial_failure':'child_exited','seed_flush':'child_exited','absolute':'absolute_deadline'}
    success=[size+'-'+cache for size in ('small','checkpoint14','large') for cache in ('advised-cold','warm')]+['slow-progress','retirement-race']
    assert {r['name'] for r in result['cases']}==set(success)|set(expected)
    rows=[]
    for name in success+list(expected):
        root=QUALIFIED/'output'/name;workspace=root/'workspace';location=read(workspace/'location.json')
        outcome=read(root/'result.json');readiness=read(workspace/'readiness.json')
        if name in expected:
            assert not readiness['ready'] and readiness['reason']==expected[name]
            assert not (workspace/'retirement.json').exists() and not (workspace/'journal/native-exit.json').exists()
            assert read(workspace/'startup-failure.json')['passed'] is False
            assert read(workspace/'abnormal-retirement-001.json')['passed'] is False
            if name in ('hang','heartbeat'):assert readiness['elapsed_s']>=1.9
            if name=='absolute':assert readiness['elapsed_s']>=readiness['policy']['total_s']
        else:
            proof=reader.verify(workspace/'journal',location['run_id'])
            kind=next((s for s in ('checkpoint14','large') if name.startswith(s)), 'small')
            assert proof['state']==read(PROFILE/'output'/('fixture-'+kind)/'filesystem-namespace.json')
            exit_receipt=read(workspace/'journal/native-exit.json')
            assert exit_receipt['libfuse_main_return']==0 and exit_receipt['requested_sigterm'] is False
            assert readiness['ready'] and readiness['total_startup_s']<=120
            if name=='slow-progress':assert outcome['startup_s']>20
        rows.append(dict(name=name,startup_s=outcome['startup_s'],reason=readiness['reason'],source_result_sha256=sha(root/'result.json')))
    originals=read(QUALIFIED/'output/original-reproductions/result.json')
    assert originals['passed'] and originals['cases'][0]['constructor_never_returned'] and originals['cases'][0]['orphan_present']
    assert 'I/O operation on closed file' in originals['cases'][1]['expected_error']
    race=read(QUALIFIED/'output/retirement-race/result.json')['race']
    assert race['retire']['finalized'] and 'closed' in race['checkpoint']['error']
    assert json.loads(result['isolation']['stdout'])['qualified'] is True
    for name,failure in read(QUALIFIED/'output/prelaunch-failures.json').items():
        assert failure['retired'] and failure['owned'] and failure['log_closed']
        assert failure['native_started'] is (name=='admission_write_failure')
    return dict(cases=rows,original_reproductions=originals,race_fixed=race,isolation=result['isolation'])

def namespace_roundtrip(out):
    root=out/'namespace';instantiate('baseline',root/'filesystem');space=None;holder=None
    result={}
    try:
        space=nr.Workspace(root/'first',root/'filesystem','audit-metadata-1')
        nr.linux("import pathlib,os,sys;p=pathlib.Path(sys.argv[1]);x=p/'probe';x.write_bytes(b'abc');x.chmod(0o751);os.link(x,p/'hard');os.symlink('probe',p/'symbolic');(p/'empty').mkdir()",space.workspace)
        # A real held FUSE descriptor must prevent normal retirement.
        holder=subprocess.Popen(['wsl.exe','-d',nr.DISTRO,'--','python3','-B','-c',
            "import pathlib,time,sys\nf=open(sys.argv[1]+'/probe','rb');pathlib.Path(sys.argv[2]).write_text('ready');end=time.monotonic()+15\nwhile not pathlib.Path(sys.argv[3]).exists() and time.monotonic()<end:time.sleep(.05)\nf.close()",
            space.workspace,space.run+'/holder-ready',space.run+'/holder-release'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        nr.linux("import pathlib,time,sys;end=time.monotonic()+5\nwhile not pathlib.Path(sys.argv[1]).exists():\n if time.monotonic()>end:raise RuntimeError('holder readiness timeout')\n time.sleep(.05)",space.run+'/holder-ready')
        try:space.close();raise AssertionError('Open handle was accepted')
        except ValueError as e:assert 'Open workspace handles' in str(e);result['open_handle_rejected']=str(e)
        nr.linux("import pathlib,sys;pathlib.Path(sys.argv[1]).write_text('release')",space.run+'/holder-release');assert holder.wait(10)==0
        final,_=space.close();state=read(space.evidence/'final-namespace.json')
        reader.verify(space.evidence/'journal',space.run_id)
        clone=root/'continued';clone.mkdir();shutil.copytree(final,clone/'filesystem');shutil.copytree(space.evidence/'final-objects',clone/'filesystem-objects');shutil.copyfile(space.evidence/'final-namespace.json',clone/'filesystem-namespace.json')
        space=nr.Workspace(root/'second',clone/'filesystem','audit-metadata-2')
        initial=json.loads((space.evidence/'journal/mutations.jsonl').read_bytes().splitlines()[0])['state'];assert initial==state
        observation=json.loads(nr.linux(r"""import pathlib,os,sys,json
p=pathlib.Path(sys.argv[1]);x=p/'probe';expected=b'abc'
with x.open('r+b',buffering=0) as f:
 f.seek(7);f.write(b'xyz');expected=expected.ljust(7,b'\0')+b'xyz'
 f.truncate(8);expected=expected[:8];f.seek(0);assert f.read()==expected
print(json.dumps({'mode':x.stat().st_mode&0o777,'hard':x.stat().st_ino==(p/'hard').stat().st_ino,'symbolic':os.readlink(p/'symbolic'),'empty':not list((p/'empty').iterdir()),'bytes_hex':expected.hex()}))
""",space.workspace))
        assert observation==dict(mode=0o751,hard=True,symbolic='probe',empty=True,bytes_hex='6162630000000078'),observation
        final,_=space.close();proof=reader.verify(space.evidence/'journal',space.run_id)
        assert (final/'probe').read_bytes()==bytes.fromhex(observation['bytes_hex'])
        result.update(exact_initial_namespace=True,metadata=observation,mutations=proof['mutations'])
        save(root/'audit.json',result);return result
    finally:
        if holder and holder.poll() is None:holder.kill();holder.wait(5)
        if space and not space.closed:space.abort()

def adversarial(out):
    results={};original=subprocess.Popen
    for fault in ('corrupt-seed','preowner-hang','poisoned-journal'):
        root=out/fault;root.mkdir();space=nr.Workspace(root/'workspace',PROFILE/'output/fixture-small/filesystem',fault,start=False)
        if fault=='preowner-hang':
            script=root/'preowner.py';script.write_text('import time\ntime.sleep(60)\n')
            space.policy=dict(stall_s=2,total_s=8,poll_s=.05)
        def injected(argv,*args,**kwargs):
            argv=list(argv)
            if 'bootstrap' in argv:
                if fault=='corrupt-seed':
                    chunk=next((space.evidence/'restore-seed/chunks').iterdir());raw=bytearray(chunk.read_bytes());raw[0]^=1;chunk.write_bytes(raw)
                if fault=='preowner-hang':argv[argv.index('bootstrap')-1]=nr.wsl(script)
            return original(argv,*args,**kwargs)
        try:
            if fault=='poisoned-journal':
                space.start()
                nr.linux("import pathlib,sys;f=(pathlib.Path(sys.argv[1])/'oversize').open('wb');f.seek(16*1024**2)\ntry:f.write(b'x');f.flush()\nexcept OSError:pass\ntry:f.close()\nexcept OSError:pass",space.workspace)
                try:space.close();raise AssertionError('Poisoned journal promoted')
                except RuntimeError:pass
                space.abort();assert not (space.evidence/'retirement.json').exists()
                try:reader.verify(space.evidence/'journal',space.run_id);raise AssertionError('Missing final accepted')
                except AssertionError as e:assert str(e)=='missing final closure',repr(e)
            else:
                with patch.object(subprocess,'Popen',injected):
                    try:space.start();raise AssertionError('Injected startup failure accepted')
                    except RuntimeError as e:results[fault+'_error']=repr(e)
                assert not space.ready and space.closed
                assert not (space.evidence/'journal/native-exit.json').exists()
            assert space.closed and space.process.poll() is not None and space.log.closed
            results[fault]=dict(retired=True,exit_status=space.process.poll(),normal_retirement=False)
        finally:
            if not space.closed:space.abort()
    save(out/'adversarial.json',results);return results

def no_leaks(out):
    locations=[]
    for root in (PROFILE,*QUALIFICATIONS,*sorted(BASE.glob('audit[0-9]*'))):
        for p in (root/'output').rglob('location.json'):
            row=read(p);locations.append(row)
        # Original constructor failures have no location.json; retain the
        # injected-owner run references recovered from the original console
        # via the still-preserved native runtime identity files below.
    roots=[row['workspace'] for row in locations]
    raw=nr.linux(r"""import json,pathlib,sys,os
x=json.load(sys.stdin);mounts=[];processes=[];open_fds=[]
for owner_path in pathlib.Path('/var/tmp/robot-codex-session10').glob('apartment-*/injected-owner.json'):
 x.append(json.loads(owner_path.read_text())['mount'])
for row in pathlib.Path('/proc/self/mountinfo').read_text().splitlines():
 if row.split()[4] in x:mounts.append(row.split()[4])
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  argv=(p/'cmdline').read_bytes().split(b'\0')
  if any(s.encode() in argv for s in x):processes.append(int(p.name))
 except (FileNotFoundError,ProcessLookupError,PermissionError):continue
# Also cover every isolated s38 original service, including the constructor
# failures for which the old code never wrote location.json.
for p in pathlib.Path('/var/tmp/robot-codex-session10').glob('apartment-*/injected-owner.json'):
 owner=json.loads(p.read_text());proc=pathlib.Path('/proc')/str(owner['pid'])
 if not proc.exists():continue
 try:
  fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
  argv=(proc/'cmdline').read_bytes().split(b'\0')
  if fields[19]==owner['start_ticks'] and fields[0]!='Z' and owner['mount'].encode() in argv:processes.append(owner['pid'])
 except FileNotFoundError:pass
print(json.dumps({'mounts':mounts,'processes':processes,'checked_workspace_paths':len(x)}))
""",payload=roots)
    result=json.loads(raw);assert not result['mounts'] and not result['processes'],result
    # Windows sharing=0 tests that every retained service/preparer log is closed.
    create=ctypes.windll.kernel32.CreateFileW;create.restype=ctypes.c_void_p
    create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    close=ctypes.windll.kernel32.CloseHandle;close.argtypes=[ctypes.c_void_p]
    logs=0
    for root in (PROFILE,*QUALIFICATIONS,*sorted(BASE.glob('audit[0-9]*'))):
        for p in (root/'output').rglob('*.log'):
            handle=create(str(p),0x80000000,0,None,3,0,None)
            assert handle!=ctypes.c_void_p(-1).value,('Open retained log handle',str(p))
            close(handle);logs+=1
    result['exclusive_log_opens']=logs;save(out/'no-leaks.json',result);return result

def preservation(out):
    result={}
    for name in ('apartment-v2','apartment-v3'):
        print('Independent full preservation readback '+name,flush=True)
        before=read(PROFILE/'output'/(name+'-before.json'));after=inventory(OFFICIAL/name)
        save(out/(name+'-after.json'),after)
        assert after==before,name
        result[name]=dict(files=len(after),bytes=sum(r['bytes'] for r in after.values()),unchanged=True,inventory_sha256=sha(out/(name+'-after.json')))
    cp=OFFICIAL/'apartment-v3/baseline/checkpoints/session-00014'
    from recording import verify_checkpoint,verify_prefix
    proof=verify_checkpoint(cp);assert proof['manifest_sha256']=='5314dc656b39dd4254325a46c94bc56c028f5f526004f85ac983e1547ec44015'
    result['checkpoint14']=proof;result['checkpoint_prefix']=verify_prefix(cp.parents[1],cp)
    pointer=read(OFFICIAL/'apartment-v3/baseline/latest-execution.json');execution=read(pointer['path'])
    assert not execution['passed'] and execution['retirement']['all_retired'] is False
    assert read(OFFICIAL/'apartment-v3/maps/run.json')['launched'] is False
    assert sha(PROFILE/'source/recovery.py')==sha(HERE/'source/recovery.py')
    result['original_false_retirement_preserved']=True;result['maps_unlaunched']=True;result['recovery_guard_unchanged']=True
    return result

def main():
    out=HERE/'output';out.mkdir();result=dict(passed=False,model_calls=0,checks={})
    try:
        for name,fn in [('source_environment',check_sources),('queue_and_failed_attempts',check_receipts),('independent_matrix_readback',read_matrix),
                        ('namespace_and_open_handles',lambda:namespace_roundtrip(out)),('adversarial_failures',lambda:adversarial(out)),
                        ('all_runtime_retired',lambda:no_leaks(out)),('official_preservation_checkpoint_and_guard',lambda:preservation(out))]:
            print(name,flush=True);result['checks'][name]=fn()
        result['passed']=True
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps(dict(passed=result['passed'],groups=list(result['checks']),error=result.get('error'))),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
