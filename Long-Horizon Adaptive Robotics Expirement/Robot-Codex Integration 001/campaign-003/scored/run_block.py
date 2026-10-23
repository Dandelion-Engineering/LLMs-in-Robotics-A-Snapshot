"""Validate frozen allocation and prior dispositions before a scored block."""
import argparse
import json
from pathlib import Path
import sys

AREA=Path(__file__).resolve().parent
sys.path.insert(0,str(AREA.parent))
from common import sha
from runtime_limits import apply_limits
from scheduler import Schedule
from freeze import validate_allocation


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def check_manifest(path):
    path=Path(path).resolve();manifest=read(path);folder=path.parents[2]
    receipt=read(folder/'freeze-receipt.json');allocation=read(folder/'allocation.json')
    validate_allocation(allocation)
    assert manifest['stage']=='reviewed_campaign'
    assert manifest['revision_id']==receipt['revision_id']
    assert receipt['scored_model_calls_at_freeze']==0 and receipt['qualified_pilot_sources_unchanged'] is True
    key=path.relative_to(folder).as_posix();assert sha(path)==receipt['manifests'][key]
    for name,digest in receipt['manifests'].items():assert sha(folder/name)==digest,name
    ref=manifest['allocation_reference']
    assert Path(ref['path']).resolve()==(folder/'allocation.json').resolve()
    assert sha(folder/'allocation.json')==ref['sha256']==receipt['allocation_sha256']
    index=ref['replicate']-1;assert 0<=index<len(allocation['blocks'])
    block=allocation['blocks'][index];assert block['id']==ref['block_id']
    assert manifest['run_id']==manifest['revision_id']+'-'+block['id']+'-attempt'
    assert manifest['encounter_limit']==3 and manifest['no_replacement'] is True
    assert manifest['model']==dict(name='gpt-6-astra',effort='max',auth='chatgpt',
        bootstrap='Follow the instructions in RobotAgentPrompt.md.',fallback=False)
    expected=apply_limits(dict(run_id=manifest['run_id'],seed=block['seed'],noise_seed=block['noise_seed'],
        schedule_seed=block['schedule_seed'],encounters=3,initial_order=Schedule(block['schedule_seed'],3).current,
        mode='serve',stage='reviewed_campaign'),'reviewed_campaign')
    assert manifest['apparatus_manifest']==expected
    expected_output=AREA/'evidence'/manifest['run_id']
    assert Path(manifest['output']).resolve()==expected_output.resolve()
    assert not expected_output.exists(), 'Never replace an existing attempt'
    gate=manifest['prerequisite_audit']
    assert sha(gate['path'])==gate['sha256'] and sha(gate['official_status_path'])==gate['official_status_sha256']
    audit=read(gate['path']);official=read(gate['official_status_path'])
    assert audit['passed'] and audit['qualification_complete'] and audit['measurements']['terminal_appends']==3
    assert official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0
    for prior in allocation['blocks'][:index]:
        prior_run=manifest['revision_id']+'-'+prior['id']+'-attempt'
        audit_root=AREA/'audits'/prior_run
        status=read(audit_root/'official-status.json');assessment=read(audit_root/'assessment/receipt.json')
        assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
        assert assessment['passed'] and assessment['task_outcome'] in ('success','failure')
        assert assessment['measurements']['original_queue_state']=='succeeded'
        assert type(assessment['measurements']['original_queue_exit_status']) is int and assessment['measurements']['original_queue_exit_status']==0
        prior_manifest=folder/'blocks'/prior['id']/'manifest.json'
        assert assessment['source_manifest_sha256']==sha(prior_manifest)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');a=p.parse_args()
    m=check_manifest(a.manifest)
    # Import and launch only after all allocation/prior-disposition gates pass.
    from coordinator import run
    raise SystemExit(run(m['output'],a.manifest))
