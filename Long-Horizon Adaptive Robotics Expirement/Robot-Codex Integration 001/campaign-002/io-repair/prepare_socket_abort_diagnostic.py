"""Prepare the declared single interruption diagnostic; never freeze or launch."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
RUN = 'RCI001-C02-shutdown-diagnostic-003'
REVISION = 'RCI001-C02-dev-091'
BASIS = CAMPAIGN / 'qualification/smoke-026-manifest.json'
BASIS_SHA = '0d6bfb4a1180f53dba8e784cdd4ef68d7d1fedef4ca7d74015b424a66380f142'
OUTPUT = HERE / 'shutdown-diagnostic-003/manifest.json'
WRAPPER = HERE / 'single-interrupt-diagnostic-v3'
METHOD = HERE / 'SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md'
CHANGED_FIELDS = ['framework_revision', 'model_turns_max', 'outer_campaign_protocol',
                  'qualification_stage', 'run_id', 'runtime_input_files', 'runtime_workspace']
WRAPPER_RECEIPT = WRAPPER / 'development/authenticated-final-001/receipt.json'
CONTROL_RECEIPT = HERE / 'socket-abort-native-control-development-001/final-checks-002/receipt.json'
SUPPORT_INPUTS = (
    'SOCKET_ABORT_DIAGNOSTICS_V1.md', 'SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md',
    'socket-abort-instrumentation-development-001/final-check-002/receipt.json',
    'socket-abort-instrumentation-development-001/final-check-002/source-parity.json',
    'socket-abort-assessment-fixture-development-001/DECLARATION.md',
    'socket-abort-assessment-fixture-development-001/final-receipt.json',
    'socket-abort-assessment-fixture-development-001/before.json',
    'socket-abort-assessment-fixture-development-001/receipt.json',
    'socket-abort-assessment-fixture-development-001/focused.stdout',
    'socket-abort-assessment-fixture-development-001/focused.stderr',
    'socket-abort-assessment-fixture-development-001/focused-002/receipt.json',
    'socket-abort-assessment-fixture-development-001/focused-002/stdout',
    'socket-abort-assessment-fixture-development-001/focused-002/stderr',
    'checks-033/test-execution.json', 'checks-033-source-state.json',
    'checks-033-execution-001/receipt.json', 'checks-033-execution-001/intent.json',
    'checks-033-execution-001/stdout.txt', 'checks-033-execution-001/stderr.txt',
    'checks-033/harness.stdout', 'checks-033/harness.stderr',
    'checks-033/assessment.stdout', 'checks-033/assessment.stderr', 'record_checks.py',
)


def require(value, message):
    if value is not True:
        raise ValueError(message)


def identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Ordinary input required: ' + str(path))
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def read(path):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    identity(path)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def load_wrapper():
    spec = importlib.util.spec_from_file_location('socket_abort_diagnostic_common', WRAPPER / 'common.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checked_path(path):
    path = Path(path)
    require(path.resolve().is_relative_to(REPO.resolve()) and not path.is_symlink(),
            'Input escapes repository or is linked')
    identity(path)
    return path.resolve()


def inputs():
    """Finite runtime, operator and test provenance closure; no result traversal."""
    common = load_wrapper()
    paths = {checked_path(REPO / name) for name in common.required_inputs()}
    paths.update(HERE / name for name in SUPPORT_INPUTS)
    paths.update([Path(__file__), HERE / 'control_socket_abort_diagnostic.py',
                  HERE / 'test_control_socket_abort_diagnostic.py', BASIS,
                  WRAPPER_RECEIPT, CONTROL_RECEIPT, CAMPAIGN / 'qualification/launch.py',
                  CAMPAIGN / 'qualification/run_final_qualification_v28.py',
                  CAMPAIGN / 'registry.py', CAMPAIGN / 'operate.py', CAMPAIGN / 'admission.py',
                  CAMPAIGN / 'PLAN.md', RCI / 'readiness-session-10/registration/register.py',
                  RCI.parent / 'Architecture Map/map.py',
                  CAMPAIGN / 'admission/storage-policy.json', CAMPAIGN / 'admission/storage-baseline-001.json',
                  RCI / 'campaign-001/admission/storage-guard/storage_guard.py'])
    # Freeze every source held around full checks, including operator dependencies.
    state = read(HERE / 'checks-033-source-state.json')
    require(state.get('passed') is True and state.get('sources_unchanged') is True,
            'Full checks source state is not passing')
    for item in state['sources']:
        path = checked_path(item['path'])
        require(identity(path)['sha256'] == item['sha256'], 'Full-check source changed')
        paths.add(path)
    for receipt_path in (WRAPPER_RECEIPT, CONTROL_RECEIPT):
        receipt = read(receipt_path)
        require(receipt.get('passed') is True, 'Final wrapper/control checks missing')
        # Only actual command output identities, not arbitrary referenced evidence.
        for command in receipt.get('commands', []):
            for key in ('stdout', 'stderr'):
                item = command[key]
                path = checked_path(item['path'])
                require(identity(path)['sha256'] == item['sha256'], 'Final test output changed')
                paths.add(path)
    return sorted({checked_path(path).relative_to(REPO).as_posix() for path in paths})


def build_manifest(basis, additions):
    require(basis.get('run_id') == 'RCI001-C02-smoke-026'
            and basis.get('framework_revision') == 'RCI001-C02-dev-090'
            and type(basis.get('model_turns_max')) is int and basis['model_turns_max'] == 2
            and type(basis.get('invocation_wall_cap_s')) is int and basis['invocation_wall_cap_s'] == 600,
            'Unexpected original smoke identity or bounds')
    value = json.loads(json.dumps(basis, allow_nan=False))
    value.update(run_id=RUN, framework_revision=REVISION, model_turns_max=1,
                 qualification_stage='campaign002-single-interrupt-diagnostic',
                 outer_campaign_protocol='RCI001-Campaign002-single-interrupt-diagnostic-v3',
                 runtime_workspace=str(Path(os.environ['LOCALAPPDATA']) / 'RobotCodex/Campaign002/diagnostic' / RUN),
                 runtime_input_files=sorted(set(basis['runtime_input_files']) | set(additions)))
    require(sorted(k for k in value if value[k] != basis.get(k)) == CHANGED_FIELDS,
            'Unexpected manifest changes')
    return value


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def main():
    require(identity(BASIS)['sha256'] == BASIS_SHA, 'Original Smoke026 policy basis changed')
    basis = read(BASIS)
    value = build_manifest(basis, inputs())
    load_wrapper().validate_manifest(value)
    OUTPUT.parent.mkdir(parents=True, exist_ok=False)
    save(OUTPUT, value)
    save(OUTPUT.with_name('preparation-receipt.json'), {
        'schema': 'campaign002-single-interrupt-preparation-1', 'diagnostic_only': True,
        'run_id': RUN, 'framework_revision': REVISION, 'basis': identity(BASIS),
        'preparer': identity(Path(__file__)), 'declaration': identity(METHOD),
        'manifest': identity(OUTPUT), 'changed_fields': CHANGED_FIELDS,
        'added_runtime_inputs': sorted(set(value['runtime_input_files']) - set(basis['runtime_input_files'])),
        'model_invocations_max': 1, 'resume_allowed': False, 'retry_allowed': False,
    })
    print(json.dumps({'manifest': identity(OUTPUT), 'changed_fields': CHANGED_FIELDS}))


if __name__ == '__main__':
    main()
