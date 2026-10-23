"""Publish one verified history append; preserve all prior row bytes and exports."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import stage_rows as base

HERE=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',required=True);parser.add_argument('--job-id',required=True)
    parser.add_argument('--verification-sha256',required=True);parser.add_argument('--browser-qa',type=Path,required=True)
    args=parser.parse_args();candidate=HERE/args.candidate;assert candidate.parent==HERE
    official=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(base.QUEUE),'status',args.job_id],text=True,encoding='utf-8'))
    assert official['id']==args.job_id and official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0
    vpath=candidate/'verification.json';assert base.digest(vpath)==args.verification_sha256
    v=base.read(vpath);assert v['passed'] is True and v['prior_raw_rows_preserved'] is True and v['canonical_history_written'] is False
    assert v['active_outputs_read'] is False and v['outcomes_recomputed'] is False
    for path,sha in v['source_bindings'].items():assert base.digest(path)==sha
    browser=base.read(args.browser_qa)
    assert browser['passed'] is True and browser['candidate_verification_sha256']==args.verification_sha256
    for name in ('qualification-report.html','qualification-data.json','qualification-provenance.json','qualification-qa.json'):
        assert base.digest(candidate/'html'/name)==browser['files'][name]
    s=base.load('publication_span_tools',base.I/'v29-append-staging/stage_append.py')
    before=base.HISTORY.read_bytes();assert s.sha(before)==v['history_before_sha256']
    raw=(candidate/'candidate-history.json').read_bytes();assert s.sha(raw)==v['history_candidate_sha256']
    _,old_spans,_=s.raw_rows(before);_,new_spans,_=s.raw_rows(raw)
    assert len(old_spans)==v['prior_rows'] and len(new_spans)==v['rows']
    assert s.row_spans(new_spans[:len(old_spans)])==s.row_spans(old_spans)
    rows=json.loads(raw)['attempts'][len(old_spans):];assert [r['run_id'] for r in rows]==v['appended']
    exports=v['exports_preserved'];assert len(exports)==19 and all(s.bind(x['path'])==x for x in exports)
    folder=HERE/(args.candidate+'-publication');folder.mkdir(exist_ok=False)
    auth=folder/'official';auth.mkdir();jobs={}
    for row in rows:s.authenticate(row,auth,jobs)
    with (folder/'prior-history.json').open('xb') as f:f.write(before);f.flush();os.fsync(f.fileno())
    base.save(folder/'intent.json',{'created_at':datetime.now(timezone.utc).isoformat(),'candidate_job':official,
        'candidate_verification':s.bind(vpath),'browser_qa':s.bind(args.browser_qa),'publisher':s.bind(Path(__file__)),
        'prior_history_sha256':s.sha(before),'candidate_sha256':s.sha(raw),'appended':v['appended']})
    pending=folder/'history.pending'
    with pending.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    assert base.HISTORY.read_bytes()==before
    os.replace(pending,base.HISTORY)
    assert base.HISTORY.read_bytes()==raw and all(s.bind(x['path'])==x for x in exports)
    base.save(folder/'receipt.json',{'passed':True,'history':s.bind(base.HISTORY),'prior_raw_rows_preserved':len(old_spans),
        'rows':len(new_spans),'appended':v['appended'],'exports_preserved':exports,'active_outputs_read':False,'outcomes_recomputed':False})
    print(json.dumps({'published':True,'rows':len(new_spans),'prior_raw_rows_preserved':len(old_spans),'history':s.bind(base.HISTORY)}))

if __name__=='__main__':main()
