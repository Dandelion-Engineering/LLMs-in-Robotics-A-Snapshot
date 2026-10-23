"""Preserve one failed boundary result and diagnostic lifecycle receipts."""
import json
import subprocess
import sys
from pathlib import Path
import collect as a

def main():
    job = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B',
        str(a.REPO.parent/'tools/compute_queue/compute_queue.py'), 'status', a.JOB],
        text=True, encoding='utf-8'))
    assert job == json.loads((a.HERE/'official-status.json').read_text(encoding='utf-8'))
    root=Path(job['argv'][-1])/'runtime'; rows=[]
    for path in sorted(root.glob('*retirement.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        rows.append({'input':a.identity(path),'qualified':data.get('qualified'),'error':data.get('error')})
    assert len(rows)==4 and all(x['qualified'] is True for x in rows)
    a.save('retirement-diagnostics.json',{'records':rows,'scope':'Failed queue diagnostic; no qualification.'})
    reason='Boundary reader import failed: missing completion_chronology sibling in standalone runner. No model launched; original failed queue preserved. Fresh-process import repair and new full qualification required.'
    a.save('terminal-result.json',{'run_id':'RCI001-C02-boundary-031','framework_revision':'RCI001-C02-dev-105',
        'ended_at':job['ended_at'],'diagnostic_only':True,'scorable':False,'task_outcome':'unknown',
        'assessment_state':'infrastructure_only','reason':reason,
        'authentication':a.identity(a.HERE/'authentication.json'),'observations':a.identity(a.HERE/'observations.json'),
        'findings':a.identity(a.HERE/'FINDINGS.md'),'retirement':a.identity(a.HERE/'retirement-diagnostics.json')})
    map_root=a.C.parent.parent/'Architecture Map'
    names=['architectures','revisions','runs','results','notes']
    before={n:(map_root/(n+'.jsonl')).read_bytes() for n in names}
    assert not any(json.loads(x)['run_id']=='RCI001-C02-boundary-031' for x in before['results'].splitlines())
    cmd=[sys.executable,'-X','utf8','-B',str(a.C/'registry_session19.py'),'finish',
        '--run-id','RCI001-C02-boundary-031','--result',str(a.HERE/'terminal-result.json'),
        '--queue-receipt',str(a.HERE/'official-status.json'),'--validity','invalid',
        '--outcome','unknown','--reason',reason,'--execution','failed']
    proc=subprocess.run(cmd,cwd=a.REPO,capture_output=True,text=True,encoding='utf-8',check=True)
    for n,raw in before.items():
        current=(map_root/(n+'.jsonl')).read_bytes();assert current.startswith(raw)
        if n=='results': assert len(current[len(raw):].splitlines())==1
        else: assert current==raw
    a.save('settlement.json',{'argv':cmd,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,
        'existing_records_preserved':True,'exactly_one_result_added':True})
    print(proc.stdout)

if __name__=='__main__':main()
