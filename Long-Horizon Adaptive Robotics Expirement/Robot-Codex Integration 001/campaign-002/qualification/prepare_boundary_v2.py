"""Freeze every source the unchanged boundary suite actually measures.

Boundary004 remains invalid: its receipt included assessment/README.md while
its snapshot did not. This preparer changes inventory closure only; it neither
changes the suite nor relaxes the admission comparison.
"""
import argparse
import json
from pathlib import Path

import boundary_suite

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parent.parents[1]


def inventory():
    # Retain the earlier explicit import/test inputs and add the complete
    # measured inventory, including markdown and any nested source modules.
    sources = set((CAMPAIGN / 'harness').glob('*.py'))
    sources.update((CAMPAIGN / 'assessment').glob('*.py'))
    sources.update((CAMPAIGN.parent / 'readiness-session-10/assessment').glob('*.py'))
    sources.update(HERE / name for name in ('boundary_suite.py', 'native_suite.py',
        'test_boundary_suite.py', 'prepare_boundary.py', 'prepare_boundary_v2.py',
        'test_prepare_boundary_v2.py'))
    sources.update(REPO / name for name in boundary_suite.sources())
    if not all(path.is_file() for path in sources):
        raise ValueError('Boundary inventory contains a missing file')
    return sorted(path.relative_to(REPO).as_posix() for path in sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sources = inventory()
    value = {
        'run_id': args.run_id, 'framework_revision': args.revision,
        'stage': 'diagnostic', 'mode': 'boundary-suite',
        'qualification_stage': 'no-model-isolation-control-continuity',
        'model_turns_max': 0, 'runtime_input_files': sources,
        'scope': 'Fresh no-model isolated boundary qualification of the unchanged production sources, with complete measured source inventory including markdown. Captured executor bytes, protected control and continuity, unchanged canaries, and namespace retirement. No model timing or recovery score.'
    }
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'run_id': args.run_id, 'source_count': len(sources), 'model_calls': 0}))


if __name__ == '__main__':
    main()
