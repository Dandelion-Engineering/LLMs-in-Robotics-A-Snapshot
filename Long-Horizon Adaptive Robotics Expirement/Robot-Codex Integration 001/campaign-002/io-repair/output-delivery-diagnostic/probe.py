"""Fixed no-model native output probe. No thread, turn, tool or robot invocation."""
from __future__ import annotations
import argparse
import ast
import asyncio
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
INTEGRATION = CAMPAIGN.parent
REPO = INTEGRATION.parents[1]
METHOD = HERE.parent / 'OUTPUT_DELIVERY_PROBE_V1.md'
SCHEMA = 'campaign002-output-delivery-probe-1'
MANIFEST_SCHEMA = 'campaign002-output-delivery-probe-manifest-1'
LIMIT_S = 120
OUTPUT_CAP = 65536
NAMES = ('immediate_streaming', 'separated_streaming', 'immediate_buffered',
         'separated_buffered', 'empty_streaming', 'mixed_streaming')
ALLOWED_CALLS = {'initialize', 'config/read', 'environment/info', 'environment/status', 'command/exec'}
LAUNCH_BLOCK_REASON = ('Unsupported remote route: pinned app-server command_exec.rs:143-294 '
    'uses local subprocess launch, not the selected remote executor. This prospective '
    'diagnostic is retained unlaunched; a new supported method is required.')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def required_inputs():
    paths = [Path(__file__), HERE / 'test_probe.py', HERE / 'README.md', METHOD,
             CAMPAIGN / 'assessment/assess.py', CAMPAIGN / 'assessment/retained_reads.py',
             INTEGRATION / 'launch/robot_codex_launcher.py',
             INTEGRATION / 'isolation-session-9/wsl/qualification.py']
    paths += sorted((CAMPAIGN / 'harness').glob('*.py'))
    schema = INTEGRATION / 'isolation-session-9/native/app-server-schema/v2'
    paths += [schema / name for name in ('CommandExecParams.json', 'CommandExecResponse.json',
              'CommandExecOutputDeltaNotification.json', 'EnvironmentInfoResponse.json',
              'EnvironmentStatusResponse.json')]
    return sorted({p.relative_to(REPO).as_posix() for p in paths})


