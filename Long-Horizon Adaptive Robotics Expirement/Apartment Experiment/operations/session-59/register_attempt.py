"""Register and submit one immutable operator attempt, never resubmit."""
import argparse
from support import *

MAP=REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
def invoke(*args):return output(sys.executable,'-X','utf8','-B',str(MAP),*args)
def mapref(label,p):return dict(label=label,uri=str(p),sha256=sha(p),state='available',access='operator',locator=None)
def base():return dict(schema_version='architecture-map-1.0',recorded_at=now(),author='Codex session 59',tags=['apartment','storage-routing','engineering'],details={})
def append(kind,record):
    path=HERE/('map-'+record['id']+'.json');save(path,record)
    print(invoke('append',kind,'--input',str(path),'--expected-sha256',read_status()['store_sha256']),flush=True)
def read_status():return json.loads(invoke('status','--json'))
def register(name,entry):
    authority=HERE/'authority-original.md'
    if not authority.exists():
        transcript=REPO/'chats/Codex-Human/Apartment v4 Maps Launch and Monitoring/Apartment v4 Maps Launch and Monitoring - Active.md'
        raw=transcript.read_bytes();assert raw.count(b'**Randy (2026-10-10 09:13 PDT):**')==1
        with authority.open('xb') as f:f.write(raw)
    names=[entry,'support.py','PROTOCOL.md','authority-original.md']
    manifest=HERE/(name+'-manifest.json')
    save(manifest,dict(id='APARTMENT-s59-'+name,created_utc=now(),files={n:dict(sha256=sha(HERE/n),bytes=(HERE/n).stat().st_size) for n in names},
        source_manifest=ref(FROZEN/'source-manifest.json'),certificate=ref(CODE/'commissioning.json'),
        original_pair=str(PAIR),original_maps=str(PAIR/'maps'),destination=str(RUN),model_calls_planned=0,
        source_changes=[],run_metadata_changes=[],automatic_retry=False))
    fref=mapref('Storage-only attempt manifest',manifest);known=dict(state='recorded',refs=[fref],reason=None)
    append('run',base()|dict(id='APARTMENT-s59-'+name,revision_id='APARTMENT-v4-integrated-repair-frozen',stage='diagnostic',
        condition_id='maps-storage-routing',protocol_id='APARTMENT-s59-storage',scenario_id=name,paired_block_id='unpaired-engineering',replicate=1,
        started_at=None,rerun_of_run_id=None,condition_details=dict(model_calls_planned=0,scientific_condition_unchanged=True),
        seeds=dict(state='none',refs=[],reason='Operator storage qualification with fixed private engineering fixtures; no official assignment consumed'),
        frozen_refs={k:known for k in ('code','environment','protocol','scenario')}|{'models':dict(state='none',refs=[],reason='No provider invocation')},evidence=[fref]))
    argv=[sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(HERE),'--',sys.executable,'-X','utf8','-B',str(HERE/entry)]
    save(HERE/(name+'-submission-intent.json'),dict(argv=argv,created_utc=now(),automatic_resubmission=False))
    p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
    save(HERE/(name+'-submission-response.json'),dict(exit_status=p.returncode,stdout=p.stdout,stderr=p.stderr))
    assert p.returncode==0,'Uncertain submission; inspect, never automatically resubmit'
    q=json.loads(p.stdout);save(HERE/(name+'-queue.json'),q);print(json.dumps(q),flush=True)
def complete(name,result):
    q=queue('status',read(HERE/(name+'-queue.json'))['id']);assert q['state'] not in ('queued','running','cancel_requested')
    save(HERE/(name+'-terminal.json'),q)
    passed=q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0 and Path(result).is_file() and read(result)['passed'] is True
    refs=[mapref('Terminal queue receipt',HERE/(name+'-terminal.json'))]
    if Path(result).is_file():refs.append(mapref('Retained exact attempt result',result))
    append('result',base()|dict(id='APARTMENT-s59-'+name+'-result',run_id='APARTMENT-s59-'+name,supersedes_result_id=None,
        execution_status='completed' if passed else 'failed',validity='valid' if passed else 'invalid',
        validity_reason='Operator qualification only; no official scientific outcome. Exact failures retained.',outcome='success' if passed else 'not_assessed',
        ended_at=q['ended_at'],termination_reason='Declared gates passed' if passed else 'Preserved failed gate; no official launch',metrics=[],evidence=refs,
        details=dict(queue_id=q['id'],exit_status=q['exit_status'])))
    print(json.dumps(dict(passed=passed,name=name,state=q['state'])))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['register','complete']);p.add_argument('name');p.add_argument('entry_or_result');a=p.parse_args()
    if a.command=='register':register(a.name,a.entry_or_result)
    else:complete(a.name,a.entry_or_result)
