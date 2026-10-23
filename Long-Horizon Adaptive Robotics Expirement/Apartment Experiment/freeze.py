"""Copy exact apparatus inputs and prepare two pristine, unconsumed official starts."""
import argparse
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from common import HERE,REPO,DEFAULT_ROOT,save,read,sha,inventory,canonical
from run import source_identity,prepare
from schedule import build,validate

def copy_sources(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    integration=Path('Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001')
    apartment=Path('Long-Horizon Adaptive Robotics Expirement/Apartment Experiment')
    for key,digest in source_identity().items():
        if key.startswith('apartment/'):
            relative=apartment/key.removeprefix('apartment/');source=HERE/key.removeprefix('apartment/')
        elif key.startswith('inherited/'):
            relative=integration/key.removeprefix('inherited/');source=REPO/relative
        elif key.startswith('repository/'):
            relative=Path(key.removeprefix('repository/'));source=REPO/relative
        else:relative=Path(key.removeprefix('template/'));source=REPO/relative
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if sha(target)!=digest:raise ValueError('Frozen copy differs: '+key)
    for name in ('commissioning.json','commissioning-audit.json','calibration.json','audit-inputs.json','README.md','COMPARISON.md','EVIDENCE.md','REPAIR.md','evidence-index.json'):
        if (HERE/name).is_file():shutil.copy2(HERE/name,destination/apartment/name)
    license=REPO/integration/'campaign-005/vendor/LICENSE'
    if license.is_file():shutil.copy2(license,destination/integration/'campaign-005/vendor/LICENSE')
    save(destination/'source-manifest.json',inventory(destination))
    return destination/apartment

def create(root):
    root=Path(root).resolve()
    if root.drive.upper()!='D:' or root.exists():raise ValueError('A new D: comparison root is required')
    certificate=read(HERE/'commissioning.json')
    from environment import identity
    if certificate['passed'] is not True or certificate['source_identity']!=source_identity() or certificate['environment']!=identity():raise ValueError('Current commissioning certificate required')
    root.mkdir(parents=True)
    frozen=copy_sources(root/'frozen_repository')
    schedule=build(secrets.randbits(128));validate(schedule)
    save(root/'hidden-schedule.json',schedule)
    for condition in ('baseline','maps'):prepare(root/condition,condition,'official',schedule,certificate['config'])
    if sha(root/'baseline/schedule.json')!=sha(root/'maps/schedule.json'):raise ValueError('Matched schedules differ')
    evidence=dict(passed=True,official_launched=False,official_assignments_consumed=0,root=str(root),frozen_apparatus=str(frozen),
        schedule_sha256=sha(root/'hidden-schedule.json'),source_manifest_sha256=sha(root/'frozen_repository/source-manifest.json'),
        certificate_sha256=sha(HERE/'commissioning.json'),config=certificate['config'],
        initial={c:read(root/c/'initial-filesystem.json') for c in ('baseline','maps')})
    save(root/'prepared.json',evidence)
    print(canonical({k:v for k,v in evidence.items() if k!='initial'}).decode())
    return evidence

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();create(a.root)
