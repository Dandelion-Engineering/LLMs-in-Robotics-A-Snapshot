"""One unchanged smoke interruption invocation; never resume or qualify."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import common
sys.path.insert(0,str(common.PACKET))
import trace_control


def execute(args):
    common.control_digest(args.observer_config_sha256)
    common.validate(args.manifest, args.snapshot)
    common.output_paths(args.evidence, args.host_evidence, args.workspace)
    physical = common.load_physical()
    args.evidence.mkdir(parents=True, exist_ok=False)
    args.workspace.mkdir(parents=True, exist_ok=False)
    result = {'schema': 'campaign002-single-interrupt-diagnostic-1', 'run_id': common.RUN,
              'framework_revision': common.REVISION, 'diagnostic_only': True,
              'qualifier_claim': False, 'scorable': False, 'task_outcome': 'unknown',
              'model_invocations_max': 1, 'mode': 'interrupt', 'stages': [],
              'orchestrator_completed': False, 'resume_attempted': False}
    control = host = stdout = stderr = capture = None
    trace_events=[]
    original_transition=physical.transition
    try:
        capture=trace_control.Client(expected_sha=args.observer_config_sha256)
        physical.transition=trace_control.wrap_transition(original_transition,capture,trace_events)
        prewarm_started = time.time()
        warm = subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c',
            'import json,sys; print(json.dumps({"python":sys.version_info[:3],"ready":True}))'],
            capture_output=True, text=True, encoding='utf-8', timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if warm.returncode or json.loads(warm.stdout).get('ready') is not True:
            raise RuntimeError('WSL prewarm failed before host start')
        physical.write_json(args.evidence / 'prewarm.json', {'started_unix_s': prewarm_started,
            'finished_unix_s': time.time(), 'ready': True,
            'scope': 'Existing service warmup before physics; no model'})
        stdout = (args.evidence / 'host.stdout').open('x', encoding='utf-8')
        stderr = (args.evidence / 'host.stderr').open('x', encoding='utf-8')
        host = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(common.CAMPAIGN / 'harness/run_host.py'),
            '--manifest', str(args.manifest), '--evidence', str(args.host_evidence),
            '--runtime-workspace', str(args.workspace)], stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if host.poll() is not None:
                raise RuntimeError('Host exited before activation')
            endpoint_path = args.host_evidence / 'operator-endpoint.json'
            if endpoint_path.exists():
                control = common.read(endpoint_path)
                state = physical.operator(control, 'GET', 'status')
                if state['owner'] == 'robot' and not state.get('active_command'):
                    break
            time.sleep(.2)
        else:
            raise RuntimeError('Host activation deadline')
        # The only invocation call. The unchanged function owns the 600-second
        # model bound, canaries, action trigger, authority retirement and exports.
        first = physical.run_invocation('interrupt', args.evidence / 'interrupt', control, args.workspace)
        result['stages'].append(first)
        if not capture.armed or any(e['error'] for e in trace_events):
            raise RuntimeError('Trace arming failed; original runtime cleanup was retained')
        if not (first.get('injected_interruption') and first.get('durable_retention_verified')
                and first.get('old_token_denied_after_retirement') and first.get('all_namespaces_retired')
                and first.get('cleanup_clean')):
            raise RuntimeError('Interruption stage failed its gate; diagnostic ends without restart')
        result['orchestrator_completed'] = True
    except Exception as error:
        result['error'] = str(error)
    finally:
        physical.transition=original_transition
        result['trace_arming']=trace_events
        if capture is not None:
            try:
                result['trace_control_completion']=capture.finish()
            except Exception as error:
                result['trace_error']=str(error)
                result['orchestrator_completed']=False
            result['trace_control_events']=capture.events
        if host is not None:
            if control and host.poll() is None:
                try:
                    physical.transition(control, 'stop', reason='Bounded readiness smoke complete')
                except Exception as error:
                    result['stop_error'] = str(error)
            try:
                host.wait(timeout=25)
            except subprocess.TimeoutExpired:
                host.terminate(); host.wait(timeout=10); result['forced_host_exit'] = True
            result['host_exit_code'] = host.returncode
        for stream in (stdout, stderr):
            if stream is not None:
                stream.close()
        common.save(args.evidence / 'sequence-result.json', result)
    print(json.dumps({'diagnostic_only': True, 'orchestrator_completed': result['orchestrator_completed'],
                      'error': result.get('error'), 'stages': len(result['stages']), 'resume_attempted': False}))
    return 0 if result['orchestrator_completed'] and result.get('host_exit_code') == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'snapshot', 'evidence', 'host-evidence', 'workspace'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--observer-config-sha256',required=True)
    return execute(parser.parse_args(argv))


if __name__ == '__main__':
    raise SystemExit(main())
