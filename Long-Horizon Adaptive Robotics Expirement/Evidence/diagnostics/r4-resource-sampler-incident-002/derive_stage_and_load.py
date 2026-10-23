"""Derive stage timing and incident token-load metadata; never policy text/outcomes."""
from pathlib import Path
import json,hashlib
from collections import defaultdict
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent
EXP=BASE.parents[2]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ref(p):
 p=Path(p);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
run=BASE/'stage-probe-001'; report=load(run/'report.json'); child=load(run/'probe/result.json')
receipt=EXP/'Evidence/queue-receipts/20260924T195134595236Z-4502b0df.json';r=load(receipt)
assert r['state']=='succeeded' and type(r['exit_status']) is int and r['exit_status']==0
assert report['sources_unchanged'] and child['sources_unchanged']
metrics=defaultdict(list); calls=[]; traces=[]
for p in sorted((run/'probe/stage-traces').glob('*.jsonl')):
 traces.append(ref(p))
 for line in p.open(encoding='utf-8'):
  e=json.loads(line)
  if 'duration_s' in e: metrics[e['event']].append(e['duration_s'])
  if e['event']=='generic_model_result':
   v=e['record'];ans=v.get('response',{})
   calls.append({'index':v['index'],'error':v['error'],'prompt_tokens':ans.get('prompt_tokens'),'completion_tokens':ans.get('completion_tokens'),'latency_s':ans.get('latency_s'),'timings':ans.get('timings')})
stages={k:{'count':len(v),'min_s':min(v),'max_s':max(v)} for k,v in sorted(metrics.items())}
incidents=[]
for name in ('batch01-eval-r4-C24-rep2-A3-no-persistence','batch01-eval-r4-C24-rep2-A3-persistent'):
 attempt=EXP/'Evidence/releases/batch01-eval-r4/attempts'/name
 terminal=load(attempt/'terminal.json'); ep=attempt/'evidence/events.jsonl'; replies=[]
 for line in ep.open(encoding='utf-8'):
  e=json.loads(line)
  if e['event_type']=='model_response':
   ans=e['payload']['result'];replies.append({'event_id':e['event_id'],'wall_elapsed_s':e['wall_elapsed_s'],'prompt_tokens':ans.get('prompt_tokens'),'completion_tokens':ans.get('completion_tokens'),'latency_s':ans.get('latency_s'),'timings':ans.get('timings')})
 assert len(replies)==terminal['result']['model_responses']
 incidents.append({'run_id':name,'terminal':ref(attempt/'terminal.json'),'events':ref(ep),'responses_resource_metadata_only':replies})
out={'schema_version':'resource-stage-probe-and-load-review-1','recorded_at_utc':datetime.now(timezone.utc).isoformat(),'source':ref(__file__),'probe_report':ref(run/'report.json'),'probe_result':ref(run/'probe/result.json'),'official_probe_receipt':ref(receipt),'trace_refs':traces,'stages':stages,'generic_calls':calls,'incident_load_metadata':incidents,'limitations':['Only numeric resource/inference load metadata retained; no policy prompts, outputs, task success or concealed manifests used.','Stage nonreproduction is not readiness or authorization to resume.','Short generic prompts may not exercise long-context prefill exposure; token load is a diagnostic covariate, not policy performance.']}
p=BASE/'stage-probe-and-load-review.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(ref(p)))