"""Stage explicitly selected terminal rows; all input/output identities are bound."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import stage_rows as base

HERE=Path(__file__).resolve().parent

def bindings():
    return {str(p.resolve()):base.digest(p) for p in [Path(__file__),HERE/'stage_rows.py',
        base.I/'qualification_report.py',base.I/'qualification_qa.py']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','run']);parser.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args();plan=args.plan.resolve();value=base.read(plan)
    assert value['schema']=='campaign002-explicit-terminal-history-selection-1'
    out=HERE/value['directory'];assert out.parent==HERE and not out.exists()
    assert base.digest(base.HISTORY)==value['history_sha256']
    assert isinstance(value['allocations'],list) and value['allocations']
    intent=HERE/(value['directory']+'-intent.json');submit=HERE/(value['directory']+'-submit.json')
    if args.action=='submit':
        base.save(intent,{'plan_sha256':base.digest(plan),'sources':bindings(),'created_at':datetime.now(timezone.utc).isoformat()})
        cmd=[sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'run','--plan',str(plan)]
        job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(base.QUEUE),'submit',
            '--project','LLMs-in-Robotics','--cwd',str(base.REPO),'--',*cmd],text=True,encoding='utf-8'))
        base.save(submit,job);print(json.dumps({'job_id':job['id'],'state':job['state']}));return
    bound=base.read(intent);assert bound['sources']==bindings() and bound['plan_sha256']==base.digest(plan)
    out.mkdir();jobs={}
    for short,rev,kind,ledger in value['allocations']:
        stored=base.read(base.metadata_paths(short,kind)[0]);jid=stored['id']
        fresh=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(base.QUEUE),'status',jid],text=True,encoding='utf-8'))
        assert all(stored.get(k)==fresh.get(k) for k in ['id','state','exit_status','started_at','ended_at','argv','cwd'])
        assert type(fresh['exit_status']) is int
        if kind.startswith('failed-'):assert fresh['state']=='failed' and fresh['exit_status']!=0
        else:assert fresh['state']=='succeeded' and fresh['exit_status']==0
        jobs[short]=fresh
    base.save(out/'fresh-official.json',{'checked_at':datetime.now(timezone.utc).isoformat(),'jobs':jobs})
    report=base.load('selected_report',base.I/'qualification_report.py');qa=base.load('selected_qa',base.I/'qualification_qa.py')
    rows=[]
    for short,rev,kind,ledger in value['allocations']:
        row=base.row_for(short,rev,kind,ledger,jobs[short]);display=report.qualification_row(row,base.I)
        if display.get('queue_failure'):qa.failed_queue_guard(display,base.I)
        elif display.get('queue_completion'):qa.completed_diagnostic_guard(display,base.I)
        elif display.get('diagnostic_result'):qa.no_model_diagnostic_guard(display,base.I)
        elif display.get('host_prerequisite'):qa.host_prerequisite_guard(display,base.I)
        base.save(out/(short+'.json'),row);rows.append(row)
    assert base.digest(base.HISTORY)==value['history_sha256'] and bindings()==bound['sources']
    base.save(out/'rows.json',rows)
    base.save(out/'verification.json',{'passed':True,'rows':len(rows),'run_ids':[r['run_id'] for r in rows],
        'sources':bound['sources'],'history_unchanged':True,'canonical_history_written':False,
        'active_outputs_read':False,'outcomes_recomputed':False,'reader_inputs':report.READS})
    print(json.dumps({'passed':True,'rows':len(rows)}))

if __name__=='__main__':main()
