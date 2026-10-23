"""Compact queue/readback status; optional terminal Architecture Map closeout."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

CODE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(CODE))
from common import DEFAULT_ROOT,REPO,canonical,read,save

p=argparse.ArgumentParser();p.add_argument('identifier');p.add_argument('--finish',action='store_true');a=p.parse_args()
root=DEFAULT_ROOT/'engineering'/a.identifier;job=read(root/'queue-submission.json')['id']
status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',job],text=True,encoding='utf-8'))
terminal=status['state'] in ('succeeded','failed','canceled')
if terminal:
    path=root/'queue-status.json'
    if path.exists():
        assert read(path)==status,'An already retained terminal queue receipt changed'
    else:save(path,status)
result_path=root/'output/result.json'
if not result_path.exists():result_path=root/'output/progress.json'
result=read(result_path) if result_path.exists() else {}
summary=dict(identifier=a.identifier,job=job,state=status['state'],exit_status=status['exit_status'],
    passed=result.get('passed'),checks=result.get('checks'),error=result.get('error'),traceback=result.get('traceback'))
if not terminal:
    for stage in ('failed','recovered'):
        for condition in ('baseline','maps'):
            active=root/'output'/stage/condition
            if not (active/'running.lock').exists():continue
            summary['active_root']=str(active)
            summary['checkpoint_published']=(active/'latest-checkpoint.json').exists()
            try:
                url=read(active/'viewer.json')['url'];assert url.startswith('http://127.0.0.1:')
                with urllib.request.urlopen(url+'/frame',timeout=8) as response:frame=json.load(response)
                summary['live']={k:frame[k] for k in ('sim_time','session','phase','battery','pending_hibernation')}
            except Exception as error:summary['viewer_observation_error']=repr(error)
print(canonical(summary).decode(),flush=True)
if a.finish:
    assert terminal,'An active attempt has no terminal result to register'
    from register import call,finish
    assert not call('lookup','--id',a.identifier+'-result','--json')['total'],'Result already registered'
    finish(a.identifier,path)