def _assignment(path, name):
    nodes = [n.value for n in ast.parse(path.read_text(encoding='utf-8')).body
             if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    require(len(nodes) == 1, 'Ambiguous native constant ' + name)
    return nodes[0]


def binary_bindings():
    """Metadata reads only; no process, configuration values or credentials."""
    launch = INTEGRATION / 'launch/robot_codex_launcher.py'
    prior = INTEGRATION / 'isolation-session-9/wsl/qualification.py'
    node = _assignment(launch, 'CODEX')
    require(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'Path' and len(node.args) == 1 and not node.keywords, 'Native Windows path declaration changed')
    windows = ast.literal_eval(node.args[0])
    linux = ast.literal_eval(_assignment(prior, 'LINUX_CODEX'))
    codehost = _assignment(prior, 'LINUX_CODEHOST')
    require(ast.dump(codehost) == ast.dump(ast.parse("LINUX_CODEX.replace('codex-x86_64', 'codex-code-mode-host-x86_64')", mode='eval').body), 'Native codehost declaration changed')
    roles = {'windows_codex': (windows, None),
             'linux_codex': (linux, ast.literal_eval(_assignment(prior, 'LINUX_SHA256'))),
             'linux_codehost': (linux.replace('codex-x86_64', 'codex-code-mode-host-x86_64'), ast.literal_eval(_assignment(prior, 'CODEHOST_SHA256')))}
    result = {}
    for role, (path, expected) in roles.items():
        host = Path(path) if role == 'windows_codex' else Path(path[5].upper() + ':/' + path[7:])
        require(role == 'windows_codex' or path.startswith('/mnt/c/'), 'Unsupported pinned binary location')
        raw = host.read_bytes()
        require(expected is None or sha(raw) == expected, 'Installed Linux binary drift')
        result[role] = {'path': path, 'host_path': str(host.resolve()), 'sha256': sha(raw), 'bytes': len(raw)}
    return result


def make_cases():
    result = []
    for name in NAMES:
        empty, mixed, separated = name == 'empty_streaming', name == 'mixed_streaming', name.startswith('separated')
        stdout = b'' if empty else ((name + '|0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ\n').encode() * 400)[:13029]
        stderr = (b'MIXED-STDERR|abcdefghijklmnopqrstuvwxyz\n' * 10)[:257] if mixed else b''
        # The marker is an argv argument, not shell syntax or dynamic source.
        source = ('import os,time\n' +
                  ('' if empty else 'os.write(1,' + repr(stdout[:8192]) + ')\n') +
                  ('time.sleep(0.1)\n' if separated else '') +
                  ('os.write(2,' + repr(stderr) + ')\n' if mixed else '') +
                  ('' if empty else 'os.write(1,' + repr(stdout[8192:]) + ')\n'))
        result.append({'name': name, 'argv': ['/usr/bin/python3', '-I', '-B', '-c', source, 'output-probe-v1:' + name],
                       'process_id': 'output-probe-v1-' + name, 'streaming': 'buffered' not in name,
                       'stdout': {'bytes': len(stdout), 'sha256': sha(stdout), 'base64': base64.b64encode(stdout).decode()},
                       'stderr': {'bytes': len(stderr), 'sha256': sha(stderr), 'base64': base64.b64encode(stderr).decode()}})
    return result


def command_params(case):
    return {'command': case['argv'], 'cwd': '/workspace', 'processId': case['process_id'],
            'tty': False, 'streamStdin': False, 'streamStdoutStderr': case['streaming'],
            'timeoutMs': 10000, 'outputBytesCap': OUTPUT_CAP}


def validate_sources(snapshot_path, manifest_path):
    snapshot_path, manifest_path = Path(snapshot_path).resolve(), Path(manifest_path).resolve()
    manifest_raw = manifest_path.read_bytes()
    manifest, snapshot = json.loads(manifest_raw), json.loads(snapshot_path.read_bytes())
    require(manifest.get('schema') == MANIFEST_SCHEMA, 'Wrong diagnostic manifest schema')
    require(manifest.get('cases') == make_cases(), 'Fixed six cases changed')
    require(manifest.get('model_calls') == 0 and type(manifest.get('model_calls')) is int
            and manifest.get('model_turns_max') == 0 and type(manifest.get('model_turns_max')) is int
            and manifest.get('physical_simulation') is False and manifest.get('recovery_actions') is False,
            'Manifest permits activity outside diagnostic scope')
    require(snapshot.get('manifest_sha256') == sha(manifest_raw)
            and snapshot.get('run_id') == manifest.get('run_id'), 'Manifest snapshot mismatch')
    paths, bindings = manifest.get('runtime_input_files'), manifest.get('input_bindings')
    require(isinstance(paths, list) and len(paths) == len(set(paths)) and isinstance(bindings, dict)
            and set(paths) == set(bindings) and set(required_inputs()) <= set(paths), 'Incomplete exact method/source inventory')
    for name in paths:
        path = REPO / name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts
                and path.is_file() and not path.is_symlink(), 'Invalid source path')
        raw = path.read_bytes()
        require(bindings[name] == {'sha256': sha(raw), 'bytes': len(raw)}, 'Source drift: ' + name)
    sys.path.insert(0, str(CAMPAIGN / 'assessment'))
    checker = load_module('output_probe_frozen_assess', CAMPAIGN / 'assessment/assess.py')
    require(not checker.frozen_problems(snapshot_path, snapshot, manifest.get('framework_revision')), 'Frozen source drift')
    require(manifest.get('binaries') == binary_bindings(), 'Native binary binding drift')
    return manifest, snapshot


def _messages(rows, kind):
    return [r for r in rows if r.get('kind') == kind]


