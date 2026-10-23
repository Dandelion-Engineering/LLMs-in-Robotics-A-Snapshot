"""Preserve model qualification policy and bind immediate native idle unload scheduling."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
spec = importlib.util.spec_from_file_location('model_inventory_v12', HERE / 'prepare_model_v12.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def unload_inputs():
    sources = [Path(__file__), HERE / 'test_prepare_model_v13.py',
               CAMPAIGN / 'io-repair/NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md',
               CAMPAIGN / 'io-repair/PREFLIGHT_V3_LIFECYCLE_JOIN_V1.md',
               CAMPAIGN / 'io-repair/codehost-channel-source-001/codex-rs__core__src__config__mod.rs',
               CAMPAIGN / 'io-repair/native-output-source-002/codex-rs__app-server__src__request_processors__thread_lifecycle.rs']
    packet = CAMPAIGN / 'io-repair/native-unsubscribe-source-001'
    for name in ('codex-rs__app-server__src__lib.rs',
                 'codex-rs__app-server__src__outgoing_message.rs',
                 'codex-rs__app-server__src__request_processors__thread_processor.rs',
                 'codex-rs__app-server__src__transport.rs',
                 'codex-rs__config__src__config_toml.rs',
                 'source-evidence.json', 'analysis.json', 'analysis.md'):
        sources.append(packet / name)
    for path in sources:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked unload scheduling input: ' + str(path))
    return sorted(set(prior.quiescence_inputs()) | {p.relative_to(REPO).as_posix() for p in sources})


def runtime_inputs():
    return sorted(set(prior.runtime_inputs()) | set(unload_inputs()))


def prepare(kind, revision, run_id, seed, output):
    # Change the inventory supplier only; use the unchanged policy constructor.
    original = prior.runtime_inputs
    inputs = runtime_inputs()
    try:
        prior.runtime_inputs = lambda: inputs
        return prior.prepare(kind, revision, run_id, seed, output)
    finally:
        prior.runtime_inputs = original


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind', choices=['smoke', 'stock', 'home'], required=True)
    p.add_argument('--revision', required=True); p.add_argument('--run-id', required=True)
    p.add_argument('--seed', type=int, required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    value = prepare(args.kind, args.revision, args.run_id, args.seed, args.output)
    print(json.dumps({'run_id': args.run_id, 'kind': args.kind, 'model_invocations': value['model_turns_max']}))


if __name__ == '__main__':
    main()
