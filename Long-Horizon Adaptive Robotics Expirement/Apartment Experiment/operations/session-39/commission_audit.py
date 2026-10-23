"""Independent raw-evidence readback for the integrated prospective release.

No provider request, official preparation, recovery or launch is performed.
Fresh adversarial checks are confined to this audit's own throwaway workspace.
"""
import ast
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import traceback
from fractions import Fraction
import numpy as np

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
OPS=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-39'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
sys.path.insert(0,str(HERE/'source'))
from common import read,save,sha,inventory

def receipts(out):
    rows={}
    required=['preservation002','workspace001','offline001','recorder001','physics001','core004','native001']
    for name in ['preservation001','core001','core002','core003',*required]:
        root=BASE/name;manifest=read(root/'manifest.json')
        for n,row in manifest['files'].items():
            assert (root/n).stat().st_size==row['bytes'] and sha(root/n)==row['sha256'],(name,n)
        assert manifest['release_manifest_sha256']==sha(BASE/'release001/manifest.json')
        q=read(OPS/(name+'-queue.json'))
        actual=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',q['id']],text=True,encoding='utf-8'))
        expected=name in required
        assert actual['state']==('succeeded' if expected else 'failed')
        assert type(actual['exit_status']) is int and actual['exit_status']==(0 if expected else 1)
        assert actual['cwd']==str(root)
        result=read(root/'output/result.json');assert result['passed'] is expected,name
        if 'checks' in result and expected:assert all(result['checks'].values()),name
        registered=read(OPS/('map-APARTMENT-s39-'+name+'-result.json'))
        assert registered['execution_status']==('completed' if expected else 'failed')
        for evidence in registered['evidence']:assert sha(Path(evidence['uri']))==evidence['sha256'],(name,evidence['label'])
        recorded=read(OPS/(name+'-terminal.json'))
        assert all(actual[k]==recorded[k] for k in ('id','state','exit_status','cwd','argv','started_at','ended_at'))
        save(out/(name+'-queue.json'),actual)
        rows[name]=dict(queue_id=q['id'],state=actual['state'],exit_status=actual['exit_status'],result_sha256=sha(root/'output/result.json'))
    return rows

