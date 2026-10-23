"""Single-gap diagnostic replay; never reassess or promote original Smoke030."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent;C=HERE.parents[1];REPO=HERE.parents[4]
sys.path.insert(0,str(C/'assessment'))
import initial_read_composition as initial

def identity(p):
    p=Path(p);r=p.read_bytes();return {'path':str(p.resolve()),'sha256':hashlib.sha256(r).hexdigest(),'bytes':len(r)}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    out=HERE/'diagnostic-replay-001.json';assert not out.exists()
    job='20260930T201324760129Z-39fdac3e'
    official=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',job],text=True,encoding='utf-8'))
    assert official['id']==job and official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0
    auth=load(C/'io-repair/smoke030-read-diagnosis-001/authentication.json');e=auth['entry']
    for name in ('assessment','manifest','snapshot','queue'):
        assert identity(e[name]['path'])['sha256']==e[name]['sha256']
    archive=auth['inputs'][1];assert identity(archive['path'])==archive
    original=identity(e['assessment']['path']);a=load(original['path']);assert a['smoke_passed'] is False
    root=Path(e['evidence']);host=Path(e['host_evidence'])
    history=[json.loads(x) for x in (host/'public-history.jsonl').read_text(encoding='utf-8').splitlines()]
    inv=a['invocations']['new'];episode=load(host/'result.json')['public_episode_id']
    starts=[x for x in history if x.get('type')=='invocation_start-invocation' and x.get('payload',{}).get('invocation',{}).get('invocation_id')==inv]
    assert len(starts)==1
    audit=initial.assess_initial_read_compositions(root/'resume',host,archive['path'],episode,starts[0]['authority_epoch'],inv)
    selected=[p for p in audit['startup']['Continuity.md'] if p['item_id']=='exec-132cc072-41fb-47a1-879f-6b900f199358']
    assert len(selected)==1,(audit['errors'],audit['startup'])
    assert original==identity(original['path'])
    value={'schema':'campaign002-diagnostic-reader-replay-1','created_at':datetime.now(timezone.utc).isoformat(),
        'passed':True,'recognized_gaps':1,'official_status':official,'original_assessment':original,
        'original_verdict':'invalid/unknown;61/62;V32 stopped',
        'source_bindings':[identity(C/'assessment/initial_read_composition.py'),identity(C/'io-repair/COMPLETE_PROCESS_AND_LITERAL_READS_V2.md')],
        'evidence':selected[0],'proof':audit['proofs'][selected[0]['proof_index']],
        'scope':'Prospective reader diagnosis only; no full reassessment or historical promotion.'}
    with out.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps({'passed':True,'recognized_gaps':1,'original_verdict_unchanged':True}))

if __name__=='__main__':main()
