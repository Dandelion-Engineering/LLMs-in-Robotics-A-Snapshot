"""Once-only, bounded evaluation batches. Run ``run`` through compute_queue.

This file generates no seeds and cannot turn readiness declarations into proof.
It requires protocol.py's complete release plus stronger execution references:

freeze.artifacts = {code|environment|model: {path, sha256}}. Each hash must
equal freeze.<role>_sha256. Each referenced JSON index contains a nonempty
``files`` array of path/SHA256 references, resolved relative to that index.
The code index additionally has ``runtime_root`` and ``bundle`` (ZIP reference).
Every current Runtime/*.py must be in files and byte-identical in the ZIP;
extra declared resources are also checked. The environment index has exact
``runtime_identity`` (python, implementation, platform, machine, dependencies)
and read-only ``probes`` (name, argv, stdout_sha256, timeout_s), including
candidate_python, candidate_isolation and gpu_driver. Probe output is not logged.
The model index has ``identity``, ``config``, and ``asset_manifest`` references;
its files must cover the actual weights, asset manifest and every installed DLL
and executable. All substantial hashes/probes run inside the queue only.

Future supervisor integration (not enabled by this module): expose
EVALUATION_AUTHORIZATION_VERSION=AUTHORIZATION_VERSION and accept
evaluation_context, world_seed, layout_seed, policy_seed, noise_seed. At entry,
call context.assert_episode(...) with all exact arguments. Use context.evidence_dir
as this run's output directory and apply all four seed roles without collapse.
The context is process-local provenance, not a replacement for OS isolation.

``finalize`` is an explicit post-queue operation. It requires an official status
JSON receipt from ``compute_queue.py status JOB`` with succeeded/exit_status=0,
checks that same job in installed queue state and against the batch journal,
then appends map results. It never submits/polls/repairs the shared queue. A failed
or interrupted batch remains protected evidence and cannot be quietly rerun.
An immutable ``review`` record may authorize continuation after an isolated
host/queue/runtime incident, retaining every original result and excluding its
whole paired block from primary inference. All original unattempted manifests,
including excluded-block members for descriptive evidence, remain runnable.
Integrity breaches and unresolved started attempts cannot be waived by review.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import zipfile

import protocol

HERE=Path(__file__).resolve().parent
QUEUE_HOME=Path(r'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue')
QUEUE_STATE=QUEUE_HOME/'runtime'/'state.json'
AUTHORIZATION_VERSION='robot-evaluation-authorization-1.0'
_AUTHORITY=object()
SAFE_ID=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,179}$')


class ReleaseError(protocol.ProtocolError):pass
class IntegrityError(ReleaseError):pass


def utc():return datetime.now(timezone.utc).isoformat()
def load(path):return protocol._load(path)
def digest(path):
    hasher=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):hasher.update(block)
    return hasher.hexdigest()


def write_once(path,value):
    """Publish fully flushed JSON without replacing any existing record."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with temp.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    try:os.link(temp,path)  # Atomic exclusive publication on the Windows/NTFS host.
    finally:temp.unlink()


def safe_id(value):
    if not isinstance(value,str) or not SAFE_ID.fullmatch(value):raise ReleaseError('Unsafe record identifier')
    return value


def reference(ref,base):
    if not isinstance(ref,dict) or not isinstance(ref.get('path'),str) or not protocol.HASH_RE.fullmatch(str(ref.get('sha256',''))):
        raise ReleaseError('Malformed artifact reference')
    path=Path(ref['path']);path=path if path.is_absolute() else Path(base)/path
    path=path.resolve()
    if not path.is_file() or digest(path)!=ref['sha256']:raise ReleaseError('Missing or changed artifact: '+str(path))
    return path


def python_entrypoint(argv,cwd):
    """Find the executed file, never a .py string in another script's arguments."""
    if not isinstance(argv,list) or len(argv)<2 or not all(isinstance(a,str) and a and '\x00' not in a for a in argv):
        raise ReleaseError('Queued command lacks an explicit Python script')
    index=1
    while index<len(argv):
        arg=argv[index]
        if arg=='--':index+=1;break
        if arg in ('-X','-W'):
            if index+1>=len(argv):raise ReleaseError('Malformed queued Python option')
            index+=2;continue
        if arg in ('-B','-E','-I','-O','-OO','-P','-q','-s','-S','-u','-v','-x') or arg.startswith(('-X','-W')):
            index+=1;continue
        if arg.startswith('-'):raise ReleaseError('Queued command must directly execute the expected Python script')
        break
    if index>=len(argv):raise ReleaseError('Queued command lacks an explicit Python script')
    path=Path(argv[index]);return (path if path.is_absolute() else Path(cwd)/path).resolve()


