"""Bind the existing fixed synthetic declaration to its complete source inputs."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parent.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = json.loads(args.plan.read_text(encoding='utf-8'))
    if value.get('schema') != 'rci-recorder-journal-feasibility-1' or value.get('model_turns_max') != 0:
        raise ValueError('Expected the fixed no-model recorder declaration')
    required = [HERE / 'persist-feasibility' / name for name in
                ('candidate.py', 'benchmark.py', 'test_candidate.py', 'README.md')]
    required += [HERE / 'assess_recorder_feasibility.py', Path(__file__), args.plan.resolve()]
    required += [CAMPAIGN.parent / 'readiness-session-10/assessment' / name for name in
                 ('assess_bootstrap.py', 'assess_smoke.py', 'assess_pilot.py')]
    tests = list(HERE.glob('test_*recorder_feasibility*.py'))
    if not tests or any(not path.is_file() for path in required):
        raise ValueError('Prototype, independent assessor and tests must be ready before preparation')
    sources = set(required + tests + list((CAMPAIGN / 'harness').glob('*.py'))
                  + list((CAMPAIGN / 'assessment').glob('*.py')))
    value['runtime_input_files'] = sorted(path.resolve().relative_to(REPO).as_posix() for path in sources)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'run_id': value['run_id'], 'source_inputs': len(sources), 'model_calls': 0}))


if __name__ == '__main__':
    main()
