"""Write the unchanged model qualification manifest with complete method inputs.

This prospective preparer adds source/method inventory only. It never launches
models or changes task policy, clocks, limits, seeds, or evidence locations.
The original prepare_model.py remains the reference for manifest semantics.
"""
import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
METHOD_FILES = ('io-repair/DESIGN.md', 'io-repair/READ_EVIDENCE_V2.md',
                'io-repair/TRANSPORT_EVIDENCE_V2.md', 'io-repair/PROCESS_SEQUENCE_EVIDENCE_V1.md',
                'io-repair/CONVENTIONAL_ADMISSION_ORDER_V1.md',
                'io-repair/RAW_TOOL_RESULT_EVIDENCE_V1.md',
                'io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md',
                'io-repair/CHANNEL_TRANSPORT_V3_QUALIFICATION_001.md',
                'io-repair/CHANNEL_TRANSPORT_STARTUP_REPAIR_V1.md')

SOURCE_EVIDENCE = 'io-repair/native-output-source-002'
CHANNEL_EVIDENCE = 'io-repair/codehost-channel-source-001'
RAW_SCHEMA = 'isolation-session-9/native/app-server-schema/v2/RawResponseItemCompletedNotification.json'


def runtime_inputs():
    """Preserve every v1 source, then add the preparers, test and method text."""
    sources = (list((CAMPAIGN / 'harness').glob('*.py'))
               + list((CAMPAIGN / 'assessment').glob('*.py'))
               + list((RCI / 'readiness-session-10/assessment').glob('*.py'))
               + [HERE / 'native_suite.py', CAMPAIGN / 'transport-repair.md',
                  CAMPAIGN / 'timing-repair.md', HERE / 'smoke-001-read-diagnosis.md',
                  HERE / 'prepare_model.py', HERE / 'prepare_model_v2.py',
                  HERE / 'test_prepare_model_v2.py', HERE / 'prepare_model_v3.py',
                  HERE / 'test_prepare_model_v3.py', HERE / 'prepare_model_v4.py',
                  HERE / 'test_prepare_model_v4.py', HERE / 'prepare_model_v5.py',
                  HERE / 'test_prepare_model_v5.py', HERE / 'prepare_model_v6.py',
                  HERE / 'test_prepare_model_v6.py', HERE / 'prepare_model_v7.py',
                  HERE / 'test_prepare_model_v7.py']
               + [CAMPAIGN / name for name in METHOD_FILES])
    evidence = CAMPAIGN / SOURCE_EVIDENCE
    if not evidence.is_dir() or not list(evidence.glob('*.json')) or not list(evidence.glob('*.rs')):
        raise ValueError('Required native evidence directory is absent or incomplete')
    sources += [p for p in evidence.iterdir() if p.is_file()] + [RCI / RAW_SCHEMA]
    channel = CAMPAIGN / CHANNEL_EVIDENCE
    if not channel.is_dir() or not (channel / 'source-evidence.json').is_file() or not list(channel.glob('*.rs')):
        raise ValueError('Required native channel evidence is absent or incomplete')
    sources += [p for p in channel.iterdir() if p.is_file()]
    for folder in (CAMPAIGN / 'harness', CAMPAIGN / 'assessment', RCI / 'readiness-session-10/assessment'):
        if not folder.is_dir() or not list(folder.glob('*.py')):
            raise ValueError('Runtime source directory absent or empty: ' + str(folder))
    for source in sources:
        if not source.is_file() or source.is_symlink():
            raise ValueError('Required runtime/method source absent or linked: ' + str(source))
    return sorted({path.relative_to(REPO).as_posix() for path in sources})


def prepare(kind, revision, run_id, seed, output):
    if kind not in ('smoke', 'stock', 'home'):
        raise ValueError('Unknown model qualification kind')
    source = (RCI / 'readiness-session-10/records/smoke-002-manifest.json' if kind == 'smoke'
              else RCI / ('campaign-001/predeclared-v1/RCI001-C01-' + kind + '-01.json'))
    value = json.loads(source.read_text(encoding='utf-8'))
    value.update(run_id=run_id, framework_revision=revision, noise_seed=seed, prior_attempt=None,
                 qualification_stage='campaign002-' + kind + '-qualification',
                 outer_campaign_protocol='RCI001-Campaign002-qualification-v1')
    value['runtime_workspace'] = str(Path(os.environ['LOCALAPPDATA']) / 'RobotCodex' / 'Campaign002' / 'qualification' / run_id)
    value['runtime_input_files'] = runtime_inputs()
    with Path(output).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['smoke', 'stock', 'home'], required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    value = prepare(args.kind, args.revision, args.run_id, args.seed, args.output)
    print(json.dumps({'run_id': args.run_id, 'kind': args.kind, 'model_invocations': value['model_turns_max']}))


if __name__ == '__main__':
    main()
