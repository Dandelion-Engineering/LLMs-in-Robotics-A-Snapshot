"""Bounded proof for one observed empty-continuity read recipe.

This does not evaluate Python or infer emptiness from a compound cat/listing.
Only the exact read-only AST below is supported. Its unique repr line, complete
model-visible output, trusted process identity, fixed import boundary, and
protected mutation chronology must all agree. Historical verdicts are untouched.
"""
from __future__ import annotations
import ast
import io
import json
import math
from pathlib import Path, PurePosixPath
import shlex
import tokenize
import zipfile

from retained_reads import canonical, load_capture, process_reads, sha


EMPTY_SHA256 = sha(b'')
READ_ONLY_BODY = """import json
from pathlib import Path
h = json.loads(Path('notes/startup-history.json').read_text())
print(json.dumps({k:v for k,v in h.items() if k != 'events'}))
for e in h['events']:
    p = e['payload']
    summary = {k:e.get(k) for k in ('event_id','type','authority_epoch','owner','sim_time_s')}
    if e['type'] == 'observation':
        summary['evidence'] = {k:p.get(k) for k in ('sequence','capture_sim_time_s','gripper','incarnation','restart_generation')}
    else:
        summary['payload'] = p
    print(json.dumps(summary))
print('Continuity contents:', repr(Path('Continuity.md').read_text()))
p = Path('notes/boundary-observation.json')
print('Boundary evidence exists:', p.exists())
if p.exists():
    b = json.loads(p.read_text())
    print(json.dumps({'qualified': b.get('qualified'), 'checks': b.get('checks')}))
"""
READ_ONLY_AST = ast.dump(ast.parse(READ_ONLY_BODY), include_attributes=False)
READ_ONLY_SCRIPT = "python3 - <<'PY'\n" + READ_ONLY_BODY + 'PY'
# These reviewed, frozen sources guarantee an immutable /usr and /workspace,
# fixed HOME/PATH, and writable mounts only below notes/programs/.continuity.
# A changed boundary must be reviewed; merely re-freezing it is insufficient.
BOUNDARY_HASHES = {
    'namespace.py': '027d5ef394906ef1885b8ae8a2376031aae48ce93efe9bb90f2dc3ef9000c0f9',
    'runtime_layout.py': '525fb8ce15d3ba2cc7aa82e4aefdbbc5e43b2a09e16a8fd329268366babe1457',
    'inside.py': '6b6745e449348913e542d82aeb8b45320b6f50312540c235a3b07a66dc64faa3',
}
FIXED_ROOT_FILES = {'AGENTS.md', 'Continuity.md', 'Robot.md', 'robot.py',
                    'RobotAgentPrompt.md', 'Tasks.md', 'Tools.md'}
