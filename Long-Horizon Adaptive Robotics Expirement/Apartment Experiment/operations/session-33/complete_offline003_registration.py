"""Finish a source snapshot whose declaration was refused on a stale map digest.

The prior result-registration command had not finished when declaration began.
It is now complete; the refreshed map has no offline003 record. No test was
submitted by the refused declaration. Retain the same immutable snapshot.
"""
import json
from pathlib import Path
import subprocess
import sys

CODE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(CODE))
from common import DEFAULT_ROOT,REPO,inventory,read,save
from register import append,base,call,ref

identifier='APARTMENT-reliability-offline003'
root=DEFAULT_ROOT/'engineering'/identifier
assert inventory(root/'source')==read(root/'source-manifest.json')
assert not call('lookup','--id',identifier+'-revision','--json')['total']
assert not (root/'queue-submission.json').exists()
save(root/'registration-refusal.json',dict(reason='store changed since inspection',
    cause='Concurrent completion of offline002 result registration; awaited completion and verified no offline003 revision exists.',
    experiment_submitted_by_refused_call=False,immutable_source_reused=True))
append('revision',read(root/(identifier+'-revision.json')),root)
unknown=dict(state='unknown',refs=[],reason='Development qualification records installed environment and private fixture details in its result artifacts.')
recorded=dict(state='recorded',refs=[ref('Exact source snapshot',root/'source-manifest.json')],reason=None)
none=dict(state='none',refs=[],reason='No reasoning model used by this deterministic engineering attempt.')
append('run',{**base(identifier),'revision_id':identifier+'-revision','stage':'development','condition_id':'throwaway-apparatus',
    'protocol_id':'APARTMENT-commissioning-1','scenario_id':'private-engineering-fixtures','paired_block_id':'unpaired-engineering',
    'replicate':1,'started_at':None,'rerun_of_run_id':None,'condition_details':dict(official_schedule_consumed=False),
    'seeds':unknown,'frozen_refs':dict(code=recorded,environment=unknown,models=none,protocol=unknown,scenario=unknown),'evidence':[]},root)
receipt=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),
    'submit','--project','LLMs-in-Robotics','--cwd',str(REPO),'--',sys.executable,'-X','utf8','-B',str(root/'source/reliability_engineering.py'),
    '--output',str(root/'output')],text=True,encoding='utf-8'))
save(root/'queue-submission.json',receipt)
print(json.dumps(dict(submitted=identifier,queue_job=receipt['id'])))