def identity_check():
    from run import source_identity
    from environment import identity
    from revision_config import CONFIG
    release=BASE/'release001';manifest=read(release/'manifest.json')
    for n,row in manifest['files'].items():assert sha(release/'frozen_repository'/n)==row['sha256'],n
    assert source_identity()==manifest['source_identity']
    assert identity()==manifest['environment']
    assert CONFIG==manifest['config']
    for name in ['workspace001','offline001','recorder001','physics001','core001','core002','core003','core004','native001']:
        attempt=read(BASE/name/'manifest.json')
        assert attempt['source_identity']==manifest['source_identity'] and attempt['environment']==manifest['environment'] and attempt['config']==CONFIG
        for key,value in manifest['source_identity'].items():
            if key.startswith('apartment/'):assert sha(BASE/name/'source'/key.removeprefix('apartment/'))==value,(name,key)
    old=read(Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3/frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json'))['source_identity']
    changed=[k for k in manifest['source_identity'] if old.get(k)!=manifest['source_identity'][k]]
    assert sorted(changed)==['apartment/journal_service.py','apartment/native_runtime.py','apartment/run.py','apartment/workspace_lifecycle.py','apartment/workspace_restore.py'],changed
    assert set(old)<=set(manifest['source_identity'])
    assert CONFIG['normal_work_s']==360 and CONFIG['throw_work_s']==600 and CONFIG['reserve_s']==3600 and CONFIG['model_wall_s']==7200
    assert manifest['environment']['model']=='gpt-6-astra' and manifest['environment']['effort']=='max'
    notices=BASE/'third-party-notices';notice=read(notices/'manifest.json')
    assert sha(notices/notice['file'])==sha(Path(notice['source']))==notice['sha256']
    return dict(passed=True,changed_from_v3=changed,source_entries=len(manifest['source_identity']),environment=manifest['environment'],inherited_license_sha256=notice['sha256'])

def physics(out):
    root=BASE/'physics001';result=read(root/'output/result.json')
    assert len(result['checks'])==30 and all(result['checks'].values())
    cases=read(root/'manifest.json')['cases']
    prior=read(Path('D:/Dandelion-Apartment-Experiment/engineering/physics-recommission-session37/verification001/manifest.json'))['cases']
    assert cases==prior
    numeric=[]
    for case in cases:
        with np.load(root/'output'/(case['id']+'.npz')) as z:
            a=z['samples'];steps=z['sample_steps'];flags=z['sample_flags']
            metadata=read(root/'output'/(case['id']+'.json'));rec=metadata['recording']
            dt=Fraction(str(rec['timestep_seconds']));interval=Fraction(str(case.get('sample_interval',.04)))
            n=math.ceil(Fraction(str(case.get('seconds',120)))/dt);ratio=interval/dt
            slots=np.arange(1,math.floor(n*dt/interval)+1,dtype=np.int64)
            expected=np.unique(np.concatenate(([0],(slots*ratio.numerator+ratio.denominator-1)//ratio.denominator,[n])))
            assert np.array_equal(steps,expected) and np.all(np.diff(steps)>0)
            assert np.max(np.abs(a[:,0]-steps*float(dt)))<1e-5 and np.all(np.diff(a[:,0])>0)
            assert rec['integration_steps']==rec['planned_integration_steps']==n==steps[-1]
            assert float(z['terminal_time'])==a[-1,0]==rec['terminal_simulation_time']
            assert np.array_equal(a[-1,1:8],z['terminal_qpos']) and np.array_equal(a[-1,8:14],z['terminal_qvel'])
            assert sum(bool(x&2) for x in flags)==1 and flags[-1]&2
            late=a[:,0]>=case.get('seconds',120)-30
            energy=a[:,14]+a[:,15];gain=float(np.max(energy-energy[0]));drift=float(np.linalg.norm(np.ptp(a[late,1:3],axis=0)))
            assert abs(a[-1,0]-case.get('seconds',120))<1e-5 and np.isfinite(a).all()
            assert drift<.002 and np.linalg.norm(a[late,8:11],axis=1).max()<.001
            assert gain<max(1e-5,.02*abs(float(energy[0])) if case.get('drop') else 1e-5)
            assert .025<a[-1,3]<.065 and not any(metadata['warnings'])
            assert not any(metadata['force_max_applied_passive_actuator_xfrc']) and metadata['min_contact_distance_m']>-.01
            numeric.append(dict(case=case['id'],samples=len(a),steps=n,actual_seconds=float(a[-1,0]),max_energy_gain_J=gain,late_drift_m=drift))
    for path in ['geometry/geometry.json','integrated/result.json','throwing/result.json']:
        r=read(root/'output'/path);assert r['passed'] and all(r['checks'].values())
    recorder=read(BASE/'recorder001/output/result.json');assert len(recorder['checks'])==14 and all(recorder['checks'].values())
    recorder_cases=read(BASE/'recorder001/manifest.json')['cases']
    assert recorder_cases==read(Path('D:/Dandelion-Apartment-Experiment/engineering/physics-recommission-session37/recorder001/manifest.json'))['cases']
    short_readback=[];recorded=BASE/'recorder001/output'
    for case in recorder_cases:
        with np.load(recorded/(case['id']+'.npz')) as z:
            a=z['samples'];steps=z['sample_steps'];flags=z['sample_flags'];rec=read(recorded/(case['id']+'.json'))['recording']
            dt=Fraction(str(rec['timestep_seconds']));interval=Fraction(str(case.get('sample_interval',.04)))
            n=math.ceil(Fraction(str(case['seconds']))/dt);ratio=interval/dt
            slots=np.arange(1,math.floor(n*dt/interval)+1,dtype=np.int64)
            expected=np.unique(np.concatenate(([0],(slots*ratio.numerator+ratio.denominator-1)//ratio.denominator,[n])))
            assert np.array_equal(steps,expected) and np.all(np.diff(steps)>0)
            assert rec['integration_steps']==rec['planned_integration_steps']==n==steps[-1]
            assert np.max(np.abs(a[:,0]-steps*float(dt)))<1e-10 and np.all(np.diff(a[:,0])>0)
            assert float(z['terminal_time'])==a[-1,0]==rec['terminal_simulation_time']
            assert np.array_equal(a[-1,1:8],z['terminal_qpos']) and np.array_equal(a[-1,8:14],z['terminal_qvel'])
            assert sum(bool(x&2) for x in flags)==1 and flags[-1]&2
            short_readback.append(dict(case=case['id'],samples=len(a),steps=n,actual_seconds=float(a[-1,0])))
    with np.load(recorded/'legacy/legacy_equivalence.npz') as old,np.load(recorded/'legacy_equivalence.npz') as new:
        assert np.array_equal(old['samples'],new['samples'])
    save(out/'numerical-readback.json',numeric)
    save(out/'recorder-readback.json',short_readback)
    return dict(passed=True,numerical_cases=len(numeric),integrated_groups=3,recorder_gates=14,raw_recorder_cases=len(short_readback),legacy_physics_bit_exact=True)

def clock_readback(root):
    from audit import chain
    events=chain(root/'events.jsonl');epochs={};last_sim=-float('inf');event_wall_regressions=0
    for row in events:
        assert row['sim_time']>=last_sim;last_sim=row['sim_time'];epoch=row['clock_epoch']
        if epoch in epochs:
            previous=epochs[epoch];assert row['monotonic_ns']>=previous['monotonic_ns']
            event_wall_regressions+=int(row['wall_ns']<previous['wall_ns'])
        epochs[epoch]=row
    last_sim=-float('inf');replay_epochs={};samples=0;wall_regressions=0;largest_wall_backstep_ns=0
    index=read(root/'replay/index.json')
    for part in index:
        with np.load(root/'replay'/part['file']) as z:
            t=z['t'];mono=z['monotonic_ns'];wall=z['wall_ns'];epoch=part['clock_epoch']
            assert len(t)==part['samples'] and t[0]==part['first'] and t[-1]==part['last']
            assert t[0]>=last_sim and np.all(np.diff(t)>=0) and np.all(np.diff(mono)>=0)
            assert np.isfinite(z['qpos']).all() and np.isfinite(z['qvel']).all()
            wall_deltas=np.diff(wall)
            if epoch in replay_epochs:
                prior=replay_epochs[epoch];assert mono[0]>=prior[0]
                wall_deltas=np.concatenate(([wall[0]-prior[1]],wall_deltas))
            if len(wall_deltas):
                wall_regressions+=int(np.sum(wall_deltas<0));largest_wall_backstep_ns=max(largest_wall_backstep_ns,int(max(0,-wall_deltas.min())))
            replay_epochs[epoch]=(mono[-1],wall[-1]);last_sim=float(t[-1]);samples+=len(t)
    return dict(passed=True,event_epochs=len(epochs),event_wall_regressions=event_wall_regressions,replay_epochs=len(replay_epochs),replay_chunks=len(index),replay_samples=samples,replay_wall_regressions=wall_regressions,largest_replay_wall_backstep_ns=largest_wall_backstep_ns,simulation_and_monotonic_order_preserved=True,wall_timestamps_preserved_without_normalization=True)

def native_readback(out):
    from audit import native,chain
    from repair_validation import transport_readback
    from recording import verify_checkpoint,verify_prefix
    from revision_validation import viewer_readback
    pilot=read(BASE/'native001/output/result.json')
    assert pilot['official_sessions']==0 and pilot['real_model_calls']==4 and pilot['injected_starts']==2
    evidence={};threads=[]
    for condition in ('baseline','maps'):
        root=Path(pilot['conditions'][condition]['root'])
        assert root.is_relative_to(BASE/'native001/output')
        r=native(root)
        r['transport']={p.name:transport_readback(p/'native') for p in sorted((root/'sessions').iterdir())}
        events=chain(root/'events.jsonl');starts=[e for e in events if e['kind']=='session_started'];closes=[e for e in events if e['kind']=='session_closed']
        assert len(starts)==len(closes)==2
        assert [e['payload']['work_s'] for e in starts]==[600,360]
        assert read(root/'config.json')==read(BASE/'release001/manifest.json')['config']
        for p in sorted((root/'sessions').iterdir()):threads.append(read(p/'native/client/result.json')['thread_id'])
        checkpoints=list((root/'checkpoints').iterdir());assert len(checkpoints)==2
        for cp in checkpoints:verify_checkpoint(cp);verify_prefix(root,cp)
        failed=BASE/'native001/output/failed'/condition;recovery=read(root/'recovery-ready.json')
        assert inventory(failed)==recovery['parent_inventory'] and recovery['cumulative_interrupted_sessions']==1
        execution=read(read(failed/'latest-execution.json')['path'])
        assert execution['passed'] is False and execution['retirement']['all_retired'] is True
        admitted={e['payload']['request_id'] for e in events if e['kind']=='command_admitted'}
        for start in starts:
            sid=start['payload']['session'];warning=start['sim_time']+start['payload']['work_s']
            commands=[e for e in events if e['kind']=='command_requested' and e['payload']['session']==sid and e['payload']['request']['request_id'] in admitted]
            dock=next(e for e in commands if e['payload']['request']['kind']=='dock');assert dock['sim_time']>=warning
        assert not (root/'running.lock').exists() and not (failed/'running.lock').exists()
        r['viewer']=viewer_readback(root);r['clock_integrity']=clock_readback(root);evidence[condition]=r
    assert len(threads)==len(set(threads))==4
    save(out/'native-readback.json',evidence)
    return dict(passed=True,real_model_calls=4,unique_native_threads=4,conditions=list(evidence))

def core_readback():
    failed=read(BASE/'core001/output/result.json');assert failed['passed'] is False
    assert failed['checks']==dict(all_four_toy_pick_carry_release=True,usable_chargers_and_return_reserve=False)
    second=read(BASE/'core002/output/result.json');assert second['passed'] is False and second['checks']==failed['checks']
    old=ast.parse((BASE/'core001/current_navigation_fixture.py').read_text(encoding='utf-8'))
    new=ast.parse((BASE/'core003/current_navigation_fixture.py').read_text(encoding='utf-8'))
    corrections=0
    for node in ast.walk(old):
        if isinstance(node,ast.For) and isinstance(node.iter,ast.List):
            route=ast.literal_eval(node.iter)
            if (9.1,4.05) in route:
                assert route[7:10]==[(9.1,5.6),(9.1,4.05),(9.85,4.05)]
                route[7:9]=[(9.35,5.6),(9.35,4.05)];node.iter=ast.parse(repr(route),mode='eval').body;corrections+=1
    assert corrections==1 and ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False)
    assert sha(BASE/'core001/current_toy_fixture.py')==sha(BASE/'core002/current_toy_fixture.py')==sha(BASE/'core003/current_toy_fixture.py')
    assert sha(BASE/'core001/core_suite.py')==sha(BASE/'core002/core_suite.py')==sha(BASE/'core003/core_suite.py')
    root=BASE/'core003/output';result=read(root/'result.json')
    groups=('all_four_toy_pick_carry_release','usable_chargers_and_return_reserve','storage_and_million_frame_fidelity')
    assert result['passed'] is False and len(result['checks'])==4 and all(result['checks'][n] for n in groups)
    assert result['checks']['native_stream_bounds_and_failure_cleanup'] is False
    assert not (root/'exact_frozen_bundle_native_preflight').exists()
    for name in groups:
        r=read(root/name/'result.json');assert r['passed'] and all(r['checks'].values()),name
    toys=read(root/'all_four_toy_pick_carry_release/result.json')
    assert all(toys['checks']['pickup_'+color] and toys['checks'][color+'_contained'] for color in ('red','green','blue','yellow'))
    assert toys['checks']['bedroom_complete']
    nav=read(root/'usable_chargers_and_return_reserve/result.json')
    assert nav['measurements']['reserve_s']==3600 and nav['measurements']['four_rooms_route_sim_s']*10<3600
    storage=read(root/'storage_and_million_frame_fidelity/result.json')
    assert storage['append_stress']['writes']==8192 and storage['transport_stress']['frames']==1000000
    remaining=BASE/'core004/output';last=read(remaining/'result.json')
    assert last['passed'] and set(last['checks'])=={'native_stream_bounds_and_failure_cleanup','exact_frozen_bundle_native_preflight'} and all(last['checks'].values())
    for name in last['checks']:
        r=read(remaining/name/'result.json');assert r['passed'] and all(r['checks'].values()),name
    original=ast.parse((BASE/'core004/source/native_stream_engineering.py').read_text(encoding='utf-8'))
    adapted=ast.parse((BASE/'core004/current_native_stream_fixture.py').read_text(encoding='utf-8'));inserted=0
    for function in original.body:
        if isinstance(function,ast.FunctionDef) and function.name=='fixture':
            for i,node in enumerate(function.body):
                if isinstance(node,ast.Assign) and ast.unparse(node.targets[0])=='client.args':
                    function.body[i+1:i+1]=ast.parse('from structured_errors import FailureTrace\nclient.failure_trace=FailureTrace(client.args.redact_tokens)\nclient.args.apartment_failure_trace=client.failure_trace').body
                    inserted+=1;break
    assert inserted==1 and ast.dump(original,include_attributes=False)==ast.dump(adapted,include_attributes=False)
    stream=read(remaining/'native_stream_bounds_and_failure_cleanup/result.json')['stream']
    event_file=remaining/'native_stream_bounds_and_failure_cleanup/large-notifications/events.jsonl'
    assert sha(event_file)==stream['event_sha256'] and event_file.stat().st_size==stream['event_bytes']
    assert stream['records']==769 and stream['raw_bytes']>3*32*1024**2
    return dict(passed=True,groups=5,toy_colors=4,return_tour_sim_s=nav['measurements']['four_rooms_route_sim_s'],append_writes=8192,metadata_frames=1000000,failed_core001_core002_core003_preserved=True,fixture_delta_exactly_two_route_x_coordinates=True,synthetic_stream_delta_only_constructor_state=True,composition={'core003':list(groups),'core004':list(last['checks'])})

def preserved(out):
    protected=read(BASE/'preservation002/output/protected-inventory.json');total=0;size=0
    for name,before in protected.items():
        after=inventory(Path(name));assert after==before,name
        total+=len(after);size+=sum(r['bytes'] for r in after.values())
        print('Preserved '+name,flush=True)
    from recording import verify_checkpoint,verify_prefix
    cp=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3/baseline/checkpoints/session-00014')
    assert verify_checkpoint(cp)['manifest_sha256']=='5314dc656b39dd4254325a46c94bc56c028f5f526004f85ac983e1547ec44015'
    verify_prefix(cp.parents[1],cp)
    old=read(read(cp.parents[1]/'latest-execution.json')['path'])
    assert not old['passed'] and old['retirement']['all_retired'] is False
    assert not read(cp.parents[2]/'maps/run.json')['launched']
    result=dict(passed=True,roots=len(protected),files=total,bytes=size,before_sha256=sha(BASE/'preservation002/output/protected-inventory.json'),v3_original_false_retirement_unchanged=True)
    save(out/'preservation-readback.json',result);return result

def actual_retirement(out,workspace):
    result=workspace.no_leaks(out)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetProcessTimes.argtypes=(wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4));kernel.GetProcessTimes.restype=wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD));kernel.GetExitCodeProcess.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,);kernel.CloseHandle.restype=wintypes.BOOL
    identities={}
    for attempt in BASE.iterdir():
        if not attempt.is_dir() or not (attempt/'manifest.json').exists():continue
        for pattern in ('native-owner.json','codehost-native-owner-v3.json'):
            for path in (attempt/'output').rglob(pattern):
                owner=read(path);key=(owner['pid'],owner['process_creation_filetime'])
                identities[key]=owner
    observed=[]
    for (pid,created),owner in identities.items():
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:
            error=ctypes.get_last_error();assert error==87,('Cannot inspect recorded native process',pid,error)
            observed.append(dict(pid=pid,creation_filetime=created,retired=True,state='absent'));continue
        try:
            times=[wintypes.FILETIME() for _ in range(4)];code=wintypes.DWORD()
            assert kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]) and kernel.GetExitCodeProcess(handle,ctypes.byref(code))
            actual=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
            same=actual==created;assert not (same and code.value==259),('Native process still active',pid,created)
            observed.append(dict(pid=pid,creation_filetime=created,current_creation_filetime=actual,exit_code=code.value,retired=True,state='exited' if same else 'pid_reused'))
        finally:kernel.CloseHandle(handle)
    assert identities,'No actual native owner identities were retained'
    import native_runtime as nr
    linux=json.loads(nr.linux(r'''import os,pathlib,json
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  args=(p/'cmdline').read_bytes().split(b'\0')
  if any(b'/var/tmp/robot-codex-session10/apartment-' in a for a in args):processes.append(int(p.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
mounts=[r.split()[4] for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if '/robot-codex-session10/apartment-' in r]
print(json.dumps({'processes':processes,'mounts':mounts}))
'''))
    assert not linux['processes'] and not linux['mounts'],linux
    result.update(native_windows_identities=observed,global_linux_apartment_runtime=linux)
    save(out/'actual-native-retirement.json',result);return result

