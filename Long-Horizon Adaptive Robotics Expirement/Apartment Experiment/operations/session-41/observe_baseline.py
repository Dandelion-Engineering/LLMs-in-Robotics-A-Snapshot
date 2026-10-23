"""One observational baseline check. No robot commands or recovery mutations."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

CODE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(CODE))
from common import REPO,canonical,inventory,read,save,sha


def observe(pair,job,out,label):
    pair=pair.resolve();root=Path(read(pair/'baseline-lineage.json')['active_root']).resolve()
    assert root==(pair/'baseline').resolve(),'No recovery branch is authorized'
    out=out.resolve();assert out.is_relative_to(pair/'operator'),'Observations belong outside experiment branches'
    out.mkdir(parents=True,exist_ok=True)
    value=dict(label=label,observed_utc=datetime.now(timezone.utc).isoformat(),observed_monotonic_ns=time.monotonic_ns(),
        active_root=str(root),queue_job=job,observational_only=True)
    value['queue']=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',job],text=True,encoding='utf-8'))
    value['running_lock']=(root/'running.lock').exists()
    value['free_disk_gib']=shutil.disk_usage(pair).free/1024**3
    rows=[];incomplete=0
    if (root/'events.jsonl').exists():
        for line in (root/'events.jsonl').open('rb'):
            if not line.endswith(b'\n'):incomplete+=1;continue
            row=json.loads(line)
            if row['kind'] in ('session_started','session_closed','boundary_checkpoint','task_success','resumed'):rows.append(row)
    value['event_counts']=dict(Counter(r['kind'] for r in rows));value['incomplete_event_lines']=incomplete
    value['last_lifecycle_event']=rows[-1] if rows else None
    for name in ('latest-checkpoint.json','completed.json','controller-failure.json','hibernate-requested.json','recovery-ready.json'):
        if (root/name).exists():
            data=read(root/name)
            if name=='recovery-ready.json':data={k:v for k,v in data.items() if k!='parent_inventory'}
            value[name]=data
    if (root/'latest-execution.json').exists():
        pointer=read(root/'latest-execution.json');path=Path(pointer['path'])
        assert path.parent.resolve()==root and sha(path)==pointer['sha256'],'Execution pointer failed authentication'
        execution=read(path)
        value['execution']={k:execution.get(k) for k in ('passed','error','failure_phase','structured_failure','retirement','elapsed_monotonic_ns')}
    if (root/'viewer.json').exists():
        url=read(root/'viewer.json')['url'];assert url.startswith('http://127.0.0.1:')
        value['viewer_url']=url
        try:
            with urllib.request.urlopen(url+'/frame',timeout=12) as response:frame=json.load(response)
            value['frame']={k:v for k,v in frame.items() if k not in ('geoms','activity')}
            value['frame']['geometry_count']=len(frame['geoms'])
            value['viewer_responding']=True
        except Exception as error:value.update(viewer_responding=False,viewer_error=repr(error))
    maps=pair/'maps';maps_run=read(maps/'run.json')
    value['maps_pristine']=(maps_run['launched'] is False and inventory(maps/'filesystem')==read(maps/'initial-filesystem.json')
        and not (maps/'sessions').exists() and not (maps/'events.jsonl').exists() and not (maps/'latest-checkpoint.json').exists())
    assert value['maps_pristine'],'Maps is no longer pristine'
    path=out/(label+'-'+uuid.uuid4().hex+'.json');save(path,value)
    summary=dict(evidence=str(path),queue_state=value['queue']['state'],exit_status=value['queue']['exit_status'],
        active_root=str(root),event_counts=value['event_counts'],frame=value.get('frame'),viewer_responding=value.get('viewer_responding'),
        maps_pristine=value['maps_pristine'],free_disk_gib=value['free_disk_gib'],execution=value.get('execution'))
    print(canonical(summary).decode())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pair',type=Path,required=True);p.add_argument('--job',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--label',default='periodic')
    a=p.parse_args();observe(a.pair,a.job,a.out,a.label)
