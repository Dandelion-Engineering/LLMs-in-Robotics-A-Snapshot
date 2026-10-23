"""Exactly one v4 Baseline submission after independent pair verification."""
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
from attempts import HERE,ROOT,QUEUE,read,sha,save,inventory,append,base,ref

PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')

def main():
    preflight=ROOT/'preflight001/output/result.json';proof=read(preflight)
    q=read(HERE/'preflight001-queue.json')
    status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',q['id']],text=True,encoding='utf-8'))
    assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
    assert proof['passed'] and all(proof['checks'].values()) and proof['prepared_sha256']==sha(PAIR/'prepared.json')
    assert shutil.disk_usage(PAIR).free>=50*1024**3
    prepared=read(PAIR/'prepared.json');frozen=PAIR/'frozen_repository';code=frozen/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
    expected=read(frozen/'source-manifest.json');actual=inventory(frozen);actual.pop('source-manifest.json');assert actual==expected
    assert sha(frozen/'source-manifest.json')==prepared['source_manifest_sha256']
    authority=Path(prepared['human_authority']['uri']);assert sha(authority)==prepared['human_authority']['sha256']
    assert '**Randy (2026-10-09 14:50 PDT):**' in authority.read_text(encoding='utf-8')
    for condition in ('baseline','maps'):
        root=PAIR/condition;assert not read(root/'run.json')['launched']
        assert inventory(root/'filesystem')==read(root/'initial-filesystem.json')
        assert not any((root/n).exists() for n in ('running.lock','events.jsonl','sessions','latest-checkpoint.json'))
    for state in ('running','queued'):
        jobs=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'list','--state',state],text=True,encoding='utf-8'))
        assert not any('apartment-v4' in ' '.join(j['argv']).lower() for j in jobs), 'Duplicate v4 queue entry'
    subprocess.run([sys.executable,'-X','utf8','-B','-c','from run import verify_run;import sys;verify_run(sys.argv[1],True)',str(PAIR/'baseline')],cwd=code,check=True)
    operator=PAIR/'operator/launch-baseline';operator.mkdir(parents=True,exist_ok=False)
    argv=[sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(frozen),'--',sys.executable,'-X','utf8','-B',str(code/'run.py'),'launch','--root',str(PAIR/'baseline'),'--official']
    save(operator/'intent.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),argv=argv,authority_sha256=sha(authority),prepared_sha256=sha(PAIR/'prepared.json'),independent_preflight_sha256=sha(preflight),automatic_resubmission=False))
    response=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
    (operator/'queue-submit.stdout.txt').write_text(response.stdout,encoding='utf-8');(operator/'queue-submit.stderr.txt').write_text(response.stderr,encoding='utf-8')
    save(operator/'submission-process.json',dict(exit_status=response.returncode))
    if response.returncode:raise RuntimeError('Submission failed or uncertain; inspect retained response. Do not resubmit automatically.')
    q=json.loads(response.stdout);save(operator/'queue-submission.json',q);save(HERE/'official-queue-submission.json',q)
    append('note',base()|dict(id='APARTMENT-v4-baseline-launch-001',target_ids=['APARTMENT-v4-baseline'],claim_type='observation',supersedes_note_id=None,
        body='Fresh integrated commissioning and independent pristine-pair verification passed. The v4 Baseline was submitted exactly once under Randy October 9 14:50 PDT authority. This is submission only, not startup or endpoint success. Maps remains pristine and unlaunched; no automatic recovery or replacement is authorized.',
        evidence=[ref('Explicit ordered human authority',authority),ref('Unique submission intent',operator/'intent.json'),ref('Queue submission',operator/'queue-submission.json')],details=dict(queue_id=q['id'],root=str(PAIR/'baseline'))))
    print(json.dumps(dict(job=q['id'],state=q['state'],root=str(PAIR/'baseline'))))
if __name__=='__main__':main()
