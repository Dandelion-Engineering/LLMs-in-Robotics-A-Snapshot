"""REJECTED, UNLAUNCHED diagnostic scaffold. All operator actions are blocked.

Pinned native command/exec uses a local subprocess launcher, so the declared
remote-executor diagnostic has no supported route. Retain this draft as design
history only; do not prepare, freeze, submit, settle, or adopt its workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
MAP = RCI.parent / 'Architecture Map'
PYTHON = REPO / 'venv/Scripts/python.exe'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
RUN = 'RCI001-C02-output-delivery-001'
REV = 'RCI001-C02-dev-038'
ROOT = HERE / 'output-delivery-001'
RECORDS = ROOT / 'records'
MANIFEST = ROOT / 'manifest.json'
OUTPUT = ROOT / 'evidence'
SNAPSHOT = MAP / 'releases' / REV / 'snapshot.json'
PROBE = HERE / 'output-delivery-diagnostic/probe.py'
METHOD = HERE / 'OUTPUT_DELIVERY_PROBE_V1.md'
BASELINE = MAP / 'releases/RCI001-wsl-010d/snapshot.json'
BASELINE_SHA256 = 'd84c510ee923a395417944e70a90ab1fa3759bc0061c2b6a4a714fb708f25581'
CASE_NAMES = ('immediate_streaming', 'separated_streaming', 'immediate_buffered',
              'separated_buffered', 'empty_streaming', 'mixed_streaming')
ACTIVE = {'queued', 'running', 'cancel_requested'}
TERMINAL = {'succeeded', 'failed', 'cancelled', 'canceled', 'timed_out', 'aborted'}
SCOPE = ('Six standalone remote command/exec output cases only. No model calls, physical '
         'simulation or recovery action; task outcome unknown. Does not qualify model '
         'unified_exec, establish smoke008 causality, or replace its failed assessment.')
REJECTED_REASON = ('Rejected prospective diagnostic: unsupported local-only command/exec route. '
                   'No prepare, launch or settlement is authorized by this obsolete scaffold.')


def reject_unsupported_route():
    """Unconditional, before loading registry modules or touching any footprint."""
    raise RuntimeError(REJECTED_REASON)


def require(condition, message):
    if condition is not True:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Missing ordinary input: ' + str(path))
    path = path.resolve()
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def modules():
    return (load(CAMPAIGN / 'registry.py', 'output_probe_registry'),
            load(PROBE, 'output_probe_implementation'))


def protected_sources(sources):
    require(sha(BASELINE) == BASELINE_SHA256, 'Original source baseline changed')
    original = read(BASELINE)['sources']
    require(len(original) == 624, 'Original 624-source baseline incomplete')
    require(all(sources.get(name) == row for name, row in original.items()),
            'Original protected source changed or omitted')


def source_inputs(probe):
    paths = set((CAMPAIGN / 'harness').rglob('*.py'))
    paths.update((CAMPAIGN / 'assessment').rglob('*.py'))
    paths.update((RCI / 'readiness-session-10/assessment').glob('*.py'))
    paths.update(PROBE.parent.glob('*.py'))
    paths.update([PROBE.parent / 'README.md', METHOD, Path(__file__),
                  HERE / 'test_operate_output_probe.py', CAMPAIGN / 'registry.py'])
    for name in probe.required_inputs():
        require(isinstance(name, str) and not Path(name).is_absolute() and '..' not in Path(name).parts,
                'Probe input must be repository relative')
        paths.add(REPO / name)
    result = {}
    for path in sorted(paths):
        require(path.resolve().is_relative_to(REPO.resolve()) and not path.is_symlink(),
                'Input escapes repository or is a symlink')
        item = identity(path)
        result[path.relative_to(REPO).as_posix()] = {k: item[k] for k in ('sha256', 'bytes')}
    return result


def cases(probe):
    value = probe.make_cases()
    require(isinstance(value, list) and len(value) == 6
            and tuple(row.get('name') for row in value) == CASE_NAMES, 'Declared six cases changed')
    return value


def validate_manifest(value, probe):
    require(value.get('schema') == 'campaign002-output-delivery-probe-manifest-1'
            and value.get('run_id') == RUN and value.get('framework_revision') == REV
            and value.get('stage') == 'diagnostic'
            and value.get('qualification_stage') == 'source-bound-no-model-output-delivery-probe',
            'Fixed diagnostic identity changed')
    require(type(value.get('model_calls')) is int and value['model_calls'] == 0
            and type(value.get('model_turns_max')) is int and value['model_turns_max'] == 0
            and value.get('physical_simulation') is False and value.get('recovery_actions') is False
            and value.get('task_outcome') == 'unknown', 'Diagnostic scope changed')
    require(value.get('cases') == cases(probe), 'Fixed case parameters changed')
    inputs = source_inputs(probe)
    require(value.get('runtime_input_files') == sorted(inputs)
            and value.get('input_bindings') == inputs, 'Diagnostic source inventory changed')
    require(value.get('binaries') == probe.binary_bindings(), 'Native binary bindings changed')
    return value


def unused(registry):
    require(not ROOT.exists() and not SNAPSHOT.parent.exists(), 'Existing footprint; never retry')
    data, _, errors = registry.am.read_store(MAP)
    require(not errors, 'Architecture map is invalid')
    known = {row['id'] for rows in data.values() for row in rows}
    require(RUN not in known and REV not in known, 'Diagnostic identities already used')


def prepare():
    reject_unsupported_route()
    registry, probe = modules()
    unused(registry)
    inputs = source_inputs(probe)
    value = {'schema': 'campaign002-output-delivery-probe-manifest-1', 'run_id': RUN,
             'framework_revision': REV, 'stage': 'diagnostic',
             'qualification_stage': 'source-bound-no-model-output-delivery-probe',
             'model_calls': 0, 'model_turns_max': 0, 'physical_simulation': False,
             'recovery_actions': False, 'task_outcome': 'unknown', 'scope': SCOPE,
             'cases': cases(probe), 'runtime_input_files': sorted(inputs),
             'input_bindings': inputs, 'binaries': probe.binary_bindings()}
    validate_manifest(value, probe)
    payloads = registry.prior.capture_sources(value)
    protected_sources({name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                       for name, raw in payloads.items()})
    ROOT.mkdir(exist_ok=False)
    RECORDS.mkdir(exist_ok=False)
    save(RECORDS / 'prepare-intent.json', {'run_id': RUN, 'revision': REV, 'manifest': value,
                                         'registry': identity(CAMPAIGN / 'registry.py')})
    save(MANIFEST, value)
    receipt = registry.freeze(MANIFEST, REV)
    verify_frozen(probe)
    save(RECORDS / 'prepared.json', {'freeze': receipt, 'inputs': frozen_identities()})
    return {'prepared': True, 'run_id': RUN, 'revision': REV, 'model_calls': 0}


def frozen_identities():
    return {'manifest': identity(MANIFEST), 'snapshot': identity(SNAPSHOT),
            'archive': identity(SNAPSHOT.with_name('code.zip'))}


def verify_frozen(probe):
    manifest = validate_manifest(read(MANIFEST), probe)
    frozen = read(SNAPSHOT)
    require(frozen.get('schema') == 'robot-codex-readiness-source-1'
            and frozen.get('revision') == REV and frozen.get('run_id') == RUN
            and frozen.get('manifest_sha256') == sha(MANIFEST), 'Frozen manifest/source identity differs')
    sources = frozen['sources']
    protected_sources(sources)
    require(all(sources.get(name) == row for name, row in manifest['input_bindings'].items()),
            'Frozen diagnostic source inventory incomplete')
    with zipfile.ZipFile(SNAPSHOT.with_name('code.zip')) as archive:
        require(len(archive.namelist()) == len(sources) and set(archive.namelist()) == set(sources),
                'Frozen archive inventory differs')
        for name, row in sources.items():
            require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                    'Invalid frozen source path')
            path = REPO / name
            require(path.resolve().is_relative_to(REPO.resolve()), 'Frozen source escapes repository')
            current = identity(path)
            raw = archive.read(name)
            require(current['sha256'] == row['sha256'] and current['bytes'] == row['bytes']
                    and hashlib.sha256(raw).hexdigest() == row['sha256'] and len(raw) == row['bytes'],
                    'Frozen source/archive drift: ' + name)
    return frozen


def argv():
    return list(map(str, [PYTHON, '-X', 'utf8', '-B', PROBE, '--snapshot', SNAPSHOT,
                         '--manifest', MANIFEST, '--output', OUTPUT]))


def queue(*arguments):
    raw = subprocess.check_output([str(PYTHON), '-X', 'utf8', '-B', str(QUEUE), *map(str, arguments)],
                                  cwd=REPO, text=True, encoding='utf-8', timeout=30,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    value = json.loads(raw)
    return value.get('job', value)


def job_identity(job, expected_id=None):
    require(isinstance(job.get('id'), str) and bool(job['id'])
            and (expected_id is None or job['id'] == expected_id), 'Wrong official job identity')
    require(job.get('argv') == argv() and Path(job.get('cwd', '')).resolve() == REPO.resolve()
            and Path(job.get('resolved_executable', '')).resolve() == PYTHON.resolve()
            and job.get('submitting_project') == 'LLMs-in-Robotics', 'Queue command or project differs')


def launch():
    reject_unsupported_route()
    _, probe = modules()
    verify_frozen(probe)
    require(read(RECORDS / 'prepared.json')['inputs'] == frozen_identities(), 'Prepared identities drifted')
    require(not OUTPUT.exists() and not (RECORDS / 'submit.json').exists()
            and not (RECORDS / 'launch-intent.json').exists(), 'Existing execution footprint; never resubmit')
    save(RECORDS / 'launch-intent.json', {'run_id': RUN, 'argv': argv(), 'cwd': str(REPO),
                                        'inputs': frozen_identities()})
    job = queue('submit', '--project', 'LLMs-in-Robotics', '--cwd', REPO, '--', *argv())
    save(RECORDS / 'submit.json', job)
    job_identity(job)
    return {'job_id': job['id'], 'state': job['state'], 'run_id': RUN}


def settle():
    reject_unsupported_route()
    submitted = read(RECORDS / 'submit.json')
    job_identity(submitted)
    intent = read(RECORDS / 'launch-intent.json')
    require(intent.get('argv') == argv() and intent.get('cwd') == str(REPO), 'Launch intent differs')
    job = queue('status', submitted['id'])  # Fresh official authentication precedes every outcome read.
    job_identity(job, submitted['id'])
    if job.get('state') in ACTIVE:
        return {'job_id': job['id'], 'state': job['state'], 'settled': False}
    require(job.get('state') in TERMINAL, 'Unknown official queue state')
    require(not (RECORDS / 'settle-intent.json').exists(), 'Settlement already attempted; reconcile manually')
    save(RECORDS / 'settle-intent.json', {'job_id': job['id'], 'official_job': job,
                                       'inputs': intent['inputs']})
    save(RECORDS / 'official-status.json', job)
    queue_ok = (job.get('state') == 'succeeded' and type(job.get('exit_status')) is int
                and job['exit_status'] == 0)
    result = {'schema': 'campaign002-output-delivery-settlement-1', 'run_id': RUN,
              'framework_revision': REV, 'passed': False, 'task_outcome': 'unknown',
              'model_calls': 0, 'physical_simulation': False, 'recovery_actions': False, 'scope': SCOPE,
              'official_queue': identity(RECORDS / 'official-status.json'),
              'queue_succeeded_integer_zero': queue_ok, 'assessment': None,
              'probe_outputs_consumed': False}
    registry, probe = modules()
    if queue_ok:
        try:
            verify_frozen(probe)
            require(intent['inputs'] == frozen_identities(), 'Launch input identities drifted')
            result['probe_outputs_consumed'] = True
            assessment = probe.assess(OUTPUT, SNAPSHOT, MANIFEST)
            require(type(assessment.get('passed')) is bool, 'Independent assessment has no boolean verdict')
            result['assessment'] = assessment
            result['passed'] = assessment['passed']
        except Exception as error:
            result['error'] = {'type': type(error).__name__, 'message': str(error)}
    else:
        result['error'] = {'type': 'OfficialQueueFailure',
                           'message': 'No probe outputs consumed; task evidence remains unknown.'}
    save(ROOT / 'assessment.json', result)
    # The immutable legacy registry uses Python equality for exit_status. Do not
    # let a malformed succeeded/False or succeeded/0.0 receipt be mislabeled there.
    if job.get('state') == 'succeeded' and type(job.get('exit_status')) is not int:
        return {'settled': False, 'passed': False, 'run_id': RUN, 'task_outcome': 'unknown',
                'requires_reconciliation': 'Official succeeded receipt has a noninteger exit status'}
    reason = ('Bounded standalone command/exec output diagnostic ' + ('passed' if result['passed'] else 'failed')
              + '; no model/recovery/physical or task-performance evidence.')
    receipt = registry.finish(RUN, ROOT / 'assessment.json', RECORDS / 'official-status.json',
                              'valid' if result['passed'] else 'invalid', 'unknown', reason,
                              execution='completed' if queue_ok else 'failed')
    save(RECORDS / 'finish-receipt.json', receipt)
    return {'settled': True, 'passed': result['passed'], 'run_id': RUN, 'task_outcome': 'unknown'}


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'launch', 'settle'))
    args = parser.parse_args(arguments)
    print(json.dumps({'prepare': prepare, 'launch': launch, 'settle': settle}[args.action]()))


if __name__ == '__main__':
    main()
