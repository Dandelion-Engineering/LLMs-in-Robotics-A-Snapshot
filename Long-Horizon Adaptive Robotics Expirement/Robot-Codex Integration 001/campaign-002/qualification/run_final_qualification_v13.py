"""Run five fresh qualifiers after the prospective channel-host startup repair.

This external coordinator is deliberately outside the runtime source inventory.
It invokes the existing preparers, registry, direct shared queue and assessors.
An intent without a completed command receipt requires operator reconciliation;
no submission, failed command, failed assessment or existing output is retried.
Invoke with --readiness PATH --readiness-sha256 SHA after repair validation.
It never creates a campaign certificate, release or scored attempt.

Readiness binds the repaired source snapshot, a successfully authenticated and
independently replayed host diagnostic, retained passing repair tests and fixed
stage identities. It is a prospective operator declaration, not admission or a
claim that an earlier baseline diagnostic qualified the repaired runtime.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
MAP = RCI.parent / 'Architecture Map'
RAW = RCI / 'local-evidence/campaign002/qualification'
LEDGER = HERE / 'final-qualification-013'
STARTUP_REPAIR_METHOD = CAMPAIGN / 'io-repair/CHANNEL_TRANSPORT_STARTUP_REPAIR_V1.md'
PYTHON = REPO / 'venv/Scripts/python.exe'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
STAGE_IDENTITIES = (('native-012', 'native', 24000),
                    ('boundary-013', 'boundary', None),
                    ('smoke-011', 'smoke', 24101),
                    ('pilot-stock-010', 'stock', 24102),
                    ('pilot-home-010', 'home', 24103))
READINESS_SCHEMA = 'campaign002-final-qualification-readiness-1'
TEST_RECEIPT_SCHEMA = 'campaign002-repair-test-receipt-1'
POLL_SECONDS = 15
STORAGE_GRACE_SECONDS = 60
ACTIVE_STATES = {'queued', 'running', 'cancel_requested'}

sys.path.insert(0, str(CAMPAIGN))
import operate
import admission

read, sha, save, save_exact = operate.read, operate.sha, operate.save, operate.save_exact
require = admission.require


def identity(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path)}


def notice(phase, **fields):
    print(json.dumps({'phase': phase, **fields}), flush=True)


def python(script, *args):
    return [str(PYTHON), '-X', 'utf8', '-B', str(script), *map(str, args)]


def invoke(argv):
    return subprocess.run(argv, cwd=REPO, capture_output=True, text=True,
                          encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def command_once(folder, name, argv, *, inputs=(), outputs=(), absent=(), allow_failure=False):
    """Durable action journal; an ambiguous side effect is never repeated."""
    folder = Path(folder)
    intent_path, receipt_path = folder / (name + '-intent.json'), folder / (name + '-receipt.json')
    script_inputs = [Path(argv[4])] if len(argv) > 4 and Path(argv[4]).is_file() else []
    expected = {'argv': list(map(str, argv)), 'cwd': str(REPO),
                'inputs': [identity(path) for path in [*script_inputs, *inputs]],
                'outputs': [str(Path(path).resolve()) for path in outputs]}
    if intent_path.exists():
        require(read(intent_path) == expected, 'Changed command intent: ' + name)
        require(receipt_path.exists(), 'Unresolved command intent; reconcile without retry: ' + name)
        receipt = read(receipt_path)
        require(receipt['intent_sha256'] == sha(intent_path), 'Command receipt/intent mismatch')
        for item in receipt['outputs']:
            admission.artifact(item)
    else:
        require(not receipt_path.exists(), 'Orphan command receipt: ' + name)
        require(not any(Path(path).exists() for path in (*outputs, *absent)),
                'Existing output requires reconciliation; never retry: ' + name)
        save(intent_path, expected)
        result = invoke(expected['argv'])
        receipt = {'intent_sha256': sha(intent_path), 'exit_code': result.returncode,
                   'stdout': result.stdout, 'stderr': result.stderr,
                   'outputs': [identity(path) for path in outputs if Path(path).is_file()]}
        save(receipt_path, receipt)
    require(type(receipt.get('exit_code')) is int, 'Missing native command exit receipt')
    require(allow_failure or receipt['exit_code'] == 0, 'Command failed; no retry: ' + name)
    require({item['path'] for item in receipt['outputs']} == set(expected['outputs']),
            'Command output absent; reconcile without retry: ' + name)
    return receipt


def revision_number(value):
    require(isinstance(value, str) and re.fullmatch(r'RCI001-C02-dev-[0-9]{3}', value) is not None,
            'Invalid prospective development revision')
    return int(value.rsplit('-', 1)[1])


def load_readiness(path, expected_sha256):
    require(isinstance(expected_sha256, str) and re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is not None,
            'Readiness requires a caller-held SHA256')
    path = admission.artifact({'path': str(Path(path).resolve()), 'sha256': expected_sha256})
    value = read(path)
    require(value.get('schema') == READINESS_SCHEMA, 'Wrong repaired-source readiness schema')
    require(admission.same_path(value.get('ledger_directory', ''), LEDGER), 'Wrong immutable qualifier ledger')
    stages = value.get('stages')
    require(isinstance(stages, list) and len(stages) == len(STAGE_IDENTITIES)
            and all(isinstance(row, list) and len(row) == 4 for row in stages),
            'Exactly five fixed qualifier stages required')
    require(tuple((row[0], row[1], row[3]) for row in stages) == STAGE_IDENTITIES,
            'Qualifier identities, order, families or seeds changed')
    require(all(type(row[3]) is int if expected[2] is not None else row[3] is None
                for row, expected in zip(stages, STAGE_IDENTITIES)), 'Qualifier seeds must be exact integers')
    revisions = [revision_number(row[2]) for row in stages]
    require(revisions == [44, 45, 46, 46, 46],
            'Qualifier revisions must be dev044, dev045 and shared final dev046')
    diagnostic = value.get('diagnostic', {})
    require(diagnostic.get('run_id') == 'RCI001-C02-host-probe-013',
            'Readiness requires a fresh repaired-host diagnostic')
    require(isinstance(diagnostic.get('job_id'), str) and bool(diagnostic['job_id'].strip()),
            'Missing diagnostic official job identity')
    return value


def assert_sources(readiness, snapshot_path=None):
    anchor = admission.artifact(readiness['source_snapshot'])
    frozen = read(anchor)
    require(anchor == MAP / 'releases' / frozen['revision'] / 'snapshot.json',
            'Repaired source anchor is outside its canonical release')
    anchor_number = revision_number(frozen['revision'])
    require(anchor_number == 43 and revision_number(readiness['stages'][0][2]) == 44,
            'Repaired source anchor must be dev043 before native dev044')
    require(not admission.base.frozen_problems(anchor, frozen, frozen['revision']),
            'Frozen repaired source/archive identity changed')
    require(frozen['sources'].get(STARTUP_REPAIR_METHOD.relative_to(REPO).as_posix()) == {
                'sha256': sha(STARTUP_REPAIR_METHOD), 'bytes': STARTUP_REPAIR_METHOD.stat().st_size},
            'Repaired source anchor must bind the exact startup-repair declaration')
    core = admission.runtime_identities(frozen)
    prefix = (CAMPAIGN / 'assessment').relative_to(REPO).as_posix() + '/'
    assessor_names = {name for name in frozen['sources'] if name.startswith(prefix)}
    current_names = {path.relative_to(REPO).as_posix() for path in (CAMPAIGN / 'assessment').rglob('*.py')}
    require(assessor_names == current_names, 'Repaired source assessor module set changed')
    core.update({name: frozen['sources'][name] for name in assessor_names})
    if snapshot_path is not None and Path(snapshot_path) != anchor:
        other = read(snapshot_path)
        require(not admission.base.frozen_problems(snapshot_path, other, other['revision']),
                'Stage source/archive identity changed')
        admission.verify_runtime_lineage(core, other)
    return core


def official(job_id):
    value = operate.queue('status', job_id)
    value = value.get('job', value)
    require(value.get('id') == job_id, 'Official queue returned the wrong job')
    return value


def test_targets(argv):
    """Resolve the declared test command, so unrelated successful commands fail."""
    if argv[4:7] == ['-m', 'unittest', 'discover']:
        options = argv[7:]
        require(options.count('-s') == 1 and options.count('-p') == 1,
                'Repair unittest discovery must declare exact source directory and pattern')
        allowed = {'-s', '-p', '-v', '-q', '--failfast', '-f', '--buffer', '-b'}
        index, values = 0, {}
        while index < len(options):
            option = options[index]
            require(option in allowed, 'Unsupported repair unittest discovery option')
            if option in ('-s', '-p'):
                require(index + 1 < len(options), 'Missing repair unittest discovery value')
                values[option] = options[index + 1]
                index += 2
            else:
                index += 1
        directory = Path(values['-s'])
        require(directory.is_absolute() and directory.is_dir(), 'Repair test discovery directory must be absolute')
        pattern = values['-p']
        require(isinstance(pattern, str) and '/' not in pattern and '\\' not in pattern,
                'Repair test pattern must select direct frozen test files')
        return {str(path.resolve()) for path in directory.glob(pattern) if path.is_file()}
    require(not argv[4].startswith('-') and Path(argv[4]).is_absolute(),
            'Repair test must directly run a frozen test or use exact unittest discovery')
    return {str(Path(argv[4]).resolve())}


def verify_repair_tests(record, readiness):
    receipt = read(admission.artifact(record))
    require(receipt.get('schema') == TEST_RECEIPT_SCHEMA and receipt.get('passed') is True
            and receipt.get('source_snapshot') == readiness['source_snapshot'],
            'Repair tests are not bound to the repaired source anchor')
    commands = receipt.get('commands')
    require(isinstance(commands, list) and bool(commands), 'Passing repair-test commands are required')
    frozen = read(admission.artifact(readiness['source_snapshot']))
    frozen_tests = {str((REPO / name).resolve()) for name in frozen['sources']
                    if Path(name).name.startswith('test') and Path(name).suffix == '.py'}
    for command in commands:
        argv = command.get('argv', [])
        require(type(command.get('exit_code')) is int and command['exit_code'] == 0
                and isinstance(argv, list) and len(argv) >= 5 and all(isinstance(arg, str) for arg in argv)
                and argv[:4] == [str(PYTHON), '-X', 'utf8', '-B'], 'Repair test command failed or interpreter differs')
        # The receipt names actual frozen test inputs, including unittest discovery.
        inputs = command.get('test_inputs')
        require(isinstance(inputs, list) and bool(inputs), 'Repair test command omits frozen test inputs')
        declared = set()
        for item in inputs:
            path = admission.artifact(item)
            require(str(path.resolve()) not in declared, 'Duplicate repair test input')
            declared.add(str(path.resolve()))
            require(str(path.resolve()) in frozen_tests, 'Repair test input is absent from the repaired freeze')
            expected = frozen['sources'][path.relative_to(REPO).as_posix()]
            require(item['sha256'] == expected['sha256'], 'Repair test input differs from repaired freeze')
        require(declared == test_targets(argv), 'Repair command targets differ from declared frozen tests')
        admission.artifact(command['stdout'])
        admission.artifact(command['stderr'])
    return receipt


def replay_diagnostic(assessor, manifest, evidence, queue, snapshot):
    spec = importlib.util.spec_from_file_location('final_qualification_probe_v6', assessor)
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    return evaluator.evaluate(manifest, evidence, queue, snapshot)


def verify_transport_probe(record, snapshot):
    require(isinstance(record, dict) and record.get('run_id') == 'RCI001-C02-transport-probe-006',
            'A fresh fixed no-model transport probe is required')
    # Authenticate before reading any probe outcome, including its hash.
    job = admission.base.queue_gate(official(record['job_id']), record['job_id'])
    retained_queue = admission.artifact(record['queue'])
    require(read(retained_queue) == job, 'Transport probe queue receipt differs from official status')
    output = CAMPAIGN / 'io-repair/transport-probe-006/evidence'
    script = CAMPAIGN / 'harness/codehost_transport_probe_v3.py'
    frozen = read(snapshot)
    expected = python(script, '--run-id', record['run_id'], '--framework-revision', frozen['revision'],
                      '--snapshot', snapshot, '--output', output)
    require(job.get('argv') == expected and admission.same_path(job.get('cwd', ''), REPO)
            and admission.same_path(job.get('resolved_executable', ''), PYTHON),
            'Transport probe official direct command changed')
    result_path = admission.artifact(record['result'])
    require(result_path == output / 'result.json', 'Transport probe output outside declared path')
    result = read(result_path)
    require(result.get('schema') == 'campaign002-codehost-channel-probe-3'
            and result.get('run_id') == record['run_id'] and result.get('framework_revision') == frozen['revision']
            and result.get('snapshot_sha256') == sha(snapshot) and result.get('passed') is True
            and type(result.get('model_calls')) is int and result['model_calls'] == 0
            and result.get('physical_simulation') is False,
            'Transport probe is not a successful no-model check of the exact anchor')
    cases = result.get('cases')
    require(isinstance(cases, list) and [case.get('case') for case in cases] ==
            ['multi_channel', 'foreign_owner', 'in_flight_eof'],
            'Exactly the three declared channel transport cases are required')
    require(replay_raw_preflight(script, output, snapshot) == result,
            'Transport probe independent replay differs from its retained result')
    return result


def replay_raw_preflight(script, output, snapshot):
    spec = importlib.util.spec_from_file_location('final_raw_preflight_v13', script)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    return probe.assess(output, snapshot)


def verify_raw_preflight(record, snapshot):
    require(isinstance(record, dict) and record.get('run_id') == 'RCI001-C02-raw-preflight-003',
            'A fresh fixed no-model raw-event preflight is required')
    # Authenticate before reading any empirical result or result hash.
    job = admission.base.queue_gate(official(record['job_id']), record['job_id'])
    require(read(admission.artifact(record['queue'])) == job,
            'Raw-event preflight queue receipt differs from official status')
    output = CAMPAIGN / 'io-repair/raw-preflight-003/evidence'
    script = CAMPAIGN / 'harness/raw_event_preflight_v2.py'
    frozen = read(snapshot)
    expected = python(script, '--run-id', record['run_id'], '--framework-revision', frozen['revision'],
                      '--snapshot', snapshot, '--output', output)
    require(job.get('argv') == expected and admission.same_path(job.get('cwd', ''), REPO)
            and admission.same_path(job.get('resolved_executable', ''), PYTHON),
            'Raw-event preflight official direct command changed')
    result_path = admission.artifact(record['result'])
    require(result_path == output / 'result.json', 'Raw-event preflight output outside declared path')
    result = read(result_path)
    require(result.get('schema') == 'campaign002-raw-event-preflight-2'
            and result.get('run_id') == record['run_id'] and result.get('framework_revision') == frozen['revision']
            and result.get('snapshot_sha256') == sha(snapshot) and result.get('passed') is True
            and type(result.get('model_calls')) is int and result['model_calls'] == 0
            and result.get('physical_simulation') is False,
            'Raw-event preflight is not a successful no-model check of the exact anchor')
    require(replay_raw_preflight(script, output, snapshot) == result,
            'Raw-event preflight independent replay differs from retained result')
    return result


def preflight(readiness_path, expected_sha256):
    readiness = load_readiness(readiness_path, expected_sha256)
    diagnostic = readiness['diagnostic']
    # Fresh official authentication precedes every diagnostic outcome hash/read.
    job = admission.base.queue_gate(official(diagnostic['job_id']), diagnostic['job_id'])
    probe_queue = admission.artifact(diagnostic['queue'])
    require(read(probe_queue) == job, 'Diagnostic retained receipt differs from official queue')
    core = assert_sources(readiness)
    snapshot = admission.artifact(readiness['source_snapshot'])
    manifest = admission.artifact(diagnostic['manifest'])
    assessment = admission.artifact(diagnostic['assessment'])
    assessor = admission.artifact(diagnostic['assessor'])
    require(assessor == HERE / 'assess_host_probe.py', 'Wrong diagnostic assessor implementation')
    evidence = Path(diagnostic['evidence']).resolve()
    require(evidence == RAW / diagnostic['run_id'], 'Diagnostic evidence outside its fixed run identity')
    replayed = replay_diagnostic(assessor, manifest, evidence, probe_queue, snapshot)
    require(read(assessment) == replayed, 'Retained diagnostic assessment differs from independent replay')
    require(replayed.get('schema') == 'campaign002-host-probe-assessment-1'
            and replayed.get('diagnostic_passed') is True and not replayed.get('errors')
            and replayed.get('run_id') == diagnostic['run_id'] and replayed.get('queue_job_id') == job['id']
            and replayed.get('framework_revision') == read(snapshot)['revision']
            and replayed.get('model_calls') == 0 and replayed.get('scorable') is False,
            'Repaired host diagnostic did not pass on its exact source anchor')
    admission.strict_timing_summary(replayed.get('timing'), diagnostic['run_id'])
    verify_repair_tests(readiness['repair_test_receipt'], readiness)
    verify_transport_probe(readiness.get('transport_diagnostic'), snapshot)
    verify_raw_preflight(readiness.get('raw_event_preflight'), snapshot)
    return readiness, core


def await_success(submitted, receipt_path, expected_argv):
    require(submitted.get('argv') == expected_argv, 'Submitted command differs from fixed direct launch')
    while True:
        job = official(submitted['id'])
        require(job.get('argv') == expected_argv and admission.same_path(job.get('cwd', ''), REPO)
                and admission.same_path(job.get('resolved_executable', ''), PYTHON),
                'Official direct queue command changed')
        if job.get('state') in operate.TERMINAL_QUEUE_STATES:
            save_exact(receipt_path, job)
            # Never read even an existing assessment following failed queue execution.
            return admission.base.queue_gate(job, submitted['id'])
        require(job.get('state') in ACTIVE_STATES, 'Unknown queue state; stop for reconciliation')
        require(not Path(receipt_path).exists(), 'Retained terminal receipt conflicts with active official job')
        time.sleep(POLL_SECONDS)


def wait_storage(records, job, manifest, evidence, host, workspace):
    path = records / 'storage/receipt.json'
    deadline = admission.stamp(job['ended_at']) + STORAGE_GRACE_SECONDS
    while not path.is_file():
        require(time.time() < deadline, 'Final storage receipt missing after bounded grace; stop')
        time.sleep(min(5, max(.01, deadline - time.time())))
    queue_path = records / 'storage/queue-receipt.json'
    require(read(queue_path) == job, 'Storage monitor retained a different official queue receipt')
    artifacts = {name: identity(path) for name, path in (
        ('storage_monitor', operate.GUARD), ('storage_policy', CAMPAIGN / 'admission/storage-policy.json'),
        ('storage_baseline', CAMPAIGN / 'admission/storage-baseline-001.json'))}
    attempt = dict(run_id=read(manifest)['run_id'], manifest=identity(manifest), evidence=str(evidence),
                   host_evidence=str(host), workspace=str(workspace))
    admission.verify_storage(path, {'artifacts': artifacts}, attempt, queue_path, job)
    return path


def storage_gate(folder, paths, manifest, job):
    """A storage failure is retained independently, without reading host outcomes."""
    stop = folder / 'storage-stop.json'
    require(not stop.exists(), 'Prior storage failure requires operator reconciliation; no retry')
    try:
        return wait_storage(paths['records'], job, paths['manifest'], paths['evidence'], paths['host'],
                            Path(manifest['runtime_workspace']))
    except Exception as error:
        receipt = paths['records'] / 'storage/receipt.json'
        save(stop, {'schema': 'campaign002-final-qualification-storage-stop-1',
            'run_id': paths['run_id'], 'queue_job_id': job['id'], 'queue': identity(paths['queue']),
            'storage_receipt': identity(receipt) if receipt.is_file() else None,
            'error': str(error), 'immediate_stop': True, 'outcomes_read': False,
            'scope': 'Storage diagnostic only; no host assessment or task outcome was produced.'})
        raise


def entry_for(name, kind, revision):
    run_id = 'RCI001-C02-' + name
    manifest = HERE / (name + '-manifest.json')
    root = RAW / run_id
    model = kind not in ('native', 'boundary')
    return dict(run_id=run_id, manifest=manifest, snapshot=MAP / 'releases' / revision / 'snapshot.json',
                evidence=root / 'orchestrator' if model else root, host=root / 'host',
                records=HERE / run_id, queue=HERE / (name + '-queue.json'),
                assessment=root / 'suite-result.json' if kind == 'boundary' else HERE / (name + '-assessment.json'))


def prepare_stage(folder, name, kind, revision, seed, paths, readiness):
    manifest, snapshot = paths['manifest'], paths['snapshot']
    args = ['--run-id', paths['run_id'], '--revision', revision, '--output', manifest]
    if kind == 'native':
        prepare = python(HERE / 'prepare_native.py', *args, '--seed-base', seed)
    elif kind == 'boundary':
        prepare = python(HERE / 'prepare_boundary_v3.py', *args)
    else:
        prepare = python(HERE / 'prepare_model_v7.py', *args, '--kind', kind, '--seed', seed)
    command_once(folder, 'prepare', prepare, outputs=[manifest])
    value = read(manifest)
    require(value['run_id'] == paths['run_id'] and value['framework_revision'] == revision,
            'Prepared manifest identity differs')
    if kind not in ('native', 'boundary'):
        require(value['noise_seed'] == seed and value['seed'] == 173, 'Prepared model seeds differ')
    elif kind == 'native':
        require([slot['manifest']['noise_seed'] for slot in value['slots']] == list(range(24001, 24007)),
                'Prepared native seeds differ')
    pilot = kind in ('stock', 'home')
    outputs = [snapshot.parent / 'runs' / (paths['run_id'] + '.json')] if pilot else [
        snapshot, snapshot.with_name('code.zip'), snapshot.with_name('run-record.json')]
    command_once(folder, 'register', python(CAMPAIGN / 'registry.py', 'add-run' if pilot else 'freeze',
                 '--manifest', manifest, '--revision', revision), inputs=[manifest], outputs=outputs,
                 absent=[] if pilot else [snapshot.parent])
    assert_sources(readiness, snapshot)
    if kind == 'boundary':
        spec = importlib.util.spec_from_file_location('boundary_inventory_v6', HERE / 'boundary_suite_v3.py')
        suite = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(suite)
        inventory = read(snapshot)['sources']
        require(all(name in inventory and inventory[name]['sha256'] == digest
                    for name, digest in suite.sources().items()),
                'Boundary freeze omits or changes a measured source')
    return value


def launch_stage(folder, kind, paths, manifest):
    if kind in ('native', 'boundary'):
        submit_path = HERE / (paths['run_id'].removeprefix('RCI001-C02-') + '-submit.json')
        argv = python(HERE / ('boundary_suite_v3.py' if kind == 'boundary' else 'native_suite.py'), *(
            ['--manifest', paths['manifest'], '--output', paths['evidence']] if kind == 'native'
            else ['--output', paths['evidence']]))
        receipt = command_once(folder, 'submit', python(QUEUE, 'submit', '--project', 'LLMs-in-Robotics',
            '--cwd', REPO, '--', *argv), inputs=[paths['manifest'], paths['snapshot']],
            absent=[paths['evidence'], paths['queue'], submit_path,
                    *[Path(slot['workspace']) for slot in manifest.get('slots', [])]])
        submitted = json.loads(receipt['stdout'])
        submitted = submitted.get('job', submitted)
        save_exact(submit_path, submitted)
    else:
        mode = 'smoke' if kind == 'smoke' else 'pilot'
        workspace = Path(manifest['runtime_workspace'])
        argv = python(CAMPAIGN / 'harness/physical.py', '--manifest', paths['manifest'],
            '--evidence', paths['evidence'], '--host-evidence', paths['host'], '--workspace', workspace, '--mode', mode)
        command_once(folder, 'launch', python(HERE / 'launch.py', '--manifest', paths['manifest'],
            '--snapshot', paths['snapshot'], '--mode', mode), inputs=[paths['manifest'], paths['snapshot']],
            outputs=[paths['records'] / 'queue-submit.json', paths['records'] / 'launch-intent.json'],
            absent=[paths['records'], paths['evidence'].parent, workspace])
        submitted = read(paths['records'] / 'queue-submit.json')
    notice('submitted', run_id=paths['run_id'], job_id=submitted['id'])
    return await_success(submitted, paths['queue'], argv)


def assess_stage(folder, kind, revision, paths, manifest, job):
    if kind == 'boundary':
        require(paths['assessment'].is_file(), 'Boundary suite result is missing')
        return
    args = ['--manifest', paths['manifest'], '--queue-receipt', paths['queue'], '--evidence', paths['evidence'],
            '--snapshot', paths['snapshot'], '--output', paths['assessment'], '--framework-revision', revision]
    if kind == 'native':
        script = HERE / 'assess_native.py'
    else:
        script = CAMPAIGN / 'assessment' / ('assess_smoke_v2.py' if kind == 'smoke' else 'assess.py')
        args += ['--host-evidence', paths['host'], '--workspace', manifest['runtime_workspace'],
                 '--manifest-sha256', sha(paths['manifest']), '--job-id', job['id']]
    command_once(folder, 'assess', python(script, *args),
                 inputs=[paths['manifest'], paths['snapshot'], paths['queue']],
                 outputs=[paths['assessment']], allow_failure=True)


def finish_stage(folder, kind, revision, paths, core):
    entry = {key: identity(paths[key]) for key in ('manifest', 'snapshot', 'queue', 'assessment')}
    entry['evidence'] = str(paths['evidence'])
    artifacts = {key: identity(CAMPAIGN / 'assessment' / filename) for key, filename in
                 [('base_assessor', 'assess.py'), ('smoke_assessor', 'assess_smoke_v2.py')]}
    error = None
    try:
        if kind == 'native':
            entry['assessor'] = identity(HERE / 'assess_native.py')
            admission.verify_native(entry, core, time.time(), artifacts)
        elif kind == 'boundary':
            admission.verify_boundary(entry, core, time.time())
        else:
            entry['host_evidence'] = str(paths['host'])
            if kind != 'smoke':
                entry['family'] = {'stock': 'misplaced-stock', 'home': 'blocked-insert-home'}[kind]
            admission.verify_model_qualifier(entry, 'smoke' if kind == 'smoke' else 'pilot', core, time.time(), artifacts)
    except Exception as failure:
        error = str(failure)
    result = read(paths['assessment'])
    validity = 'valid' if error is None else 'invalid'
    outcome = result['task_outcome'] if error is None and kind in ('stock', 'home') else ('success' if error is None else 'unknown')
    reason = 'Fixed final qualification passed' if error is None else 'Fixed final qualification failed: ' + error
    target = MAP / 'releases' / revision / ('result-' + paths['run_id'])
    command_once(folder, 'finish', python(CAMPAIGN / 'registry.py', 'finish', '--run-id', paths['run_id'],
        '--result', paths['assessment'], '--queue-receipt', paths['queue'], '--validity', validity,
        '--outcome', outcome, '--reason', reason), inputs=[paths['assessment'], paths['queue']],
        outputs=[target / 'result-record.json', target / 'result.json', target / 'queue.json'], absent=[target])
    save_exact(folder / 'disposition.json', {'run_id': paths['run_id'], 'passed': error is None,
               'error': error, 'entry': entry, 'registered_result': identity(target / 'result-record.json')})
    require(error is None, reason)
    notice('completed', run_id=paths['run_id'], job_id=read(paths['queue'])['id'])
    return entry


@contextmanager
def coordinator_lock():
    LEDGER.mkdir(parents=True, exist_ok=True)
    with (LEDGER / '.lock').open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'\0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run(readiness_path, expected_sha256):
    with coordinator_lock():
        readiness, core = preflight(readiness_path, expected_sha256)
        save_exact(LEDGER / 'preflight.json', {'schema': 'campaign002-final-qualification-preflight-1',
            'source_snapshot': readiness['source_snapshot'], 'coordinator': identity(__file__),
            'readiness': identity(readiness_path), 'readiness_sha256': expected_sha256,
            'diagnostic': readiness['diagnostic'], 'repair_test_receipt': readiness['repair_test_receipt'],
            'transport_diagnostic': readiness['transport_diagnostic'],
            'raw_event_preflight': readiness['raw_event_preflight'],
            'orchestration_sources': [identity(path) for path in (
                HERE / 'prepare_native.py', HERE / 'prepare_boundary_v3.py', HERE / 'prepare_model_v7.py',
                HERE / 'launch.py', HERE / 'assess_native.py', HERE / 'boundary_suite_v3.py',
                HERE / 'native_suite.py', CAMPAIGN / 'registry.py', CAMPAIGN / 'admission.py',
                CAMPAIGN / 'operate.py', QUEUE, operate.GUARD,
                CAMPAIGN / 'admission/storage-policy.json', CAMPAIGN / 'admission/storage-baseline-001.json',
                STARTUP_REPAIR_METHOD)],
            'stages': readiness['stages']})
        entries = []
        for name, kind, revision, seed in readiness['stages']:
            require(sha(readiness_path) == expected_sha256, 'Readiness changed during final qualification')
            assert_sources(readiness)
            folder, paths = LEDGER / name, entry_for(name, kind, revision)
            manifest = prepare_stage(folder, name, kind, revision, seed, paths, readiness)
            job = launch_stage(folder, kind, paths, manifest)
            if kind not in ('native', 'boundary'):
                storage_gate(folder, paths, manifest, job)
            assess_stage(folder, kind, revision, paths, manifest, job)
            entries.append(finish_stage(folder, kind, revision, paths, core))
        save_exact(LEDGER / 'completed.json', {'schema': 'campaign002-final-qualification-completed-1',
            'native': entries[0], 'boundary': entries[1], 'smoke': entries[2], 'pilots': entries[3:],
            'scope': 'Qualification entries only; requires separate final index, certificate and release admission.'})
        notice('all_qualification_stages_completed', evidence=str(LEDGER / 'completed.json'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--readiness', type=Path, required=True)
    parser.add_argument('--readiness-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        run(args.readiness.resolve(), args.readiness_sha256)
    except Exception as error:
        notice('stopped', error=str(error), reconciliation='No automatic retry or replacement is permitted.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
