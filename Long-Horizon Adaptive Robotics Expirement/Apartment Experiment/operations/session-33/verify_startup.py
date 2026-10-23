"""Retain a bounded startup observation; it cannot certify a terminal outcome."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import uuid

CODE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(CODE))
from common import REPO,canonical,inventory,read,save,sha


def prefix(path):
    raw=path.read_bytes();raw=raw[:raw.rfind(b'\n')+1]
    rows=[json.loads(line) for line in raw.splitlines()]
    return rows,dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),records=len(rows))


def verify(pair,job):
    pair=pair.resolve();root=Path(read(pair/'baseline-lineage.json')['active_root']).resolve()
    assert root.is_relative_to(pair)
    out=pair/'operator/startup';out.mkdir(parents=True,exist_ok=True)
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),queue_job=job,root=str(root),checks={},passed=False,
        assessment='Startup observation only; no terminal validity, task completion or scientific performance is assessed. Browser rendering is verified separately.')
    try:
        status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',job],text=True,encoding='utf-8'))
        result['queue']=status;result['checks']['queue_running']=status['state']=='running' and status['exit_status'] is None
        result['checks']['run_launched']=read(root/'run.json')['launched'] is True
        result['checks']['runtime_lock']=(root/'running.lock').exists()
        viewer=read(root/'viewer.json');url=viewer['url'];assert url.startswith('http://127.0.0.1:')
        frames=[]
        for _ in range(2):
            with urllib.request.urlopen(url+'/frame',timeout=12) as response:frames.append(json.load(response))
            time.sleep(.2)
        result['viewer_url']=url;result['frames']=[{k:v for k,v in f.items() if k not in ('geoms','activity')} for f in frames]
        result['checks']['advancing_simulator']=frames[1]['sim_time']>frames[0]['sim_time'] and len(frames[1]['geoms'])>0
        session=root/'sessions'/('session-'+str(frames[1]['session']).zfill(5));native=session/'native'
        preflight=read(native/'client/preflight.json')
        result['native']={k:preflight[k] for k in ('model_effective','effort_effective','auth_type','preflight_passed','thread_id')}
        result['checks']['native_identity']=preflight['preflight_passed'] is True and preflight['model_effective']=='gpt-6-astra' and preflight['effort_effective']=='max' and preflight['auth_type']=='chatgpt'
        result['checks']['namespace_canaries']=all(read(native/name)['exit_status']==0 and json.loads(read(native/name)['stdout'])['qualified'] is True for name in ('canary.json','codehost-canary.json'))
        events,result['native_prefix']=prefix(native/'client/events.jsonl')
        counts=Counter(row.get('method',row.get('kind','unknown')) for row in events);result['native_event_counts']=dict(counts)
        result['checks']['native_turn_started']=counts['turn/started']>0
        result['checks']['observable_tool_activity']=counts['item/tool/call']>0 or counts['public_tool_call']>0
        physical,result['physical_prefix']=prefix(root/'events.jsonl')
        result['physical_event_counts']=dict(Counter(row['kind'] for row in physical))
        result['checks']['sensors_and_images']=all(result['physical_event_counts'].get(k,0)>0 for k in ('sensor_capture','image_delivered'))
        journal,result['journal_prefix']=prefix(session/'workspace/journal/mutations.jsonl')
        result['checks']['protected_journal_active']=len(journal)>1
        index=read(root/'replay/index.json');result['replay']=dict(chunks=len(index),last=index[-1] if index else None)
        result['checks']['physics_recording']=bool(index) and sha(root/'replay'/index[-1]['file'])==index[-1]['sha256']
        maps=pair/'maps'
        result['checks']['maps_pristine']=not read(maps/'run.json')['launched'] and inventory(maps/'filesystem')==read(maps/'initial-filesystem.json') and not (maps/'sessions').exists()
        result['passed']=all(result['checks'].values())
    except Exception as error:result['error']=repr(error)
    path=out/('observation-'+uuid.uuid4().hex+'.json');save(path,result)
    print(canonical(dict(evidence=str(path),passed=result['passed'],checks=result['checks'],error=result.get('error'),viewer_url=result.get('viewer_url'))).decode())
    return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pair',type=Path,required=True);p.add_argument('--job',required=True);a=p.parse_args()
    raise SystemExit(0 if verify(a.pair,a.job) else 1)
