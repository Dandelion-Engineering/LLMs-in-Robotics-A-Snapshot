"""Preserve model policy; bind literal prepared-result index labels."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
spec = importlib.util.spec_from_file_location('model_inventory_v18', HERE / 'prepare_model_v18.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

INDEX_LABEL_INPUTS = (
    'qualification/prepare_model_v19.py',
    'qualification/test_prepare_model_v19.py',
    'io-repair/PREPARED_INDEX_LABELS_V1.md',
    'io-repair/smoke-024-read-diagnosis-001/analysis.json',
    'io-repair/smoke-024-read-diagnosis-001/analysis.md',
    'io-repair/smoke-024-read-diagnosis-001/authentication.json',
    'io-repair/smoke-024-read-diagnosis-001/diagnose.py',
    'io-repair/smoke-024-read-diagnosis-001/execution-001/diagnose-failed.py',
    'io-repair/smoke-024-read-diagnosis-001/execution-001/intent.json',
    'io-repair/smoke-024-read-diagnosis-001/execution-001/receipt.json',
    'io-repair/smoke-024-read-diagnosis-001/execution-001/stderr.txt',
    'io-repair/smoke-024-read-diagnosis-001/execution-001/stdout.txt',
    'io-repair/smoke-024-read-diagnosis-001/execution-002/intent.json',
    'io-repair/smoke-024-read-diagnosis-001/execution-002/receipt.json',
    'io-repair/smoke-024-read-diagnosis-001/execution-002/stderr.txt',
    'io-repair/smoke-024-read-diagnosis-001/execution-002/stdout.txt',
    'io-repair/smoke-024-read-diagnosis-001/official-status.json',
    'io-repair/smoke-024-read-diagnosis-001/official-status.stderr',
    'io-repair/smoke-024-read-diagnosis-001/official-status.stdout',
    'assessment/prepared_result_segments.py',
    'assessment/test_prepared_result_segments.py',
    'assessment/prepared_startup_segments.py',
    'assessment/test_prepared_startup_segments.py',
)


def index_label_inputs():
    sources = [CAMPAIGN / name for name in INDEX_LABEL_INPUTS]
    for path in sources:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked prepared-index-label input: ' + str(path))
    return sorted(set(prior.revocation_readback_inputs()) | {p.relative_to(REPO).as_posix() for p in sources})


def runtime_inputs():
    return sorted(set(prior.runtime_inputs()) | set(index_label_inputs()))


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
