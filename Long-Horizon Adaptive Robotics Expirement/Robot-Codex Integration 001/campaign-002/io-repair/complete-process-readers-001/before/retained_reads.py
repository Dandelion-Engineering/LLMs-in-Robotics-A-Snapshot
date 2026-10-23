"""Authenticate process bytes independently of shortened app command aggregates.

This reader proves executor bytes submitted to the app-server transport. A send
completion is not an app acknowledgment. It separately records the app projection
and does not infer that a model attended to each byte.
Missing, redacted, unsequenced, undelivered or truncated streams fail closed.
"""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import re
import shlex


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def script(item):
    try:
        tokens = shlex.split(item.get('command', ''))
    except ValueError:
        return None
    if len(tokens) == 3 and tokens[0] in ('/usr/bin/bash', '/bin/bash') and tokens[1] in ('-lc', '-c'):
        return tokens[2]
    return item.get('command')


def exact_cat_paths(item):
    try:
        tokens = shlex.split(script(item) or '')
    except ValueError:
        return []
    if not tokens or tokens[0] not in ('cat', '/bin/cat', '/usr/bin/cat') or len(tokens) < 2:
        return []
    if any(not token or token.startswith('-') or any(c in token for c in '|;&<>$`\n') for token in tokens[1:]):
        return []
    return [token.removeprefix('/workspace/') for token in tokens[1:]]


