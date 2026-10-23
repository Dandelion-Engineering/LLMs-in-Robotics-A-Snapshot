"""Build a terminal-status companion without changing any historical attempt row."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import stage_rows as base

HERE=Path(__file__).resolve().parent
HELPER=base.I/'v29-append-staging/stage_append.py'

def helpers():
    return [Path(__file__),HERE/'stage_rows.py',HELPER,base.I/'qualification_report.py',
        base.I/'qualification_qa.py',base.I/'qualification_template.html']

def bindings():return {str(p.resolve()):base.digest(p) for p in helpers()}

def replace_value(text,key,value):
    marker=json.dumps(key)+': ';assert text.count(marker)==1
    start=text.index(marker)+len(marker);_,end=json.JSONDecoder().raw_decode(text,start)
    return text[:start]+json.dumps(value,indent=2,ensure_ascii=False)+text[end:]

def official(job_id):
    return json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(base.QUEUE),'status',job_id],text=True,encoding='utf-8'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','run']);parser.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args();plan=args.plan.resolve();v=base.read(plan)
    assert v['schema']=='campaign002-history-candidate-plan-1'
    assert v['row_packets']==[] and v['current_status']['state']=='campaign_terminal'
    out=HERE/v['directory'];assert out.parent==HERE and not out.exists()
    intent=HERE/(v['directory']+'-intent.json');submit=HERE/(v['directory']+'-submit.json')
    assert base.digest(base.HISTORY)==v['history_sha256']
    if args.action=='submit':
        base.save(intent,{'plan_sha256':base.digest(plan),'sources':bindings(),'created_at':datetime.now(timezone.utc).isoformat()})
        cmd=[sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'run','--plan',str(plan)]
        job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(base.QUEUE),'submit',
            '--project','LLMs-in-Robotics','--cwd',str(base.REPO),'--',*cmd],text=True,encoding='utf-8'))
        base.save(submit,job);print(json.dumps({'job_id':job['id'],'state':job['state']}));return
    bound=base.read(intent);assert bound['sources']==bindings() and bound['plan_sha256']==base.digest(plan)
    check=official(v['development_check_job_id'])
    assert check['state']=='succeeded' and type(check['exit_status']) is int and check['exit_status']==0
    out.mkdir();s=base.load('history_span_tools',HELPER)
    original=base.HISTORY.read_bytes();assert base.digest(base.HISTORY)==v['history_sha256']
    text,old_spans,end=s.raw_rows(original);old=base.read(base.HISTORY);assert len(old_spans)==v['prior_rows']
    exports=base.read(base.I/'v29-append-staging/smoke027-publication-receipt.json')['exports_preserved']
    assert len(exports)==19 and all(s.bind(x['path'])==x for x in exports)
    rows=[];stage_jobs={}
    for packet in v['row_packets']:
        job=official(packet['job_id']);assert job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0
        stage_jobs[job['id']]=job
        for name in ('rows','verification'):
            assert base.digest(packet[name]['path'])==packet[name]['sha256']
        proof=base.read(packet['verification']['path']);assert proof['passed'] is True and proof['canonical_history_written'] is False and proof['active_outputs_read'] is False
        rows+=base.read(packet['rows']['path'])
    all_rows=old['attempts']+rows;ids=[r['run_id'] for r in all_rows];assert len(ids)==len(set(ids))
    auth=out/'official';auth.mkdir();jobs={}
    for row in all_rows:s.authenticate(row,auth,jobs)
    base.save(out/'fresh-official.json',{'jobs':jobs,'stage_jobs':stage_jobs})
    addition=',\n'+',\n'.join('    '+json.dumps(r,indent=2,ensure_ascii=False).replace('\n','\n    ') for r in rows)
    assert not rows  # Status-only: preserve the complete attempts array byte-for-byte.
    last=old_spans[-1][3]
    text=replace_value(text,'updated_at',datetime.now(timezone.utc).isoformat())
    text=replace_value(text,'current_status',v['current_status'])
    candidate=text.encode('utf-8');_,spans,_=s.raw_rows(candidate)
    assert s.row_spans(spans[:len(old_spans)])==s.row_spans(old_spans) and len(spans)==len(all_rows)
    with (out/'candidate-history.json').open('xb') as f:f.write(candidate)
    report=base.load('candidate_report',base.I/'qualification_report.py');qa=base.load('candidate_qa',base.I/'qualification_qa.py')
    result=report.build(out/'candidate-history.json',out/'html')
    checked=qa.verify(out/'html');base.save(out/'html/qualification-qa.json',checked)
    assert checked['history_records']==len(all_rows) and checked['scored_outcome_rows']==0
    assert base.digest(base.HISTORY)==v['history_sha256'] and bindings()==bound['sources']
    assert all(s.bind(x['path'])==x for x in exports)
    base.save(out/'verification.json',{'passed':True,'prior_rows':len(old_spans),'rows':len(spans),
        'appended':[r['run_id'] for r in rows],'prior_raw_rows_preserved':True,'canonical_history_written':False,
        'source_bindings':bound['sources'],'exports_preserved':exports,'history_before_sha256':v['history_sha256'],
        'history_candidate_sha256':base.digest(out/'candidate-history.json'),'active_outputs_read':False,
        'outcomes_recomputed':False,'build':result,'qa':checked})
    print(json.dumps({'passed':True,'rows':len(spans),'old_rows_preserved':len(old_spans)}))

if __name__=='__main__':main()
