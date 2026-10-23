"""Preserve every model policy field; add the complete-process/read source closure."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
RCI=CAMPAIGN.parent
REPO=RCI.parents[1]
spec=importlib.util.spec_from_file_location('model_inventory_v23',HERE/'prepare_model_v23.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
READER_INPUTS=(
    'qualification/prepare_model_v24.py','qualification/test_prepare_model_v24.py',
    'io-repair/COMPLETE_PROCESS_AND_LITERAL_READS_V2.md',
    'assessment/retained_reads.py','assessment/completion_chronology.py',
    'assessment/canary_readback_proof.py','assessment/initial_read_composition.py',
    'assessment/test_smoke030_print_recipe.py',
)


def reader_inputs():
    paths=[CAMPAIGN/name for name in READER_INPUTS]
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise ValueError('Missing or linked complete-process/read source')
    return sorted(set(prior.reader_inputs())|{path.relative_to(REPO).as_posix() for path in paths})

def runtime_inputs():return sorted(set(prior.runtime_inputs())|set(reader_inputs()))

def prepare(kind,revision,run_id,seed,output):
    original=prior.runtime_inputs;inputs=runtime_inputs()
    try:
        prior.runtime_inputs=lambda:inputs
        return prior.prepare(kind,revision,run_id,seed,output)
    finally:prior.runtime_inputs=original

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=['smoke','stock','home'],required=True)
    parser.add_argument('--revision',required=True);parser.add_argument('--run-id',required=True)
    parser.add_argument('--seed',type=int,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    value=prepare(args.kind,args.revision,args.run_id,args.seed,args.output)
    print(json.dumps({'run_id':args.run_id,'kind':args.kind,'model_invocations':value['model_turns_max']}))

if __name__=='__main__':main()
