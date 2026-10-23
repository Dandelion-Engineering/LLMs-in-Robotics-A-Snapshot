"""Read-only compact pilot observation; never issues a robot command."""
from collections import Counter
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from attempts import HERE,ROOT,QUEUE,read

parser=argparse.ArgumentParser();parser.add_argument('--attempt',default='native002',choices=['native001','native002']);args=parser.parse_args()
root=ROOT/args.attempt;receipt=read(HERE/(args.attempt+'-queue.json'))
queue=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',receipt['id']],text=True,encoding='utf-8'))
value={k:queue[k] for k in ('id','state','exit_status','started_at','ended_at')}
for name in ('result.json','progress.json'):
    path=root/'output'/name
    if path.exists():
        result=read(path);value.update(record=name,**{k:result.get(k) for k in ('passed','checks','real_model_calls','injected_starts','error')});break
active=[]
for path in (root/'output').glob('*/*/running.lock'):
    branch=path.parent;row=dict(branch=str(branch.relative_to(root/'output')))
    sessions=sorted((branch/'sessions').glob('session-*'))
    if sessions:
        preflight=sessions[-1]/'native/client/preflight.json'
        if preflight.exists():row['native']={k:read(preflight).get(k) for k in ('preflight_passed','model_effective','effort_effective')}
        native_events=sessions[-1]/'native/client/events.jsonl'
        if native_events.exists():
            stat=native_events.stat();row['native_event_bytes']=stat.st_size;row['native_event_write_age_s']=round(time.time()-stat.st_mtime,3)
        native_result=sessions[-1]/'native/client/result.json'
        if native_result.exists():
            result=read(native_result);row['native_result']={k:result.get(k) for k in ('success','model_started','turn_status','error')}
    events=branch/'events.jsonl'
    if events.exists():
        counts=Counter(json.loads(line)['kind'] for line in events.open('rb') if line.endswith(b'\n'))
        row['events']={k:counts[k] for k in ('session_started','session_closed','boundary_checkpoint','sensor_capture','image_delivered')}
    if (branch/'viewer.json').exists():
        try:
            with urllib.request.urlopen(read(branch/'viewer.json')['url']+'/frame',timeout=8) as response:frame=json.load(response)
            row['frame']={k:frame[k] for k in ('session','sim_time','phase','battery','pending_hibernation')}
        except Exception as error:row['viewer_error']=repr(error)
    active.append(row)
value['active']=active
print(json.dumps(value))