def assess_records(app, wire, captures):
    """Pure semantic assessment. Captures supplied only by load_capture in assess()."""
    require(captures and len(captures) == 1, 'Missing/reconnected executor capture')
    rows, delivered = captures[0]
    for event in app:
        if event.get('kind') == 'request':
            require(event.get('method') in ALLOWED_CALLS, 'Unexpected model/tool method')
        require(event.get('kind') not in ('unexpected_server_request', 'rpc_error', 'config_warning'), 'Native RPC/config failure')
        if event.get('kind') == 'notification':
            require(not any(x in event.get('method', '').lower() for x in ('thread/', 'turn/', 'item/')), 'Unexpected model notification')
    requests = [r for r in app if r.get('kind') == 'request' and r.get('method') == 'command/exec']
    require(len(requests) == 6 and len({r['id'] for r in requests}) == 6, 'Six unique commands required')
    starts = [r for r in rows if r.get('kind') == 'request' and (r.get('message') or {}).get('method') == 'process/start']
    require(len(starts) == 6, 'Unexpected native process/start count')
    require(len({r['message']['params']['processId'] for r in starts}) == 6, 'Ambiguous native process identity')
    raw_messages = []
    for item in wire:
        raw = base64.b64decode(item['base64'], validate=True)
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'] and raw.endswith(b'\n'), 'Original app wire binding mismatch')
        raw_messages.append(json.loads(raw))
    cases = []
    for case, request in zip(make_cases(), requests):
        require(request.get('params') == command_params(case), 'Changed case command/limits')
        replies = [r for r in app if r.get('kind') == 'response' and r.get('method') == 'command/exec' and r.get('id') == request['id']]
        require(len(replies) == 1, 'Missing/duplicate command response')
        reply = replies[0]
        require(type(reply.get('result', {}).get('exitCode')) is int and reply['result']['exitCode'] == 0, 'Nonzero/noninteger public exit')
        require(app.index(request) < app.index(reply), 'Response before request')
        start = [r for r in starts if r['message']['params'].get('argv') == case['argv']]
        require(len(start) == 1, 'Wrong or ambiguous remote route')
        start = start[0]; params = start['message']['params']; pid = params['processId']
        require(params.get('cwd') == 'file:///workspace' and params.get('tty') is False, 'Wrong remote cwd/TTY')
        require(request['probe_wall_unix_s'] <= start['wall_unix_s'] <= reply['probe_wall_unix_s'], 'Native start outside serial app request')
        starts_ok = [r for r in rows if r.get('kind') == 'response' and r.get('message', {}).get('id') == start['message']['id']]
        require(len(starts_ok) == 1 and starts_ok[0]['message'].get('result', {}).get('processId') == pid
                and starts_ok[0]['sequence'] in delivered, 'Native start acknowledgment mismatch')
        native = [r for r in rows if r.get('kind') == 'response' and (r.get('message') or {}).get('method') in
                  ('process/output', 'process/exited', 'process/closed') and r['message']['params'].get('processId') == pid]
        require(native and native[-1]['message']['method'] == 'process/closed', 'Native lifecycle incomplete')
        require([r['message']['params'].get('seq') for r in native] == list(range(1, len(native) + 1))
                and all(type(r['message']['params'].get('seq')) is int for r in native), 'Native sequence gap/duplicate')
        require(all(r['sequence'] in delivered and r.get('original_message_sha256') == r.get('retained_message_sha256')
                    and all(b['raw_sha256'] == b['retained_sha256'] and b['raw_bytes'] == b['retained_bytes'] for b in r.get('blobs', [])) for r in native), 'Undelivered/redacted native output')
        exits = [r for r in native if r['message']['method'] == 'process/exited']
        require(len(exits) == 1 and type(exits[0]['message']['params'].get('exitCode')) is int
                and exits[0]['message']['params']['exitCode'] == 0
                and exits[0]['message']['params'].get('sandboxDenied') is False
                and sum(r['message']['method'] == 'process/closed' for r in native) == 1, 'Native exit/close mismatch')
        executor = {'stdout': b'', 'stderr': b''}
        for row in native:
            if row['message']['method'] == 'process/output':
                param = row['message']['params']; require(param.get('stream') in executor, 'Unknown native output stream')
                executor[param['stream']] += base64.b64decode(param['chunk'], validate=True)
        deltas = [r for r in app if r.get('kind') == 'notification' and r.get('method') == 'command/exec/outputDelta'
                  and r.get('params', {}).get('processId') == case['process_id']]
        public = {'stdout': b'', 'stderr': b''}
        for delta in deltas:
            param = delta['params']; require(param.get('capReached') is False and param.get('stream') in public, 'Output cap/stream mismatch')
            require(app.index(request) < app.index(delta) < app.index(reply), 'Output outside command interval')
            public[param['stream']] += base64.b64decode(param['deltaBase64'], validate=True)
        for stream in public:
            require(isinstance(reply['result'].get(stream), str), 'Missing public output')
            if case['streaming']:
                require(reply['result'][stream] == '', 'Streaming output duplicated in final response')
            else:
                require(not deltas, 'Buffered command emitted deltas')
                public[stream] = reply['result'][stream].encode('utf-8')
        logged = [{k: v for k, v in r.items() if k not in ('kind', 'method', 'probe_wall_unix_s')} for r in [reply]]
        require(sum(x == logged[0] for x in raw_messages) == 1, 'Original response envelope mismatch')
        for delta in deltas:
            normalized = {k: v for k, v in delta.items() if k not in ('kind', 'probe_wall_unix_s')}
            require(sum(x == normalized for x in raw_messages) == sum({k:v for k,v in d.items() if k not in ('kind','probe_wall_unix_s')} == normalized for d in deltas), 'Original delta envelope mismatch')
        parity = all(executor[s] == public[s] == base64.b64decode(case[s]['base64']) for s in executor)
        cases.append({'name': case['name'], 'passed': parity, 'app_process_id': case['process_id'], 'native_process_id': pid,
                      'native_request_id': start['message']['id'], 'native_sequences': [r['message']['params']['seq'] for r in native],
                      'streams': {s: {'expected': {k:case[s][k] for k in ('sha256','bytes')},
                                      'executor': {'bytes':len(executor[s]),'sha256':sha(executor[s])},
                                      'public': {'bytes':len(public[s]),'sha256':sha(public[s])}} for s in executor}})
    expected_ids = {c['process_id'] for c in make_cases()}
    require(all(r.get('params', {}).get('processId') in expected_ids for r in app if r.get('method') == 'command/exec/outputDelta'), 'Unmatched extra output delta')
    require(len(raw_messages) == 6 + sum(r.get('method') == 'command/exec/outputDelta' for r in app), 'Extra/missing original command wire records')
    return {'schema': 'campaign002-output-delivery-assessment-1', 'passed': all(c['passed'] for c in cases),
            'protocol_passed': True, 'cases': cases, 'scope': 'Standalone native command/exec only; no model path or causal attribution.'}


