"""Run the fixed final qualification sequence only after host-probe-004 passes.

This external coordinator is deliberately outside the runtime source inventory.
It invokes the existing preparers, registry, direct shared queue and assessors.
An intent without a completed command receipt requires operator reconciliation;
no submission, failed command, failed assessment or existing output is retried.
Invoke with --probe-queue-receipt PATH --probe-assessment PATH after the probe.
It never creates a campaign certificate, release or scored attempt.

This unlaunched v2 draft binds the instrumentation-only probe004/dev009 pass.
That pass neither attributes nor resolves probe003's I/O stall. Every remaining
native, boundary, actual-model smoke and family pilot qualification is required.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
MAP = RCI.parent / 'Architecture Map'
RAW = RCI / 'local-evidence/campaign002/qualification'
LEDGER = HERE / 'final-qualification-002'
PYTHON = REPO / 'venv/Scripts/python.exe'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
BASE_REVISION = 'RCI001-C02-dev-009'
BASE_SNAPSHOT = MAP / 'releases' / BASE_REVISION / 'snapshot.json'
BASE_SNAPSHOT_SHA = 'f43baf0b4728c20516d571209a6fcc96d63c28f576ba615812ffc43ad44a00e8'
PROBE_ID = 'RCI001-C02-host-probe-004'
PROBE_JOB = '20260927T230552620519Z-60d9eea8'
PROBE_MANIFEST = HERE / 'host-probe-004-manifest.json'
PROBE_MANIFEST_SHA = '207300f467ab7f71be4f3a3e28b425115b99859879147c4bb415a708e4f1d57d'
PROBE_QUEUE = HERE / PROBE_ID / 'official-status.json'
PROBE_QUEUE_SHA = '41814727a1e255b11fe55f75f8c3941dbca550bfb44502cb991b2ae375e1df8f'
PROBE_ASSESSMENT = HERE / 'host-probe-004-assessment.json'
PROBE_ASSESSMENT_SHA = '3180add4004ed7091212364ec62ed5906e2669018d0d82cd59cbc8ac7f0f06b4'
STAGES = (('native-002', 'native', 'RCI001-C02-dev-012', 24000),
          ('boundary-004', 'boundary', 'RCI001-C02-dev-013', None),
          ('smoke-002', 'smoke', 'RCI001-C02-dev-014', 24101),
          ('pilot-stock-001', 'stock', 'RCI001-C02-dev-014', 24102),
          ('pilot-home-001', 'home', 'RCI001-C02-dev-014', 24103))
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


def assert_sources(snapshot_path=BASE_SNAPSHOT):
    require(sha(BASE_SNAPSHOT) == BASE_SNAPSHOT_SHA, 'Frozen dev009 trust anchor changed')
    frozen = read(BASE_SNAPSHOT)
    require(not admission.base.frozen_problems(BASE_SNAPSHOT, frozen, BASE_REVISION),
            'Frozen dev009 source/archive identity changed')
    core = admission.runtime_identities(frozen)
    prefix = (CAMPAIGN / 'assessment').relative_to(REPO).as_posix() + '/'
    assessor_names = {name for name in frozen['sources'] if name.startswith(prefix)}
    current_names = {path.relative_to(REPO).as_posix() for path in (CAMPAIGN / 'assessment').rglob('*.py')}
    require(assessor_names == current_names, 'Dev009 assessor module set changed')
    core.update({name: frozen['sources'][name] for name in assessor_names})
    if Path(snapshot_path) != BASE_SNAPSHOT:
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


def preflight(probe_queue, probe_assessment):
    # Fresh official authentication precedes all assessment/host output reads.
    job = admission.base.queue_gate(official(PROBE_JOB), PROBE_JOB)
    require(admission.same_path(probe_queue, PROBE_QUEUE) and sha(probe_queue) == PROBE_QUEUE_SHA,
            'Pinned probe official receipt path/hash changed')
    require(read(probe_queue) == job, 'Probe retained receipt differs from official queue')
    core = assert_sources()
    require(sha(PROBE_MANIFEST) == PROBE_MANIFEST_SHA, 'Fixed 900-second probe manifest changed')
    require(admission.same_path(probe_assessment, PROBE_ASSESSMENT)
            and sha(probe_assessment) == PROBE_ASSESSMENT_SHA, 'Pinned probe assessment path/hash changed')
    spec = importlib.util.spec_from_file_location('final_qualification_probe', HERE / 'assess_host_probe.py')
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    replayed = evaluator.evaluate(PROBE_MANIFEST, RAW / PROBE_ID, Path(probe_queue), BASE_SNAPSHOT)
    require(read(probe_assessment) == replayed, 'Retained probe assessment differs from independent replay')
    require(replayed.get('diagnostic_passed') is True and not replayed.get('errors')
            and replayed.get('run_id') == PROBE_ID and replayed.get('queue_job_id') == PROBE_JOB
            and replayed.get('framework_revision') == BASE_REVISION,
            'Host-probe-004 did not qualify unchanged dev009')
    admission.strict_timing_summary(replayed.get('timing'), 'Host-probe-004')
    return core


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


def prepare_stage(folder, name, kind, revision, seed, paths):
    manifest, snapshot = paths['manifest'], paths['snapshot']
    args = ['--run-id', paths['run_id'], '--revision', revision, '--output', manifest]
    if kind == 'native':
        prepare = python(HERE / 'prepare_native.py', *args, '--seed-base', seed)
    elif kind == 'boundary':
        prepare = python(HERE / 'prepare_boundary.py', *args)
    else:
        prepare = python(HERE / 'prepare_model.py', *args, '--kind', kind, '--seed', seed)
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
    assert_sources(snapshot)
    return value


def launch_stage(folder, kind, paths, manifest):
    if kind in ('native', 'boundary'):
        submit_path = HERE / (paths['run_id'].removeprefix('RCI001-C02-') + '-submit.json')
        argv = python(HERE / (kind + '_suite.py'), *(
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


def run(probe_queue, probe_assessment):
    with coordinator_lock():
        core = preflight(probe_queue, probe_assessment)
        save_exact(LEDGER / 'preflight.json', {'schema': 'campaign002-final-qualification-preflight-1',
            'source_snapshot': identity(BASE_SNAPSHOT), 'coordinator': identity(__file__),
            'probe_queue': identity(probe_queue), 'probe_assessment': identity(probe_assessment),
            'orchestration_sources': [identity(path) for path in (
                HERE / 'prepare_native.py', HERE / 'prepare_boundary.py', HERE / 'prepare_model.py',
                HERE / 'launch.py', HERE / 'assess_native.py', HERE / 'boundary_suite.py',
                HERE / 'native_suite.py', CAMPAIGN / 'registry.py', CAMPAIGN / 'admission.py',
                CAMPAIGN / 'operate.py', QUEUE, operate.GUARD,
                CAMPAIGN / 'admission/storage-policy.json', CAMPAIGN / 'admission/storage-baseline-001.json')],
            'stages': [list(stage) for stage in STAGES]})
        entries = []
        for name, kind, revision, seed in STAGES:
            assert_sources()
            folder, paths = LEDGER / name, entry_for(name, kind, revision)
            manifest = prepare_stage(folder, name, kind, revision, seed, paths)
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
    parser.add_argument('--probe-queue-receipt', type=Path, required=True)
    parser.add_argument('--probe-assessment', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        run(args.probe_queue_receipt.resolve(), args.probe_assessment.resolve())
    except Exception as error:
        notice('stopped', error=str(error), reconciliation='No automatic retry or replacement is permitted.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
