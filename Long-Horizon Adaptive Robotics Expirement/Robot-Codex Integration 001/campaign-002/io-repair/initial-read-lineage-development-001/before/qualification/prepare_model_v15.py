"""Preserve model policy; bind the authenticated native cleanup transport repair."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
spec = importlib.util.spec_from_file_location('model_inventory_v14', HERE / 'prepare_model_v14.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

CLEANUP_INPUTS = (
    'qualification/prepare_model_v15.py', 'qualification/test_prepare_model_v15.py',
    'io-repair/NATIVE_CLEANUP_CANCELLATION_V1.md',
    'io-repair/smoke-020-transport-failure-analysis.json',
    'io-repair/smoke-020-transport-failure-analysis.md',
    'harness/native_cleanup_protocol.py', 'harness/test_native_cleanup_protocol.py',
    'harness/native_quiescence.py', 'harness/test_client_quiescence.py',
    'harness/runtime.py', 'harness/test_native_owner_bootstrap.py',
    'harness/codehost_entry_v3.py', 'harness/test_codehost_entry_v3.py',
    'harness/codehost_mux_protocol.py', 'harness/test_codehost_mux_protocol.py',
    'harness/codehost_bridge_v3.py', 'harness/test_codehost_bridge_v3.py',
    'harness/codehost_inside_v3.py', 'harness/test_codehost_inside_v3.py',
    'assessment/cleanup_transport.py', 'assessment/test_cleanup_transport.py',
    'assessment/client_quiescence.py', 'assessment/test_client_quiescence.py',
    'assessment/transport_integrity_v3.py', 'assessment/test_transport_integrity_v3.py',
    'assessment/raw_tool_result_reads.py', 'assessment/test_raw_tool_result_reads.py',
    'assessment/literal_read_segments.py', 'assessment/test_literal_read_segments.py',
)


def cleanup_inputs():
    sources = [CAMPAIGN / name for name in CLEANUP_INPUTS]
    for path in sources:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked native cleanup input: ' + str(path))
    return sorted(set(prior.terminal_control_inputs()) | {p.relative_to(REPO).as_posix() for p in sources})


def runtime_inputs():
    return sorted(set(prior.runtime_inputs()) | set(cleanup_inputs()))


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
