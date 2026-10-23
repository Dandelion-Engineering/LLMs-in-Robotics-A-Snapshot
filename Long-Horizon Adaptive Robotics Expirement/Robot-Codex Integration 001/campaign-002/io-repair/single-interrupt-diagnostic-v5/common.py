"""Fixed declarations and read-only validation for one diagnostic invocation."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
RUN = 'RCI001-C02-shutdown-diagnostic-005'
REVISION = 'RCI001-C02-dev-097'
STAGE = 'campaign002-single-interrupt-diagnostic'
PROTOCOL = 'RCI001-Campaign002-single-interrupt-diagnostic-v5'
ROOT = CAMPAIGN / 'io-repair/shutdown-diagnostic-005'
MANIFEST = ROOT / 'manifest.json'
RECORDS = ROOT / 'records'
RAW = RCI / 'local-evidence/campaign002/io-repair' / RUN
EVIDENCE, HOST = RAW / 'orchestrator', RAW / 'host'
WORKSPACE = Path(os.environ['LOCALAPPDATA']) / 'RobotCodex/Campaign002/diagnostic' / RUN
SNAPSHOT = RCI.parent / 'Architecture Map/releases' / REVISION / 'snapshot.json'
REFERENCE = CAMPAIGN / 'qualification/smoke-027-manifest.json'
REFERENCE_SHA256 = 'f6e0ee7700f620f1bedcb04cfef5e91dfb9a6122577aa9b3cc4dcaaf78ac2202'
PHYSICAL = CAMPAIGN / 'harness/physical.py'
PHYSICAL_SHA256 = 'e20030568bd5d0905092a1e76f38386e6bd463541b5ff291083867e5ec9da572'
METHOD = CAMPAIGN / 'io-repair/native-os-closure-001/DECLARATION.md'
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


# All previously frozen dev096 inputs remain immutable; append only new diagnostic sources.
PREVIOUS=RCI.parent/'Architecture Map/releases/RCI001-C02-dev-096/snapshot.json'
PACKET=CAMPAIGN/'io-repair/native-os-closure-001'
QUALIFIED=CAMPAIGN/'io-repair/tcp-event-coverage-003'

def required_inputs():
    prior=read(PREVIOUS)['sources']
    paths=list(HERE.glob('*.py'))+list(PACKET.glob('*.py'))+list(PACKET.glob('*.ps1'))+[METHOD,REFERENCE,PHYSICAL,
        PACKET/'control-tests-002/receipt.json',PACKET/'wrapper-tests-001/receipt.json',
        QUALIFIED/'AUTHORIZATION.md',QUALIFIED/'assessment-001.json',QUALIFIED/'launch-source-manifest-001.json',
        QUALIFIED/'etw_session.py',QUALIFIED/'read_etl.py',QUALIFIED/'schema.json',
        CAMPAIGN/'io-repair/admin-coverage-automation-002/owned_process.py',
        CAMPAIGN/'io-repair/admin-coverage-automation-002/run_coverage.py',GUARD,STORAGE_POLICY,STORAGE_BASELINE]
    return sorted(set(prior)|{p.relative_to(REPO).as_posix() for p in paths})


def validate_manifest(value):
    require(sha(REFERENCE) == REFERENCE_SHA256, 'Original Smoke027 policy basis changed')
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


def control_digest(value):
    require(isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value) is not None,
            'Exact observer configuration SHA256 required')
    return value


def runner_argv(manifest, snapshot, observer_config_sha256):
    return [sys.executable, '-X', 'utf8', '-B', str(HERE / 'run.py'),
            '--manifest', str(Path(manifest).resolve()), '--snapshot', str(Path(snapshot).resolve()),
            '--evidence', str(EVIDENCE), '--host-evidence', str(HOST), '--workspace', str(WORKSPACE),
            '--observer-config-sha256', control_digest(observer_config_sha256)]