def assess(output, snapshot, manifest):
    output = Path(output)
    result = {'schema': 'campaign002-output-delivery-assessment-1', 'passed': False, 'protocol_passed': False, 'errors': []}
    try:
        declared, _ = validate_sources(snapshot, manifest)
        execution = json.loads((output / 'execution.json').read_bytes())
        require(execution.get('run_id') == declared['run_id'] and execution.get('execution_completed') is True
                and execution.get('cleanup_clean') is True and execution.get('client_closed') is True
                and not execution.get('errors') and 0 <= execution['elapsed_s'] <= LIMIT_S, 'Incomplete/late execution or cleanup')
        require(execution['manifest_sha256'] == sha(Path(manifest).read_bytes())
                and execution['snapshot_sha256'] == sha(Path(snapshot).read_bytes())
                and execution['binaries'] == declared['binaries'], 'Execution input binding mismatch')
        app = [json.loads(x) for x in (output / 'runtime/client/events.jsonl').read_bytes().splitlines()]
        wire = [json.loads(x) for x in (output / 'runtime/client/command-wire.jsonl').read_bytes().splitlines()]
        reader = load_module('output_probe_capture_reader', CAMPAIGN / 'assessment/retained_reads.py')
        loaded = [reader.load_capture(f) for f in sorted((output / 'runtime').glob('executor-*-capture.jsonl'))]
        result = assess_records(app, wire, [(r, d) for r, d, _ in loaded])
        result['capture_files'] = [b for _, _, b in loaded]
        result['input_bindings'] = {str(p.relative_to(output)): {'sha256':sha(p.read_bytes()), 'bytes':p.stat().st_size}
                                    for p in (output / 'execution.json', output / 'runtime/client/events.jsonl', output / 'runtime/client/command-wire.jsonl')}
    except Exception as error:
        result['errors'] = [str(error)]
        result['passed'] = result['protocol_passed'] = False
    return result


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write(json.dumps(value, indent=2).encode() + b'\n'); stream.flush(); os.fsync(stream.fileno())


