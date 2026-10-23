"""Declare an immutable no-model boundary qualification; never execute it."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parent.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sources = (list((CAMPAIGN / 'harness').glob('*.py'))
               + list((CAMPAIGN / 'assessment').glob('*.py'))
               + list((CAMPAIGN.parent / 'readiness-session-10/assessment').glob('*.py'))
               + [HERE / name for name in ('boundary_suite.py', 'native_suite.py',
                                           'test_boundary_suite.py', 'prepare_boundary.py')])
    value = {
        'run_id': args.run_id, 'framework_revision': args.revision,
        'stage': 'diagnostic', 'mode': 'boundary-suite',
        'qualification_stage': 'no-model-isolation-control-continuity',
        'model_turns_max': 0,
        'runtime_input_files': [path.relative_to(REPO).as_posix() for path in sorted(sources)],
        'scope': 'Fresh no-model isolated boundary qualification of the exact production sources: captured executor bytes, protected control and continuity, unchanged canaries, and namespace retirement. No model timing or recovery score.'
    }
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'run_id': args.run_id, 'source_count': len(sources), 'model_calls': 0}))


if __name__ == '__main__':
    main()
