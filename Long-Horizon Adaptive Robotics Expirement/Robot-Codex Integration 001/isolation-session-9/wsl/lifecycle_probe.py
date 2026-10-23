"""Nonmodel disconnect probe for an already-running isolated exec-server bridge.

This helper creates only two bounded sleeping Linux processes. It positively
locates their PID namespace through outer WSL /proc metadata, disconnects the
executor client, and requires that namespace to have no surviving processes.
It neither starts the bridge nor changes any sandbox or gateway policy.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
from pathlib import Path
import time
import uuid


_SLEEP_WITNESS = r'''
import json,os,subprocess,sys,time
marker=sys.argv[1]
# A detached session verifies that cleanup is not limited to the direct child.
# Both processes self-expire if lifecycle enforcement fails during this probe.
child=subprocess.Popen([sys.executable,'-I','-B','-c',
    'import time; time.sleep(90)',marker],start_new_session=True)
print(json.dumps({'kind':'lifecycle_witness','marker':marker,
    'parent_pid':os.getpid(),'descendant_pid':child.pid,
    'pid_namespace':os.readlink('/proc/self/ns/pid'),
    'self_expiry_seconds':90}),flush=True)
time.sleep(90)
'''


_SCAN_NAMESPACE = r'''
import json,os,pathlib,re,sys
target=sys.argv[1]
if not re.fullmatch(r'pid:\[\d+\]',target):
    raise SystemExit('Invalid PID namespace identity')
entries=[p for p in pathlib.Path('/proc').iterdir() if p.name.isdecimal()]
if len(entries)>8192:
    raise SystemExit('Process inventory exceeds bounded probe limit')
matches=[];denied=0
for p in entries:
    try:
        if os.readlink(p/'ns/pid')!=target:
            continue
        fields={}
        for line in (p/'status').read_text().splitlines():
            if line.startswith(('NSpid:','State:')):
                key,value=line.split(':',1);fields[key]=value.strip()
        matches.append({'host_pid':int(p.name),
            'namespace_pids':[int(v) for v in fields.get('NSpid','').split()],
            'state':fields.get('State')})
    except FileNotFoundError:
        pass
    except PermissionError:
        denied+=1
print(json.dumps({'pid_namespace':target,'matches':matches,
    'other_namespace_links_denied':denied,'scanned_processes':len(entries)}))
'''


async def _scan_namespace(distribution: str, namespace: str) -> dict:
    process = await asyncio.create_subprocess_exec(
        'wsl.exe', '--distribution', distribution, '--exec',
        '/usr/bin/python3', '-I', '-B', '-c', _SCAN_NAMESPACE, namespace,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 5)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await asyncio.wait_for(process.wait(), 3)
        raise
    if process.returncode:
        raise RuntimeError('Outer namespace observation failed: ' +
                           stderr.decode(errors='replace')[:1000])
    return json.loads(stdout)


async def exercise_disconnect(url: str, evidence: Path,
                              distribution: str = 'Ubuntu-24.04',
                              retirement_timeout: float = 15) -> dict:
    """Probe one bridge connection, preserve evidence, and fail closed on error.

    The bridge URL can contain a capability path and is never written to evidence.
    Call this only after the owning launcher has completed its boundary canaries.
    An observed namespace baseline is mandatory: missing visibility cannot count
    as successful retirement. The caller still owns trusted bridge/gateway cleanup.
    """
    from websockets.asyncio.client import connect

    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    record_path = evidence / 'lifecycle-disconnect.json'
    if record_path.exists():
        raise FileExistsError('Refusing to overwrite lifecycle evidence')
    marker = 'robot-codex-lifecycle-' + uuid.uuid4().hex
    result = {'qualified': False, 'scope': 'nonmodel disconnect and descendant retirement',
              'marker': marker, 'distribution': distribution,
              'processes_self_expire_after_seconds': 90,
              'host_files_written_by_guest': False}
    stdout = bytearray()
    witness = None
    counter = 0
    process_id = 'lifecycle-' + uuid.uuid4().hex

    def consume(message):
        nonlocal witness
        if message.get('method') != 'process/output':
            return
        params = message.get('params', {})
        if params.get('processId') != process_id or params.get('stream') != 'stdout':
            return
        stdout.extend(base64.b64decode(params['chunk'], validate=True))
        if len(stdout) > 32768:
            raise RuntimeError('Lifecycle witness exceeded output bound')
        if b'\n' in stdout and witness is None:
            candidate = json.loads(bytes(stdout).split(b'\n', 1)[0])
            if candidate.get('kind') != 'lifecycle_witness' or candidate.get('marker') != marker:
                raise RuntimeError('Unexpected lifecycle witness')
            witness = candidate

    try:
        async with connect(url, max_size=1024 * 1024, open_timeout=10,
                           close_timeout=3, origin=None) as websocket:
            async def call(method, params):
                nonlocal counter
                counter += 1
                request_id = counter
                await websocket.send(json.dumps({'id': request_id, 'method': method,
                                                  'params': params}))
                deadline = time.monotonic() + 15
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Executor request exceeded lifecycle deadline')
                    message = json.loads(await asyncio.wait_for(websocket.recv(), remaining))
                    consume(message)
                    if message.get('id') == request_id:
                        if 'error' in message:
                            raise RuntimeError(method + ' rejected: ' + str(message['error']))
                        return message

            await call('initialize', {'clientName': 'robot-codex-lifecycle-nonmodel'})
            await websocket.send(json.dumps({'method': 'initialized', 'params': {}}))
            result['process_start'] = await call('process/start', {
                'processId': process_id,
                'argv': ['/usr/bin/python3', '-I', '-B', '-c', _SLEEP_WITNESS, marker],
                'cwd': 'file:///workspace', 'env': {'PATH': '/usr/bin:/bin', 'HOME': '/workspace'},
                'tty': False, 'arg0': None, 'sandbox': None})
            deadline = time.monotonic() + 15
            while witness is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Executor did not produce lifecycle witness')
                consume(json.loads(await asyncio.wait_for(websocket.recv(), remaining)))
            result['witness'] = witness
            baseline = await _scan_namespace(distribution, witness['pid_namespace'])
            result['before_disconnect'] = baseline
            visible_namespace_pids = {entry['namespace_pids'][-1]
                                      for entry in baseline['matches']
                                      if entry['namespace_pids']}
            if not {witness['parent_pid'], witness['descendant_pid']} <= visible_namespace_pids:
                raise RuntimeError('Outer positive control could not locate both guest processes')
            result['positive_control_passed'] = True
            disconnected_at = time.monotonic()
            await websocket.close()
        result['disconnect_sent'] = True
        observations = []
        deadline = disconnected_at + retirement_timeout
        while time.monotonic() < deadline:
            observed = await _scan_namespace(distribution, witness['pid_namespace'])
            observed['elapsed_seconds'] = round(time.monotonic() - disconnected_at, 4)
            observations.append(observed)
            if not observed['matches']:
                result['qualified'] = True
                break
            await asyncio.sleep(.25)
        result['after_disconnect'] = observations
        result['retirement_deadline_seconds'] = retirement_timeout
        if not result['qualified']:
            raise RuntimeError('PID namespace still contains processes after bridge disconnect')
        return result
    except BaseException as error:
        result['error'] = {'type': type(error).__name__,
                           'message': str(error).replace(url, '[REDACTED_BRIDGE_URL]')[:2000]}
        raise
    finally:
        record_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--distribution', default='Ubuntu-24.04')
    args = parser.parse_args()
    result = asyncio.run(exercise_disconnect(args.url, args.evidence, args.distribution))
    print(json.dumps({'qualified': result['qualified'], 'evidence': str(args.evidence)}))


if __name__ == '__main__':
    main()
