"""Prepare the fixed, one-invocation metadata diagnostic; never launch or retry."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
RUN = 'RCI001-C02-shutdown-diagnostic-001'
REVISION = 'RCI001-C02-dev-055'
BASIS = CAMPAIGN / 'qualification/smoke-016-manifest.json'
OUTPUT = HERE / 'shutdown-diagnostic-001/manifest.json'


def identity(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def main():
    value = json.loads(BASIS.read_text(encoding='utf-8'))
    if value['run_id'] != 'RCI001-C02-smoke-016' or value['framework_revision'] != 'RCI001-C02-dev-054':
        raise ValueError('Unexpected diagnostic basis')
    if value['model_turns_max'] != 2 or value['invocation_wall_cap_s'] != 600:
        raise ValueError('Original smoke bounds changed')
    original = json.loads(json.dumps(value))
    value.update(run_id=RUN, framework_revision=REVISION, model_turns_max=1,
                 qualification_stage='campaign002-single-interrupt-diagnostic',
                 outer_campaign_protocol='RCI001-Campaign002-single-interrupt-diagnostic-v1',
                 runtime_workspace=str(Path(os.environ['LOCALAPPDATA']) / 'RobotCodex' / 'Campaign002' / 'diagnostic' / RUN))
    extra = [Path(__file__), HERE / 'control_shutdown_diagnostic.py', BASIS, HERE / 'SHUTDOWN_REJECTION_DIAGNOSTIC_V1.md',
             CAMPAIGN / 'qualification/launch.py',
             CAMPAIGN / 'admission/storage-policy.json', CAMPAIGN / 'admission/storage-baseline-001.json',
             RCI / 'campaign-001/admission/storage-guard/storage_guard.py']
    wrapper = HERE / 'single-interrupt-diagnostic'
    for name in ('run.py', 'launch.py'):
        if not (wrapper / name).is_file():
            raise ValueError('Diagnostic implementation missing: ' + name)
    extra += sorted(wrapper.glob('*.py'))
    value['runtime_input_files'] = sorted(set(value['runtime_input_files']) | {
        path.relative_to(REPO).as_posix() for path in extra})
    for name in value['runtime_input_files']:
        path = REPO / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or linked diagnostic input: ' + name)
    changed = sorted(k for k in value if value[k] != original.get(k))
    expected = ['framework_revision', 'model_turns_max', 'outer_campaign_protocol',
                'qualification_stage', 'run_id', 'runtime_input_files', 'runtime_workspace']
    if changed != expected:
        raise ValueError('Unexpected manifest change')
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    save(OUTPUT, value)
    save(OUTPUT.with_name('preparation-receipt.json'), {
        'schema': 'campaign002-single-interrupt-preparation-1', 'diagnostic_only': True,
        'run_id': RUN, 'framework_revision': REVISION, 'basis': identity(BASIS),
        'preparer': identity(Path(__file__)), 'declaration': identity(HERE / 'SHUTDOWN_REJECTION_DIAGNOSTIC_V1.md'),
        'manifest': identity(OUTPUT), 'changed_fields': changed,
        'added_runtime_inputs': sorted(set(value['runtime_input_files']) - set(original['runtime_input_files'])),
        'model_invocations_max': 1, 'resume_allowed': False, 'retry_allowed': False,
    })
    print(json.dumps({'manifest': identity(OUTPUT), 'changed_fields': changed}))


if __name__ == '__main__':
    main()