def windows_command_argv(command):
    """Decode CIM's command line using the Windows argument parser, read-only."""
    import ctypes
    from ctypes import wintypes
    if not isinstance(command,str) or not command:raise ReleaseError('Process command line is unavailable')
    shell=ctypes.WinDLL('shell32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    parse=shell.CommandLineToArgvW;parse.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_int)];parse.restype=ctypes.POINTER(wintypes.LPWSTR)
    free=kernel.LocalFree;free.argtypes=[wintypes.HLOCAL];free.restype=wintypes.HLOCAL
    count=ctypes.c_int();pointer=parse(command,ctypes.byref(count))
    if not pointer:raise ReleaseError('Cannot decode process command line')
    try:return [pointer[index] for index in range(count.value)]
    finally:free(ctypes.cast(pointer,wintypes.HLOCAL))


def windows_process_metadata(current_pid,parent_pid):
    """Bounded CIM read of these two PIDs only; never signal or inspect descendants."""
    if any(type(pid) is not int or pid<=0 for pid in (current_pid,parent_pid)):
        raise ReleaseError('Invalid process identity')
    script=("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
            "$rows=@(Get-CimInstance Win32_Process -Filter 'ProcessId = "+str(current_pid)+" OR ProcessId = "+str(parent_pid)+"' | "
            "Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,@{Name='Created';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}}); "
            "ConvertTo-Json -InputObject $rows -Compress")
    try:
        reply=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',
            timeout=8,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        if reply.returncode!=0 or len(reply.stdout)>1024*1024:raise ValueError('Metadata query failed')
        rows=json.loads(reply.stdout)
        if not isinstance(rows,list):raise ValueError('Malformed metadata')
        records={}
        for row in rows:
            pid=row['ProcessId']
            if type(pid) is not int or pid not in (current_pid,parent_pid) or pid in records:raise ValueError('Unexpected process')
            records[pid]={'pid':pid,'parent_pid':row['ParentProcessId'],'executable':row['ExecutablePath'],
                          'argv':windows_command_argv(row['CommandLine']),'created_at':row['Created']}
        return records
    except (OSError,subprocess.SubprocessError,ValueError,KeyError,TypeError) as exc:
        raise ReleaseError('Cannot verify Windows venv launcher process metadata') from exc


def verify_windows_venv_parent(job,current_pid,parent_pid):
    """Allow exactly the real interpreter directly below the queued venv launcher."""
    if sys.platform!='win32' or Path(sys.prefix).resolve()==Path(sys.base_prefix).resolve():
        raise ReleaseError('Queue parent is not an eligible Windows venv launcher')
    launcher=Path(sys.executable).resolve();base=Path(getattr(sys,'_base_executable','')).resolve()
    if launcher!=(Path(sys.prefix)/'Scripts'/'python.exe').resolve() or launcher==base or not (Path(sys.prefix)/'pyvenv.cfg').is_file():
        raise ReleaseError('Current interpreter does not identify a Windows venv launcher')
    if Path(job.get('resolved_executable','')).resolve()!=launcher:
        raise ReleaseError('Queued executable is not this venv launcher')
    rows=windows_process_metadata(current_pid,parent_pid);current=rows.get(current_pid,{});parent=rows.get(parent_pid,{})
    if (current.get('parent_pid')!=parent_pid or parent.get('pid')!=job.get('child_pid') or
            parent.get('parent_pid')!=job.get('worker_pid') or type(job.get('worker_pid')) is not int):
        raise ReleaseError('Process is not directly below the installed queue venv launcher')
    if (Path(current.get('executable') or '').resolve()!=base or Path(parent.get('executable') or '').resolve()!=launcher):
        raise ReleaseError('Observed process executable differs from the venv/base interpreter')
    expected=[str(launcher),*job['argv'][1:]]
    for row,executable in ((parent,launcher),(current,base)):
        argv=row.get('argv',[])
        if not argv or Path(argv[0]).resolve()!=executable or argv[1:]!=expected[1:]:
            raise ReleaseError('Observed process command differs from the queued command')
    try:
        started=datetime.fromisoformat(job['started_at']);parent_time=datetime.fromisoformat(parent['created_at']);current_time=datetime.fromisoformat(current['created_at'])
        if any(t.tzinfo is None for t in (started,parent_time,current_time)) or not started<=parent_time<=current_time:
            raise ValueError('Inconsistent process creation times')
    except (KeyError,TypeError,ValueError) as exc:raise ReleaseError('Process creation times do not verify the queue launcher relationship') from exc


def queued_job(expected_script=None):
    """Read-only exact child or verified Windows venv-launcher child identity."""
    expected=Path(expected_script or HERE/'release_runner.py').resolve()
    if not sys.argv or Path(sys.argv[0]).resolve()!=expected:
        raise ReleaseError('Actual sys.argv[0] is not the expected artifact/evaluation entrypoint')
    current_pid=os.getpid();parent_pid=os.getppid()
    eligible={current_pid,parent_pid} if sys.platform=='win32' else {current_pid}
    for _ in range(30):  # Worker publishes child_pid just after Popen.
        jobs=load(QUEUE_STATE).get('jobs',[])
        matching=[j for j in jobs if j.get('state')=='running' and type(j.get('child_pid')) is int and j['child_pid'] in eligible]
        if len(matching)>1:raise ReleaseError('Ambiguous installed queue process ownership')
        if matching:
            job=matching[0];cwd=job.get('cwd','')
            if not isinstance(cwd,str) or not Path(cwd).is_absolute() or python_entrypoint(job.get('argv'),cwd)!=expected:
                raise ReleaseError('Queued command is not the expected artifact/evaluation entrypoint')
            if job['child_pid']!=current_pid:verify_windows_venv_parent(job,current_pid,parent_pid)
            return job
        time.sleep(.05)
    raise ReleaseError('Heavy validation/execution requires the installed queue child or its verified direct Windows venv interpreter')


def environment_identity(dependencies):
    return {'python':platform.python_version(),'implementation':platform.python_implementation(),
            'platform':platform.platform(),'machine':platform.machine(),
            'dependencies':{name:importlib.metadata.version(name) for name in sorted(dependencies)}}


def run_probe(probe):
    argv=probe.get('argv');timeout=probe.get('timeout_s',15)
    if not isinstance(argv,list) or not argv or not all(isinstance(s,str) and s and '\x00' not in s for s in argv):raise ReleaseError('Invalid environment probe argv')
    if type(timeout) not in (int,float) or not 0<timeout<=30:raise ReleaseError('Environment probe timeout must be bounded at 30 seconds')
    if not protocol.HASH_RE.fullmatch(str(probe.get('stdout_sha256',''))):raise ReleaseError('Probe requires exact stdout hash')
    reply=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         timeout=timeout,shell=False,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if reply.returncode!=0 or hashlib.sha256(reply.stdout).hexdigest()!=probe['stdout_sha256']:
        raise ReleaseError('Live environment probe does not match freeze: '+str(probe.get('name')))


def verify_artifacts(freeze,freeze_path):
    artifacts=freeze.get('artifacts')
    if not isinstance(artifacts,dict) or set(artifacts)!={'code','environment','model'}:raise ReleaseError('Freeze requires exact code/environment/model artifact references')
    indexes={};paths={};verified={}
    for role in ('code','environment','model'):
        path=reference(artifacts[role],Path(freeze_path).parent)
        if artifacts[role]['sha256']!=freeze[role+'_sha256']:raise ReleaseError('Freeze artifact index hash mismatch: '+role)
        index=load(path);files=index.get('files')
        if not isinstance(files,list) or not files:raise ReleaseError('Artifact index has no actual files: '+role)
        rows={}
        for ref in files:
            actual=reference(ref,path.parent)
            if actual in rows:raise ReleaseError('Duplicate file reference in '+role)
            rows[actual]=ref['sha256']
        indexes[role]=index;paths[role]=path;verified[role]=rows
    code=indexes['code'];root=Path(code.get('runtime_root',''))
    root=(root if root.is_absolute() else paths['code'].parent/root).resolve()
    if root!=HERE:raise ReleaseError('Frozen code references another runtime directory')
    actual_sources={p.resolve() for p in HERE.glob('*.py')}
    declared_sources={p for p in verified['code'] if p.parent==HERE and p.suffix=='.py'}
    if declared_sources!=actual_sources:raise ReleaseError('Freeze omits or adds runtime source files')
    bundle=reference(code.get('bundle'),paths['code'].parent)
    with zipfile.ZipFile(bundle) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or set(names)!={p.name for p in actual_sources}:raise ReleaseError('Source bundle contents differ from exact runtime source set')
        for source in actual_sources:
            if hashlib.sha256(archive.read(source.name)).hexdigest()!=verified['code'][source]:raise ReleaseError('Source bundle bytes differ: '+source.name)
    environment=indexes['environment'];identity=environment.get('runtime_identity')
    if not isinstance(identity,dict) or not isinstance(identity.get('dependencies'),dict) or not {'numpy','mujoco'}<=set(identity['dependencies']):raise ReleaseError('Frozen live environment identity is incomplete')
    if environment_identity(identity['dependencies'])!=identity:raise ReleaseError('Live Python/platform/dependencies differ from freeze')
    probes=environment.get('probes')
    if not isinstance(probes,list) or not {'candidate_python','candidate_isolation','gpu_driver'}<={p.get('name') for p in probes if isinstance(p,dict)}:raise ReleaseError('Frozen live external environment probes are incomplete')
    for probe in probes:run_probe(probe)
    from model_runtime import LocalModel,ModelConfig
    from model_setup import VENDOR,MODEL_FILE,MODEL_SHA256
    model=indexes['model'];config=ModelConfig(**model.get('config',{}))
    if asdict(config)!=model.get('config'):raise ReleaseError('Model configuration must explicitly contain every effective setting')
    if LocalModel(config).identity!=model.get('identity'):raise ReleaseError('Actual model/runtime identity differs from freeze')
    asset_path=reference(model.get('asset_manifest'),paths['model'].parent)
    if asset_path!=(VENDOR/'asset_manifest.json').resolve():raise ReleaseError('Model assets do not identify the actual runtime manifest')
    assets=load(asset_path);required={asset_path: digest(asset_path),(VENDOR/MODEL_FILE).resolve():MODEL_SHA256}
    for entry in assets.get('installed_files',[]):
        path=(VENDOR/entry['path']).resolve()
        if not path.is_relative_to(VENDOR.resolve()):raise ReleaseError('Model file escapes installed asset directory')
        required[path]=entry['sha256']
    if not assets.get('installed_files') or any(verified['model'].get(path)!=sha for path,sha in required.items()):raise ReleaseError('Model index does not verify every installed executable, DLL and weight')
    return {'index_paths':{k:str(v) for k,v in paths.items()},'code_bundle':str(bundle),'model_config':asdict(config),
            'source_files':{str(p):sha for p,sha in verified['code'].items()},'model_identity':model['identity']}


def verify_release(release_dir):
    root=Path(release_dir).resolve();release=load(root/'release.json')
    freeze_path=reference(release.get('freeze_manifest'),root);ready_path=reference(release.get('readiness'),root)
    freeze,readiness=protocol.validate_release_gates(freeze_path,ready_path)
    if release.get('schema_version')!=protocol.SCHEMA_VERSION or release.get('release_id')!=freeze['release_id']:raise ReleaseError('Release index identity mismatch')
    manifests=protocol.load_release(root)
    if any('seeds' not in m for m in manifests):raise ReleaseError('Release contains no concealed seed manifest')
    indexes=[m.get('scheduled_index') for m in manifests]
    if any(type(index) is not int for index in indexes) or sorted(indexes)!=list(range(1,len(manifests)+1)):raise ReleaseError('Schedule must be the complete exact permutation')
    expected_hashes={k:freeze[k] for k in ('code_sha256','environment_sha256','model_sha256','protocol_sha256')}
    refs={r['run_id']:r for r in release['manifest_refs']}
    for manifest in manifests:
        safe_id(manifest['run_id'])
        ref=refs.get(manifest['run_id'])
        expected_id=f"{freeze['release_id']}-{manifest['case_id']}-rep{manifest['replicate']}-{manifest['architecture']}-{manifest['condition']}"
        if manifest['run_id']!=expected_id or manifest['release_id']!=freeze['release_id']:raise ReleaseError('Run identity differs from exact frozen release')
        if not ref or ref['scheduled_index']!=manifest['scheduled_index'] or ref['path']!='runs/'+manifest['run_id']+'.json':raise ReleaseError('Schedule index/path and manifest disagree')
        if manifest.get('freeze_sha256')!=release['freeze_manifest']['sha256'] or manifest.get('readiness_sha256')!=release['readiness']['sha256'] or manifest.get('artifact_hashes')!=expected_hashes:raise ReleaseError('Run is not bound to the actual freeze/readiness/artifacts')
        seeds=manifest['seeds']
        if any(seeds[k]>=2**63 for k in ('world_seed','layout_seed','noise_seed')) or seeds['policy_seed']>=2**31:raise ReleaseError('Seed exceeds its frozen role range')
    artifacts=verify_artifacts(freeze,freeze_path)
    from restart_calibration_loader import CalibrationInputError,load_restart_qualification
    try:restart_qualification=load_restart_qualification(freeze,freeze_path)
    except CalibrationInputError as exc:raise ReleaseError(str(exc)) from exc
    artifacts['restart_qualification']=restart_qualification.as_dict() if restart_qualification is not None else None
    return {'root':root,'release':release,'manifests':manifests,'freeze':freeze,'readiness':readiness,
            'freeze_path':freeze_path,'readiness_path':ready_path,'release_sha256':digest(root/'release.json'),
            'artifacts':artifacts}


def matched_public_episode_id(release_id,paired_block_id,architecture):
    """Opaque candidate identity shared by the matched persistence conditions.

    Only the release, paired block (case/replicate) and entrant participate.
    Conditions, protected run IDs and all seed roles are deliberately excluded.
    This deterministic identifier is not a cryptographic secrecy guarantee.
    """
    if any(not isinstance(value,str) or not value for value in (release_id,paired_block_id,architecture)):
        raise ReleaseError('Public episode identity requires nonempty string identities')
    if architecture not in protocol.ARCHITECTURES:raise ReleaseError('Unknown public episode entrant')
    identity=['candidate-episode-identity-v1',release_id,paired_block_id,architecture]
    return 'episode-'+hashlib.sha256(protocol.canonical(identity)).hexdigest()


@dataclass(frozen=True)
class VerifiedEvaluationContext:
    release_dir:Path
    manifest_json:str
    release_sha256:str
    manifest_sha256:str
    queue_job_id:str
    verified_at:str
    artifacts_json:str
    _authority:object=field(repr=False,compare=False,default=None)

    @property
    def manifest(self):return json.loads(self.manifest_json)
    @property
    def restart_qualification(self):
        if self._authority is not _AUTHORITY:raise ReleaseError('Evaluation context was not issued by the gated authorizer')
        return json.loads(self.artifacts_json).get('restart_qualification')
    @property
    def evidence_dir(self):return self.release_dir/'attempts'/self.manifest['run_id']/'evidence'
    @property
    def public_episode_id(self):
        m=self.manifest
        return matched_public_episode_id(m['release_id'],m['paired_block_id'],m['architecture'])
    def episode_kwargs(self):
        m=self.manifest
        return {'kind':m['architecture'],'n':m['parts'],'cap':m['cap_s'],'condition':m['condition'],
                'scenario':m['scenario'],'stage':'evaluation','run_id':m['run_id'],**m['seeds'],
                'evaluation_context':self}
    def assert_episode(self,**actual):
        if self._authority is not _AUTHORITY:raise ReleaseError('Evaluation context was not issued by the gated authorizer')
        expected=self.episode_kwargs();expected.pop('evaluation_context')
        if actual!=expected:raise ReleaseError('Supervisor arguments differ from the exact authorized manifest')
        if self.evidence_dir.exists():raise ReleaseError('Evaluation evidence directory is not fresh')
        # A path convention is not a candidate permission boundary. The frozen
        # sandbox/isolation readiness evidence must independently establish it.
        return self.evidence_dir


def authorize_evaluation(manifest,releaseDir):
    job=queued_job();verified=verify_release(releaseDir)
    actual=next((m for m in verified['manifests'] if m['run_id']==manifest.get('run_id')),None)
    if actual is None or actual!=manifest:raise ReleaseError('Supplied run differs from protected immutable manifest')
    ref=next(r for r in verified['release']['manifest_refs'] if r['run_id']==actual['run_id'])
    return VerifiedEvaluationContext(verified['root'],protocol.canonical(actual).decode(),verified['release_sha256'],
                                     ref['sha256'],job['id'],utc(),protocol.canonical(verified['artifacts']).decode(),_AUTHORITY)


def require_supervisor_hook():
    import experiment
    required={'evaluation_context','world_seed','layout_seed','policy_seed','noise_seed'}
    if getattr(experiment,'EVALUATION_AUTHORIZATION_VERSION',None)!=AUTHORIZATION_VERSION or not required<=set(inspect.signature(experiment.run_episode).parameters):
        raise ReleaseError('Supervisor has not implemented the explicit gated evaluation/four-seed hook')
    return experiment.run_episode


def map_reference(label,path,known_sha=None,locator=None):
    import record_attempt as records
    path=Path(path)
    return {'label':label,'uri':Path(os.path.relpath(path,records.MAP)).as_posix(),
            'sha256':known_sha or digest(path),'state':'available','access':'operator','locator':locator}


def register_attempt(context):
    """Only immutable revision/run registration; never a result-map write."""
    import record_attempt as records
    m=context.manifest;root=context.release_dir;release=load(root/'release.json')
    freeze_path=reference(release['freeze_manifest'],root);freeze=load(freeze_path)
    artifacts=json.loads(context.artifacts_json);aid='B01-C0' if m['architecture']=='baseline' else 'B01-'+m['architecture']
    rid=m['release_id']+'-'+m['architecture']+'-frozen'
    data,raw,errors=records.am.read_store(records.MAP)
    if errors:raise ReleaseError(str(errors))
    if not any(a['id']==aid for a in data['architecture']):raise ReleaseError('Architecture is not registered: '+aid)
    existing=next((r for r in data['revision'] if r['id']==rid),None)
    if existing and (existing.get('status')!='frozen' or existing.get('details',{}).get('freeze_sha256')!=m['freeze_sha256']):raise ReleaseError('Frozen revision identity already differs')
    bundle=Path(artifacts['code_bundle']);manifest_path=root/'runs'/(m['run_id']+'.json')
    if not existing:
        prior=[r for r in data['revision'] if r['architecture_id']==aid]
        records.append('revision',{**records.common(rid,['batch-01','evaluation','frozen']),
            'architecture_id':aid,'parent_revision_id':prior[-1]['id'] if prior else None,'status':'frozen',
            'title':m['architecture']+' frozen evaluation '+m['release_id'],
            'summary':'Exact artifact identities and ready release registered before any attempt of this revision.',
            'mechanism':'Frozen public-sensor candidate, shared physical controller and independent evaluator; exact executable behavior and model configuration are retained in the attachments.',
            'attachments':[map_reference('Immutable executable source bundle',bundle),map_reference('Frozen release',freeze_path,m['freeze_sha256'])],
            'details':{'freeze_sha256':m['freeze_sha256'],'release_id':m['release_id'],'model_identity':artifacts['model_identity']}})
    refs={role:map_reference('Frozen '+role+' artifact index',artifacts['index_paths'][role],m['artifact_hashes'][role+'_sha256']) for role in ('code','environment','model')}
    records.append('run',{**records.common(m['run_id'],['batch-01','evaluation',m['architecture']]),
        'revision_id':rid,'stage':'evaluation','condition_id':m['condition'],'protocol_id':m['protocol_id'],
        'scenario_id':m['scenario_id'],'paired_block_id':m['paired_block_id'],'replicate':m['replicate'],
        'started_at':None,'rerun_of_run_id':None,
        'condition_details':{'release_id':m['release_id'],'scheduled_index':m['scheduled_index'],'part_count':m['parts'],'cap_s':m['cap_s'],'queue_job_id':context.queue_job_id},
        'seeds':records.state(map_reference('Protected four-role seed manifest',manifest_path,context.manifest_sha256,'seeds')),
        'frozen_refs':{'code':records.state(refs['code']),'environment':records.state(refs['environment']),
            'models':records.none('Conventional baseline has no model') if m['architecture']=='baseline' else records.state(refs['model']),
            'protocol':records.state(map_reference('Frozen protocol source',HERE/'protocol.py',m['artifact_hashes']['protocol_sha256'])),
            'scenario':records.state(map_reference('Protected exact scenario manifest',manifest_path,context.manifest_sha256))},
        'evidence':[map_reference('Pre-run manifest',manifest_path,context.manifest_sha256)]})
    return rid


def integrity_breach(terminal):
    result=terminal.get('result',{})
    flags=('integrity_breach','source_integrity_breach','readiness_integrity_breach','evidence_integrity_breach',
           'evaluator_integrity_breach','oracle_exposure')
    classes={'source_hash_mismatch','readiness_failure','evidence_integrity_failure','evaluator_corruption','oracle_exposure','integrity_failure'}
    return any(obj.get(key) is True for obj in (terminal,result) for key in flags) or result.get('failure_class') in classes


def validate_review(review,verified):
    """A review changes permitted continuation, never original measured results."""
    root=verified['root'];by_id={m['run_id']:m for m in verified['manifests']}
    safe_id(review.get('review_id'))
    if review.get('schema_version')!='robot-continuation-review-1.0' or review.get('release_sha256')!=verified['release_sha256']:
        raise ReleaseError('Continuation review is not bound to this exact release')
    if review.get('classification') not in ('isolated_host_timing','isolated_queue_incident','isolated_runtime_failure'):
        raise ReleaseError('Systematic/unknown-integrity problems cannot authorize isolated-incident continuation')
    if not all(isinstance(review.get(key),str) and review[key].strip() for key in ('reviewer','rationale','recorded_at')):
        raise ReleaseError('Continuation review requires reviewer, rationale and timestamp')
    if (review.get('continuation_scope')!='all_original_unattempted' or review.get('retains_original_results') is not True
        or review.get('exclude_affected_blocks_from_primary') is not True or review.get('no_source_readiness_or_evaluator_integrity_breach') is not True
        or type(review.get('automatic_retries')) is not int or review['automatic_retries']!=0):
        raise ReleaseError('Review cannot change attempts, retry policy, original results or integrity gates')
    refs=review.get('terminal_refs');seen=set();blocks=set()
    if not isinstance(refs,list) or not refs:raise ReleaseError('Review requires exact terminal evidence references')
    for ref in refs:
        run_id=ref.get('run_id')
        if run_id not in by_id or run_id in seen:raise ReleaseError('Review names duplicate or unplanned attempt')
        path=reference(ref,root)
        if path!=root/'attempts'/run_id/'terminal.json':raise ReleaseError('Review must reference the original terminal attempt')
        terminal=load(path)
        if terminal.get('run_id')!=run_id or terminal.get('release_sha256')!=verified['release_sha256']:raise ReleaseError('Review terminal identity mismatch')
        if terminal.get('result',{}).get('validity')=='valid':raise ReleaseError('A valid attempt does not require an invalidity continuation review')
        if integrity_breach(terminal):raise IntegrityError('An actual integrity/oracle/evaluator breach cannot be waived by continuation review')
        if terminal.get('post_run_integrity',{}).get('passed') is not True:raise ReleaseError('Review requires recorded passing post-run integrity checks')
        batch=root/'batches'/safe_id(terminal.get('queue_job_id'))
        if not (batch/'finalized.json').is_file():raise ReleaseError('Review requires prior official queue verification and result finalization')
        finished=load(batch/'finished.json')
        frozen_ref=next((r for r in finished.get('terminal_refs',[]) if r.get('run_id')==run_id),None)
        if frozen_ref is None or frozen_ref.get('sha256')!=ref['sha256']:raise ReleaseError('Reviewed terminal differs from original completed batch hash')
        seen.add(run_id);blocks.add(by_id[run_id]['paired_block_id'])
    if review.get('excluded_paired_block_ids')!=sorted(blocks):raise ReleaseError('Review must preserve exclusion of each whole affected paired block')
    evidence=review.get('evidence_refs')
    if not isinstance(evidence,list) or not evidence:raise ReleaseError('Review requires supporting evidence references')
    for ref in evidence:
        path=Path(ref.get('path',''));path=path if path.is_absolute() else root/path
        if not path.is_file() or path.stat().st_size>4*1024*1024:raise ReleaseError('Review evidence must be a small existing summary/reference (at most 4 MiB each)')
        reference(ref,root)
    return seen,blocks


def continuation_state(verified):
    root=verified['root'];directory=root/'reviews';covered={};blocks=set();refs=[]
    for path in sorted(directory.glob('*.json')) if directory.exists() else []:
        review=load(path)
        if path.stem!=review.get('review_id'):raise ReleaseError('Review filename differs from immutable identity')
        attempts,excluded=validate_review(review,verified)
        for run_id in attempts:
            if run_id in covered:raise ReleaseError('Conflicting/duplicate continuation reviews cover an attempt')
            covered[run_id]=review['review_id']
        blocks.update(excluded);refs.append({'path':str(path.relative_to(root)),'sha256':digest(path),'review_id':review['review_id']})
    return {'covered_attempts':covered,'excluded_paired_block_ids':sorted(blocks),'review_refs':refs,
            'continuation_scope':'all_original_unattempted','original_manifest_count':len(verified['manifests']),
            'interpretation':'Affected whole blocks excluded from primary inference; remaining planned members may run for descriptive evidence; no retries'}


def record_review(release_dir,value):
    """Small explicit operator record; heavy artifact validation remains in run."""
    root=Path(release_dir).resolve();release=load(root/'release.json')
    verified={'root':root,'release':release,'manifests':protocol.load_release(root),'release_sha256':digest(root/'release.json')}
    review={**value,'schema_version':'robot-continuation-review-1.0','recorded_at':utc(),'release_sha256':verified['release_sha256']}
    attempts,blocks=validate_review(review,verified);existing=continuation_state(verified)
    if set(existing['covered_attempts'])&attempts:raise ReleaseError('An attempt already has an immutable continuation review')
    path=root/'reviews'/(safe_id(review['review_id'])+'.json');write_once(path,review)
    return {'review_id':review['review_id'],'path':str(path),'sha256':digest(path),'excluded_paired_block_ids':sorted(blocks),
            'readiness_changed':False,'runs_launched':0,'automatic_retries':0}


def select_runs(verified,run_ids,limit):
    if type(limit) is not int or not 1<=limit<=16:raise ReleaseError('Batch limit must be 1 through 16; default is 4')
    root=verified['root'];attempts=root/'attempts'
    batches=root/'batches'
    if batches.exists():
        for batch in batches.iterdir():
            if batch.is_dir() and not (batch/'finalized.json').is_file():
                raise ReleaseError('Prior batch has not been finalized after official queue verification: '+batch.name)
    continuation=continuation_state(verified)
    if attempts.exists():
        for path in attempts.iterdir():
            if path.is_dir() and not (path/'terminal.json').is_file():raise ReleaseError('Interrupted/unresolved attempt prevents automatic continuation: '+path.name)
            if not path.is_dir():continue
            terminal=load(path/'terminal.json')
            if integrity_breach(terminal):raise IntegrityError('Prior source/readiness/evaluator integrity breach blocks this release: '+path.name)
            if terminal.get('result',{}).get('validity')!='valid' and path.name not in continuation['covered_attempts']:
                raise ReleaseError('Prior invalid/unknown attempt requires an explicit immutable continuation review: '+path.name)
    scheduled=sorted(verified['manifests'],key=lambda r:r['scheduled_index'])
    if run_ids:
        if len(set(run_ids))!=len(run_ids) or len(run_ids)>limit:raise ReleaseError('Explicit run IDs must be unique and fit this bounded batch')
        wanted=set(run_ids)
        if not wanted<={r['run_id'] for r in scheduled}:raise ReleaseError('Unknown explicit run ID')
        selected=[r for r in scheduled if r['run_id'] in wanted]
        if any((attempts/r['run_id']).exists() for r in selected):raise ReleaseError('Attempt already exists; policy retries are forbidden')
    else:selected=[r for r in scheduled if not (attempts/r['run_id']).exists()][:limit]
    return selected


def execute_episode(context,episode):
    kwargs=context.episode_kwargs();context.assert_episode(**{k:v for k,v in kwargs.items() if k!='evaluation_context'})
    if context.manifest['architecture']=='baseline':return episode(**kwargs)
    from model_runtime import LocalModel,ModelConfig
    config=ModelConfig(**json.loads(context.artifacts_json)['model_config'])
    with LocalModel(config,log_path=context.evidence_dir.parent/'model-server.log') as model:
        return episode(model=model,**kwargs)


def failure_result(run_id,exc,phase):
    return {'run_id':run_id,'stage':'evaluation','execution_status':'aborted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
            'validity':'invalid','invalidity_class':'infrastructure','infrastructure_invalid':True,
            'validity_reason':'Evaluation driver failure in '+phase,'outcome':'unknown','ended_at':utc(),
            'termination_reason':'infrastructure_failure','error':type(exc).__name__+': '+str(exc),
            'wall_duration_s':None,'completion_time_s':None,'independent_outcome':None,
            'integrity_breach':isinstance(exc,IntegrityError)}


def run_batch(release_dir,*,limit=4,run_ids=None):
    job=queued_job();verified=verify_release(release_dir);episode=require_supervisor_hook()
    selected=select_runs(verified,run_ids,limit);root=verified['root'];job_id=safe_id(job['id'])
    continuation=continuation_state(verified)
    batch=root/'batches'/job_id;batch.mkdir(parents=True,exist_ok=False)
    write_once(batch/'planned.json',{'schema_version':AUTHORIZATION_VERSION,'queue_job_id':job_id,
        'created_at':utc(),'release_sha256':verified['release_sha256'],'limit':limit,
        'selected_run_ids':[m['run_id'] for m in selected],'schedule_order_preserved':True,
        'official_queue_completion_verified':False,'continuation':continuation})
    completed=[];terminal_refs=[];stop_reason=None
    for manifest in selected:
        # Reverify the complete release and actual bytes immediately before each
        # run; changed readiness/source causes a hard stop before registration.
        context=authorize_evaluation(manifest,root)
        if context.queue_job_id!=job_id:raise ReleaseError('Queue ownership changed')
        attempt=root/'attempts'/manifest['run_id'];attempt.mkdir(parents=True,exist_ok=False)
        write_once(attempt/'claimed.json',{'run_id':manifest['run_id'],'queue_job_id':job_id,'claimed_at':utc(),
            'manifest_sha256':context.manifest_sha256,'release_sha256':context.release_sha256})
        phase='pre_registration'
        try:
            revision=register_attempt(context)
            write_once(attempt/'registered.json',{'run_id':manifest['run_id'],'revision_id':revision,'registered_at':utc()})
            phase='episode_start'
            write_once(attempt/'started.json',{'run_id':manifest['run_id'],'started_at':utc(),'queue_job_id':job_id})
            phase='episode_execution';result=execute_episode(context,episode)
            if not isinstance(result,dict) or result.get('run_id')!=manifest['run_id'] or result.get('stage')!='evaluation' or result.get('execution_status') not in protocol.TERMINAL:
                raise IntegrityError('Supervisor did not return this run\'s explicit terminal evaluation result')
            source=context.evidence_dir/'result.json'
            if not source.is_file() or load(source)!=result:raise IntegrityError('Returned result lacks identical protected terminal evidence')
        except BaseException as exc:
            result=failure_result(manifest['run_id'],exc,phase);source=None
        try:
            after=verify_release(root)
            if after['release_sha256']!=context.release_sha256:raise IntegrityError('Release changed during the episode')
            if continuation_state(after)!=continuation:raise IntegrityError('Continuation review evidence changed during the episode')
            post_integrity={'passed':True,'verified_at':utc(),'release_sha256':after['release_sha256'],
                            'artifact_hashes':manifest['artifact_hashes'],'continuation_review_refs':continuation['review_refs']}
        except BaseException as exc:
            post_integrity={'passed':False,'verified_at':utc(),'error':type(exc).__name__+': '+str(exc)}
        terminal={'run_id':manifest['run_id'],'queue_job_id':job_id,'recorded_at':utc(),
                  'manifest_sha256':context.manifest_sha256,'release_sha256':context.release_sha256,
                  'result':result,'supervisor_result_ref':None if source is None else {'path':str(source),'sha256':digest(source)},
                  'official_queue_completion_verified':False,'post_run_integrity':post_integrity,
                  'integrity_breach':not post_integrity['passed'] or integrity_breach({'result':result}),
                  'continuation':continuation,
                  'excluded_from_primary_by_prior_review':manifest['paired_block_id'] in continuation['excluded_paired_block_ids']}
        write_once(attempt/'terminal.json',terminal);completed.append(manifest['run_id'])
        terminal_refs.append({'run_id':manifest['run_id'],'path':str((attempt/'terminal.json').relative_to(root)),
                              'sha256':digest(attempt/'terminal.json')})
        if terminal['integrity_breach'] or result.get('infrastructure_invalid') is True or result.get('validity')!='valid':
            stop_reason='Invalid attempt retained; stop batch for explicit infrastructure/readiness review';break
    write_once(batch/'finished.json',{'queue_job_id':job_id,'finished_at':utc(),'terminal_run_ids':completed,'terminal_refs':terminal_refs,
                                    'unlaunched_selected_run_ids':[m['run_id'] for m in selected if m['run_id'] not in completed],
                                    'stop_reason':stop_reason,'official_queue_completion_verified':False})
    return {'queue_job_id':job_id,'terminal_attempts':len(completed),'stop_reason':stop_reason,
            'map_results_applied':False,'next_step':'After official status is succeeded/exit0, explicitly finalize this queue job'}


def verify_queue_receipt(job_id,status_path):
    receipt=load(status_path)
    if receipt.get('id')!=job_id or receipt.get('state')!='succeeded' or receipt.get('exit_status')!=0:raise ReleaseError('Official queue status receipt does not establish succeeded with exit_status 0')
    actual=next((j for j in load(QUEUE_STATE).get('jobs',[]) if j.get('id')==job_id),None)
    if actual is None or any(actual.get(k)!=receipt.get(k) for k in ('id','state','exit_status','child_pid','started_at','ended_at','argv','cwd')):raise ReleaseError('Supplied official status differs from installed queue record')
    return receipt


def append_map_result(terminal,path,receipt_ref):
    import record_attempt as records
    result=terminal['result'];run_id=terminal['run_id'];evidence=map_reference('Protected evaluation terminal attempt',path)
    data,raw,errors=records.am.read_store(records.MAP)
    if errors:raise ReleaseError(str(errors))
    if not any(r['id']==run_id for r in data['run']):raise ReleaseError('Attempt was not pre-registered; cannot fabricate evaluation registration afterwards')
    existing=next((r for r in data['result'] if r['id']==run_id+'-result'),None)
    if existing:
        if existing.get('details',{}).get('terminal_sha256')!=evidence['sha256'] or existing.get('details',{}).get('queue_job_id')!=terminal['queue_job_id']:raise ReleaseError('Existing immutable result differs')
        return False  # Resumable finalization, never another policy execution.
    metrics=[]
    for key,unit in (('completion_time_s','s'),('wall_duration_s','s'),('model_calls','count'),('total_tokens','count'),('false_done_assertions','count')):
        value=result.get(key)
        metrics.append({'name':key,'value':value,'unit':unit,'denominator':None,'denominator_description':'One frozen evaluation attempt',
            'missing_reason':'Not measured or task did not complete; inspect protected evidence' if value is None else None,'evidence':[evidence] if value is not None else []})
    breached=integrity_breach(terminal)
    records.append('result',{**records.common(run_id+'-result',['batch-01','evaluation']),'run_id':run_id,'supersedes_result_id':None,
        'execution_status':result['execution_status'],'validity':'invalid' if breached else result.get('validity','unknown'),
        'validity_reason':'Protected driver integrity check failed; original measured result retained in terminal evidence' if breached else result.get('validity_reason','Validity was not established'),'outcome':result.get('outcome','unknown'),
        'ended_at':result['ended_at'],'termination_reason':result['termination_reason'],'metrics':metrics,
        'evidence':[evidence,receipt_ref],'details':{'queue_job_id':terminal['queue_job_id'],'official_queue_status':'succeeded','official_queue_exit_status':0,
            'terminal_sha256':evidence['sha256'],'failed_attempt_retained':result.get('outcome')!='success',
            'infrastructure_invalid':True if breached else result.get('infrastructure_invalid'),'limits':result.get('limits',[]),
            'post_run_integrity':terminal.get('post_run_integrity'),'continuation':terminal.get('continuation'),
            'excluded_from_primary_by_prior_review':terminal.get('excluded_from_primary_by_prior_review',False)}})
    return True


def finalize(release_dir,verified_queue_job_id,status_path):
    """Small evidence/map operation only; does not rehash model assets or run probes."""
    root=Path(release_dir).resolve();job_id=safe_id(verified_queue_job_id)
    receipt=verify_queue_receipt(job_id,status_path);batch=root/'batches'/job_id
    planned=load(batch/'planned.json');finished=load(batch/'finished.json')
    if planned.get('queue_job_id')!=job_id or finished.get('queue_job_id')!=job_id or digest(root/'release.json')!=planned.get('release_sha256'):raise ReleaseError('Batch does not match this queue job and release')
    done=finished.get('terminal_run_ids')
    if not isinstance(done,list) or len(done)!=len(set(done)) or not set(done)<=set(planned['selected_run_ids']):raise ReleaseError('Malformed terminal batch accounting')
    pending=finished.get('unlaunched_selected_run_ids')
    if not isinstance(pending,list) or len(pending)!=len(set(pending)) or set(pending)&set(done) or set(done)|set(pending)!=set(planned['selected_run_ids']):raise ReleaseError('Batch does not explicitly account for every selected run')
    terminal_refs=finished.get('terminal_refs')
    if not isinstance(terminal_refs,list) or [r.get('run_id') for r in terminal_refs]!=done:raise ReleaseError('Batch has no exact terminal hashes')
    checked=[]
    for run_id,ref in zip(done,terminal_refs):
        path=root/'attempts'/safe_id(run_id)/'terminal.json'
        if reference(ref,root)!=path:raise ReleaseError('Batch terminal reference names another path')
        terminal=load(path)
        if terminal.get('queue_job_id')!=job_id or terminal.get('run_id')!=run_id or terminal.get('release_sha256')!=planned['release_sha256']:raise ReleaseError('Terminal attempt is not bound to this batch')
        source=terminal.get('supervisor_result_ref')
        if source:
            actual=reference(source,path.parent)
            if load(actual)!=terminal['result']:raise ReleaseError('Protected terminal evidence changed before finalization')
        checked.append((path,terminal))
    receipt_copy=batch/'official-queue-status.json'
    if receipt_copy.exists():
        if load(receipt_copy)!=receipt:raise ReleaseError('Official status receipt already differs')
    else:write_once(receipt_copy,receipt)
    receipt_ref=map_reference('Verified official queue completion',receipt_copy)
    applied=[]
    for path,terminal in checked:
        append_map_result(terminal,path,receipt_ref);applied.append(terminal['run_id'])
    import record_attempt as records
    if records.am.main(['build'])!=0 or records.am.main(['validate','--output','validation.json'])!=0:
        raise ReleaseError('Map build/validation failed; immutable appended results remain, finalization marker withheld')
    marker=batch/'finalized.json'
    if not marker.exists():write_once(marker,{'queue_job_id':job_id,'finalized_at':utc(),'run_ids':applied,'official_queue_receipt_sha256':digest(receipt_copy)})
    return {'queue_job_id':job_id,'map_result_run_ids':applied,'official_queue_completion_verified':True}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');run.add_argument('--release-dir',required=True);run.add_argument('--limit',type=int,default=4);run.add_argument('--run-id',action='append',dest='run_ids')
    finish=sub.add_parser('finalize');finish.add_argument('--release-dir',required=True);finish.add_argument('--verified-queue-job-id',required=True);finish.add_argument('--queue-status',required=True)
    review=sub.add_parser('review',help='Record explicit isolated-incident continuation; does not launch or change readiness')
    review.add_argument('--release-dir',required=True);review.add_argument('--input',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='run':value=run_batch(args.release_dir,limit=args.limit,run_ids=args.run_ids)
        elif args.command=='review':value=record_review(args.release_dir,load(args.input))
        else:value=finalize(args.release_dir,args.verified_queue_job_id,args.queue_status)
    except (ReleaseError,protocol.ProtocolError,OSError,ValueError,TypeError,KeyError) as exc:parser.exit(2,'Refused: '+str(exc)+'\n')
    print(json.dumps(value,indent=2,allow_nan=False));return 0


if __name__=='__main__':raise SystemExit(main())
