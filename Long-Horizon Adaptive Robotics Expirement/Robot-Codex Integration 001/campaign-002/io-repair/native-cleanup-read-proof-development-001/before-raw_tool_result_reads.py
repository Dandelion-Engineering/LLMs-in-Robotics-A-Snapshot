"""Finite prepared-result evidence; never repair the displayed projection.

Code-mode attribution is explicitly unique-call correlation, not a parent-ID
claim. Every returned source byte must already occur in the actual raw result.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import re
import shlex
import zipfile

from empty_startup_reads import finite_time, require, unique_object
from retained_reads import load_capture, sha

MAX_BYTES = 4 * 1024 * 1024
CALL_TYPES = {'function_call': 'function_call_output', 'custom_tool_call': 'custom_tool_call_output'}
RAW_FIELDS = {
    'function_call': {'arguments', 'call_id', 'encrypted_function_args', 'id', 'internal_chat_message_metadata_passthrough', 'name', 'namespace', 'type'},
    'function_call_output': {'call_id', 'id', 'internal_chat_message_metadata_passthrough', 'name', 'namespace', 'output', 'type'},
    'custom_tool_call': {'call_id', 'id', 'input', 'internal_chat_message_metadata_passthrough', 'name', 'namespace', 'status', 'type'},
    'custom_tool_call_output': {'call_id', 'id', 'internal_chat_message_metadata_passthrough', 'name', 'output', 'type'},
}
OPTIONS = {'cmd', 'workdir', 'shell', 'login', 'tty', 'yield_time_ms', 'max_output_tokens'}
SOURCE_HASHES = {
    '/io-repair/native-output-source-002/codex-rs__core__src__tools__context.rs':
        '9a9acc6daab2112bd9ca1a07a1e1f2105b20a7f565878157c726ee0d7a3e00cc',
    '/io-repair/native-output-source-002/codex-rs__core__src__tools__code_mode__output.rs':
        '071a30e1811bb43939e59f910c180b5377e9aa2f99f5e2bc658032bf1d319c77',
    '/isolation-session-9/native/app-server-schema/v2/RawResponseItemCompletedNotification.json':
        'e41475a93885572579b0963718e46783b07f9ddb9e61f0669dac09da4d59185e',
    '/io-repair/RAW_TOOL_RESULT_EVIDENCE_V1.md':
        'e96ac64f3f451ceb0b0470a66306b60462bab89c026a24d139ced969b30ec128',
    '/harness/bootstrap_client_v3.py':
        'a44db8031771c4ff380b52d2abc031a015eb0afcb6e06b13d486272ea3fb0e5d',
    # Dev055 lifecycle and dev056 idle-scheduling parity preserve raw capture.
    # Bind the imported lifecycle implementation independently too.
    '/harness/bootstrap_client_v4.py':
        'a08f0b820c5ce30c0a68bc8ea7fc19102b29834a6b9b0dd447157568060706ad',
    '/harness/native_quiescence.py':
        '6a43907863e50a62bb652a82ebce143ff86cd84cd1da86d510a3c86f5ca389bc',
}
BAD = re.compile(r'\[REDACTED[^\]]*\]|Warning: truncated output|\[\.\.\.[^\]\n]{0,160}truncated[^\]\n]*\]|(?:^|\n)Script (?:failed|error|running|terminated)|App-server output limit exceeded', re.I)
NUMBER = r'[0-9]+(?:\.[0-9]+)?'
CODE_HEADER = re.compile(r'Script completed\nWall time ' + NUMBER +
    r' seconds(?: \(code-mode ' + NUMBER + r' seconds; overhead -?' + NUMBER + r' seconds\))?\nOutput:\n')
TERMINAL_CODE_HEADER = re.compile(CODE_HEADER.pattern.replace('Script completed', 'Script (?:completed|failed|terminated)'))
EXEC_HEADER = re.compile(r'(?:Chunk ID: [A-Za-z0-9_-]+\n)?Wall time: ' + NUMBER +
    r' seconds\nProcess exited with code 0\n(?:Original token count: [0-9]+\n)?Output:\n')


def json_value(text):
    def invalid(value):
        raise ValueError('Nonfinite JSON: ' + value)
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid)


def tokens(script):
    require(isinstance(script, str) and 0 < len(script.encode()) <= 16384, 'Invalid/bounded wrapper required')
    if script.startswith('// @exec:'):
        line, separator, script = script.partition('\n')
        pragma = json_value(line[len('// @exec:'):].strip())
        require(separator and isinstance(pragma, dict) and set(pragma) <= {'yield_time_ms', 'max_output_tokens'}
                and all(type(v) is int and v > 0 for v in pragma.values()), 'Unknown native pragma')
    out, pos = [], 0
    while pos < len(script):
        c = script[pos]
        if c.isspace():
            pos += 1
            continue
        if c in "\"'":
            quote, pos, value = c, pos + 1, ''
            while pos < len(script) and script[pos] != quote:
                c = script[pos]
                require(ord(c) >= 32, 'Control character in JS literal')
                pos += 1
                if c == '\\':
                    require(pos < len(script), 'Unclosed JS escape')
                    c, pos = script[pos], pos + 1
                    escaped = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f',
                               '\\': '\\', '/': '/', '"': '"', "'": "'"}
                    if c == 'u':
                        h = script[pos:pos + 4]
                        require(re.fullmatch('[0-9a-fA-F]{4}', h), 'Invalid Unicode escape')
                        c, pos = chr(int(h, 16)), pos + 4
                    else:
                        require(c in escaped, 'Unsupported JS escape')
                        c = escaped[c]
                value += c
            require(pos < len(script), 'Unclosed JS string')
            value.encode('utf-8', errors='strict')
            out.append(('string', value))
            pos += 1
        elif c in '{}().,;:=':
            out.append((c, c)); pos += 1
        else:
            match = re.match(r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+', script[pos:])
            require(match is not None, 'Unsupported JS token')
            value = match.group(); pos += len(value)
            out.append(('integer', int(value)) if value.isdigit() else ('name', value))
    return out


class Parser:
    def __init__(self, script):
        self.items, self.pos = tokens(script), 0

    def pop(self, value=None):
        require(self.pos < len(self.items), 'Incomplete wrapper')
        item = self.items[self.pos]; self.pos += 1
        require(value is None or item == ('name' if re.fullmatch('[A-Za-z_][A-Za-z_0-9]*', value) else value, value), 'Unsupported wrapper form')
        return item

    def peek(self, value):
        return self.pos < len(self.items) and self.items[self.pos][1] == value

    def semi(self):
        if self.peek(';'): self.pop(';')

    def invocation(self):
        for value in ('await', 'tools', '.', 'exec_command', '(', '{'): self.pop(value)
        options = {}
        while not self.peek('}'):
            kind, key = self.pop()
            require(kind in ('name', 'string') and key in OPTIONS and key not in options, 'Unknown/duplicate command option')
            self.pop(':'); kind, value = self.pop()
            require(kind in ('string', 'integer') or (kind == 'name' and value in ('true', 'false')), 'Nonliteral command option')
            options[key] = (value == 'true') if kind == 'name' else value
            if not self.peek(','): break
            self.pop(',')
            require(not self.peek('}'), 'Trailing object comma unsupported')
        self.pop('}'); self.pop(')')
        return options

    def printer(self):
        kind, name = self.pop()
        require(kind == 'name', 'Printer is not a literal identifier')
        if name == 'console':
            self.pop('.'); self.pop('log')
        else:
            require(name == 'text', 'Unknown printer')
        self.pop('(')


def parse_wrapper(script):
    p = Parser(script)
    if p.peek('const') or p.peek('let'):
        p.pop(); kind, variable = p.pop()
        require(kind == 'name' and variable not in ('tools', 'text', 'console', 'await', 'let', 'const'), 'Invalid binding')
        p.pop('='); options = p.invocation(); p.semi(); p.printer(); p.pop(variable)
        output_only = p.peek('.')
        if output_only: p.pop('.'); p.pop('output')
    else:
        p.printer()
        output_only = p.peek('(')
        if output_only: p.pop('(')
        options = p.invocation()
        if output_only: p.pop(')'); p.pop('.'); p.pop('output')
    p.pop(')'); p.semi()
    require(p.pos == len(p.items), 'Additional JS expression/statement')
    return options, output_only


def command_options(options, argv):
    require(isinstance(options, dict) and set(options) <= OPTIONS and isinstance(options.get('cmd'), str), 'Literal exec options absent')
    require(len(argv) == 3 and argv[:2] == ['/usr/bin/bash', '-lc'] and options['cmd'] == argv[2], 'Raw command differs from actual command')
    require(options.get('workdir', '/workspace') == '/workspace'
            and options.get('shell', '/usr/bin/bash') == '/usr/bin/bash'
            and options.get('login', True) is True and options.get('tty', False) is False,
            'Unqualified shell/workspace/login/TTY')
    for key in ('yield_time_ms', 'max_output_tokens'):
        require(key not in options or type(options[key]) is int and options[key] > 0, 'Invalid numeric command option')


def prepared_payload(body, *, code_mode, output_only):
    require(isinstance(body, (str, list)), 'Unknown output body')
    if isinstance(body, list):
        require(body and all(isinstance(x, dict) and set(x) == {'type', 'text'}
                            and x['type'] == 'input_text' and isinstance(x['text'], str) for x in body), 'Nontext/unknown output content')
        # Ordered text items are the actual complete body, not a substring search.
        body = ''.join(x['text'] for x in body)
    require(0 < len(body.encode()) <= MAX_BYTES and not BAD.search(body), 'Empty/capped/redacted/failed prepared output')
    header = CODE_HEADER if code_mode else EXEC_HEADER
    match = header.match(body)
    require(match is not None, 'Unknown native completed-output envelope')
    payload = body[match.end():]
    if code_mode and not output_only:
        result = json_value(payload)
        allowed = {'chunk_id', 'wall_time_seconds', 'exit_code', 'session_id', 'original_token_count', 'output'}
        require(isinstance(result, dict) and set(result) <= allowed
                and {'wall_time_seconds', 'exit_code', 'output'} <= result.keys(), 'Unknown native exec-result envelope')
        require(type(result['exit_code']) is int and result['exit_code'] == 0 and 'session_id' not in result,
                'Prepared command unfinished/failed')
        require(type(result['wall_time_seconds']) in (int, float) and math.isfinite(result['wall_time_seconds'])
                and result['wall_time_seconds'] >= 0, 'Invalid native timing')
        require('chunk_id' not in result or isinstance(result['chunk_id'], str) and re.fullmatch('[A-Za-z0-9_-]+', result['chunk_id']), 'Invalid chunk identity')
        require('original_token_count' not in result or type(result['original_token_count']) is int and result['original_token_count'] >= 0, 'Invalid native count')
        payload = result['output']
    require(isinstance(payload, str) and 0 < len(payload.encode()) <= MAX_BYTES, 'Missing whole source payload')
    return payload, {'prepared_body_sha256': sha(body.encode()), 'prepared_body_bytes': len(body.encode()),
                     'envelope': 'code_mode_completed' if code_mode else 'direct_exec_completed'}


def source_contract(source_zip):
    bindings = []
    with zipfile.ZipFile(source_zip) as archive:
        expected = dict(SOURCE_HASHES)
        for path in (Path(__file__),):
            expected['/campaign-002/' + path.relative_to(Path(__file__).parents[1]).as_posix()] = sha(path.read_bytes())
        for suffix, digest in expected.items():
            matches = [name for name in archive.namelist() if name.endswith(suffix)]
            require(len(matches) == 1 and sha(archive.read(matches[0])) == digest, 'Raw-result source absent/changed: ' + suffix)
            bindings.append({'path': matches[0], 'sha256': digest})
    return bindings


def raw_result_proof(root, completed_event, events, read, source_zip):
    """Return one complete proof, or raise; caller keeps the old proof unchanged."""
    root = Path(root)
    binding = source_contract(source_zip)
    input_receipts, client_receipts = [], {}
    for name, fields in [('launch.json', ('experimental_raw_events_requested',)),
                         ('preflight.json', ('experimental_raw_events_requested', 'experimental_raw_events_thread_start_accepted'))]:
        path = root / 'client' / name
        data = path.read_bytes()
        record = json_value(data.decode('utf-8'))
        input_receipts.append({'path': str(path), 'sha256': sha(data), 'bytes': len(data)})
        client_receipts[name] = record
        require(all(record.get(field) is True for field in fields), 'Raw-event option not authenticated by client receipt')
    requests = [e for e in events if e.get('kind') == 'request' and e.get('method') == 'thread/start']
    require(len(requests) == 1 and requests[0].get('params', {}).get('experimentalRawEvents') is True, 'Missing unique raw-enabled thread start')
    item = completed_event['params']['item']
    context = tuple(completed_event['params'].get(k) for k in ('threadId', 'turnId'))
    require(all(isinstance(v, str) and v for v in context), 'Missing command thread/turn')
    require(client_receipts['preflight.json'].get('preflight_passed') is True
            and client_receipts['preflight.json'].get('thread_id') == context[0], 'Command belongs to a foreign/unqualified thread')
    native_id = item.get('id')
    require(isinstance(native_id, str) and native_id and type(item.get('exitCode')) is int and item['exitCode'] == 0, 'Invalid command completion')
    raws = [(i, e, e.get('params', {}).get('item', {})) for i, e in enumerate(events)
            if e.get('method') == 'rawResponseItem/completed']
    require(raws, 'No actual raw result events')
    for _, e, obj in raws:
        require(isinstance(obj, dict), 'Malformed raw item')
        if obj.get('type') in set(CALL_TYPES) | set(CALL_TYPES.values()):
            require(isinstance(obj.get('call_id'), str) and obj['call_id'], 'Missing raw call ID')
            pair = [(i, x, o) for i, x, o in raws if o.get('call_id') == obj['call_id']]
            require(len(pair) == 2 and pair[0][2].get('type') in CALL_TYPES
                    and pair[1][2].get('type') == CALL_TYPES[pair[0][2]['type']],
                    'Duplicate/missing/reordered raw call/output')
            identities = [tuple(x.get('params', {}).get(k) for k in ('threadId', 'turnId')) for _, x, _ in pair]
            require(all(isinstance(v, str) and v for v in identities[0]) and identities[0] == identities[1],
                    'Raw pair has missing/foreign thread or turn identity')
    candidates = []
    for call_index, call_event, call in raws:
        if call.get('type') not in CALL_TYPES:
            continue
        pair = [(i, e, o) for i, e, o in raws if o.get('call_id') == call['call_id']]
        require(len(pair) == 2 and pair[0][0] == call_index and pair[1][2].get('type') == CALL_TYPES[call['type']], 'Duplicate/missing/reordered raw call/output')
        output_index, output_event, output = pair[1]
        if not all(tuple(e.get('params', {}).get(k) for k in ('threadId', 'turnId')) == context for e in (call_event, output_event)):
            continue
        completed_indices = [i for i, e in enumerate(events) if e is completed_event]
        require(len(completed_indices) == 1, 'Ambiguous completed event')
        if not call_index < completed_indices[0] < output_index:
            continue
        # Other fully ended calls establish nonoverlap, but their unrelated
        # payloads need not satisfy this read's exact byte/format contract.
        for obj in (call, output):
            require(set(obj) <= RAW_FIELDS[obj['type']], 'Unknown raw tool-item envelope')
            require(not BAD.search(json.dumps(obj)), 'Raw event redacted/truncated/failed')
        require(call.get('namespace') in (None, 'functions'), 'Unknown tool namespace')
        require(output.get('name') in (None, call.get('name')) and output.get('namespace') in (None, call.get('namespace')),
                'Foreign raw output tool name/namespace')
        require(call.get('status') in (None, 'completed') and not call.get('encrypted_function_args'), 'Incomplete/encrypted call')
        code_mode = call['type'] == 'custom_tool_call'
        if code_mode:
            require(call.get('name') == 'exec', 'Unknown custom tool')
            options, output_only = parse_wrapper(call.get('input'))
        else:
            require(call.get('name') == 'exec_command' and call['call_id'] == native_id, 'Direct native call ID mismatch')
            options, output_only = json_value(call.get('arguments', '')), True
        command_options(options, shlex.split(item['command']))
        # No raw outer call may remain active or overlap this interval, even if
        # its output is in another turn. Reject ambiguous identities globally.
        for other_index, _, other in raws:
            if other.get('type') not in CALL_TYPES or other_index == call_index:
                continue
            ends = [i for i, _, o in raws if o.get('call_id') == other.get('call_id') and o.get('type') in CALL_TYPES.values()]
            require(len(ends) == 1 and not (other_index < output_index and ends[0] > call_index), 'Overlapping/unresolved outer call')
            if other.get('type') == 'custom_tool_call' and other.get('name') == 'exec':
                body = events[ends[0]]['params']['item'].get('output')
                if isinstance(body, list):
                    body = (body[0].get('text') if body and isinstance(body[0], dict)
                            and body[0].get('type') == 'input_text' else None)
                require(isinstance(body, str) and TERMINAL_CODE_HEADER.match(body),
                        'Other code-mode cell lacks terminal status; may remain live')
        command_events = [(i, e) for i, e in enumerate(events)
                          if e.get('method') in ('item/started', 'item/completed')
                          and e.get('params', {}).get('item', {}).get('type') == 'commandExecution']
        inside = [(i, e) for i, e in command_events if call_index < i < output_index]
        require(len(inside) == 2 and [e['method'] for _, e in inside] == ['item/started', 'item/completed']
                and all(e['params']['item'].get('id') == native_id and tuple(e['params'].get(k) for k in ('threadId', 'turnId')) == context for _, e in inside), 'Additional/missing/foreign native command in raw interval')
        for i, e in command_events:
            other_id = e['params']['item'].get('id')
            if e['method'] != 'item/started' or other_id == native_id or i >= output_index:
                continue
            ends = [j for j, x in command_events if x['method'] == 'item/completed' and x['params']['item'].get('id') == other_id]
            require(len(ends) == 1 and i < ends[0] < call_index, 'Earlier native command unresolved/overlapping')
        start = finite_time(call_event.get('emittedAtMs')) / 1000
        end = finite_time(output_event.get('emittedAtMs')) / 1000
        require(start < finite_time(completed_event.get('emittedAtMs')) / 1000 <= end, 'Raw completion chronology inconsistent')
        process_requests = []
        for path in sorted(root.glob('executor-*-capture.jsonl')):
            rows, _, _ = load_capture(path)
            for row in rows:
                if row.get('kind') == 'request' and row.get('message', {}).get('method') == 'process/start' and start <= finite_time(row.get('wall_unix_s')) <= end:
                    process_requests.append(row)
        require(len(process_requests) == 1 and process_requests[0]['message']['params'].get('metadata', {}).get('toolCallId') == native_id, 'No unique captured invocation in raw interval')
        payload, envelope = prepared_payload(output.get('output'), code_mode=code_mode, output_only=output_only)
        require(payload == read['stdout'], 'Prepared whole payload differs from complete authenticated executor stdout')
        candidates.append({'schema': 'raw-tool-result-read-1', 'match': 'complete_prepared_tool_result',
            'call_id': call['call_id'], 'native_tool_call_id': native_id, 'thread_id': context[0], 'turn_id': context[1],
            'binding': 'finite_single_command_unique_call_correlation' if code_mode else 'direct_call_id',
            'raw_call_event_index': call_index, 'raw_output_event_index': output_index,
            'call_sha256': sha(json.dumps(call, sort_keys=True, ensure_ascii=False).encode()),
            'output_sha256': sha(json.dumps(output, sort_keys=True, ensure_ascii=False).encode()),
            'source_payload_sha256': sha(payload.encode()), 'source_payload_bytes': len(payload.encode()),
            'whole_prepared_payload_consumed': True, 'app_projection_equals_executor': read['provenance']['app_projection_equals_executor'],
            'source_contract': binding, 'inputs': input_receipts, **envelope,
            'scope': 'Prepared conversation tool-result bytes; no exact next-request, model-attention, or authoritative code-mode parent-ID claim.'})
    require(len(candidates) == 1, 'No unique complete prepared-result proof')
    return candidates[0]