SAFE_ENV = {'CODEX_CI', 'CODEX_SESSION_ID', 'CODEX_THREAD_ID', 'CODEX_VERSION',
            'COLORTERM', 'GH_PAGER', 'GIT_PAGER', 'LANG', 'LC_ALL', 'LC_CTYPE',
            'NO_COLOR', 'PAGER', 'TERM'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_time(value):
    require(type(value) in (int, float) and math.isfinite(value), 'Missing/nonfinite trusted timestamp')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def load_json(path, receipts, *, lines=False):
    raw = Path(path).read_bytes()
    receipts.append({'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)})
    if lines:
        require(not raw or raw.endswith(b'\n'), 'Incomplete JSONL history tail: ' + Path(path).name)
        return [json.loads(line, object_pairs_hook=unique_object) for line in raw.splitlines()]
    return json.loads(raw, object_pairs_hook=unique_object)


def recognized_recipe(argv):
    """Recognize actual literal argv and AST; commandActions are never used."""
    if (not isinstance(argv, list) or len(argv) != 3 or argv[:2] != ['/usr/bin/bash', '-lc']
            or not isinstance(argv[2], str)):
        return False
    lines = argv[2].split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    if len(lines) < 3 or lines[0] != "python3 - <<'PY'" or lines[-1] != 'PY':
        return False
    body = '\n'.join(lines[1:-1]) + '\n'
    try:
        # In particular, no encoding cookie may change how the Python child
        # interprets the UTF-8 heredoc relative to our already decoded AST.
        if any(t.type == tokenize.COMMENT for t in tokenize.generate_tokens(io.StringIO(body).readline)):
            return False
        return ast.dump(ast.parse(body), include_attributes=False) == READ_ONLY_AST
    except (SyntaxError, ValueError, tokenize.TokenError, IndentationError):
        return False


def import_boundary(source_zip, hashes):
    require(isinstance(hashes, dict), 'Missing trusted initial input inventory')
    for name, digest in hashes.items():
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in name,
                'Unsafe initial input path')
        require(name in FIXED_ROOT_FILES or (len(path.parts) > 1 and path.parts[0] in ('notes', 'programs', 'live')),
                'Initial root can shadow imports or shell profile: ' + name)
        require(isinstance(digest, str) and len(digest) == 64, 'Malformed initial input hash')
    result = []
    with zipfile.ZipFile(source_zip) as archive:
        for name, digest in BOUNDARY_HASHES.items():
            candidates = [n for n in archive.namelist() if n.endswith('/readiness-session-10/boundary/' + name)]
            require(len(candidates) == 1 and sha(archive.read(candidates[0])) == digest,
                    'Reviewed immutable import boundary absent/changed: ' + name)
            result.append({'path': candidates[0], 'sha256': digest})
    return result


def environment_proof(params):
    env, policy = params.get('env'), params.get('envPolicy')
    require(params.get('cwd') == 'file:///workspace' and params.get('tty') is False
            and params.get('arg0') is None and params.get('pipeStdin') is False,
            'Unexpected process execution mode')
    require(isinstance(env, dict) and set(env) <= SAFE_ENV
            and all(isinstance(v, str) for v in env.values()), 'Unreviewed process environment override')
    require(isinstance(policy, dict) and policy.get('inherit') == 'none'
            and policy.get('includeOnly') == [] and policy.get('ignoreDefaultExcludes') is False,
            'Process environment inheritance is not closed')
    additions = policy.get('set')
    require(isinstance(additions, dict) and set(additions) <= {'NODE_REPL_TRUSTED_BROWSER_CLIENT_SHA256S'}
            and all(isinstance(v, str) for v in additions.values()), 'Unreviewed environment policy override')
    require(all(env.get(k, 'C.UTF-8') == 'C.UTF-8' for k in ('LANG', 'LC_ALL', 'LC_CTYPE')),
            'Unreviewed text decoding locale')
    return {'cwd': params['cwd'], 'argv': params['argv'], 'env': env, 'envPolicy': policy,
            'scope': 'No PATH/HOME/PYTHON/loader/shell-function overrides; fixed readonly root and standard imports.'}


def mutation_chronology(root, host, read_start, read_end, receipts):
    require(not (root / 'broker-failure.json').exists(), 'Broker failed; mutation history is unknown')
    requests = load_json(root / 'broker-requests.jsonl', receipts, lines=True)
    events = load_json(root / 'broker-events.jsonl', receipts, lines=True)
    calls = load_json(root / 'gateway-calls.json', receipts)
    history = load_json(host / 'public-history.jsonl', receipts, lines=True)
    require(len(requests) == len(events) == len(calls), 'Unmatched/in-flight broker request')
    require(len({r.get('trace_id') for r in requests}) == len(requests)
            and all(isinstance(r.get('trace_id'), str) and r['trace_id'] for r in requests),
            'Ambiguous broker trace identity')
    require(history and history[-1].get('type') == 'episode_stopped', 'Missing complete protected history')
    for index, event in enumerate(history, 1):
        require(type(event.get('event_id')) is int and event['event_id'] == index,
                'Missing/ambiguous protected history event')
        finite_time(event.get('wall_unix_s'))
    require(history[0]['wall_unix_s'] <= read_start < read_end < history[-1]['wall_unix_s'],
            'Read outside complete protected history')
    commits = [e for e in history if e.get('type') == 'continuity_committed']
    require(all(e['wall_unix_s'] > read_end for e in commits), 'Protected continuity commit before/during read')
    mutations = []
    previous_end = None
    for request, event, call in zip(requests, events, calls):
        require(all(event.get(k) == request.get(k) for k in
                    ('trace_id', 'received_wall_unix_s', 'method', 'path', 'request_id', 'request')),
                'Broker request/completion mismatch')
        start = finite_time(request.get('received_wall_unix_s'))
        end = finite_time(event.get('wall_unix_s'))
        require(start <= end and (previous_end is None or previous_end <= start), 'Broker chronology inconsistent')
        previous_end = end
        require(call == {k: event.get(k) for k in ('method', 'path', 'status')}, 'Gateway call inventory mismatch')
        if request.get('method') == 'POST' and request.get('path') == '/continuity':
            require(start > read_end, 'Protected continuity mutation before/during read or boundary equality')
            if event.get('status') == 200:
                response = event.get('response', {})
                matches = [e for e in commits if start <= e['wall_unix_s'] <= end
                           and all(e.get('payload', {}).get(k) == response.get(k)
                                   for k in ('sha256', 'bytes', 'previous_sha256'))]
                require(len(matches) == 1, 'Protected continuity receipt lacks unique history commit')
            mutations.append({'trace_id': request['trace_id'], 'received_wall_unix_s': start,
                              'completed_wall_unix_s': end, 'status': event.get('status')})
    return {'read_request_wall_unix_s': read_start, 'read_complete_wall_unix_s': read_end,
            'all_protected_mutations_strictly_after_read': True,
            'broker_requests_and_completions': len(requests), 'protected_history_events': len(history),
            'mutations': mutations,
            'scope': 'Protected commit chronology only. Actual repr output, not absence of commits, proves local empty contents.'}


def empty_startup_read_evidence(root, host, expected_hash, source_zip):
    """Return explicit proof or fail closed; never synthesize a command/output."""
    root, host = Path(root), Path(host)
    audit = {'verified': False, 'evidence': [], 'errors': []}
    if expected_hash != EMPTY_SHA256:
        audit['errors'].append('Initial continuity is not the zero-byte hash')
        return audit
    receipts = []
    try:
        hashes = load_json(root / 'runtime-input-hashes.json', receipts)
        require(hashes.get('Continuity.md') == expected_hash, 'Initial continuity hash disagreement')
        initial = host / 'continuity-history' / (expected_hash + '.md')
        raw = initial.read_bytes()
        require(raw == b'' and sha(raw) == expected_hash, 'Initial retained continuity bytes changed/missing')
        receipts.append({'path': str(initial), 'sha256': sha(raw), 'bytes': len(raw)})
        boundary = import_boundary(source_zip, hashes)
        events = load_json(root / 'client/events.jsonl', receipts, lines=True)
        reads, integrity = process_reads(root, events)
        require(integrity['verified'], 'Executor capture integrity failed: ' + '; '.join(integrity['errors']))
        completions = [e for e in events if e.get('method') == 'item/completed'
                       and e.get('params', {}).get('item', {}).get('type') == 'commandExecution']
        for event in completions:
            item = event['params']['item']
            argv = shlex.split(item.get('command', ''))
            if not recognized_recipe(argv):
                continue
            try:
                item_id = item.get('id')
                require(isinstance(item_id, str) and item_id in reads, 'No authenticated successful recipe completion')
                identities = [e for e in events if e.get('method') in ('item/started', 'item/completed')
                              and e.get('params', {}).get('item', {}).get('id') == item_id]
                require([e['method'] for e in identities] == ['item/started', 'item/completed'],
                        'Ambiguous started/completed tool identity')
                require(all(e['params']['item'].get('command') == item['command'] for e in identities),
                        'Tool command changed between start and completion')
                read = reads[item_id]
                provenance = read['provenance']
                require(provenance['app_projection_equals_executor'] is True,
                        'Model-visible projection differs from complete process output')
                lines = read['stdout'].split('\n')
                require(lines.count("Continuity contents: ''") == 1
                        and sum(line.startswith('Continuity contents:') for line in lines) == 1,
                        'Unique literal empty repr line absent')
                rows, delivered, receipt = load_capture(root / provenance['file'])
                for row in rows:
                    finite_time(row.get('wall_unix_s'))
                require(all(a['wall_unix_s'] <= b['wall_unix_s'] for a, b in zip(rows, rows[1:])),
                        'Executor capture clock/order inconsistent')
                request = rows[provenance['request_sequence'] - 1]
                require(request.get('original_message_sha256') == request.get('retained_message_sha256'),
                        'Process request was redacted/changed')
                params = request['message']['params']
                require(params['argv'] == argv and params['metadata']['toolCallId'] == item_id,
                        'Actual process argv/identity mismatch')
                execution = environment_proof(params)
                closed = [r for r in rows if r.get('kind') == 'response'
                          and r.get('message', {}).get('method') == 'process/closed'
                          and r['message'].get('params', {}).get('processId') == provenance['process_id']]
                require(len(closed) == 1 and closed[0]['sequence'] in delivered, 'Missing unique process close')
                deliveries = [r for r in rows if r.get('kind') == 'delivered'
                              and r.get('response_sequence') == closed[0]['sequence']]
                require(len(deliveries) == 1, 'Missing close transport receipt')
                start = request['wall_unix_s']
                end = finite_time(event.get('emittedAtMs')) / 1000
                require(start < closed[0]['wall_unix_s'] <= deliveries[0]['wall_unix_s'] <= end,
                        'Request/close/delivery/app-completion chronology inconsistent')
                candidate_receipts = list(receipts)
                chronology = mutation_chronology(root, host, start, end, candidate_receipts)
                audit['evidence'].append({'item_id': item_id, 'match': 'authenticated_exact_readonly_python_empty_repr',
                    'input_sha256': expected_hash, 'observed_bytes': 0,
                    'recipe_ast_sha256': sha(READ_ONLY_AST.encode()),
                    'executor_provenance': provenance, 'execution': execution,
                    'import_boundary_sources': boundary, 'chronology': chronology, 'inputs': candidate_receipts,
                    'scope': 'Actual initial empty bytes in complete app-visible output; no attention/understanding claim.'})
            except (ValueError, KeyError, TypeError, OSError, UnicodeError) as error:
                audit['errors'].append(str(item.get('id')) + ': ' + str(error))
        audit['verified'] = bool(audit['evidence'])
        if not audit['verified'] and not audit['errors']:
            audit['errors'].append('No supported authenticated empty-read recipe')
    except (ValueError, KeyError, TypeError, OSError, UnicodeError, zipfile.BadZipFile) as error:
        audit['errors'].append(str(error))
    return audit
