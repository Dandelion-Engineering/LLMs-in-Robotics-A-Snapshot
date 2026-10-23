"""Fixed declarations and read-only validation for one diagnostic invocation."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
RUN = 'RCI001-C02-shutdown-diagnostic-003'
REVISION = 'RCI001-C02-dev-091'
STAGE = 'campaign002-single-interrupt-diagnostic'
PROTOCOL = 'RCI001-Campaign002-single-interrupt-diagnostic-v3'
ROOT = CAMPAIGN / 'io-repair/shutdown-diagnostic-003'
MANIFEST = ROOT / 'manifest.json'
RECORDS = ROOT / 'records'
RAW = RCI / 'local-evidence/campaign002/io-repair' / RUN
EVIDENCE, HOST = RAW / 'orchestrator', RAW / 'host'
WORKSPACE = Path(os.environ['LOCALAPPDATA']) / 'RobotCodex/Campaign002/diagnostic' / RUN
SNAPSHOT = RCI.parent / 'Architecture Map/releases' / REVISION / 'snapshot.json'
REFERENCE = CAMPAIGN / 'qualification/smoke-026-manifest.json'
REFERENCE_SHA256 = '0d6bfb4a1180f53dba8e784cdd4ef68d7d1fedef4ca7d74015b424a66380f142'
PHYSICAL = CAMPAIGN / 'harness/physical.py'
PHYSICAL_SHA256 = 'e20030568bd5d0905092a1e76f38386e6bd463541b5ff291083867e5ec9da572'
METHOD = CAMPAIGN / 'io-repair/SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md'
GUARD = RCI / 'campaign-001/admission/storage-guard/storage_guard.py'
STORAGE_POLICY = CAMPAIGN / 'admission/storage-policy.json'
STORAGE_BASELINE = CAMPAIGN / 'admission/storage-baseline-001.json'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')


def require(value, message):
    if value is not True:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def pairs(items):
    value = {}
    for key, item in items:
        require(key not in value, 'Duplicate JSON key')
        value[key] = item
    return value


def read(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Ordinary input required: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


@contextmanager
def search_path(path):
    previous = sys.path[:]
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path[:] = previous


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with search_path(Path(path).parent):
        spec.loader.exec_module(module)
    return module


def load_physical():
    """Keep the original CLI's import environment for all lazy runtime calls.

    Runtime inserts its boundary, WSL and host roots while importing. Those
    process-local entries must survive until the unchanged invocation finishes.
    """
    sys.path.insert(0, str(PHYSICAL.parent))
    spec = importlib.util.spec_from_file_location('single_interrupt_physical', PHYSICAL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Fixed provenance files, never discovered from a mutable run-output tree.
PROVENANCE_INPUTS = (
    'SOCKET_ABORT_DIAGNOSTICS_V1.md',
    'socket-abort-local-close-source-review-001.md',
    'single-interrupt-diagnostic-v2/run.py',
    'single-interrupt-diagnostic-v2/launch.py',
    'smoke026-queue-failure-diagnosis-001/analysis.json',
    'smoke026-queue-failure-diagnosis-001/analysis.md',
    'smoke026-queue-failure-diagnosis-001/authentication.json',
    'smoke026-queue-failure-diagnosis-001/official-status.json',
    'smoke026-queue-failure-diagnosis-001/official.stdout',
    'smoke026-queue-failure-diagnosis-001/official.stderr',
    'smoke026-queue-failure-diagnosis-001/collect.py',
    'smoke026-queue-failure-diagnosis-001/collect.stdout',
    'smoke026-queue-failure-diagnosis-001/collect.stderr',
    'smoke026-queue-failure-diagnosis-001/collect-exit.json',
    'smoke026-queue-failure-diagnosis-001/execution.json',
    'socket-abort-instrumentation-development-001/before.json',
    'socket-abort-instrumentation-development-001/receipt.json',
    'socket-abort-instrumentation-development-001/final-check-002/receipt.json',
    'socket-abort-instrumentation-development-001/final-check-002/source-parity.json',
    'socket-abort-instrumentation-development-001/final-check-002/source.diff',
    'socket-abort-instrumentation-development-001/final-check-002/execution.json',
    'socket-abort-instrumentation-development-001/final-check-002/verify_parity.py',
    'socket-abort-instrumentation-development-001/final-check-002/stdout.txt',
    'socket-abort-instrumentation-development-001/final-check-002/stderr.txt',
    'socket-abort-instrumentation-development-001/red-001/receipt.json',
    'socket-abort-instrumentation-development-001/red-001/stdout.txt',
    'socket-abort-instrumentation-development-001/red-001/stderr.txt',
    'socket-abort-instrumentation-development-001/green-001/receipt.json',
    'socket-abort-instrumentation-development-001/green-001/stdout.txt',
    'socket-abort-instrumentation-development-001/green-001/stderr.txt',
    'socket-abort-instrumentation-development-001/green-002/receipt.json',
    'socket-abort-instrumentation-development-001/green-002/stdout.txt',
    'socket-abort-instrumentation-development-001/green-002/stderr.txt',
    'socket-abort-loopback-development-002/CORRECTION.md',
    'socket-abort-loopback-development-002/fixture.py',
    'socket-abort-loopback-development-002/launch.py',
    'socket-abort-loopback-development-002/no_socket_regression.py',
    'socket-abort-loopback-development-002/verify_correction.py',
    'socket-abort-loopback-development-002/source.diff',
    'socket-abort-loopback-development-002/original-001-bindings.json',
    'socket-abort-loopback-development-002/receipt.json',
    'socket-abort-loopback-development-002/red-001/receipt.json',
    'socket-abort-loopback-development-002/red-001/stdout.txt',
    'socket-abort-loopback-development-002/red-001/stderr.txt',
    'socket-abort-loopback-development-002/green-001/receipt.json',
    'socket-abort-loopback-development-002/green-001/stdout.txt',
    'socket-abort-loopback-development-002/green-001/stderr.txt',
    'socket-abort-loopback-development-002/execution-001/receipt.json',
    'socket-abort-loopback-development-002/execution-001/intent.json',
    'socket-abort-loopback-development-002/execution-001/source-manifest.json',
    'socket-abort-loopback-development-002/execution-001/process-start.json',
    'socket-abort-loopback-development-002/execution-001/stdout-summary.json',
    'socket-abort-loopback-development-002/execution-001/stderr-summary.json',
    'socket-abort-loopback-development-002/execution-001/child/result.json',
    'socket-abort-loopback-development-002/execution-001/child/events.jsonl',
    'socket-abort-assessment-fixture-development-001/DECLARATION.md',
    'socket-abort-assessment-fixture-development-001/before.json',
    'socket-abort-assessment-fixture-development-001/receipt.json',
    'socket-abort-assessment-fixture-development-001/focused.stdout',
    'socket-abort-assessment-fixture-development-001/focused.stderr',
    'socket-abort-assessment-fixture-development-001/focused-002/receipt.json',
    'socket-abort-assessment-fixture-development-001/focused-002/stdout',
    'socket-abort-assessment-fixture-development-001/focused-002/stderr',
    'socket-abort-assessment-fixture-development-001/final-receipt.json',
    'socket-abort-assessment-fixture-development-001/source.diff',
    'checks-032/test-execution.json',
    'checks-032/harness.stdout',
    'checks-032/harness.stderr',
    'checks-032/assessment.stdout',
    'checks-032/assessment.stderr',
    'checks-033/test-execution.json',
    'checks-033/harness.stdout',
    'checks-033/harness.stderr',
    'checks-033/assessment.stdout',
    'checks-033/assessment.stderr',
    'checks-033-source-state.json',
    'checks-033-execution-001/receipt.json',
    'checks-033-execution-001/intent.json',
    'checks-033-execution-001/stdout.txt',
    'checks-033-execution-001/stderr.txt',
)


def required_inputs():
    paths = list(HERE.glob('*.py')) + [REFERENCE, METHOD, PHYSICAL,
        HERE.parent / 'prepare_socket_abort_diagnostic.py',
        HERE.parent / 'control_socket_abort_diagnostic.py',
        HERE.parent / 'test_control_socket_abort_diagnostic.py',
        CAMPAIGN / 'harness/run_host.py', CAMPAIGN / 'harness/runtime.py',
        CAMPAIGN / 'harness/bootstrap_client_v4.py', CAMPAIGN / 'assessment/assess.py',
        CAMPAIGN / 'harness/codehost_bridge_v3.py',
        CAMPAIGN / 'harness/test_codehost_bridge_v3.py',
        CAMPAIGN / 'assessment/transport_integrity_v3.py',
        CAMPAIGN / 'assessment/test_transport_integrity_v3.py',
        GUARD, STORAGE_POLICY, STORAGE_BASELINE]
    paths += [HERE.parent / name for name in PROVENANCE_INPUTS]
    return sorted({p.relative_to(REPO).as_posix() for p in paths})


def validate_manifest(value):
    require(sha(REFERENCE) == REFERENCE_SHA256, 'Original Smoke026 policy basis changed')
    basis = read(REFERENCE)
    require(isinstance(value, dict) and set(value) == set(basis), 'Diagnostic manifest field inventory differs')
    expected = dict(basis)
    expected.update(run_id=RUN, framework_revision=REVISION, qualification_stage=STAGE,
                    outer_campaign_protocol=PROTOCOL, model_turns_max=1,
                    runtime_workspace=str(WORKSPACE), runtime_input_files=value.get('runtime_input_files'))
    require(exact(value, expected), 'Diagnostic caps, fixture, policy, identity or configuration differs')
    inputs = value['runtime_input_files']
    require(isinstance(inputs, list) and all(isinstance(x, str) for x in inputs)
            and inputs == sorted(set(inputs)) and set(required_inputs()) <= set(inputs),
            'Complete diagnostic source inventory required')
    for name in inputs:
        path = REPO / name
        require(not Path(name).is_absolute() and path.resolve().is_relative_to(REPO.resolve())
                and path.is_file() and not path.is_symlink()
                and path.relative_to(REPO).as_posix() == name, 'Invalid diagnostic source path')


def validate(manifest, snapshot):
    require(Path(manifest).resolve() == MANIFEST.resolve() and Path(snapshot).resolve() == SNAPSHOT.resolve(),
            'Fixed manifest and source snapshot paths required')
    value, frozen = read(manifest), read(snapshot)
    validate_manifest(value)
    require(frozen.get('revision') == REVISION and frozen.get('run_id') == RUN
            and frozen.get('manifest_sha256') == sha(manifest), 'Frozen diagnostic identity or manifest differs')
    require(sha(PHYSICAL) == PHYSICAL_SHA256, 'Original physical runner changed')
    for name in value['runtime_input_files']:
        path = REPO / name; item = frozen.get('sources', {}).get(name)
        require(isinstance(item, dict) and type(item.get('bytes')) is int
                and item == {'bytes': path.stat().st_size, 'sha256': sha(path)},
                'Diagnostic input missing from snapshot or changed: ' + name)
    assessor = load(CAMPAIGN / 'assessment/assess.py', 'single_interrupt_source_assessor')
    require(not assessor.frozen_problems(Path(snapshot), frozen, REVISION),
            'Full frozen source/archive verification failed')
    return value, frozen


def output_paths(evidence, host, workspace):
    for supplied, fixed in ((evidence, EVIDENCE), (host, HOST), (workspace, WORKSPACE)):
        require(Path(supplied).resolve() == fixed.resolve(), 'Fixed diagnostic output path required')
        require(not fixed.exists(), 'Existing diagnostic footprint; never resubmit: ' + str(fixed))


def runner_argv(manifest, snapshot):
    return [sys.executable, '-X', 'utf8', '-B', str(HERE / 'run.py'),
            '--manifest', str(Path(manifest).resolve()), '--snapshot', str(Path(snapshot).resolve()),
            '--evidence', str(EVIDENCE), '--host-evidence', str(HOST), '--workspace', str(WORKSPACE)]
