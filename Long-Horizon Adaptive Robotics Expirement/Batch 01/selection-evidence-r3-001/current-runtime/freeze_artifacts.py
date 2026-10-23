"""Prepare exact artifact indexes inside a queued job, without declaring readiness.

CLI: freeze_artifacts.py --output-dir <new operator directory>
Optional --probe-spec JSON supplies {probes:[{name,argv,timeout_s}]} in place of
the default read-only Windows GPU / Ubuntu-24.04 Python / bubblewrap identities.
Optional --model-config JSON explicitly supplies ModelConfig settings. Current
model_setup constants and asset manifest are used; no model family is hardcoded.

The helper hashes actual Runtime Python, Architecture Map code, requirements,
pinned Panda files, current model weights/runtime/license files, and executes
bounded read-only identity probes. It creates code/environment/model indexes,
a source ZIP, and prepared-artifacts.json. It never downloads, starts inference,
changes readiness, creates a freeze manifest, or generates held-out seeds.
The helper refuses use outside its own installed queue child. A failed partial
output directory is retained and cannot be overwritten on retry. After the
official queue status succeeds/exit0, an operator may use these references in a
separately reviewed freeze. Artifact identity is not evidence of scored readiness.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

import release_runner as runner

HERE=Path(__file__).resolve().parent


def file_ref(path,expected=None):
    path=Path(path).resolve()
    if not path.is_file():raise runner.ReleaseError('Artifact file is missing: '+str(path))
    sha=runner.digest(path)
    if expected is not None and sha!=expected:raise runner.IntegrityError('Pinned artifact hash differs: '+str(path))
    return {'path':str(path),'sha256':sha,'bytes':path.stat().st_size}


def asset_refs(root,manifest_path,list_fields):
    root=Path(root).resolve();manifest=runner.load(manifest_path);refs=[file_ref(manifest_path)];seen={Path(manifest_path).resolve()}
    for field in list_fields:
        entries=manifest.get(field)
        if not isinstance(entries,list) or not entries:raise runner.ReleaseError('Asset manifest lacks '+field)
        for entry in entries:
            relative=entry.get('path',entry.get('name'))
            if not isinstance(relative,str) or not runner.protocol.HASH_RE.fullmatch(str(entry.get('sha256',''))):raise runner.ReleaseError('Malformed pinned asset reference')
            path=(root/relative).resolve()
            if not path.is_relative_to(root):raise runner.IntegrityError('Asset path escapes its pinned directory')
            if path not in seen:refs.append(file_ref(path,entry['sha256']));seen.add(path)
    return refs


def default_probes():
    wsl=shutil.which('wsl.exe');gpu=shutil.which('nvidia-smi')
    if not wsl or not gpu:raise runner.ReleaseError('Default identity probes require installed wsl.exe and nvidia-smi')
    base=[wsl,'--distribution','Ubuntu-24.04','--exec']
    script="import hashlib,json,pathlib,platform,sys; print(json.dumps({'version':sys.version,'implementation':platform.python_implementation(),'executable_sha256':hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest()},sort_keys=True))"
    return [
        {'name':'candidate_python','argv':base+['/usr/bin/python3','-I','-c',script],'timeout_s':20},
        {'name':'candidate_isolation','argv':base+['/usr/bin/bwrap','--version'],'timeout_s':20},
        {'name':'gpu_driver','argv':[gpu,'--query-gpu=name,driver_version,memory.total','--format=csv,noheader,nounits'],'timeout_s':15},
    ]


def capture_probe(spec):
    name=spec.get('name');argv=spec.get('argv');timeout=spec.get('timeout_s',15)
    if not isinstance(name,str) or not name or not isinstance(argv,list) or not argv or not all(isinstance(v,str) and v and '\x00' not in v for v in argv):raise runner.ReleaseError('Malformed identity probe')
    if type(timeout) not in (int,float) or not 0<timeout<=30:raise runner.ReleaseError('Probe timeout must be positive and at most 30 seconds')
    reply=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        shell=False,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if reply.returncode!=0:raise runner.ReleaseError('Identity probe failed: '+name)
    if len(reply.stdout)>2*1024*1024 or len(reply.stderr)>2*1024*1024:raise runner.ReleaseError('Identity probe output exceeds 2 MiB bound')
    return {'name':name,'argv':argv,'timeout_s':timeout,'stdout_sha256':hashlib.sha256(reply.stdout).hexdigest(),
            'stdout_bytes':len(reply.stdout),'interpretation':'Read-only runtime identity, not adversarial isolation or physical readiness evidence'}


def prepare(output_dir,*,probe_spec=None,model_config=None,dependencies=None):
    job=runner.queued_job(Path(__file__).resolve())  # Before hashing, probes, or output mutation.
    output=Path(output_dir).resolve()
    if output.exists():raise runner.ReleaseError('Artifact output directory already exists; retain prior attempt and choose a new one')
    if any(part.casefold()=='candidate_state' for part in output.parts):raise runner.ReleaseError('Artifacts cannot be prepared in candidate state')
    if not output.parent.is_dir():raise runner.ReleaseError('Artifact output parent must already exist')
    specs=default_probes() if probe_spec is None else runner.load(probe_spec).get('probes')
    if not isinstance(specs,list) or not 3<=len(specs)<=16:raise runner.ReleaseError('Provide 3 through 16 bounded identity probes')
    names=[p.get('name') for p in specs if isinstance(p,dict)]
    if len(names)!=len(specs) or len(names)!=len(set(names)) or not {'candidate_python','candidate_isolation','gpu_driver'}<=set(names):raise runner.ReleaseError('Required distinct environment probe names are missing')
    from model_runtime import LocalModel,ModelConfig
    from model_setup import VENDOR,MODEL_FILE,MODEL_SHA256
    config=ModelConfig(**(runner.load(model_config) if model_config else {}))
    output.mkdir()
    runner.write_once(output/'started.json',{'queue_job_id':job['id'],'started_at':runner.utc(),'purpose':'artifact identity preparation only','creates_readiness':False,'creates_seeds':False})
    source_files=sorted(HERE.glob('*.py'))
    if not source_files:raise runner.ReleaseError('Runtime source directory is empty')
    code_refs=[file_ref(path) for path in source_files]
    map_source=HERE.parent/'Architecture Map'/'map.py'
    code_refs.append(file_ref(map_source))
    bundle=output/'runtime.zip'
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files:archive.write(path,path.name)
    code={'schema_version':'robot-artifact-index-1.0','role':'code','runtime_root':str(HERE.resolve()),'files':code_refs,
          'bundle':file_ref(bundle),'includes':'Every current Runtime Python source plus the map registrar dependency'}
    panda=HERE/'vendor'/'panda'
    environment_refs=[file_ref(HERE.parents[1]/'requirements.txt'),*asset_refs(panda,panda/'manifest.json',('files',))]
    names=sorted(set(dependencies or [])|{'numpy','mujoco'})
    if len(names)>32:raise runner.ReleaseError('At most 32 named dependency identities may be captured')
    environment={'schema_version':'robot-artifact-index-1.0','role':'environment','files':environment_refs,
                 'runtime_identity':runner.environment_identity(names),'probes':[capture_probe(spec) for spec in specs],
                 'limitations':['Identity checks are not isolation or scored-readiness proof','Native environment/kernel behavior still requires frozen readiness evidence']}
    manifest_path=VENDOR/'asset_manifest.json'
    model_refs=asset_refs(VENDOR,manifest_path,('installed_files','license_files'))
    weight=(VENDOR/MODEL_FILE).resolve();weight_ref=file_ref(weight,MODEL_SHA256)
    if all(Path(ref['path'])!=weight for ref in model_refs):model_refs.append(weight_ref)
    manifest=runner.load(manifest_path)
    if manifest.get('model_file')!=MODEL_FILE or manifest.get('model_sha256')!=MODEL_SHA256:raise runner.IntegrityError('Current model constants and installed asset manifest differ')
    model={'schema_version':'robot-artifact-index-1.0','role':'model','files':model_refs,'asset_manifest':file_ref(manifest_path),
           'config':asdict(config),'identity':LocalModel(config).identity,
           'source_archive_identity':'Original download/archive identities remain in the pinned asset manifest; executable and weight bytes are reverified'}
    indexes={}
    for role,value in (('code',code),('environment',environment),('model',model)):
        path=output/(role+'.json');runner.write_once(path,value);indexes[role]=file_ref(path)
    candidate={'artifacts':indexes,**{role+'_sha256':ref['sha256'] for role,ref in indexes.items()}}
    # Reverify after capture to detect edits during ZIP/probe/hash collection.
    runner.verify_artifacts(candidate,output/'not-a-freeze.json')
    prepared={'schema_version':'robot-prepared-artifacts-1.0','queue_job_id':job['id'],'prepared_at':runner.utc(),**candidate,
              'protocol_sha256':file_ref(HERE/'protocol.py')['sha256'],'scored_ready':False,
              'freeze_manifest_created':False,'readiness_created':False,'held_out_seeds_created':False,
              'official_queue_completion_verified':False,
              'scope':'Identity indexes only; use after official queue succeeded/exit0 in a separately reviewed freeze/readiness workflow'}
    runner.write_once(output/'prepared-artifacts.json',prepared)
    return {'output_dir':str(output),'prepared_artifacts':file_ref(output/'prepared-artifacts.json'),
            'queue_job_id':job['id'],'scored_ready':False,'freeze_manifest_created':False,'held_out_seeds_created':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',required=True);parser.add_argument('--probe-spec');parser.add_argument('--model-config');parser.add_argument('--dependency',action='append',default=[])
    args=parser.parse_args(argv)
    try:value=prepare(args.output_dir,probe_spec=args.probe_spec,model_config=args.model_config,dependencies=args.dependency)
    except (runner.ReleaseError,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:parser.exit(2,'Refused: '+str(exc)+'\n')
    print(json.dumps(value,indent=2,allow_nan=False));return 0


if __name__=='__main__':raise SystemExit(main())
