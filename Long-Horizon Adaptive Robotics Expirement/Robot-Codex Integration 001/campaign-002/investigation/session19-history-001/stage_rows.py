"""Queued historical rows for eighteen already-terminal Session19 attempts.

Never read active outputs, recompute verdicts, publish history or launch a run.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent;I=HERE.parent;C=I.parent;Q=C/'qualification';IO=C/'io-repair'
REPO=C.parents[2];M=C.parent.parent/'Architecture Map';QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
BASELINE='cc2bc83f1c7b887c3e8f16d0cab65beb509f1f7e55e44310833725000375590e'
HISTORY=I/'qualification-history.json'
ALLOCATIONS=[('shutdown-diagnostic-005','097','failed-interrupt',None),
    ('shutdown-diagnostic-006','098','completed-interrupt',None),
    ('raw-preflight-020','099','raw',None),('transport-probe-023','099','transport',None),('host-probe-030','099','host',None),
    ('native-029','100','native','030'),('boundary-030','101','boundary','030'),('smoke-028','102','smoke','030'),
    ('raw-preflight-021','103','raw',None),('transport-probe-024','103','transport',None),('host-probe-031','103','host',None),
    ('native-030','104','native','031'),('boundary-031','105','failed-boundary','031'),
    ('raw-preflight-022','107','raw',None),('transport-probe-025','107','transport',None),('host-probe-032','107','host',None),
    ('native-031','108','native','032'),('boundary-032','109','boundary','032')]

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def artifact(p,label):
    p=Path(p).resolve();return {'path':str(p),'sha256':digest(p),'bytes':p.stat().st_size,'label':label}
def save(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2);f.write('\n')
def load(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def metadata_paths(short,kind):
    if kind=='failed-interrupt':return IO/'native-os-closure-assessment-001/official-status.json',IO/short/'manifest.json'
    if kind=='completed-interrupt':return IO/'graceful-process-assessment-001/official-status.json',IO/short/'manifest.json'
    if kind=='failed-boundary':return IO/'boundary031-diagnosis-001/official-status.json',Q/(short+'-manifest.json')
    if kind in ['raw','transport']:return IO/short/'records/official-status.json',IO/short/'manifest.json'
    if kind=='host':return Q/('RCI001-C02-'+short)/'official-status.json',Q/(short+'-manifest.json')
    return Q/(short+'-queue.json'),Q/(short+'-manifest.json')

def row_for(short,rev,kind,ledger,job):
    run='RCI001-C02-'+short;revision='RCI001-C02-dev-'+rev
    queue,manifest=metadata_paths(short,kind);snapshot=M/'releases'/revision/'snapshot.json'
    row={'run_id':run,'revision':revision,'scorable':False,'task_outcome':'unknown',
         'queue':{k:job[k] for k in ['id','state','exit_status','started_at','ended_at']},'details':{}}
    items={}
    def add(path,label,expected=None):
        item=artifact(path,label)
        if expected is not None:assert item['sha256']==expected
        old=items.get(item['path'])
        if old is not None:assert old['sha256']==item['sha256'];return old
        items[item['path']]=item;return item
    official=add(queue,'Official queue receipt');snap=add(snapshot,'Frozen source snapshot')
    if kind in ['failed-interrupt','completed-interrupt','failed-boundary']:
        mp=add(manifest,'Frozen attempt manifest')
        completion=kind=='completed-interrupt'
        contract='queue_completion_contract' if completion else 'queue_failure_contract'
        schema=('campaign002-completed-unassessed-interrupt-queue-1' if completion else
                'campaign002-failed-boundary-queue-1' if kind=='failed-boundary' else 'campaign002-failed-single-interrupt-queue-1')
        row.update(status='completed' if completion else 'failed',validity='unknown',assessment_state='not_assessed',model_calls=None,
            reason='Official execution metadata only. Separate bounded infrastructure findings are preserved in HumanReport19 and the linked Architecture Map result; no task outcome or qualification is inferred here.')
        row[contract]={'schema':schema,'official_queue_sha256':official['sha256'],'manifest_sha256':mp['sha256'],'snapshot_sha256':snap['sha256']}
    elif kind in ['raw','transport']:
        result=IO/short/'evidence/result.json';entry=IO/short/'records/verified-readiness-entry.json'
        value=read(result);assert value['passed'] is True
        rp=add(result,'Original no-model diagnostic result');ep=add(entry,'Verified readiness entry')
        row.update(status='passed',validity='diagnostic_checks_passed',model_calls=0,
            attempt_kind='raw_event_preflight_diagnostic' if kind=='raw' else 'transport_probe_diagnostic',
            reason='Original no-model prerequisite passed and was independently replayed. This does not qualify a model or establish task performance.',
            diagnostic_contract={'schema':'campaign002-history-diagnostic-1','result_schema':value['schema'],
                'result':rp,'verified_readiness_entry':ep,'physical_simulation':False,
                'proof_scope':'Original fixed no-model prerequisite only; no model-read, robot-task or full-qualification claim.'},
            details={'checks':value['checks'],'qualifier_claim':False})
    elif kind=='host':
        mp=add(manifest,'Frozen host prerequisite manifest');ap=add(Q/(short+'-assessment.json'),'Original host diagnostic assessment')
        a=read(ap['path']);assert a['diagnostic_passed'] is True
        row.update(status='passed',validity='diagnostic_passed',model_calls=0,attempt_kind='host_prerequisite_diagnostic',
            reason='Original idle-host prerequisite passed all eight checks; model and fixture qualification remain separate.',
            host_prerequisite_contract={'schema':'campaign002-host-prerequisite-history-1','assessment_sha256':ap['sha256'],
                'official_queue_sha256':official['sha256'],'manifest_sha256':mp['sha256'],'snapshot_sha256':snap['sha256']},
            details={'checks_passed':sum(v is True for v in a['checks'].values()),'failed_checks':[k for k,v in a['checks'].items() if v is not True],
                'timing':{k:v for k,v in a['timing']['replayed_timing'].items() if isinstance(v,(str,int,float,bool))}})
        host=a['bindings'].get('host_result')
        if host:add(host['path'],'Original protected host result',host['sha256'])
    else:
        dp=Q/('final-qualification-'+ledger)/short/'disposition.json';d=read(dp);e=d['entry']
        for key in ['manifest','snapshot','queue','assessment']:
            add(e[key]['path'],{'queue':'Official queue receipt','snapshot':'Frozen source snapshot',
                'manifest':'Frozen qualification manifest','assessment':'Original qualification assessment'}[key],e[key]['sha256'])
        row['admission_disposition']=add(dp,'Original coordinator admission disposition')
        a=read(e['assessment']['path']);passed=d['passed'];assert type(passed) is bool
        row.update(status='passed' if passed else 'failed',validity='valid' if passed else 'invalid',
            reason='Original source-bound qualification and coordinator verdict retained without reassessment.',
            model_calls=0 if kind in ['native','boundary'] else sum(a['checks'].get(stage+':actual_model_started') is True for stage in ['interrupt','resume']))
        checks=({r['run_id']+'::'+k:v for r in a['rows'] for k,v in r['checks'].items()} if kind=='native' else a['checks'])
        row['details']={'admission_passed':passed,'admission_error':d.get('error'),
            'checks_passed':sum(v is True for v in checks.values()),'checks_total':len(checks),
            'failed_checks':[k for k,v in checks.items() if v is not True]}
        if kind=='smoke':
            add(snapshot.with_name('code.zip'),'Original frozen source archive')
            for path,sha in a.get('evidence_sha256',{}).items():
                add(path,'Original smoke evidence: '+str(Path(path)),sha)
        if kind=='boundary':
            for name in ['source-binding-before.json','source-binding-after.json']:
                add(Path(e['evidence'])/name,'Original measured sources: '+name)
    row['artifacts']=list(items.values())
    return row

def main():
    out=HERE/'drafts-001';out.mkdir(exist_ok=False)
    assert digest(HISTORY)==BASELINE
    baseline=read(HISTORY);assert len(baseline['attempts'])==129
    save(out/'input-history.json',{'path':str(HISTORY.resolve()),'sha256':BASELINE,'rows':129})
    jobs={}
    for short,rev,kind,ledger in ALLOCATIONS:
        stored=read(metadata_paths(short,kind)[0]);job_id=stored['id']
        fresh=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',job_id],text=True,encoding='utf-8'))
        assert all(stored.get(k)==fresh.get(k) for k in ['id','state','exit_status','started_at','ended_at','argv','cwd'])
        assert type(fresh['exit_status']) is int
        if kind.startswith('failed-'):assert fresh['state']=='failed' and fresh['exit_status']!=0
        else:assert fresh['state']=='succeeded' and fresh['exit_status']==0
        jobs[short]=fresh
    save(out/'fresh-official.json',{'checked_at':datetime.now(timezone.utc).isoformat(),'jobs':jobs})
    report=load('session19_qualification_report',I/'qualification_report.py');qa=load('session19_qualification_qa',I/'qualification_qa.py')
    rows=[];rendered=[]
    for short,rev,kind,ledger in ALLOCATIONS:
        row=row_for(short,rev,kind,ledger,jobs[short]);display=report.qualification_row(row,I)
        if display.get('queue_failure'):qa.failed_queue_guard(display,I)
        elif display.get('queue_completion'):qa.completed_diagnostic_guard(display,I)
        elif display.get('diagnostic_result'):qa.no_model_diagnostic_guard(display,I)
        elif display.get('host_prerequisite'):qa.host_prerequisite_guard(display,I)
        save(out/(short+'.json'),row);rows.append(row);rendered.append(display)
    assert digest(HISTORY)==BASELINE
    save(out/'rows.json',rows)
    save(out/'verification.json',{'passed':True,'rows':len(rows),'run_ids':[r['run_id'] for r in rows],
        'prior_history':{'sha256':BASELINE,'rows':129},'prior_history_unchanged':True,'canonical_history_written':False,
        'active_outputs_read':False,'outcomes_recomputed':False,'reader_inputs':report.READS})
    print(json.dumps({'staged':len(rows),'history_unchanged':True}))

if __name__=='__main__':main()
