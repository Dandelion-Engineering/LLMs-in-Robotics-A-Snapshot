"""Exactly one prospective initial baseline submission after successful freeze."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

CODE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(CODE))
from common import REPO,canonical,inventory,read,save,sha
from register import append,base,ref


def launch(pair):
    pair=pair.resolve();prepared=read(pair/'prepared.json');analysis=read(pair/'analysis-freeze.json')
    assert prepared['passed'] is True and prepared['revision_id']=='APARTMENT-v2-reliability-frozen'
    assert analysis['passed'] is True and analysis['frozen_before_official_launch'] is True
    assert analysis['prepared_sha256']==sha(pair/'prepared.json')
    assert sha(Path(analysis['analysis_path']))==analysis['analysis_sha256']
    frozen=pair/'frozen_repository';code=frozen/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
    expected=read(frozen/'source-manifest.json');actual=inventory(frozen);actual.pop('source-manifest.json')
    assert expected==actual and sha(frozen/'source-manifest.json')==prepared['source_manifest_sha256']
    authority=Path(prepared['human_authority']['uri'])
    assert sha(authority)==prepared['human_authority']['sha256']
    assert read(authority)['header']=='**Randy (2026-10-07 11:50 PDT):**'
    lineage=read(pair/'baseline-lineage.json');assert not lineage['history']
    assert Path(lineage['active_root']).resolve()==pair/'baseline'
    for condition in ('baseline','maps'):
        root=pair/condition;run=read(root/'run.json')
        assert run['launched'] is False and inventory(root/'filesystem')==read(root/'initial-filesystem.json')
        assert not any((root/name).exists() for name in ('running.lock','events.jsonl','sessions','latest-checkpoint.json'))
    validation=subprocess.run([sys.executable,'-X','utf8','-B','-c',
        'from run import verify_run; import sys; verify_run(sys.argv[1],True); print("Frozen baseline launch inputs verified")',str(pair/'baseline')],
        cwd=code,capture_output=True,text=True,encoding='utf-8',check=True)
    operator=pair/'operator/launch-baseline'
    operator.mkdir(parents=True,exist_ok=False)
    queue=REPO.parent/'tools/compute_queue/compute_queue.py'
    argv=[sys.executable,'-X','utf8','-B',str(queue),'submit','--project','LLMs-in-Robotics','--cwd',str(frozen),
          '--',sys.executable,'-X','utf8','-B',str(code/'run.py'),'launch','--root',str(pair/'baseline'),'--official']
    intent=dict(created_utc=datetime.now(timezone.utc).isoformat(),argv=argv,authority_sha256=sha(authority),
        prepared_sha256=sha(pair/'prepared.json'),analysis_freeze_sha256=sha(pair/'analysis-freeze.json'),
        preflight=validation.stdout.strip(),automatic_resubmission=False)
    save(operator/'intent.json',intent)
    response=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
    (operator/'queue-submit.stdout.txt').write_text(response.stdout,encoding='utf-8')
    (operator/'queue-submit.stderr.txt').write_text(response.stderr,encoding='utf-8')
    save(operator/'submission-process.json',dict(exit_status=response.returncode))
    if response.returncode:raise RuntimeError('Queue submission failed or is uncertain; inspect the retained response before any further action')
    status=json.loads(response.stdout);save(operator/'queue-submission.json',status)
    copy=Path(__file__).with_name('official-queue-submission.json');assert not copy.exists();save(copy,status)
    append('note',{**base('APARTMENT-v2-baseline-launch-001'),'tags':['apartment','baseline','official-submission'],
        'target_ids':['APARTMENT-v2-baseline'],'claim_type':'observation','supersedes_note_id':None,
        'body':'The commissioned fresh baseline was submitted once from the frozen D: source under the explicit October 7 11:50 PDT authority. This records submission only; startup health, terminal validity and scientific outcomes require separate evidence. Maps remains pristine and requires a later human instruction.',
        'details':dict(queue_job=status['id'],active_root=str(pair/'baseline')),
        'evidence':[ref('Explicit human launch and monitoring instruction',authority),ref('Unique submission intent',operator/'intent.json'),ref('Queue submission',operator/'queue-submission.json')]},operator)
    print(canonical(dict(job=status['id'],state=status['state'],root=str(pair/'baseline'),evidence=str(operator))).decode())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pair',type=Path,required=True);a=p.parse_args();launch(a.pair)
