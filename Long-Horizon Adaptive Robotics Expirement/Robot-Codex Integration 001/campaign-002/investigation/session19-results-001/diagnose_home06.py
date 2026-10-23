"""Bounded infrastructure-only inspection of the failed official queue attempt."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
I=HERE.parent
C=I.parent
REPO=I.parents[3]
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
E=C.parent/'local-evidence/campaign002/RCI001-C02-home-06'
OUT=HERE/'home06-diagnostic-001'
JOB='20260930T231138503466Z-c3a5f10f'

def binding(p):
    raw=p.read_bytes()
    return {'path':str(p.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def main():
    assert not OUT.exists()
    receipt=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',JOB],text=True,encoding='utf-8'))
    assert receipt['state']=='failed' and type(receipt['exit_status']) is int and receipt['exit_status']==1
    OUT.mkdir()
    selected={}
    inputs=[]
    fields={
      'host/result.json':['run_id','execution_completed','error','continuous_physics'],
      'host/timing-v2.json':['schema','sample_file','sha256','byte_count','sample_count','maximum_sample','phases','slow_phases','slow_phases_by_name','scope'],
      'host/supervisory-diagnostics/timing-v2.json':['schema','sample_file','sha256','byte_count','sample_count','maximum_sample','phases','slow_phases','slow_phases_by_name','scope'],
      'orchestrator/sequence-result.json':['orchestrator_completed','host_exit_code','error','forced_host_exit','stop_error'],
      'orchestrator/pilot/stage-result.json':['all_namespaces_retired','watchdog_errors','retirement_error','old_token_check_error','cleanup_clean','durable_retention_verified'],
      'orchestrator/pilot/cleanup.json':['clean','errors'],
      'orchestrator/pilot/codehost-owner-retirement-v3.json':['qualified','normal_wait_timed_out','windows_wrapper_killed_after_linux_retired','windows_exit_code','elapsed_seconds'],
      'orchestrator/pilot/mirror-error.json':['wall_unix_s','method','path','type','error','phase','authority_revocation_established'],
    }
    for name,keys in fields.items():
        p=E/name
        d=json.loads(p.read_text(encoding='utf-8'))
        selected[name]={k:d[k] for k in keys if k in d}
        inputs.append(binding(p))
    # Worker error and lease are infrastructure diagnostics; remove terminal
    # and metrics fields so failed execution never supplies task results.
    cp=selected['host/result.json']['continuous_physics']
    selected['host/result.json']['continuous_physics']={k:cp[k] for k in ('schema','error','heartbeat_timeout_s','owner_finished','queue_bytes','queue_count','rpc_count') if k in cp}
    assert selected['host/result.json']['error']['message'].startswith('Physics owner failure:')
    sources=[binding(C/'harness'/name) for name in ('physical.py','physics_worker.py','continuous_adapter.py','run_host.py')]
    proof={'schema':'campaign002-failed-slot-infrastructure-inspection-1','created_at':datetime.now(timezone.utc).isoformat(),'official_queue':receipt,'inputs':inputs,'sources':sources,'selected_infrastructure':selected,'scorable':False,'task_outcome':'unknown','original_disposition_unchanged':binding(C/'execution/RCI001-C02-home-06/disposition.json'),'scope':'Infrastructure diagnosis only; no task evaluator, model transcript, public world outcome, image, timing qualification or replacement assessment consumed or produced.'}
    (OUT/'inspection.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'diagnostic_complete':True,'task_outcome':'unknown','output':str(OUT)}))

if __name__=='__main__':main()
