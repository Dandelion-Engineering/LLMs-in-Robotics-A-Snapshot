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
RUN = 'RCI001-C02-shutdown-diagnostic-002'
REVISION = 'RCI001-C02-dev-062'
STAGE = 'campaign002-single-interrupt-diagnostic'
PROTOCOL = 'RCI001-Campaign002-single-interrupt-diagnostic-v2'
ROOT = CAMPAIGN / 'io-repair/shutdown-diagnostic-002'
MANIFEST = ROOT / 'manifest.json'
RECORDS = ROOT / 'records'
RAW = RCI / 'local-evidence/campaign002/io-repair' / RUN
EVIDENCE, HOST = RAW / 'orchestrator', RAW / 'host'
WORKSPACE = Path(os.environ['LOCALAPPDATA']) / 'RobotCodex/Campaign002/diagnostic' / RUN
SNAPSHOT = RCI.parent / 'Architecture Map/releases' / REVISION / 'snapshot.json'
REFERENCE = CAMPAIGN / 'qualification/smoke-019-manifest.json'
REFERENCE_SHA256 = '827e96a429b50ede8594cf57ca7d4f6c30542520ea47ad1fc13cbc3bc20f3f7d'
PHYSICAL = CAMPAIGN / 'harness/physical.py'
PHYSICAL_SHA256 = 'e20030568bd5d0905092a1e76f38386e6bd463541b5ff291083867e5ec9da572'
METHOD = CAMPAIGN / 'io-repair/RESET_REJECTION_DIAGNOSTIC_V1.md'
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


def required_inputs():
    paths = list(HERE.glob('*.py')) + [REFERENCE, METHOD, PHYSICAL,
        HERE.parent / 'prepare_reset_diagnostic.py', HERE.parent / 'control_reset_diagnostic.py',
        CAMPAIGN / 'harness/run_host.py', CAMPAIGN / 'harness/runtime.py',
        CAMPAIGN / 'harness/bootstrap_client_v4.py', CAMPAIGN / 'assessment/assess.py',
        GUARD, STORAGE_POLICY, STORAGE_BASELINE]
    return sorted({p.relative_to(REPO).as_posix() for p in paths})


def validate_manifest(value):
    require(sha(REFERENCE) == REFERENCE_SHA256, 'Original Smoke019 policy basis changed')
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
