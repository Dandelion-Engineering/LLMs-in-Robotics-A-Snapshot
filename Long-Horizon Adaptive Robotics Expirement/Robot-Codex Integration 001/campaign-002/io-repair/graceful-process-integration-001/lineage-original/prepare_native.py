"""Prepare one immutable six-episode apparatus qualification, without execution."""
import argparse
import importlib.util
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
RCI=CAMPAIGN.parent
REPO=RCI.parents[1]
spec=importlib.util.spec_from_file_location('c02_challenges',RCI/'host/challenges.py')
challenges=importlib.util.module_from_spec(spec);spec.loader.exec_module(challenges)

METHOD_FILES=('io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md',
              'io-repair/CHANNEL_TRANSPORT_STARTUP_REPAIR_V1.md',
              'io-repair/CHANNEL_PROBE_PROCESS_IDENTITY_V1.md',
              'io-repair/CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',
              'io-repair/CHANNEL_PROBE_SEQUENCE_SYNCHRONIZATION_V1.md',
              'io-repair/CHANNEL_OWNER_DRAIN_V1.md',
              'io-repair/NATIVE_THREAD_QUIESCENCE_V1.md',
              'io-repair/NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md',
              'io-repair/NORMAL_CLOSED_CANCEL_V1.md',
              'io-repair/NATIVE_CLEANUP_CANCELLATION_V1.md',
              'io-repair/READ_EVIDENCE_V3.md',
              'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md',
              'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md',
              'io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md',
              'io-repair/PREPARED_INDEX_LABELS_V1.md',
              'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md')

def inventory():
    spec=importlib.util.spec_from_file_location('native_quiescence_inventory',HERE/'prepare_model_v21.py')
    extra=importlib.util.module_from_spec(spec);spec.loader.exec_module(extra)
    sources=(list((CAMPAIGN/'harness').glob('*.py'))
             +list((CAMPAIGN/'assessment').glob('*.py'))
             +list((RCI/'readiness-session-10/assessment').glob('*.py'))
             +[HERE/'native_suite.py', HERE/'assess_native.py', Path(__file__),
               HERE/'test_prepare_native.py']
             +[CAMPAIGN/name for name in METHOD_FILES]
             +[REPO/name for name in extra.pre_exit_inputs()])
    if any(not path.is_file() or path.is_symlink() for path in sources):
        raise ValueError('Native inventory contains a missing or linked source')
    return sorted(set(sources))

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seed-base',type=int,default=24000)
    a=p.parse_args();slots=[]
    for index in range(6):
        family=('misplaced-stock','blocked-insert-home')[index%2]
        run_id=a.run_id+'-'+('stock' if index%2==0 else 'home')+'-'+str(index//2+1)
        manifest=challenges.make_manifest(family,'reference',run_id)
        manifest.update(seed=173,noise_seed=a.seed_base+index+1,sim_cap_s=240,wall_cap_s=420,storage_cap_bytes=209715200,
                        framework_revision=a.revision,qualification_stage='no-model-reference')
        challenges.validate_manifest(manifest)
        workspace=Path(os.environ['LOCALAPPDATA'])/'RobotCodex'/'Campaign002'/'qualification'/run_id
        slots.append({'run_id':run_id,'manifest':manifest,'workspace':str(workspace)})
    sources=inventory()
    value={'run_id':a.run_id,'framework_revision':a.revision,'stage':'development-only','mode':'native-reference-suite',
           'qualification_stage':'six-no-model-reference-episodes','model_turns_max':0,'slots':slots,
           'runtime_input_files':[p.relative_to(REPO).as_posix() for p in sorted(sources)],
           'scope':'Apparatus qualification with protected reference control, not Robot-Codex success evidence'}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps({'run_id':a.run_id,'slots':6,'model_calls':0}))

if __name__=='__main__':main()
