"""Preserve model policy; bind the exact pilot retirement inventory repair."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
spec = importlib.util.spec_from_file_location('model_inventory_v19', HERE / 'prepare_model_v19.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

PILOT_RETIREMENT_INPUTS = (
    'qualification/prepare_model_v20.py',
    'qualification/test_prepare_model_v20.py',
    'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/authentication.json',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/collect-exit.json',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/collect.py',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/collect.stderr',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/collect.stdout',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.json',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.md',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/execution.json',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/official-status.json',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/official.stderr',
    'io-repair/pilot-stock024-lifecycle-diagnosis-001/official.stdout',
    'assessment/assess.py',
    'assessment/test_assess.py',
)


def pilot_retirement_inputs():
    sources = [CAMPAIGN / name for name in PILOT_RETIREMENT_INPUTS]
    for path in sources:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked pilot-retirement input: ' + str(path))
    return sorted(set(prior.index_label_inputs()) | {p.relative_to(REPO).as_posix() for p in sources})


def runtime_inputs():
    return sorted(set(prior.runtime_inputs()) | set(pilot_retirement_inputs()))


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
