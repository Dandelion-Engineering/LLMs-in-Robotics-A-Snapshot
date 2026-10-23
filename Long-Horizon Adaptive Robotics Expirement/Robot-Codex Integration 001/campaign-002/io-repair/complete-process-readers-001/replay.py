"""Diagnose three original gaps with revised readers; never rewrite a verdict."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
C=HERE.parents[1];REPO=HERE.parents[4]
sys.path.insert(0,str(C/'assessment'))
import retained_reads as reads
import literal_read_segments as literal
import initial_read_composition as initial
from canary_exit_proof import retained_file
JOB='20260930T183719742147Z-06b11f8b'

def identity(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return {'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def main():
    out=HERE/'diagnostic-replay-001.json';assert not out.exists()
    status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',JOB],text=True,encoding='utf-8'))
    assert status['id']==JOB and status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
    auth=load(C/'io-repair/smoke028-evidence-diagnosis-001/authentication.json')
    for name in ('assessment','manifest','snapshot'):
        item=auth['entry'][name];assert identity(item['path'])['sha256']==item['sha256']
    archive=auth['archive'];assert identity(archive['path'])==archive
    a=load(auth['entry']['assessment']['path']);original=identity(auth['entry']['assessment']['path'])
    root=Path(auth['entry']['evidence']);host=Path(auth['entry']['host_evidence'])
    history=[json.loads(x) for x in (host/'public-history.jsonl').read_text(encoding='utf-8').splitlines()]
    episode=load(host/'result.json')['public_episode_id']
    sources=[identity(p) for p in sorted((C/'assessment').glob('*.py'))]
    sources.append(identity(C/'io-repair/COMPLETE_PROCESS_AND_LITERAL_READS_V1.md'))
    answers={}
    stage=root/'interrupt';inv=a['invocations']['old']
    epoch=next(e['authority_epoch'] for e in history if e.get('type')=='invocation_start-invocation' and (e.get('payload',{}).get('invocation') or {}).get('invocation_id')==inv)
    audit=literal.assess_literal_reads(stage,host,archive['path'],episode,epoch,inv)
    selected=[p for p in audit['live']['live/activation.json'] if p['item_id']=='exec-3c0ba3cc-07a2-460a-bb7e-26df782fde2b']
    assert len(selected)==1
    answers['activation_late_exit']={'evidence':selected[0],'proof':audit['proofs'][selected[0]['proof_index']]}
    stage=root/'resume';inv=a['invocations']['new']
    epoch=next(e['authority_epoch'] for e in history if e.get('type')=='invocation_start-invocation' and (e.get('payload',{}).get('invocation') or {}).get('invocation_id')==inv)
    audit=initial.assess_initial_read_compositions(stage,host,archive['path'],episode,epoch,inv)
    selected=[p for p in audit['startup']['Continuity.md'] if p['item_id']=='exec-e5fa7fcf-c9ac-403e-b9a7-d7544a75c063']
    assert len(selected)==1,(audit['errors'],audit['startup'])
    answers['initial_continuity_prefix']={'evidence':selected[0],'proof':audit['proofs'][selected[0]['proof_index']]}
    events=[json.loads(x) for x in (stage/'client/events.jsonl').read_text(encoding='utf-8').splitlines()]
    commands,capture=reads.authenticated_commands(stage,events);assert capture['verified']
    target='notes/resume-boundary-observation.json'
    note=retained_file(load(stage/'runtime-before-close.json'),load(stage/'runtime-after-close.json'),target)
    matched=reads.canary_matches(commands,{target:note},load(stage/'canary-stdout.json'))
    assert len(matched)==1 and matched[0]['item_id']=='exec-63fbd134-37b5-410b-8331-f95db27ce075'
    answers['conditional_canary']=matched[0]
    assert original==identity(original['path']) and a['smoke_passed'] is False
    assert all(identity(p['path'])==p for p in sources)
    value={'schema':'campaign002-diagnostic-reader-replay-1','created_at':datetime.now(timezone.utc).isoformat(),
        'passed':True,'recognized_gaps':3,'official_status':status,'original_assessment':original,
        'original_verdict':'invalid/unknown;59/62;V30 stopped','source_bindings':sources,'findings':answers,
        'scope':'New reader development against retained inputs, not a full assessment or fresh qualification; no historical promotion.'}
    with out.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps({'passed':True,'recognized_gaps':3,'original_verdict_unchanged':True}))

if __name__=='__main__':main()
