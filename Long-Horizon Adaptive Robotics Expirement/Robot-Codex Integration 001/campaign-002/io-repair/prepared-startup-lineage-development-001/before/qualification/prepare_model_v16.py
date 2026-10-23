"""Preserve model policy; bind initial-read composition and completion chronology."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
spec = importlib.util.spec_from_file_location('model_inventory_v15', HERE / 'prepare_model_v15.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

READ_EVIDENCE_INPUTS = (
    'qualification/prepare_model_v16.py', 'qualification/test_prepare_model_v16.py',
    'io-repair/READ_EVIDENCE_V3.md',
    'io-repair/smoke-021-read-proof-diagnosis.json',
    'io-repair/smoke-021-read-proof-diagnosis.md',
    'io-repair/smoke-021-chronology-analysis.json',
    'io-repair/smoke-021-chronology-analysis.md',
    'io-repair/smoke-021-chronology-development-001/counterexample.py',
    'io-repair/smoke-021-chronology-development-001/receipt.json',
    'io-repair/smoke-021-chronology-development-001/stdout.txt',
    'io-repair/smoke-021-chronology-development-001/stderr.txt',
    'io-repair/smoke-021-chronology-development-001/official-status.json',
    'io-repair/native-unsubscribe-source-001/codex-rs__app-server__src__outgoing_message.rs',
    'io-repair/native-output-source-001/codex-rs__core__src__unified_exec__process.rs',
    'io-repair/native-output-source-001/codex-rs__core__src__unified_exec__process_manager.rs',
    'io-repair/native-output-source-001/codex-rs__core__src__unified_exec__async_watcher.rs',
    'assessment/completion_chronology.py', 'assessment/test_completion_chronology.py',
    'assessment/initial_read_composition.py', 'assessment/test_initial_read_composition.py',
    'assessment/literal_read_segments.py', 'assessment/test_literal_read_segments.py',
    'assessment/empty_startup_reads.py', 'assessment/test_empty_startup_reads.py',
    'assessment/canary_exit_proof.py', 'assessment/test_canary_exit_proof.py',
    'assessment/assess_smoke_v2.py', 'assessment/test_smoke_v2.py',
)


def read_evidence_inputs():
    sources = [CAMPAIGN / name for name in READ_EVIDENCE_INPUTS]
    for path in sources:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked initial-read evidence input: ' + str(path))
    return sorted(set(prior.cleanup_inputs()) | {p.relative_to(REPO).as_posix() for p in sources})


def runtime_inputs():
    return sorted(set(prior.runtime_inputs()) | set(read_evidence_inputs()))


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
