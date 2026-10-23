"""Append the terminal observation and investigation; never alter run manifests."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
MAP=REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ref(label,p):return {'label':label,'uri':str(p),'sha256':sha(p),'state':'available','access':'operator','locator':None}
def invoke(*args):
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(MAP),*args],capture_output=True,text=True,encoding='utf-8',check=True)
    return p.stdout
def record(kind,d):
    path=HERE/('map-'+kind+'.json')
    with path.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2);f.write('\n')
    status=json.loads(invoke('status','--json'))
    print(invoke('append',kind,'--input',str(path),'--expected-sha256',status['store_sha256']))

e=read(HERE/'evidence.json');q=read(HERE/'queue-statuses.json')['second_baseline']
references=[ref('Read-only investigation and ranked repair choices',HERE.parents[1]/'SECOND-FAILURE-INVESTIGATION.md'),
    ref('Authenticated compact readback and external evidence bindings',HERE/'evidence.json'),
    ref('Terminal queue statuses, including failed first audit',HERE/'queue-statuses.json')]
base={'schema_version':'architecture-map-1.0','recorded_at':datetime.now(timezone.utc).isoformat(),'author':'Codex',
    'tags':['apartment','evaluation','baseline','service-interruption','investigation-only']}
def metric(name,value,unit,denominator,description):
    return {'name':name,'value':value,'unit':unit,'denominator':denominator,'denominator_description':description,'missing_reason':None,'evidence':[references[1]]}
rid='APARTMENT-v1-restart001-baseline-service-stop-result'
record('result',base|{'id':rid,'run_id':'APARTMENT-v1-restart001-baseline','supersedes_result_id':None,
    'execution_status':'failed','validity':'invalid','outcome':'not_assessed','ended_at':q['ended_at'],
    'validity_reason':'The stopped condition does not satisfy the frozen complete-history endpoint or normal-session termination contract: six starts, five clean closes, one of 21 assignments advanced. This label concerns the incomplete evaluation; earlier authentic observations remain preserved. It is not a decision to discard them or authorize recovery.',
    'termination_reason':'The sixth native turn returned serverOverloaded and willRetry=false before recorded assistant output or robot tool activity. The launcher raised its generic Bootstrap turn did not complete error after qualified native/transport/filesystem retirement.',
    'details':{'queue_job':q['id'],'exit_status':q['exit_status'],'native_error':'serverOverloaded','native_turn_duration_ms':2920,
        'validated_resume_checkpoint_exists':False,'maps_pristine':True,'repair_implemented':False,'official_launch_or_resume_this_session':False},
    'metrics':[metric('started_sessions',6,'sessions',None,'All session_started records in this one condition history'),
        metric('normally_closed_sessions',5,'sessions',6,'Six started sessions'),
        metric('assignments_advanced',1,'assignments',21,'Matched 21-assignment schedule; advancement is not throwing mastery')],
    'evidence':references})
record('note',base|{'id':'APARTMENT-v1-restart001-investigation-001','target_ids':[rid,'APARTMENT-v1-baseline-failed-launch-result',
    'APARTMENT-v1-storage2-frozen','APARTMENT-repair-live004-result','APARTMENT-v1-restart001-maps'],
    'claim_type':'comparison','supersedes_note_id':None,
    'body':'Read-only Session 32 diagnosis finds an explicit model-service capacity rejection in the sixth native turn. The first five sessions closed normally. The first restarted session retained 3,779,435 content bytes and 12,824,518 metadata bytes for 3,893,783 write bytes; the original failure retained 3,211,381,062 content bytes for 2,900,579 write bytes. No restarted journal has rejected mutations; all six journal/native/transport retirements passed. No validated resume checkpoint exists at an ordinary boundary. Replay has one 7.7461822-second backward wall-clock jump with ordered simulation/monotonic clocks. Rank 1 recommends structured errors and verified clean-boundary recovery, retaining the same model and explicit operator decisions; automatic startup retry is a separate prospective amendment. No fix, commissioning, reset, launch or resume was performed.',
    'details':{'read_only_audit_job':'20261007T174758541852Z-b6a03c0c','audit_exit_status':0,
        'preserved_file_count':20101,'frozen_manifest_files':254,'replay_chunks':1500,'replay_samples':191834,
        'journal_records':17385,'wall_clock_regression_s':-7.7461822,'provider_internals':'unavailable',
        'decision_pending':'Repair scope and future comparison lineage require Randy direction; no recovery rule is approved.'},'evidence':references})
print(invoke('build'))
print(invoke('validate','--output',str(MAP.parent/'validation.json')))
