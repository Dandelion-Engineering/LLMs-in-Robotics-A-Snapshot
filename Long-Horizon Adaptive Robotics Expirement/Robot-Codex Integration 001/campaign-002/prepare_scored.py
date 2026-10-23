"""Prepare exactly twenty fresh manifests, never launch or retry an attempt."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
RCI=HERE.parent
REPO=RCI.parents[1]
spec=importlib.util.spec_from_file_location('c02_challenges',RCI/'host/challenges.py')
challenges=importlib.util.module_from_spec(spec);spec.loader.exec_module(challenges)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();frozen=json.loads(a.snapshot.read_text(encoding='utf-8'));revision=frozen['revision']
    if any(not (REPO/name).is_file() or sha(REPO/name)!=value['sha256'] for name,value in frozen['sources'].items()):
        raise ValueError('Frozen implementation changed')
    a.output.mkdir(parents=True,exist_ok=False);slots=[];attempts=[]
    for pair in range(1,11):
        families=['misplaced-stock','blocked-insert-home']
        if pair%2==0:families.reverse()
        for family in families:
            ordinal=len(slots)+1;code='stock' if family=='misplaced-stock' else 'home';run_id=f'RCI001-C02-{code}-{pair:02d}'
            m=challenges.make_manifest(family,'serve',run_id)
            m.update(seed=173,noise_seed=23000+ordinal,sim_cap_s=900,wall_cap_s=1100,storage_cap_bytes=536870912,
                model='gpt-6-astra',effort='max',bootstrap='Follow the instructions in RobotAgentPrompt.md.',
                model_turns_max=1,invocation_wall_cap_s=600,action_request_budget=20,observation_request_budget=50,
                interruption_trigger=None,prior_attempt=None,framework_revision=revision,
                outer_campaign_protocol='RCI001-Campaign002-v1',replicate=pair,
                scoring_scope='Prospective known-fixture repeatability; no held-out geometry or causal infrastructure benefit',
                runtime_workspace=str(Path(os.environ['LOCALAPPDATA'])/'RobotCodex'/'Campaign002'/run_id))
            challenges.validate_manifest(m);mp=a.output/(run_id+'.json');save(mp,m)
            slot={'ordinal':ordinal,'run_id':run_id,'family':family,'within_family_replicate':pair,
                  'world_seed':173,'noise_seed':23000+ordinal,'maximum_model_invocations':1,
                  'manifest':mp.name,'sha256':sha(mp),'runtime_workspace':m['runtime_workspace']}
            slots.append(slot)
            attempts.append({'ordinal':ordinal,'run_id':run_id,'family':family,'manifest':{'path':str(mp.resolve()),'sha256':sha(mp)},
                'workspace':m['runtime_workspace'],'evidence':str(RCI/'local-evidence/campaign002'/run_id/'orchestrator'),
                'host_evidence':str(RCI/'local-evidence/campaign002'/run_id/'host'),
                'storage_receipt':str(HERE/'execution'/run_id/'storage/receipt.json')})
    schedule={'schema':'campaign002-fixed-schedule-1','campaign_id':'RCI001-Campaign002','source_revision':revision,
       'prepared_at':datetime.now(timezone.utc).isoformat(),'attempt_count':20,'replacements_allowed':0,
       'plan_sha256':sha(HERE/'PLAN.md'),'source_snapshot_sha256':sha(a.snapshot),'slots':slots}
    save(a.output/'schedule.json',schedule)
    save(HERE/'execution-plan.json',{'schema':'campaign002-execution-plan-1','campaign_id':'RCI001-Campaign002',
         'framework_revision':revision,'release_revision':'RCI001-C02-frozen-001','attempts':attempts})
    print(json.dumps({'attempts':20,'source_revision':revision,'schedule_sha256':sha(a.output/'schedule.json')}))

if __name__=='__main__':main()
