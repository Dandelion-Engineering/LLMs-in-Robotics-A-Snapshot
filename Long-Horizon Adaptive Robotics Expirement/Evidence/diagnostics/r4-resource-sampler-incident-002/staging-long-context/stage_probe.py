"""Queue-only, single-shot infrastructure diagnosis; never a robot/policy episode."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
import types
import uuid

SCRIPT = Path(__file__).resolve()
EXP = SCRIPT.parents[4]
RUNTIME = EXP / 'Runtime 004'
PLAN = SCRIPT.with_name('stage-probe-plan.json')
sys.path.insert(0, str(RUNTIME))
import release_runner as rr


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


AUTH_PATH = EXP / 'Batch 01' / 'Calibration Tools' / 'calibration_authority.py'
CAP_PATH = EXP / 'Batch 01' / 'Recovery Qualification' / 'process_caps.py'
authority = module('stage_probe_authority', AUTH_PATH)
caps = module('stage_probe_caps', CAP_PATH)


def source_inventory():
    paths = [SCRIPT, PLAN, AUTH_PATH, CAP_PATH, Path(subprocess.__file__),
             Path(sys.executable), EXP.parent / 'requirements.txt',
             EXP / 'Runtime' / 'vendor' / 'model' / 'asset_manifest.json']
    paths.extend(sorted(RUNTIME.glob('*.py')))
    return {str(p.resolve()): sha(p) for p in paths}


def safe_queue_state():
    """Read live queue bytes with the required Windows delete-sharing handle."""
    path = str(rr.QUEUE_STATE).replace("'", "''")
    command = ("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$fs=[IO.FileStream]::new('" + path + "',[IO.FileMode]::Open,[IO.FileAccess]::Read,"
        "([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)); $sr=[IO.StreamReader]::new($fs); "
        "try { $raw=$sr.ReadToEnd() } finally { $sr.Dispose(); $fs.Dispose() }; [Console]::Write($raw)")
    reply = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',
        timeout=8.,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
    if reply.returncode != 0 or len(reply.stdout) > 32*1024*1024:
        raise RuntimeError('Delete-sharing queue snapshot failed: ' + reply.stderr[:500])
    return json.loads(reply.stdout)


def safe_queued_job():
    """Run the original authority checks with only the queue reader replaced."""
    original_load = rr.load
    def load_with_safe_queue(path):
        if Path(path).resolve() == Path(rr.QUEUE_STATE).resolve():
            return safe_queue_state()
        return original_load(path)
    private_globals = dict(rr.queued_job.__globals__, load=load_with_safe_queue)
    private_check = types.FunctionType(rr.queued_job.__code__, private_globals,
        rr.queued_job.__name__, rr.queued_job.__defaults__, rr.queued_job.__closure__)
    private_check.__kwdefaults__ = rr.queued_job.__kwdefaults__
    assert private_check.__code__ is rr.queued_job.__code__
    return private_check(expected_script=SCRIPT)


class Trace:
    """Independent per-thread streams avoid a shared diagnostic logging lock."""
    def __init__(self, directory):
        self.directory = directory; directory.mkdir()
        self.local = threading.local(); self.phase = 'initialization'

    def emit(self, event, **fields):
        if not hasattr(self.local, 'stream'):
            name = ''.join(c if c.isalnum() else '-' for c in threading.current_thread().name)
            path = self.directory / f'{name}-{threading.get_ident()}-{time.time_ns()}.jsonl'
            self.local.stream = path.open('x', encoding='utf-8', newline='\n', buffering=1)
        row = dict(event=event, utc=utc(), monotonic_s=time.perf_counter(), phase=self.phase,
                   thread=threading.current_thread().name,
                   capture_id=getattr(self.local, 'capture_id', None), **fields)
        self.local.stream.write(json.dumps(row, allow_nan=False, separators=(',', ':')) + '\n')
        self.local.stream.flush()

    def call(self, stage, function, *args, **kwargs):
        # Flush the entry marker before the timed native call. A hang retains it.
        self.emit(stage + '_enter')
        start = time.perf_counter()
        try:
            result = function(*args, **kwargs)
        except BaseException as exc:
            end = time.perf_counter()
            self.emit(stage + '_exit', call_started_monotonic_s=start,
                      call_ended_monotonic_s=end, duration_s=end-start,
                      error=f'{type(exc).__name__}: {exc}')
            raise
        end = time.perf_counter()
        self.emit(stage + '_exit', call_started_monotonic_s=start,
                  call_ended_monotonic_s=end, duration_s=end-start, error=None)
        return result

    def close_thread(self):
        stream = getattr(self.local, 'stream', None)
        if stream is not None:
            stream.flush(); stream.close(); del self.local.stream


class FirstFailure:
    def __init__(self, trace):
        self.event = threading.Event(); self.lock = threading.Lock()
        self.value = None; self.trace = trace

    def record(self, kind, details):
        with self.lock:
            if self.value is not None:
                return
            self.value = dict(kind=kind, details=details, utc=utc(),
                              monotonic_s=time.perf_counter(), phase=self.trace.phase)
            self.event.set()
        self.trace.emit('first_failure', failure=self.value)


def instrument_gpu(resources, trace, failure):
    """Clone function environments, not bodies; never patch global subprocess."""
    class TimedGPUProcess(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            self.diag_killed = False
            trace.emit('gpu_command', argv=args[0], kwargs={k: v for k, v in kwargs.items()
                       if isinstance(v, (str, int, float, bool, type(None)))})
            trace.call('gpu_popen', super().__init__, *args, **kwargs)
            trace.emit('gpu_process_created', pid=self.pid)

        def communicate(self, input=None, timeout=None):
            stage = 'gpu_timeout_drain' if self.diag_killed and timeout is None else 'gpu_communicate'
            trace.emit('gpu_communicate_parameters', timeout_s=timeout, after_kill=self.diag_killed)
            return trace.call(stage, super().communicate, input=input, timeout=timeout)

        def kill(self):
            self.diag_killed = True
            return trace.call('gpu_kill', super().kill)

        def wait(self, timeout=None):
            return trace.call('gpu_wait', super().wait, timeout=timeout)

        def __exit__(self, *args):
            return trace.call('gpu_context_exit', super().__exit__, *args)

    run_globals = dict(subprocess.run.__globals__, Popen=TimedGPUProcess)
    private_run = types.FunctionType(subprocess.run.__code__, run_globals,
                                    subprocess.run.__name__, subprocess.run.__defaults__,
                                    subprocess.run.__closure__)
    private_run.__kwdefaults__ = dict(subprocess.run.__kwdefaults__ or {})

    class GPUOnlySubprocess:
        run = staticmethod(private_run)
        def __getattr__(self, name):
            return getattr(subprocess, name)

    gpu_globals = dict(resources.gpu_sample.__globals__, subprocess=GPUOnlySubprocess())
    exact_gpu = types.FunctionType(resources.gpu_sample.__code__, gpu_globals,
                                  resources.gpu_sample.__name__, resources.gpu_sample.__defaults__,
                                  resources.gpu_sample.__closure__)
    exact_gpu.__kwdefaults__ = resources.gpu_sample.__kwdefaults__
    assert private_run.__code__ is subprocess.run.__code__
    assert exact_gpu.__code__ is resources.gpu_sample.__code__

    def reader(**kwargs):
        result = trace.call('gpu_reader', exact_gpu, **kwargs)
        trace.emit('gpu_observation', result=result)
        if result.get('missing_reason') or not result.get('devices'):
            failure.record('gpu_observation_unavailable', result)
        return result
    return reader


def child(args):
    raw = args.parent_manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.parent_manifest_sha256:
        raise RuntimeError('Parent manifest hash differs')
    manifest = json.loads(raw); proof = manifest['queue']; output = args.output.resolve()
    if (args._child != 'probe' or args.seed != 0 or manifest['modes'] != ['probe']
            or output != args.parent_manifest.resolve().parent / 'probe'
            or Path(proof['script']).resolve() != SCRIPT):
        raise RuntimeError('Child declaration differs from exact parent command')
    expected = authority.child_command(proof['launcher_executable'], SCRIPT, 'probe', output,
                                       0, args.parent_manifest.resolve(), args.parent_manifest_sha256)
    rows = rr.windows_process_metadata(os.getpid(), os.getppid())
    rows.update(rr.windows_process_metadata(proof['pid'], proof['parent_pid']))
    jobs = [j for j in safe_queue_state().get('jobs', []) if j.get('id') == proof['job_id']]
    if len(jobs) != 1 or rr.python_entrypoint(jobs[0]['argv'], jobs[0]['cwd']) != SCRIPT:
        raise RuntimeError('Actual parent queue entrypoint differs')
    child_proof = authority.validate_child_chain(manifest, jobs[0], os.getpid(), os.getppid(), rows, expected)
    caps.join_job(manifest['containment_job'])
    if source_inventory() != manifest['sources_before']:
        raise RuntimeError('Source inventory changed before child workload')
    output.mkdir()
    import resources
    import model_runtime
    from experiment import RESOURCE_POLICY, resource_breaches, protected_model_snapshot, model_lifecycle_failure
    if any(Path(m.__file__).resolve().parent != RUNTIME for m in (resources, model_runtime, rr)):
        raise RuntimeError('Runtime import escaped Runtime 004')
    trace = Trace(output / 'stage-traces'); failure = FirstFailure(trace)
    model = None; sampler = None; inference = None; inference_stop = threading.Event()
    cleanup = []; cleanup_observations = []; phases = []; calls = []; sampler_reports = []; active_sampler_started = None
    gpu_reader = instrument_gpu(resources, trace, failure)

    def snapshot():
        return trace.call('model_pid_lookup', protected_model_snapshot, model)

    def model_pid():
        current = snapshot()
        return current.resource_pid if current is not None else None

    def process_reader(pid):
        value = trace.call('windows_process_read', resources.windows_process_sample, pid)
        trace.emit('process_observation', pid=pid, result=value)
        if pid is not None and (value.get('rss_bytes') is None or value.get('private_commit_bytes') is None):
            failure.record('process_observation_unavailable', value)
        return value

    class TimedStream:
        def __init__(self, stream): self.stream = stream
        def write(self, value): return trace.call('resource_stream_write', self.stream.write, value)
        def flush(self): return trace.call('resource_stream_flush', self.stream.flush)
        def close(self): return trace.call('resource_stream_close', self.stream.close)

    class TimedSampler(resources.ResourceSampler):
        def _capture(self):
            if not isinstance(self._stream, TimedStream):
                self._stream = TimedStream(self._stream)
            trace.local.capture_id = str(self.path.name) + ':' + str(self._sample_count + 1)
            return trace.call('capture', super()._capture)

        def __setattr__(self, name, value):
            super().__setattr__(name, value)
            if name == '_latest' and value is not None:
                trace.emit('sample_published', capture_monotonic_s=value['capture_monotonic_s'],
                           capture_duration_s=value['capture_duration_s'],
                           publication_age_s=time.perf_counter()-value['capture_monotonic_s'])

        def _run(self):
            try: super()._run()
            finally: trace.close_thread()

    def begin_sampler(name):
        nonlocal sampler, active_sampler_started
        active_sampler_started = time.perf_counter()
        sampler = TimedSampler(output / (name + '-resources.jsonl'), model_pid=model_pid,
                               period_s=5., gpu_timeout_s=2., process_reader=process_reader, gpu_reader=gpu_reader)
        sampler.start()

    def end_sampler():
        nonlocal sampler
        if sampler is None: return
        current = sampler
        try: trace.call('sampler_close', current.close)
        except Exception as exc:
            observation = f'sampler close: {type(exc).__name__}: {exc}'
            cleanup_observations.append(observation)
            trace.emit('original_sampler_close_failed', error=observation)
            # Additional diagnostic cleanup only; the original failure stays recorded.
            # Do not kill an in-flight query before its timeout/drain stages are visible.
            trace.call('diagnostic_sampler_drain', current._thread.join, timeout=10.)
            if current._thread.is_alive(): cleanup.append(observation)
        report = current.summary(); sampler_reports.append(report)
        if report.get('failure'): failure.record('sampler_failure', report)
        if report['sampler_stopped']: sampler = None

    def check_resources():
        now = time.perf_counter(); current = protected_model_snapshot(model)
        breaches = resource_breaches(sampler.latest(), now_monotonic_s=now,
            sampler_started_monotonic_s=active_sampler_started, model_required=model is not None,
            model_pid=current.resource_pid if current is not None else None, model_lifecycle=current)
        if breaches: failure.record('frozen_resource_watchdog', breaches)
        lifecycle = model_lifecycle_failure(current, at_monotonic_s=now)
        if lifecycle: failure.record('model_lifecycle_failure', lifecycle)
        if failure.event.is_set(): sampler._stop.set()  # No further captures after first failure.

    def window(name, duration):
        trace.phase = name; start = time.perf_counter(); next_check = start
        trace.emit('phase_start', duration_s=duration)
        while time.perf_counter()-start < duration and not failure.event.is_set():
            now = time.perf_counter()
            if now >= next_check:
                next_check = now + .25
                check_resources()
            time.sleep(.02)
        if failure.event.is_set(): sampler._stop.set()
        phases.append(dict(name=name, duration_requested_s=duration, started_monotonic_s=start,
                           ended_monotonic_s=time.perf_counter(), interrupted=failure.event.is_set()))
        trace.emit('phase_end', record=phases[-1])

    def infer():
        try:
            for index in range(120):
                if inference_stop.is_set() or failure.event.is_set(): break
                start = time.perf_counter()
                try:
                    response = trace.call('generic_model_request', model.generate_json,
                        manifest['plan']['generic_prompt'], manifest['plan']['generic_schema'],
                        max_tokens=1024, timeout_s=30.)
                    record = dict(index=index, started_monotonic_s=start,
                                  ended_monotonic_s=time.perf_counter(), response=response, error=None)
                except Exception as exc:
                    record = dict(index=index, started_monotonic_s=start,
                                  ended_monotonic_s=time.perf_counter(), error=f'{type(exc).__name__}: {exc}')
                    failure.record('model_request_failure', record)
                calls.append(record); trace.emit('generic_model_result', record=record)
                if record['error'] is not None: break
        finally: trace.close_thread()

    started = utc(); unexpected = None
    try:
        begin_sampler('host'); window('idle_host', 30.); end_sampler()
        if not failure.event.is_set() and not cleanup:
            trace.phase = 'model_startup'
            model = model_runtime.LocalModel(model_runtime.ModelConfig(), log_path=output / 'model-server.log')
            trace.call('model_start', model.start)
            write_new(output / 'model-identity.json', model.identity)
            begin_sampler('model'); window('loaded_model_idle', 30.)
            if not failure.event.is_set():
                trace.phase = 'generic_inference'
                inference = threading.Thread(target=infer, name='generic-inference', daemon=True)
                inference.start(); window('generic_inference', 120.)
    except BaseException as exc:
        unexpected = f'{type(exc).__name__}: {exc}'
        failure.record('diagnostic_exception', unexpected)
    finally:
        trace.phase = 'cleanup'; inference_stop.set()
        # Keep sampling through the final request's unchanged budget; never submit a retry.
        if inference is not None:
            deadline = time.perf_counter() + 31.
            while inference.is_alive() and time.perf_counter() < deadline:
                inference.join(timeout=.25)
                if sampler is not None: check_resources()
            if inference.is_alive():
                failure.record('request_drain_timeout', {'join_limit_s':31.})
        end_sampler()
        if model is not None:
            try: trace.call('model_stop', model.stop)
            except Exception as exc: cleanup.append(f'model stop: {type(exc).__name__}: {exc}')
        if inference is not None and inference.is_alive():
            inference.join(timeout=2.)
            if inference.is_alive(): cleanup.append('generic inference thread still alive after model stop')
        if sampler is not None: cleanup.append('resource sampler still alive; parent containment will terminate descendants')
        source_unchanged = source_inventory() == manifest['sources_before']
        result = dict(schema_version='resource-stage-probe-child-1', started_at=started, ended_at=utc(),
            scope=manifest['plan']['scope'], queue_job_id=proof['job_id'], child_authority=child_proof,
            phases=phases, first_failure=failure.value, unexpected_error=unexpected,
            cleanup_errors=cleanup, cleanup_observations=cleanup_observations,
            sampler_reports=sampler_reports, model_calls_recorded=len(calls),
            sources_unchanged=source_unchanged, resource_policy=RESOURCE_POLICY,
            all_phases_completed=len(phases)==3 and not any(p['interrupted'] for p in phases),
            no_failure_observed=failure.value is None and not cleanup and source_unchanged,
            continuation_authorized=False, nonrecurrence_established=False,
            notes=manifest['plan']['limitations'])
        write_new(output / 'result.json', result)
        trace.emit('diagnostic_finished', first_failure=failure.value, cleanup_errors=cleanup)
        trace.close_thread()
    return 2 if unexpected or cleanup or not source_unchanged else 0


def parent(args):
    job = safe_queued_job()
    if os.name != 'nt': raise RuntimeError('This diagnostic uses the declared Windows containment')
    output = args.output.resolve()
    if not args.output.is_absolute() or not output.parent.is_dir():
        raise RuntimeError('Require a fresh absolute output beneath an existing directory')
    output.mkdir()
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if plan['phase_seconds'] != [30, 30, 120] or plan['parent_wall_limit_s'] != 480:
        raise RuntimeError('Prospective fixed phase/wall plan differs')
    rows = rr.windows_process_metadata(os.getpid(), os.getppid())
    proof = dict(job_id=job['id'], pid=os.getpid(), parent_pid=os.getppid(), argv=job['argv'],
                 started_at=job['started_at'], queue_job=job, driver_metadata=rows[os.getpid()],
                 driver_parent_metadata=rows[os.getppid()], launcher_executable=str(Path(sys.executable).resolve()),
                 base_executable=str(Path(sys._base_executable).resolve()), script=str(SCRIPT))
    before = source_inventory(); name = 'Local\\LLMsResourceStageProbe-' + uuid.uuid4().hex
    manifest = dict(schema_version='resource-stage-probe-parent-1', created_at=utc(), queue=proof,
                    modes=['probe'], seed=0, containment_job=name, plan=plan, sources_before=before,
                    python=sys.version, platform=platform.platform())
    manifest_path = output / 'manifest.json'; write_new(manifest_path, manifest)
    command = authority.child_command(sys.executable, SCRIPT, 'probe', output / 'probe', 0,
                                      manifest_path, sha(manifest_path))
    cap = caps.JobCap(name); timed_out = False; error = None; code = None; child_pid = None
    try:
        with (output/'child.stdout.log').open('x') as stdout, (output/'child.stderr.log').open('x') as stderr:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW, cwd=str(EXP.parent))
            child_pid = process.pid
            try: code = process.wait(timeout=480.)
            except subprocess.TimeoutExpired:
                timed_out = True; cap.terminate()
                try: code = process.wait(timeout=10.)
                except subprocess.TimeoutExpired:
                    process.kill(); code = process.wait(timeout=10.)
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        cap.terminate()
    finally:
        cap.close()
    after = source_inventory(); child_result_path = output/'probe'/'result.json'
    result = json.loads(child_result_path.read_text(encoding='utf-8')) if child_result_path.is_file() else None
    complete = code == 0 and not timed_out and error is None and before == after and result is not None
    report = dict(schema_version='resource-stage-probe-1', ended_at=utc(), queue_job_id=job['id'],
        command=command, child_launcher_pid=child_pid, child_exit_code=code, parent_wall_timeout=timed_out,
        error=error, inputs_before=before, inputs_after=after, sources_unchanged=before==after,
        manifest={'path':str(manifest_path),'sha256':sha(manifest_path)},
        child_result={'path':str(child_result_path),'sha256':sha(child_result_path)} if result else None,
        first_failure=result.get('first_failure') if result else None,
        diagnostic_collection_completed=complete,
        no_failure_observed=result.get('no_failure_observed',False) if result else False,
        continuation_authorized=False, nonrecurrence_established=False)
    write_new(output/'report.json', report)
    print(json.dumps({'report':str(output/'report.json'), 'diagnostic_collection_completed':complete,
                      'no_failure_observed':report['no_failure_observed']}))
    return 0 if complete else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--_child', choices=['probe'])
    parser.add_argument('--seed', type=int)
    parser.add_argument('--parent-manifest', type=Path)
    parser.add_argument('--parent-manifest-sha256')
    arguments = parser.parse_args()
    raise SystemExit(child(arguments) if arguments._child else parent(arguments))