class Deadline:
    def __init__(self, limit=LIMIT_S): self.start, self.limit = time.monotonic(), limit
    def remaining(self):
        left = self.limit - (time.monotonic() - self.start)
        require(left > 0, 'Whole diagnostic deadline exceeded')
        return left


def client_work(runtime, url, deadline, bootstrap):
    """Runs entirely on a worker; event-loop bridge remains available."""
    args = argparse.Namespace(evidence=runtime.evidence/'client', host_cwd=runtime.root,
        timeout=deadline.remaining(), redact_tokens=runtime.tokens, abort_event=runtime.abort_event,
        client_finishing=runtime.client_finishing)
    args.evidence.mkdir(exist_ok=False)
    wire_path = args.evidence/'command-wire.jsonl'; wire_path.touch(exist_ok=False)
    class ProbeClient(bootstrap.Client):
        def __init__(self, *a):
            self.command_ids, self.wire_error, self.wire_bytes = set(), None, 0
            self.wire_lock = threading.Lock()
            super().__init__(*a)
        def call(self, method, params, **kwargs):
            require(method in ALLOWED_CALLS, 'Model/tool RPC prohibited')
            if method == 'command/exec': self.command_ids.add(self.next_id + 1)
            return super().call(method, params, **kwargs)
        def log(self, value): super().log({**value, 'probe_wall_unix_s': time.time()})
        def _drain(self, label, stream):
            try:
                while raw := stream.readline(bootstrap.MAX_BYTES + 1):
                    if label == 'stdout':
                        msg = json.loads(raw)
                        if msg.get('id') in self.command_ids or msg.get('method') == 'command/exec/outputDelta':
                            self.wire_bytes += len(raw)
                            require(self.wire_bytes <= 1024*1024, 'Original command-wire byte bound')
                            row = {'base64':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':sha(raw)}
                            with self.wire_lock, wire_path.open('ab') as f:
                                f.write(canonical(row)+b'\n');f.flush();os.fsync(f.fileno())
                    self.messages.put((label,raw))
            except Exception as error:
                self.wire_error = type(error).__name__;runtime.abort_event.set()
            finally: self.messages.put((label,None))
    home = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    names = bootstrap.mcp_header_names(home);config = bootstrap.overrides(names, False)
    command = [str(bootstrap.LAUNCH.CODEX),'app-server','--stdio','--strict-config',*bootstrap.LAUNCH.config_args(config)]
    env = bootstrap.LAUNCH.clean_environment(home);env['CODEX_EXEC_SERVER_URL'] = url
    client = None; closed = False
    try:
        require(not (runtime.root/'.codex').exists() and not (home/'environments.toml').exists(), 'Ambient executor/project override')
        client = ProbeClient(args,command,env)
        client.call('initialize',{'clientInfo':{'name':'campaign002-output-probe','version':'1'},'capabilities':{'experimentalApi':True}})
        client.send({'method':'initialized','params':{}})
        effective = client.call('config/read',{'includeLayers':False,'cwd':str(runtime.root)},private=True)
        summary = bootstrap.inspect_config(effective['config'],names,False);del effective
        client.log({'kind':'validated_config','summary':summary})
        require(client.call('environment/status',{'environmentId':'local'}).get('status') == 'unknown','Local executor appeared')
        info = client.call('environment/info',{'environmentId':'remote'})
        require(info.get('cwd') == 'file:///workspace' and info.get('shell',{}).get('path','').startswith('/'),'Remote environment metadata mismatch')
        require(client.call('environment/status',{'environmentId':'remote'}).get('status') == 'ready','Remote executor unavailable')
        for case in make_cases():
            deadline.remaining();client.call('command/exec',command_params(case))
        require(client.wire_error is None,'Original command wire capture failed')
    finally:
        if client is not None:
            client.close();closed = True
    return closed


async def execute_runtime(output, deadline, runtime_module):
    fixture = None; errors = []; client_closed = cleanup_clean = False
    original_linux = runtime_module.linux
    def bounded_linux(*args, **kwargs):
        kwargs['timeout'] = min(kwargs.get('timeout',30),deadline.remaining())
        return original_linux(*args,**kwargs)
    runtime_module.linux = bounded_linux
    try:
        fixture = runtime_module.Runtime.__new__(runtime_module.Runtime)
        await asyncio.to_thread(fixture.__init__,output/'runtime',runtime_module.template('bootstrap'))
        for mode in ('canary','codehost-canary'):
            proc = await asyncio.to_thread(subprocess.run,fixture.argv(mode),capture_output=True,text=True,encoding='utf-8',timeout=min(45,deadline.remaining()))
            (fixture.evidence/(mode+'-stdout.json')).write_text(fixture.redact(proc.stdout),encoding='utf-8')
            (fixture.evidence/(mode+'-stderr.txt')).write_text(fixture.redact(proc.stderr),encoding='utf-8')
            value = json.loads(proc.stdout)
            require(type(proc.returncode) is int and proc.returncode == 0 and value.get('qualified',value.get('host_qualified')) is True,'Boundary canary failure')
        async def callback(url):
            nonlocal client_closed
            client_closed = await asyncio.to_thread(client_work,fixture,url,deadline,runtime_module.bootstrap)
        await asyncio.wait_for(runtime_module.captured_executor.bridge_executor(fixture,callback),deadline.remaining())
    except Exception as error:
        errors.append(type(error).__name__ + ': ' + str(error))
        if fixture is not None and hasattr(fixture,'abort_event'): fixture.abort_event.set()
    finally:
        runtime_module.linux = original_linux
        if fixture is not None:
            try: cleanup_clean = await asyncio.to_thread(fixture.close)
            except Exception as error: errors.append('cleanup: ' + type(error).__name__)
    return {'errors':errors,'client_closed':client_closed,'cleanup_clean':cleanup_clean,
            'execution_completed':not errors and client_closed and cleanup_clean}


def run(args):
    # Source review invalidated the proposed route before any empirical launch.
    # Keep the draft/semantic tests, but never run a local fallback experiment.
    raise RuntimeError(LAUNCH_BLOCK_REASON)


def _unlaunched_draft_run(args):
    """Preserved proposed lifecycle, deliberately absent from the CLI run path."""
    deadline = Deadline()
    manifest, _ = validate_sources(args.snapshot,args.manifest)
    output = args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(CAMPAIGN/'harness'))
    execution = {'run_id':manifest['run_id'],'manifest_sha256':sha(args.manifest.read_bytes()),
                 'snapshot_sha256':sha(args.snapshot.read_bytes()),'binaries':manifest['binaries'],
                 'errors':[],'execution_completed':False,'cleanup_clean':False,'client_closed':False}
    try:
        runtime_module = load_module('output_probe_runtime',CAMPAIGN/'harness/runtime.py')
        execution.update(asyncio.run(execute_runtime(output,deadline,runtime_module)))
    except Exception as error: execution['errors'].append(type(error).__name__ + ': ' + str(error))
    execution['elapsed_s'] = time.monotonic()-deadline.start
    execution['execution_completed'] &= execution['elapsed_s'] <= LIMIT_S
    save(output/'execution.json',execution)
    assessment = assess(output,args.snapshot,args.manifest)
    result = {'schema':SCHEMA,'run_id':manifest['run_id'],'framework_revision':manifest['framework_revision'],
              'model_calls':0,'model_turns_max':0,'physical_simulation':False,'recovery_actions':False,
              'execution_completed':execution['execution_completed'] and assessment['protocol_passed'],
              'passed':assessment['passed'],'assessment':assessment,
              'scope':'Standalone command/exec diagnostic only. No model path qualification, repair or causal attribution.'}
    save(output/'result.json',result)
    print(json.dumps({'result':str(output/'result.json'),'execution_completed':result['execution_completed'],'passed':result['passed']}))
    return 0 if result['execution_completed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output',type=Path)
    group.add_argument('--assess',type=Path)
    args = parser.parse_args()
    if args.assess:
        value=assess(args.assess,args.snapshot,args.manifest);print(json.dumps(value,indent=2));return 0 if value['passed'] else 1
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
