"""Append immutable attempts/results and submit once through the shared queue."""
import argparse
from common63 import *
MAP=REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
def invoke(*args):return output(sys.executable,'-X','utf8','-B',str(MAP),*args)
def mapref(label,p):return dict(label=label,uri=str(p),sha256=sha(p),state='available',access='operator',locator=None)
def base():return dict(schema_version='architecture-map-1.0',recorded_at=now(),author='Codex session 63',tags=['apartment','checkpoint-recovery','operator-engineering'],details={})
def append(kind,record):
    p=HERE/('map-'+record['id']+'.json');save(p,record)
    digest=json.loads(invoke('status','--json'))['store_sha256']
    print(invoke('append',kind,'--input',str(p),'--expected-sha256',digest),flush=True)
def register(name,entry):
    authority=HERE/'authority-original.md'
    if not authority.exists():
        transcript=REPO/'chats/Codex-Human/Apartment v4 Maps Launch and Monitoring/Apartment v4 Maps Launch and Monitoring - Active.md'
        raw=transcript.read_bytes();assert raw.count(b'**Randy (2026-10-10 11:32 PDT):**')==1
        with authority.open('xb') as f:f.write(raw)
    names=['common63.py','prepare_branch.py',entry,'PROTOCOL.md','authority-original.md']
    names=list(dict.fromkeys(names))
    manifest=HERE/(name+'-manifest.json')
    save(manifest,dict(id='APARTMENT-s63-'+name,created_utc=now(),files={n:dict(sha256=sha(HERE/n),bytes=(HERE/n).stat().st_size) for n in names},
        parent=str(PARENT),checkpoint=ref(CP/'manifest.json'),source_manifest=ref(FROZEN/'source-manifest.json'),certificate=ref(CODE/'commissioning.json'),
        model_calls_planned=0,scientific_source_changes=0,automatic_retry=False))
    r=mapref('Immutable operator recovery attempt manifest',manifest);known=dict(state='recorded',refs=[r],reason=None)
    append('run',base()|dict(id='APARTMENT-s63-'+name,revision_id='APARTMENT-v4-integrated-repair-frozen',stage='diagnostic',
        condition_id='maps-operator-checkpoint5-recovery',protocol_id='APARTMENT-s63-operator-recovery',scenario_id=name,paired_block_id='unpaired-engineering',replicate=1,
        started_at=None,rerun_of_run_id=None,condition_details=dict(model_calls_planned=0,scientific_apparatus_unchanged=True),
        seeds=dict(state='none',refs=[],reason='Operator qualification restores the existing checkpoint and never rerolls the schedule'),
        frozen_refs={k:known for k in ('code','environment','protocol','scenario')}|{'models':dict(state='none',refs=[],reason='No provider invocation')},evidence=[r]))
    argv=[sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(HERE),'--',sys.executable,'-X','utf8','-B',str(HERE/entry)]
    save(HERE/(name+'-submission-intent.json'),dict(argv=argv,created_utc=now(),automatic_resubmission=False))
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
    save(HERE/(name+'-submission-response.json'),dict(exit_status=p.returncode,stdout=p.stdout,stderr=p.stderr))
    assert p.returncode==0,'Uncertain submission; preserve and inspect, never automatically resubmit'
    q=json.loads(p.stdout);save(HERE/(name+'-queue.json'),q);print(json.dumps(dict(job=q['id'],state=q['state'])),flush=True)
def complete(name,path):
    q=queue('status',read(HERE/(name+'-queue.json'))['id']);assert q['state'] not in ('queued','running','cancel_requested')
    save(HERE/(name+'-terminal.json'),q)
    passed=q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0 and Path(path).is_file() and read(path)['passed'] is True
    refs=[mapref('Terminal queue receipt',HERE/(name+'-terminal.json'))]
    if Path(path).is_file():refs.append(mapref('Preserved attempt result',path))
    append('result',base()|dict(id='APARTMENT-s63-'+name+'-result',run_id='APARTMENT-s63-'+name,supersedes_result_id=None,
        execution_status='completed' if passed else 'failed',validity='valid' if passed else 'invalid',
        validity_reason='Operator engineering only. No official scientific outcome; failures remain visible.',outcome='success' if passed else 'not_assessed',
        ended_at=q['ended_at'],termination_reason='Declared gates passed' if passed else 'Failed qualification gate; no new model call',metrics=[],evidence=refs,
        details=dict(queue_id=q['id'],exit_status=q['exit_status'])))
    print(json.dumps(dict(passed=passed,name=name,state=q['state'])))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['register','complete']);p.add_argument('name');p.add_argument('entry_or_result');a=p.parse_args()
    if a.command=='register':register(a.name,a.entry_or_result)
    else:complete(a.name,a.entry_or_result)
