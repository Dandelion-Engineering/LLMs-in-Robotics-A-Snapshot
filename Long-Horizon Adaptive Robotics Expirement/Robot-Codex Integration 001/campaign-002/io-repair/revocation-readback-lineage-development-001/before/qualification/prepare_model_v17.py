"""Preserve model policy; bind prepared startup-file result segments."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
spec = importlib.util.spec_from_file_location('model_inventory_v16', HERE / 'prepare_model_v16.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

PREPARED_STARTUP_INPUTS = (
    'qualification/prepare_model_v17.py',
    'qualification/test_prepare_model_v17.py',
    'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md',
    'io-repair/smoke-022-read-proof-diagnosis.json',
    'io-repair/smoke-022-read-proof-diagnosis.md',
    'assessment/prepared_result_segments.py',
    'assessment/test_prepared_result_segments.py',
    'assessment/prepared_startup_segments.py',
    'assessment/test_prepared_startup_segments.py',
    'io-repair/native-output-source-003/codex-rs__code-mode-protocol__src__description.rs',
    'io-repair/native-output-source-003/codex-rs__code-mode-protocol__src__lib.rs',
    'io-repair/native-output-source-003/codex-rs__code-mode-protocol__src__response.rs',
    'io-repair/native-output-source-003/codex-rs__code-mode-protocol__src__runtime.rs',
    'io-repair/native-output-source-003/codex-rs__code-mode__src__lib.rs',
    'io-repair/native-output-source-003/codex-rs__core__src__tools__code_mode__response_adapter.rs',
    'io-repair/native-output-source-003/codex-rs__core__src__unified_exec__mod.rs',
    'io-repair/native-output-source-003/codex-rs__utils__output-truncation__src__lib.rs',
    'io-repair/native-output-source-003/codex-rs__utils__string__src__lib.rs',
    'io-repair/native-output-source-003/codex-rs__utils__string__src__truncate.rs',
    'io-repair/native-output-source-003/findings.json',
    'io-repair/native-output-source-003/findings.md',
    'io-repair/native-output-source-003/LICENSE',
    'io-repair/native-output-source-003/manifest.json',
    'io-repair/native-output-source-003/NOTICE',
    'io-repair/native-output-source-003/source-evidence-001.json',
    'io-repair/native-output-source-003/source-evidence-002.json',
    'io-repair/native-output-source-003/source-evidence-003.json',
)


def prepared_startup_inputs():
    sources = [CAMPAIGN / name for name in PREPARED_STARTUP_INPUTS]
    for path in sources:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked prepared-startup input: ' + str(path))
    return sorted(set(prior.read_evidence_inputs()) | {p.relative_to(REPO).as_posix() for p in sources})


def runtime_inputs():
    return sorted(set(prior.runtime_inputs()) | set(prepared_startup_inputs()))


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