def main():
    out=HERE/'output';out.mkdir(exist_ok=False);result=dict(passed=False,checks={},model_calls=0,official_writes=False)
    try:
        for n,row in read(HERE/'manifest.json')['files'].items():assert sha(HERE/n)==row['sha256'],n
        for name,call in [('fresh_immutable_attempts',lambda:receipts(out)),('exact_source_environment_config',identity_check),('physics_recording_numeric_readback',lambda:physics(out))]:
            result['checks'][name]=call();save(out/'progress.json',result)
        import workspace_reader as workspace
        result['checks']['workspace_matrix_raw_readback']=workspace.read_matrix()
        result['checks']['namespace_metadata_open_handles']=workspace.namespace_roundtrip(out)
        result['checks']['adversarial_startup_and_retirement']=workspace.adversarial(out)
        result['checks']['complete_applicable_regressions']=core_readback()
        result['checks']['fresh_native_transport_checkpoint_replay']=native_readback(out)
        result['checks']['actual_resource_retirement']=actual_retirement(out,workspace)
        result['checks']['all_original_histories_preserved']=preserved(out)
        manifest=read(BASE/'release001/manifest.json')
        certificate=dict(schema='apartment-integrated-commissioning-4',passed=True,source_identity=manifest['source_identity'],environment=manifest['environment'],config=manifest['config'],
            protocol_sha256=manifest['protocol_sha256'],release_manifest_sha256=sha(BASE/'release001/manifest.json'),
            qualification_composition='Fresh workspace, offline integration, recorder, fixed physics, all five applicable core regressions (three passed groups in failed core003 plus two groups in core004) and four genuine native pilot calls; separately implemented raw evidence audit and adversarial workspace checks. Failed preservation001 and core001/core002/core003 remain failed. No official data or pilot learning transfer.',
            scope='One fresh pristine matched pair on this exact repaired release. Baseline launch alone authorized after independent pair verification; Maps needs later direct instruction.',
            attempt_results={name:sha(BASE/name/'output/result.json') for name in ['preservation002','workspace001','offline001','recorder001','physics001','core003','core004','native001']})
        save(out/'certificate.json',certificate);result.update(passed=True,certificate=certificate)
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('checks','certificate')}) ,flush=True)
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
