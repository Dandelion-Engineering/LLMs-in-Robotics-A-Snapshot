"""Queue-only finite initial observation-posture calibration; no task policies."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import itertools
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import uuid
import zipfile

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
RUNTIME=PROJECT/'Runtime'
CALIBRATION=HERE.parent/'Calibration Tools'
sys.path[:0]=[str(RUNTIME),str(CALIBRATION)]
from calibration_authority import parent_authority,child_authority,child_command

VERSION='initial-observation-posture-screen-1.0'
EXISTING_HOME=[0.,-.5,0.,-2.2,0.,1.7,.7854]
SEED=2
CHILD_CAP_S=45.
STATION_REGIONS=('fixture','inspection','parking1','parking2','tray1','tray2','tray3',
                 'quarantine','insert_home_A','insert_home_B')


def postures():
    return [{'id':f'posture-{i:02d}','q':[a,b,0.,c,0.,1.7,.7854]} for i,(a,b,c) in
            enumerate(itertools.product((-.8,0.,.8),(-.5,-1.,-1.5),(-2.2,-2.6)))]


def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def save(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
def source_files():
    paths=set(RUNTIME.glob('*.py'))|set(HERE.glob('*.py'))|set(HERE.glob('*.md'))
    paths.add(CALIBRATION/'calibration_authority.py')
    paths.update(p for p in (RUNTIME/'vendor/panda').rglob('*') if p.is_file())
    return sorted(paths)
def sources():return {p.relative_to(PROJECT).as_posix():sha(p) for p in source_files()}


def job_handle(name,create=False):
    """Named Windows job retained by driver; child joins before any physics.

    The job contains the actual probe interpreter (not just its venv launcher).
    Only the driver retains a handle, so driver exit kills its owned probe tree.
    """
    if os.name!='nt':raise RuntimeError('Posture screen ownership requires Windows')
    import ctypes
    from ctypes import wintypes as wt
    class Basic(ctypes.Structure):
        _fields_=[('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',wt.DWORD),
                  ('MinimumWS',ctypes.c_size_t),('MaximumWS',ctypes.c_size_t),('ActiveLimit',wt.DWORD),
                  ('Affinity',ctypes.c_size_t),('Priority',wt.DWORD),('Scheduling',wt.DWORD)]
    class IO(ctypes.Structure):
        _fields_=[(name,ctypes.c_uint64) for name in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
    class Extended(ctypes.Structure):
        _fields_=[('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),
                  ('PeakProcessMemory',ctypes.c_size_t),('PeakJobMemory',ctypes.c_size_t)]
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    for key,args,restype in [('CreateJobObjectW',[ctypes.c_void_p,wt.LPCWSTR],wt.HANDLE),
        ('OpenJobObjectW',[wt.DWORD,wt.BOOL,wt.LPCWSTR],wt.HANDLE),
        ('AssignProcessToJobObject',[wt.HANDLE,wt.HANDLE],wt.BOOL),
        ('SetInformationJobObject',[wt.HANDLE,ctypes.c_int,ctypes.c_void_p,wt.DWORD],wt.BOOL),
        ('GetCurrentProcess',[],wt.HANDLE),('CloseHandle',[wt.HANDLE],wt.BOOL),
        ('TerminateJobObject',[wt.HANDLE,wt.UINT],wt.BOOL)]:
        getattr(k,key).argtypes=args;getattr(k,key).restype=restype
    handle=k.CreateJobObjectW(None,name) if create else k.OpenJobObjectW(0x1F003F,False,name)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    if create:
        limits=Extended();limits.Basic.Flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            k.CloseHandle(handle);raise ctypes.WinError(ctypes.get_last_error())
    else:
        if not k.AssignProcessToJobObject(handle,k.GetCurrentProcess()):
            k.CloseHandle(handle);raise ctypes.WinError(ctypes.get_last_error())
        k.CloseHandle(handle);handle=None  # Driver is the sole lifetime owner.
    return k,handle


def comparison(detections,snapshot):
    true={o['id']:o for o in snapshot['objects']};seen={d['id']:d for d in detections};rows=[]
    for identity,obj in true.items():
        d=seen.get(identity);row={'id':identity,'detected':d is not None}
        if d:
            error=[d['pos'][i]-obj['position'][i] for i in range(3)]
            row.update(error_m=math.sqrt(sum(v*v for v in error)),signed_error_m=error,
                       public_mark=d['visible_mark'],pixels=d['pixels'])
        rows.append(row)
    return {'rows':rows,'missing_ids':sorted(set(true)-set(seen)),'unexpected_ids':sorted(set(seen)-set(true)),
            'duplicate_ids':len(seen)!=len(detections)}


def region_visibility(depth,calibration,zones,zone_half):
    """Public fixed region footprints versus image depth; no object poses."""
    import numpy as np
    rotation=np.asarray(calibration['world_from_camera_rotation']);camera=np.asarray(calibration['camera_position_world_m'])
    if not np.allclose(rotation,np.eye(3),atol=1e-8):raise RuntimeError('Uncalibrated overhead axes')
    h,w=depth.shape;f=calibration['focal_px'];z=float(camera[2]);rows=[]
    for name in STATION_REGIONS:
        x,y=zones[name];hx,hy=zone_half(name)
        u=[(x+dx-camera[0])*f/z+(w-1)/2 for dx in (-hx,hx)]
        v=[-(y+dy-camera[1])*f/z+(h-1)/2 for dy in (-hy,hy)]
        lo=[math.ceil(min(u)),math.ceil(min(v))];hi=[math.floor(max(u)),math.floor(max(v))]
        in_frame=0<=lo[0]<=hi[0]<w and 0<=lo[1]<=hi[1]<h
        region=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1] if in_frame else np.array([])
        good=bool(region.size and np.isfinite(region).all())
        clear=float(np.mean(region>=z-.020)) if good else None
        rows.append({'region':name,'pixel_bounds':[lo,hi],'in_frame':in_frame,'clear_fraction':clear,
                     'passed':clear is not None and clear>=.98})
    return rows


def decision(initial,robot,perception,regions):
    rows=perception['rows']
    flags={'initial_valid':initial['valid'],'joint_workspace_contact_stability':robot['passed'],
        'all_12_ids':len(rows)==12 and not perception['missing_ids'] and not perception['unexpected_ids'] and not perception['duplicate_ids'],
        'all_marks_raw':all(r.get('public_mark')=='raw' for r in rows),
        'all_errors_le_4mm':all(r.get('error_m',float('inf'))<=.004 for r in rows),
        'all_station_regions_clear':len(regions)==len(STATION_REGIONS) and all(r['passed'] for r in regions)}
    return {'eligible':all(flags.values()),'flags':flags,'selection_scope':'operator arena calibration only; never online policy feedback'}


def candidate_order(rows):
    eligible=[r for r in rows if r.get('status')=='completed' and r.get('sources_unchanged') is True
              and r.get('decision',{}).get('eligible')]
    return sorted(eligible,key=lambda r:(sum((a-b)**2 for a,b in zip(r['q'],EXISTING_HOME)),r['id']))


def probe(args):
    authority=child_authority(__file__,args._child,args.output,args.seed,args.parent_manifest,args.parent_manifest_sha256)
    manifest=json.loads(Path(args.parent_manifest).read_text());definition=next(p for p in manifest['postures'] if p['id']==args._child)
    kernel,handle=job_handle(manifest['jobs'][args._child]);out=Path(args.output);out.mkdir(exist_ok=False)
    result={'schema_version':VERSION,**definition,'queue_authority':authority,'status':'failed','error':None}
    cell=None;before=sources();start=time.perf_counter()
    try:
        if before!=manifest['source_hashes']:raise RuntimeError('Source identity changed before probe')
        import numpy as np
        import mujoco
        import cell as cm
        from initial_conditions import initial_world_report
        old_home=cm.HOME
        if old_home.tolist()!=EXISTING_HOME:raise RuntimeError('Existing HOME changed from the declared comparator')
        try:
            cm.HOME=np.array(definition['q']);cell=cm.Cell(10,SEED,noise_seed=0,layout_seed=SEED)
        finally:cm.HOME=old_home
        (out/'world.xml').write_text(cell.xml,encoding='utf-8')
        initial_qpos=cell.data.qpos.tolist();save(out/'initial-qpos.json',initial_qpos)
        root=mujoco.mj_name2id(cell.model,mujoco.mjtObj.mjOBJ_BODY,'link0')
        if root<0:raise RuntimeError('Panda root absent; cannot classify contacts')
        def robot_body(body):
            while body>0:
                if body==root:return True
                body=int(cell.model.body_parentid[body])
            return False
        contacts={};tail_velocity=[]
        for tick in range(250):
            cell.tick()
            if tick>=200:tail_velocity.append(float(np.max(np.abs(cell.data.qvel[:7]))))
            for i in range(cell.data.ncon):
                c=cell.data.contact[i];a,b=int(c.geom1),int(c.geom2)
                ra,rb=robot_body(int(cell.model.geom_bodyid[a])),robot_body(int(cell.model.geom_bodyid[b]))
                if not (ra or rb) or c.efc_address<0:continue
                force=np.zeros(6);mujoco.mj_contactForce(cell.model,cell.data,i,force)
                if c.dist>=-.001 and abs(force[0])<=.1:continue
                key=f'{a}:{b}';contacts[key]={'geoms':[mujoco.mj_id2name(cell.model,mujoco.mjtObj.mjOBJ_GEOM,k) for k in (a,b)],
                    'kind':'self' if ra and rb else 'robot_environment','distance_m':float(c.dist),'normal_force_N':float(force[0])}
        snapshot=cell.evaluator.snapshot_cell(cell,zones=cm.ZONES,zone_half=cm.zone_half)
        initial=initial_world_report(cell,10,zones=cm.ZONES,zone_half=cm.zone_half)
        q=cell.data.qpos[:7];ranges=cell.arm_adapter.position_range
        robot={'joint_range_pass':bool(np.all(q>=ranges[:,0]) and np.all(q<=ranges[:,1])),
            'target_joint_range_pass':bool(np.all(np.array(definition['q'])>=ranges[:,0]) and np.all(np.array(definition['q'])<=ranges[:,1])),
            'workspace_pass':cell.arm_adapter.workspace_contains(cell.data.site_xpos[cell.tcp]),
            'tail_max_joint_speed_rad_s':max(tail_velocity),'target_error_rad':float(np.max(abs(q-definition['q']))),
            'finger_speed_m_s':float(np.max(abs(cell.data.qvel[7:9]))),'gripper_width_m':float(sum(cell.data.qpos[7:9])),
            'contacts':list(contacts.values()),'tcp_m':cell.data.site_xpos[cell.tcp].tolist(),'q':q.tolist()}
        robot['passed']=bool(robot['joint_range_pass'] and robot['target_joint_range_pass'] and robot['workspace_pass']
            and robot['tail_max_joint_speed_rad_s']<=.02 and robot['target_error_rad']<=.02
            and robot['finger_speed_m_s']<=.01 and robot['gripper_width_m']>=.065 and not contacts)
        save(out/'protected-settled-snapshot.json',snapshot);save(out/'protected-initial-validity.json',initial);save(out/'robot-checks.json',robot)
        cell.prepare_sensor();request=cell.request_sense(sequence=1,rgb_path=out/'overhead.png',depth_path=out/'overhead-depth.npz')
        if not request['accepted']:raise RuntimeError('Fresh sensor job was not accepted')
        # Static calibration: physics intentionally stops after exactly250ticks.
        captured=cell.sensor_worker.wait()
        if captured is None or captured.capture_sim_time_s!=float(cell.data.time):raise RuntimeError('Capture/snapshot clocks differ')
        perception=comparison(captured.detections,snapshot)
        regions=region_visibility(captured.depth,captured.calibration,cm.ZONES,cm.zone_half)
        save(out/'public-capture.json',{'detections':captured.detections,'calibration':captured.calibration,
             'artifacts':captured.artifacts,'sim_time_s':captured.capture_sim_time_s})
        result.update(initial_validity=initial,robot=robot,perception=perception,region_visibility=regions,
                      decision=decision(initial,robot,perception,regions),status='completed')
    except BaseException as exc:result['error']=type(exc).__name__+': '+str(exc);result['traceback']=traceback.format_exc()
    finally:
        if cell is not None:
            try:cell.close()
            except Exception as exc:result['cleanup_error']=str(exc);result['status']='failed'
        result.update(wall_duration_s=time.perf_counter()-start,sources_unchanged=sources()==before,finished_at=utc(),
                      task_success_claimed=False,actual_host_realtime_claimed=False)
        if not result['sources_unchanged']:result['status']='integrity_failure';result['decision']={'eligible':False}
        save(out/'result.json',result)
    return 0


def driver(args):
    authority=parent_authority(__file__);out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    before=sources();grid=postures();nonce=uuid.uuid4().hex
    with zipfile.ZipFile(out/'source-bundle.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in source_files():archive.write(p,p.relative_to(PROJECT).as_posix())
    manifest={'schema_version':VERSION,'created_at':utc(),'queue':authority,'seed':SEED,'part_count':10,
        'modes':[p['id'] for p in grid],'postures':grid,'existing_home':EXISTING_HOME,
        'jobs':{p['id']:'Local\\CodexPosture-'+nonce+'-'+p['id'] for p in grid},
        'source_hashes':before,'source_bundle_sha256':sha(out/'source-bundle.zip'),
        'child_hard_wall_cap_s':CHILD_CAP_S,'settling_steps':250,'noise_seed':0,'layout_seed':SEED,
        'selection':'all declared flags; then least squared joint distance from existing HOME, then grid index',
        'environment':{'python':platform.python_version(),'platform':platform.platform(),
                       'mujoco':importlib.metadata.version('mujoco'),'numpy':importlib.metadata.version('numpy')}}
    save(out/'manifest.json',manifest);manifest_hash=sha(out/'manifest.json');rows=[]
    for definition in grid:
        mode=definition['id'];path=out/mode;kernel,handle=job_handle(manifest['jobs'][mode],create=True)
        command=child_command(sys.executable,Path(__file__).resolve(),mode,path,SEED,out/'manifest.json',manifest_hash)
        save(out/'progress.json',{'completed_ids':[r['id'] for r in rows],'started':mode,'remaining_ids':[p['id'] for p in grid[len(rows)+1:]]})
        try:
            with (out/(mode+'.stdout.log')).open('wb') as stdout,(out/(mode+'.stderr.log')).open('wb') as stderr:
                child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
                timed_out=False
                try:exit_status=child.wait(timeout=CHILD_CAP_S)
                except subprocess.TimeoutExpired:
                    timed_out=True;kernel.TerminateJobObject(handle,124)
                    try:exit_status=child.wait(timeout=5.)
                    except subprocess.TimeoutExpired:child.kill();exit_status=child.wait(timeout=5.)
            if not timed_out and exit_status==0 and (path/'result.json').exists():row=json.loads((path/'result.json').read_text())
            else:row={**definition,'status':'infrastructure_failure','hard_timeout':timed_out,'exit_status':exit_status,'decision':{'eligible':False}}
            rows.append(row)
        finally:kernel.TerminateJobObject(handle,125);kernel.CloseHandle(handle)
        if sources()!=before:break  # Source breach blocks all remaining cases, never silently mixes revisions.
    unchanged=sources()==before;ordered=candidate_order(rows) if unchanged and len(rows)==18 else []
    summary={'schema_version':VERSION,'queue_job_id':authority['job_id'],'rows':rows,'sources_unchanged':unchanged,
        'completed_cases':len(rows),'planned_cases':18,'eligible_ids':[r['id'] for r in ordered],
        'recommended_for_followup':ordered[0]['id'] if ordered else None,'runtime_modified':False,
        'classification':'single-seed initial observation calibration; no task/trajectory/readiness claim','finished_at':utc()}
    save(out/'summary.json',summary)
    save(out/'evidence-index.json',{'files':[{'path':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
        for p in sorted(out.rglob('*')) if p.is_file()]})
    print(json.dumps({'completed_cases':len(rows),'eligible_ids':summary['eligible_ids'],'sources_unchanged':unchanged}))
    return 0 if unchanged and len(rows)==18 else 2


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--seed',type=int,default=SEED);parser.add_argument('--_child',choices=[p['id'] for p in postures()],help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest',help=argparse.SUPPRESS);parser.add_argument('--parent-manifest-sha256',help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if args.seed!=SEED:parser.error('This finite calibration is preregistered for development seed2 only')
    if args._child and (not args.parent_manifest or not args.parent_manifest_sha256):parser.error('Child requires exact parent authority')
    return probe(args) if args._child else driver(args)


if __name__=='__main__':raise SystemExit(main())