def load_capture(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete executor capture tail')
    records = [json.loads(line) for line in raw.splitlines()]
    if not records or records[0].get('kind') != 'open' or records[-1].get('kind') != 'closed':
        raise ValueError('Executor capture missing open/closed receipt')
    connection = records[0].get('connection_id')
    previous, delivered, responses = None, set(), {}
    for sequence, row in enumerate(records, 1):
        check = {k: v for k, v in row.items() if k != 'record_sha256'}
        if (row.get('schema') != 'campaign002-executor-capture-1' or row.get('sequence') != sequence
                or row.get('connection_id') != connection or row.get('previous_sha256') != previous
                or sha(canonical(check)) != row.get('record_sha256')):
            raise ValueError('Executor capture sequence/hash mismatch')
        if 'message' in row and sha(canonical(row['message'])) != row.get('retained_message_sha256'):
            raise ValueError('Executor message hash mismatch')
        previous = row['record_sha256']
        if row.get('kind') == 'response':
            responses[sequence] = row
        if row.get('kind') == 'delivered':
            target = row.get('response_sequence')
            if target not in responses or target in delivered:
                raise ValueError('Executor delivery lacks unique preceding response')
            delivered.add(target)
    if records[-1].get('failures'):
        raise ValueError('Executor capture closed with forwarding failure')
    return records, delivered, {'file': Path(path).name, 'sha256': sha(raw),
                                'connection_id': connection, 'records': len(records)}


def process_reads(root, events):
    """Join exact dispatch, contiguous successful output, and app completion."""
    paths = sorted(Path(root).glob('executor-*-capture.jsonl'))
    if not paths:
        return {}, {'verified': False, 'errors': ['Missing trusted executor capture'], 'files': []}
    completed = {}
    for event in events:
        item = event.get('params', {}).get('item', {})
        if event.get('method') == 'item/completed' and item.get('type') == 'commandExecution':
            completed.setdefault(item.get('id'), []).append(item)
    matched, errors, files = {}, [], []
    for path in paths:
        try:
            rows, delivered, receipt = load_capture(path)
            files.append(receipt)
            requests = [r for r in rows if r.get('kind') == 'request'
                        and r.get('message', {}).get('method') == 'process/start']
            for request in requests:
                message = request['message']
                params = message.get('params', {})
                item_id = params.get('metadata', {}).get('toolCallId')
                if item_id not in completed:
                    continue  # Nonmodel qualification probes or interrupted commands.
                if len(completed[item_id]) != 1 or item_id in matched:
                    raise ValueError('Ambiguous completed process tool ID')
                item = completed[item_id][0]
                pid = params.get('processId')
                if (params.get('cwd') != 'file:///workspace' or params.get('tty') is not False
                        or type(item.get('exitCode')) is not int or item['exitCode'] != 0
                        or params.get('argv') != shlex.split(item.get('command', ''))):
                    continue
                # Identity reuse would make output attribution ambiguous.
                if sum(r['message']['params'].get('processId') == pid for r in requests) != 1:
                    raise ValueError('Reused process ID in executor connection')
                responses = [r for r in rows if r.get('kind') == 'response' and r['sequence'] > request['sequence']]
                starts = [r for r in responses if r['message'].get('id') == message.get('id')]
                if (len(starts) != 1 or starts[0]['sequence'] not in delivered
                        or starts[0]['message'].get('result', {}).get('processId') != pid
                        or 'error' in starts[0]['message']):
                    continue
                process = [r for r in responses if r['message'].get('method') in ('process/output', 'process/exited', 'process/closed')
                           and r['message'].get('params', {}).get('processId') == pid]
                if not process or process[-1]['message'].get('method') != 'process/closed':
                    continue
                exits = [r for r in process if r['message'].get('method') == 'process/exited']
                if len(exits) != 1 or sum(r['message'].get('method') == 'process/closed' for r in process) != 1:
                    continue
                process_order = [r['message']['params'].get('seq') for r in process]
                output_order = [r['message']['params'].get('seq') for r in process
                                if r['message'].get('method') == 'process/output']
                # Native exit notification can overtake output on the retained
                # transport. Preserve arrival order; never sort or repair bytes.
                # With one exit, closed last/max, and ordered outputs, only the
                # exit notice can differ from globally increasing native seq.
                if (any(type(sequence) is not int for sequence in process_order)
                        or set(process_order) != set(range(1, len(process) + 1))
                        or process_order[-1] != len(process)
                        or any(left >= right for left, right in zip(output_order, output_order[1:]))):
                    continue
                stdout, stderr = bytearray(), bytearray()
                valid = True
                for row in process:
                    obj = row['message']
                    p = obj['params']
                    if (row['sequence'] not in delivered
                            or row.get('original_message_sha256') != row.get('retained_message_sha256')):
                        valid = False
                        break
                    if obj['method'] == 'process/output':
                        data = base64.b64decode(p['chunk'], validate=True)
                        blobs = row.get('blobs', [])
                        if (len(blobs) != 1 or blobs[0].get('path') != ['params', 'chunk']
                                or blobs[0].get('raw_sha256') != sha(data)
                                or blobs[0].get('retained_sha256') != sha(data)
                                or blobs[0].get('raw_bytes') != len(data)
                                or blobs[0].get('retained_bytes') != len(data)
                                or p.get('stream') not in ('stdout', 'stderr')):
                            valid = False
                            break
                        (stdout if p['stream'] == 'stdout' else stderr).extend(data)
                end = exits[0]['message']['params']
                if (not valid or type(end.get('exitCode')) is not int or end['exitCode'] != 0
                        or end.get('sandboxDenied') is not False or stderr):
                    continue
                output = bytes(stdout).decode('utf-8', errors='strict')
                projection = item.get('aggregatedOutput')
                matched[item_id] = {'stdout': output, 'provenance': {**receipt,
                    'request_sequence': request['sequence'], 'request_id': message['id'],
                    'process_id': pid, 'tool_call_id': item_id,
                    'process_sequences': len(process), 'stdout_bytes': len(stdout), 'stdout_sha256': sha(stdout),
                    'process_sequence_order': process_order, 'output_sequence_order': output_order,
                    'closed_sequence': process_order[-1], 'exit_sequence': end['seq'],
                    'exit_interleaved_out_of_sequence': process_order != list(range(1, len(process) + 1)),
                    'app_projection_bytes': len(projection.encode()) if isinstance(projection, str) else None,
                    'app_projection_sha256': sha(projection.encode()) if isinstance(projection, str) else None,
                    'app_projection_equals_executor': projection == output,
                    'scope': 'Complete source process stdout with websocket send completion; no app acknowledgment inferred; app/model projection recorded separately.'}}
        except (ValueError, KeyError, TypeError, UnicodeError) as error:
            errors.append(path.name + ': ' + str(error))
    return ({} if errors else matched), {'verified': not errors, 'errors': errors, 'files': files}


def authenticated_commands(root, events):
    reads, integrity = process_reads(root, events)
    commands = []
    for event in events:
        item = event.get('params', {}).get('item', {})
        if (event.get('method') != 'item/completed' or item.get('type') != 'commandExecution'
                or type(item.get('exitCode')) is not int or item['exitCode'] != 0):
            continue
        if item.get('id') in reads:
            commands.append({**item, 'aggregatedOutput': reads[item['id']]['stdout'],
                             'executor_provenance': reads[item['id']]['provenance']})
    return commands, integrity


def canary_recipe(item):
    """Recognize bounded literal recipes, never arbitrary shell equivalence.

    The four-line form preserves the protected canary's exit status while
    retaining its stdout and stderr separately. No intervening command can
    replace the output or status. Paths contain only literal notes components.
    """
    lines = (script(item) or '').strip().splitlines()
    if not lines:
        return None
    invocation = r'(?:python3|python|/usr/bin/python3|/usr/bin/python)(?:[ \t]+-[IB])*[ \t]+/canary\.py'
    note = r'notes/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+'
    first = re.fullmatch(invocation + r'(?:[ \t]+>[ \t]+(' + note + r')'
                         + r'(?:[ \t]+2>[ \t]+(' + note + r'))?)?[ \t]*', lines[0])
    if first is None:
        return None
    output, stderr = first.groups()
    for name in (output, stderr):
        if name is not None and any(part in ('.', '..') for part in name.split('/')):
            return None
    if output is None:
        return {'form': 'direct', 'output': None, 'stderr': None} if len(lines) == 1 else None
    if not output.endswith('boundary-observation.json'):
        return None
    if stderr is None:
        if len(lines) != 2 or lines[1] != 'cat ' + output:
            return None
        return {'form': 'redirect_then_read', 'output': output, 'stderr': None}
    if (stderr == output or len(lines) != 4 or lines[1] != 'canary_status=$?'
            or lines[2] != 'cat ' + output or lines[3] != 'exit "$canary_status"'):
        return None
    return {'form': 'status_preserving_redirect_then_read', 'output': output, 'stderr': stderr}


def canary_matches(commands, contents, initial):
    matches = []
    for item in commands:
        # Independent actual protected script execution is required; a model
        # printing or saving a fabricated all-true dictionary cannot satisfy this.
        try:
            recipe = canary_recipe(item)
            provenance = item.get('executor_provenance', {})
            output = item.get('aggregatedOutput')
            if (recipe is None or type(item.get('exitCode')) is not int or item['exitCode'] != 0
                    or not isinstance(output, str) or not isinstance(provenance, dict)
                    or provenance.get('tool_call_id') != item.get('id')
                    or type(provenance.get('stdout_bytes')) is not int
                    or provenance['stdout_bytes'] != len(output.encode())
                    or provenance.get('stdout_sha256') != sha(output.encode())):
                continue
            if recipe['stderr'] is not None and contents.get(recipe['stderr']) != b'':
                continue
            obj = json.loads(output)
        except (ValueError, KeyError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        checks = obj.get('checks', {})
        if (obj.get('qualified') is not True or not isinstance(checks, dict) or len(checks) != 45
                or set(checks) != set(initial.get('checks', {})) or not all(v is True for v in checks.values())):
            continue
        for name, raw in contents.items():
            if not name.startswith('notes/') or not name.endswith('boundary-observation.json'):
                continue
            if recipe['output'] is not None and name != recipe['output']:
                continue
            try:
                saved = json.loads(raw)
            except ValueError:
                continue
            if saved == obj:
                matches.append({'file': name, 'item_id': item['id'], 'saved_sha256': sha(raw),
                    'actual_output_sha256': sha(item['aggregatedOutput'].encode()),
                    'canonical_json_sha256': sha(canonical(obj)),
                    'executor_provenance': provenance, 'recipe': recipe,
                    'join': 'actual protected canary output equals separately retained named note as complete JSON'})
    return matches


def upgrade_stage(root, stage, source_zip=None):
    """Prospective proofs keep observed output and source-bound check values distinct."""
    commands, integrity = authenticated_commands(root, stage['events'])
    initial = json.loads((Path(root) / 'canary-stdout.json').read_text(encoding='utf-8'))
    matches = canary_matches(commands, stage['contents'], initial)
    if source_zip is not None:
        # Lazy import avoids the helper's shared transport-reader import cycle.
        from canary_exit_proof import canary_exit_evidence
        audit = canary_exit_evidence(root, source_zip)
        stage['canary_exit_proof'] = audit
        matches.extend(audit['evidence'])
        if not matches:
            # A readback alone is not protected-canary execution evidence.
            # This optional proof must close the complete prior-writer history.
            from canary_readback_proof import canary_readback_evidence
            readback = canary_readback_evidence(root, source_zip)
            stage['canary_readback_proof'] = readback
            if readback.get('verified') is True:
                matches.extend(readback['evidence'])
    # Startup instruction evidence remains the model-visible aggregate. The
    # only normalization is a successful exact cat with authenticated zero bytes.
    visible = list(stage['commands'])
    seen = {item['id'] for item in visible}
    for item in commands:
        if (item['id'] not in seen and item['aggregatedOutput'] == ''
                and exact_cat_paths(item) == ['Continuity.md']):
            visible.append(item)
    stage['commands'] = visible
    stage['source_commands'] = commands
    stage['executor_capture'] = integrity
    stage['canary_matches'] = matches
    stage['checks']['trusted_executor_capture_integrity'] = integrity['verified']
    stage['checks']['all_45_model_canaries_saved'] = bool(matches)
    return stage
