"""Preserve model qualification policy and bind the native quiescence method."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
spec = importlib.util.spec_from_file_location('model_inventory_v11', HERE / 'prepare_model_v11.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def quiescence_inputs():
    sources = [Path(__file__), HERE / 'test_prepare_model_v12.py',
               CAMPAIGN / 'io-repair/NATIVE_THREAD_QUIESCENCE_V1.md']
    packet = CAMPAIGN / 'io-repair/native-shutdown-source-001'
    if not packet.is_dir() or len(list(packet.glob('*.rs'))) != 2:
        raise ValueError('Bounded native shutdown source packet is incomplete')
    sources += [p for p in packet.iterdir() if p.is_file()]
    sources += [RCI / 'isolation-session-9/native/app-server-schema/v2' / name for name in (
        'ThreadUnsubscribeParams.json', 'ThreadUnsubscribeResponse.json', 'ThreadClosedNotification.json',
        'TurnInterruptParams.json', 'TurnInterruptResponse.json', 'TurnCompletedNotification.json')]
    for path in sources:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked quiescence input: ' + str(path))
    return sorted({p.relative_to(REPO).as_posix() for p in sources})


def runtime_inputs():
    return sorted(set(prior.runtime_inputs()) | set(quiescence_inputs()))


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
