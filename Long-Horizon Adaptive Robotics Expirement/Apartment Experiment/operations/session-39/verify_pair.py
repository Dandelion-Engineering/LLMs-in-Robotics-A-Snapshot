"""Independent prelaunch inspection of both pristine conditions; no model."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

HERE=Path(__file__).resolve().parent
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
OPS=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-39'
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,indent=2);f.write('\n')
def inventory(root):return {p.relative_to(root).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(root.rglob('*')) if p.is_file()}
def main():
    out=HERE/'output';out.mkdir();result=dict(passed=False,checks={})
    try:
        manifest=read(HERE/'manifest.json')
        for name,row in manifest['files'].items():assert sha(HERE/name)==row['sha256'],name
        prepared=read(PAIR/'prepared.json');frozen=PAIR/'frozen_repository';code=frozen/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
        rows=inventory(frozen);rows.pop('source-manifest.json')
        assert rows==read(frozen/'source-manifest.json') and sha(frozen/'source-manifest.json')==prepared['source_manifest_sha256']
        certificate=read(code/'commissioning.json');assert certificate['passed'] and sha(code/'commissioning.json')==prepared['certificate_sha256']
        for name,key in certificate['protocol_sha256'].items():assert sha(code/name)==key,name
        result['checks']['certified_frozen_files']=True
        schedule=sha(PAIR/'hidden-schedule.json')
        for previous in ['apartment-v1','apartment-v2','apartment-v3']:
            assert read(PAIR.parent/previous/'prepared.json')['schedule_sha256']==schedule
        for condition in ('baseline','maps'):
            root=PAIR/condition;run=read(root/'run.json');initial=read(root/'initial-filesystem.json')
            assert not run['launched'] and run['stage']=='official' and run['condition']==condition
            assert run['source_identity']==certificate['source_identity']
            assert inventory(root/'filesystem')==initial==prepared['initial'][condition]==read(PAIR.parent/'apartment-v2'/condition/'initial-filesystem.json')
            assert len(initial)==(15 if condition=='baseline' else 19)
            assert read(root/'config.json')==certificate['config'] and sha(root/'config.json')==run['config_sha256']
            assert sha(root/'schedule.json')==schedule==run['schedule_sha256']
            assert not any((root/n).exists() for n in ('events.jsonl','sessions','running.lock','completed.json','latest-checkpoint.json','filesystem-namespace.json'))
            lineage=read(PAIR/(condition+'-lineage.json'));assert not lineage['history'] and Path(lineage['active_root'])==root
        result['checks']['both_pristine_original_templates_and_schedule']=True
        analysis=read(PAIR/'analysis-freeze.json')
        assert analysis['prepared_sha256']==sha(PAIR/'prepared.json') and analysis['frozen_before_official_launch']
        assert sha(Path(analysis['analysis_path']))==analysis['analysis_sha256']
        result['checks']['prospective_analysis_bound']=True
        response=subprocess.check_output([sys.executable,'-X','utf8','-B','-c',
            'from run import verify_run;import sys;verify_run(sys.argv[1],True);print("verified")',str(PAIR/'baseline')],cwd=code,text=True,encoding='utf-8')
        assert response.strip()=='verified';result['checks']['current_environment_and_source_admitted']=True
        jobs=[]
        for state in ('queued','running'):
            jobs+=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'list','--state',state],text=True,encoding='utf-8'))
        duplicate=[j for j in jobs if any('official' in str(x).lower() and 'apartment' in str(x).lower() for x in j['argv'])]
        assert not duplicate,duplicate
        runtime_probe="""import os,pathlib,json
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  args=(p/'cmdline').read_bytes().split(b'\\0')
  if any(b'apartment-' in a and b'/var/tmp/robot-codex-session10/' in a for a in args):processes.append(int(p.name))
 except (FileNotFoundError,PermissionError):pass
mounts=[r.split()[4] for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if '/robot-codex-session10/apartment-' in r]
print(json.dumps({'processes':processes,'mounts':mounts}))
"""
        runtime=json.loads(subprocess.check_output(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',runtime_probe],text=True,encoding='utf-8'))
        assert not runtime['processes'] and not runtime['mounts'],runtime
        result['runtime']=runtime;result['checks']['no_duplicate_official_queue_or_native_runtime']=True
        result['free_disk_gib']=shutil.disk_usage(PAIR).free/1024**3
        assert result['free_disk_gib']>=50;result['checks']['storage_margin']=True
        result.update(passed=True,pair=str(PAIR),official_starts=0,prepared_sha256=sha(PAIR/'prepared.json'))
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps(result));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
