"""Read-only, bounded Windows queue -> driver -> probe launcher proof.

No arbitrary ancestor walk, descendants, process signalling or queue status call.
Only the four explicitly identified driver/probe interpreter/launcher PIDs are
queried through the existing release_runner CIM helper.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys


class CalibrationAuthorityError(RuntimeError):pass


def _runtime():
    runtime=Path(__file__).resolve().parents[2]/'Runtime'
    if str(runtime) not in sys.path:sys.path.insert(0,str(runtime))
    import release_runner
    return release_runner


def parent_authority(script):
    runtime=_runtime();job=runtime.queued_job(expected_script=script)
    if sys.platform!='win32':raise CalibrationAuthorityError('This probe ownership handshake requires Windows CIM metadata')
    pid,parent=os.getpid(),os.getppid()
    rows=runtime.windows_process_metadata(pid,parent)
    if pid not in rows or parent not in rows:raise CalibrationAuthorityError('Incomplete driver process metadata')
    return {'job_id':job['id'],'pid':pid,'parent_pid':parent,'argv':job['argv'],'started_at':job['started_at'],
            'queue_job':job,'driver_metadata':rows[pid],'driver_parent_metadata':rows[parent],
            'launcher_executable':str(Path(sys.executable).resolve()),
            'base_executable':str(Path(sys._base_executable).resolve()),'script':str(Path(script).resolve())}


def child_command(executable,script,mode,output,seed,parent_manifest,manifest_sha256):
    return [str(executable),'-X','utf8','-B',str(script),'--_child',mode,'--output',str(output),
            '--seed',str(seed),'--parent-manifest',str(parent_manifest),'--parent-manifest-sha256',manifest_sha256]


def _time(value):
    parsed=datetime.fromisoformat(value)
    if parsed.tzinfo is None:raise CalibrationAuthorityError('Process creation time lacks timezone')
    return parsed


def validate_child_chain(manifest,job,current_pid,parent_pid,rows,expected_argv):
    """Pure verification, also used by synthetic counterexample tests."""
    proof=manifest['queue'];driver_pid=proof['pid'];driver_parent=proof['parent_pid']
    if len({current_pid,parent_pid,driver_pid})!=3:raise CalibrationAuthorityError('Probe interpreter, launcher and driver must be distinct')
    required=(current_pid,parent_pid,driver_pid,driver_parent)
    if any(pid not in rows for pid in required):raise CalibrationAuthorityError('Explicit process chain metadata missing')
    current,launcher,driver=rows[current_pid],rows[parent_pid],rows[driver_pid]
    if current['parent_pid']!=parent_pid or launcher['parent_pid']!=driver_pid:
        raise CalibrationAuthorityError('Probe is not the immediate launcher/interpreter pair created by this driver')
    for pid,record in ((driver_pid,proof['driver_metadata']),(driver_parent,proof['driver_parent_metadata'])):
        if rows[pid]!=record:raise CalibrationAuthorityError('Parent driver identity changed or PID was recycled')
    saved=proof['queue_job']
    fields=('id','child_pid','worker_pid','resolved_executable','argv','cwd','started_at')
    if job.get('state')!='running' or any(job.get(k)!=saved.get(k) for k in fields):
        raise CalibrationAuthorityError('Parent driver no longer has the same live installed queue ownership')
    if job['id']!=proof['job_id']:raise CalibrationAuthorityError('Queue job identity differs from manifest')
    if driver_pid!=job['child_pid']:
        if driver_parent!=job['child_pid'] or rows[driver_parent]['parent_pid']!=job['worker_pid']:
            raise CalibrationAuthorityError('Parent is not the validated direct queue venv chain')
        parent_pairs=((driver,proof['base_executable']),(rows[driver_parent],proof['launcher_executable']))
    else:parent_pairs=((driver,job['resolved_executable']),)
    for record,executable in parent_pairs:
        if Path(record['executable']).resolve()!=Path(executable).resolve() or not record['argv'] or record['argv'][1:]!=job['argv'][1:]:
            raise CalibrationAuthorityError('Driver command differs from validated queued command')
    for record,executable in ((current,proof['base_executable']),(launcher,proof['launcher_executable'])):
        if (Path(record['executable']).resolve()!=Path(executable).resolve() or not record['argv']
                or Path(record['argv'][0]).resolve()!=Path(executable).resolve() or record['argv'][1:]!=expected_argv[1:]):
            raise CalibrationAuthorityError('Probe executable/arguments differ from the exact declared child command')
    times=[_time(job['started_at']),_time(driver['created_at']),_time(launcher['created_at']),_time(current['created_at'])]
    if times!=sorted(times):raise CalibrationAuthorityError('Creation times do not prove parent-before-child identity')
    return {'job_id':job['id'],'driver_pid':driver_pid,'probe_launcher_pid':parent_pid,'probe_pid':current_pid,
            'verified_chain':'installed queue -> verified driver -> immediate venv launcher -> base interpreter',
            'process_creation_times':[t.isoformat() for t in times]}


def child_authority(script,mode,output,seed,parent_manifest,manifest_sha256):
    if sys.platform!='win32':raise CalibrationAuthorityError('This probe ownership handshake requires Windows CIM metadata')
    path=Path(parent_manifest).resolve();raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest_sha256:raise CalibrationAuthorityError('Immutable parent manifest hash mismatch')
    manifest=json.loads(raw);proof=manifest['queue'];runtime=_runtime()
    if Path(script).resolve()!=Path(proof['script']).resolve() or mode not in manifest['modes'] or seed!=manifest['seed']:
        raise CalibrationAuthorityError('Probe not declared by this parent manifest')
    if Path(output).resolve()!=path.parent/mode:raise CalibrationAuthorityError('Probe output is not the declared protected subdirectory')
    expected=child_command(proof['launcher_executable'],proof['script'],mode,str(Path(output).resolve()),seed,str(path),manifest_sha256)
    rows=runtime.windows_process_metadata(os.getpid(),os.getppid())
    rows.update(runtime.windows_process_metadata(proof['pid'],proof['parent_pid']))
    state=runtime.load(runtime.QUEUE_STATE)
    matches=[j for j in state.get('jobs',[]) if j.get('id')==proof['job_id']]
    if len(matches)!=1:raise CalibrationAuthorityError('Queue owner is absent or ambiguous')
    # The normal Runtime parser rejects .py strings supplied merely as wrapper args.
    if runtime.python_entrypoint(matches[0].get('argv'),matches[0].get('cwd'))!=Path(script).resolve():
        raise CalibrationAuthorityError('Parent queued entrypoint is not this driver')
    return validate_child_chain(manifest,matches[0],os.getpid(),os.getppid(),rows,expected)
