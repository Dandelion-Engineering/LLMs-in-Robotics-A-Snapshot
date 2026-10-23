"""Preserve model policy; bind epoch revocation and canary readback evidence."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
spec = importlib.util.spec_from_file_location('model_inventory_v17', HERE / 'prepare_model_v17.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

REVOCATION_READBACK_INPUTS = (
    'qualification/prepare_model_v18.py',
    'qualification/test_prepare_model_v18.py',
    'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md',
    'io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md',
    'io-repair/smoke-023-read-proof-diagnosis.json',
    'io-repair/smoke-023-read-proof-diagnosis.md',
    'io-repair/smoke-023-transport-diagnosis.json',
    'io-repair/smoke-023-transport-diagnosis.md',
    'io-repair/smoke-023-canary-diagnosis.json',
    'assessment/canary_readback_proof.py',
    'assessment/test_canary_readback_proof.py',
)


def revocation_readback_inputs():
    sources = [CAMPAIGN / name for name in REVOCATION_READBACK_INPUTS]
    for path in sources:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked revocation/readback input: ' + str(path))
    return sorted(set(prior.prepared_startup_inputs()) | {p.relative_to(REPO).as_posix() for p in sources})


def runtime_inputs():
    return sorted(set(prior.runtime_inputs()) | set(revocation_readback_inputs()))


def prepare(kind, revision, run_id, seed, output):
    original = prior.runtime_inputs
    inputs = runtime_inputs()
    try:
        prior.runtime_inputs = lambda: inputs
        return prior.prepare(kind, revision, run_id, seed, output)
    finally:
        prior.runtime_inputs = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['smoke', 'stock', 'home'], required=True)
    parser.add_argument('--revision', required=True); parser.add_argument('--run-id', required=True)
    parser.add_argument('--seed', type=int, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = prepare(args.kind, args.revision, args.run_id, args.seed, args.output)
    print(json.dumps({'run_id': args.run_id, 'kind': args.kind, 'model_invocations': value['model_turns_max']}))


if __name__ == '__main__': main()
