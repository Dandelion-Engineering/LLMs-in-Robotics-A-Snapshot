"""Finite prepared-result attribution for complete, initial fixed-file segments.

The caller supplies literal source segmentation. This adapter independently joins
all declared children to retained processes; it never repairs the app projection.
"""
from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import shlex
import zipfile

import literal_read_segments as literal
import prepared_result_segments as parser
import raw_tool_result_reads as raw
from completion_chronology import upper_float
from empty_startup_reads import load_json, require
from retained_reads import load_capture, process_reads, sha


SCHEMA = 'prepared-startup-segments-1'
FIXED = frozenset(('RobotAgentPrompt.md', 'Tasks.md', 'Robot.md', 'Tools.md'))
METHOD = 'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md'


def source_contract(source_zip):
    proof = parser.source_contract(source_zip)
    paths = [Path(__file__).with_name(name) for name in (
        'prepared_startup_segments.py', 'literal_read_segments.py',
        'retained_reads.py', 'empty_startup_reads.py', 'completion_chronology.py')]
    paths.append(Path(__file__).parents[1] / METHOD)
    with zipfile.ZipFile(source_zip) as archive:
        for path in paths:
            suffix = '/campaign-002/' + path.relative_to(Path(__file__).parents[1]).as_posix()
            names = [name for name in archive.namelist() if name.endswith(suffix)]
            digest = sha(path.read_bytes())
            require(len(names) == 1 and sha(archive.read(names[0])) == digest,
                    'Prepared startup source absent/changed: ' + suffix)
            proof.append({'path': names[0], 'sha256': digest})
    return proof


def context(event):
    value = tuple(event.get('params', {}).get(k) for k in ('threadId', 'turnId'))
    require(all(isinstance(v, str) and v for v in value), 'Missing thread/turn identity')
    return value


def emission(event):
    value = event.get('emittedAtMs')
    require(type(value) is int and 0 <= value <= 2**63 - 1,
            'Native emission must be an exact nonnegative i64 millisecond value')
    return value


def outer_pair(events, completed_event):
    selected = [i for i, event in enumerate(events) if event is completed_event]
    require(len(selected) == 1, 'Completed event must occur exactly once')
    groups = {}
    for i, event in enumerate(events):
        obj = event.get('params', {}).get('item', {})
        if event.get('method') != 'rawResponseItem/completed' or obj.get('type') not in raw.RAW_FIELDS:
            continue
        identity = obj.get('call_id')
        require(isinstance(identity, str) and identity, 'Missing raw call ID')
        groups.setdefault(identity, []).append((i, event, obj))
    candidates = []
    for identity, group in groups.items():
        require(len(group) in (1, 2), 'Duplicate raw call/output identity')
        if len(group) == 2:
            first, last = group
            require(first[2].get('type') in raw.CALL_TYPES
                    and last[2].get('type') == raw.CALL_TYPES[first[2]['type']]
                    and context(first[1]) == context(last[1])
                    and emission(first[1]) <= emission(last[1]),
                    'Raw pair reordered/foreign/inconsistent')
            if first[0] < selected[0] < last[0]:
                candidates.append(group)
    require(len(candidates) == 1, 'No unique completed outer interval')
    first, last = candidates[0]
    require(context(first[1]) == context(completed_event), 'Foreign selected outer context')
    for identity, group in groups.items():
        if group is candidates[0]:
            continue
        if len(group) == 1:
            require(group[0][2].get('type') in raw.CALL_TYPES and group[0][0] > last[0]
                    and emission(group[0][1]) >= emission(last[1]),
                    'Earlier unresolved/orphan raw call overlaps selected evidence')
        else:
            a, b = group
            require(b[0] < first[0] or a[0] > last[0], 'Overlapping outer calls')
            if b[0] < first[0] and a[2].get('type') == 'custom_tool_call' and a[2].get('name') == 'exec':
                body = b[2].get('output')
                if isinstance(body, list):
                    body = body[0].get('text') if body and isinstance(body[0], dict) else None
                require(isinstance(body, str) and raw.TERMINAL_CODE_HEADER.match(body),
                        'Earlier code-mode cell lacks terminal status')
    for _, event, obj in (first, last):
        require(set(obj) <= raw.RAW_FIELDS[obj['type']], 'Unknown raw item envelope')
    call, output = first[2], last[2]
    require(call.get('type') == 'custom_tool_call' and call.get('name') == 'exec'
            and call.get('namespace') in (None, 'functions')
            and call.get('status') in (None, 'completed') and not call.get('encrypted_function_args'),
            'Unsupported selected raw call')
    require(output.get('name') in (None, call['name'])
            and output.get('namespace') in (None, call.get('namespace')), 'Foreign raw output tool')
    return first, last


def prove_prepared_segments(root, completed_event, events, reads, source_zip, segments):
    """Return covered fixed-file indices, or raise without altering old evidence."""
    root, source_zip = Path(root), Path(source_zip)
    source = source_contract(source_zip)
    inputs = []
    require(load_json(root / 'client/events.jsonl', inputs, lines=True) == events,
            'Events differ from retained native journal')
    launch = load_json(root / 'client/launch.json', inputs)
    preflight = load_json(root / 'client/preflight.json', inputs)
    require(launch.get('experimental_raw_events_requested') is True
            and preflight.get('experimental_raw_events_requested') is True
            and preflight.get('experimental_raw_events_thread_start_accepted') is True
            and preflight.get('preflight_passed') is True, 'Raw result option lacks qualified receipts')
    starts = [e for e in events if e.get('kind') == 'request' and e.get('method') == 'thread/start']
    require(len(starts) == 1 and starts[0].get('params', {}).get('experimentalRawEvents') is True,
            'Missing unique raw-enabled thread start')
    first, last = outer_pair(events, completed_event)
    begin, end = first[0], last[0]
    identity = context(first[1])
    require(preflight.get('thread_id') == identity[0], 'Foreign preflight thread')
    recipe = parser.parse_wrapper(first[2]['input'])
    children = recipe['children']
    require(1 <= len(children) <= 8, 'Child count outside finite bound')
    lower = Decimal(emission(first[1])) / 1000
    upper = Decimal(emission(last[1]) + 1) / 1000

    # Recheck the supplied authenticated mapping, so direct callers cannot forge
    # stdout/provenance while presenting an otherwise valid capture.
    actual_reads, integrity = process_reads(root, events)
    require(integrity['verified'], 'Executor capture integrity failed')
    captures, requests = {}, []
    for path in sorted(root.glob('executor-*-capture.jsonl')):
        rows, _, receipt = load_capture(path)
        captures[path.name] = rows
        inputs.append({'path': str(path), 'sha256': receipt['sha256'], 'bytes': path.stat().st_size})
        requests.extend((path.name, row) for row in rows if row.get('kind') == 'request'
                        and row.get('message', {}).get('method') == 'process/start')
    in_window = [(name, row) for name, row in requests
                 if lower <= Decimal(str(row['wall_unix_s'])) < upper]
    require(len(in_window) == len(children), 'Additional/missing captured invocation in outer interval')
    native = [(i, e) for i, e in enumerate(events) if e.get('method') in ('item/started', 'item/completed')
              and e.get('params', {}).get('item', {}).get('type') == 'commandExecution']
    inside = [(i, e) for i, e in native if begin < i < end]
    require(len(inside) == 2 * len(children), 'Additional/missing native lifecycle in outer interval')
    for i, event in native:
        if event['method'] == 'item/started' and i < begin:
            tool_id = event['params']['item'].get('id')
            endings = [j for j, e in native if e['method'] == 'item/completed'
                       and e['params']['item'].get('id') == tool_id]
            require(len(endings) == 1 and i < endings[0] < begin, 'Earlier native command unresolved/overlapping')

    linked, used, signatures = [], set(), set()
    for index, options in enumerate(children):
        argv = ['/usr/bin/bash', '-lc', options['cmd']]
        raw.command_options(options, argv)
        paths = literal.literal_cat_paths(argv)
        require(paths, 'Child is not an approved literal cat')
        signature = tuple(argv)
        require(signature not in signatures, 'Ambiguous duplicate child command')
        signatures.add(signature)
        matches = [(i, e) for i, e in inside if e['method'] == 'item/completed'
                   and shlex.split(e['params']['item'].get('command', '')) == argv]
        require(len(matches) == 1, 'No unique child command signature match')
        _, event = matches[0]
        item = event['params']['item']; tool_id = item.get('id')
        require(isinstance(tool_id, str) and tool_id and tool_id not in used, 'Duplicate child ID')
        used.add(tool_id)
        life = [(i, e) for i, e in native if e['params']['item'].get('id') == tool_id]
        require(len(life) == 2 and [e['method'] for _, e in life] == ['item/started', 'item/completed']
                and all(begin < i < end and context(e) == identity for i, e in life),
                'Duplicate/missing/foreign child lifecycle')
        require(all(emission(first[1]) <= emission(e) <= emission(last[1]) for _, e in life),
                'Child emission outside selected parent interval')
        require(tool_id in reads and tool_id in actual_reads and reads[tool_id] == actual_reads[tool_id],
                'Child lacks complete authenticated successful stream')
        read = actual_reads[tool_id]; provenance = read['provenance']
        reqs = [(name, row) for name, row in requests
                if row['message']['params'].get('metadata', {}).get('toolCallId') == tool_id]
        require(len(reqs) == 1 and reqs[0] in in_window
                and reqs[0][0] == provenance['file']
                and reqs[0][1]['sequence'] == provenance['request_sequence'], 'Child capture identity ambiguity')
        execution = literal.execution_proof(root, event, events, read)
        require(Decimal(str(execution['closed_wall_unix_s'])) < upper, 'Child close outside raw completion interval')
        linked.append({'command_index': index, 'native_tool_call_id': tool_id, 'options': options,
                       'argv': argv, 'paths': paths, 'executor_provenance': provenance, 'execution': execution})
    require({row['message']['params'].get('metadata', {}).get('toolCallId') for _, row in in_window} == used,
            'Captured process set differs from declared children')
    target_id = completed_event['params']['item'].get('id')
    target = next((child for child in linked if child['native_tool_call_id'] == target_id), None)
    require(target is not None, 'Selected command not in child bijection')
    result = parser.parse_prepared_result(last[2]['output'], recipe)
    records = result['records']
    require([r['command_index'] for r in records] == (list(range(len(children)))
            if result['mode'] == 'complete' else [0]), 'Prepared record cardinality/order differs')
    summaries = []
    for record in records:
        child = linked[record['command_index']]
        stdout = actual_reads[child['native_tool_call_id']]['stdout'].encode()
        prefix = record['stdout_prefix']
        require(isinstance(prefix, bytes) and (prefix == stdout if record['complete'] else stdout.startswith(prefix)),
                'Prepared child bytes differ from authenticated stdout')
        rounding = parser.validate_prefix_rounding(record, stdout, result['truncation'])
        summaries.append({k: v for k, v in record.items() if not k.startswith('_')
                          and k not in ('stdout_prefix', 'uncredited_trailing_escape')})
        summaries[-1].update(stdout_prefix_sha256=sha(prefix),
                             prefix_rounding=rounding,
                             uncredited_trailing_escape_bytes=len(record['uncredited_trailing_escape']),
                             uncredited_trailing_escape_sha256=sha(record['uncredited_trailing_escape']))
    hashes = load_json(root / 'runtime-input-hashes.json', inputs)
    stdout = actual_reads[target_id]['stdout'].encode()
    require(isinstance(segments, list) and len(segments) == len(target['paths']), 'Missing trusted literal segments')
    offset, covered = 0, []
    record = next((r for r in records if r['command_index'] == target['command_index']), None)
    for index, segment in enumerate(segments):
        end_byte = segment.get('end_byte')
        require(segment.get('path') == target['paths'][index] and type(end_byte) is int
                and type(segment.get('start_byte')) is int and segment['start_byte'] == offset
                and end_byte > offset and segment.get('bytes') == end_byte - offset
                and end_byte <= len(stdout) and sha(stdout[offset:end_byte]) == segment.get('sha256'),
                'Literal segment boundary/hash differs from source stdout')
        if segment['path'] in FIXED:
            require(hashes.get(segment['path']) == segment['sha256'], 'Initial fixed-file hash differs')
            if record is not None and end_byte <= len(record['stdout_prefix']):
                covered.append({'segment_index': index, 'path': segment['path'], 'sha256': segment['sha256'],
                                'bytes': end_byte - offset, 'encoded_span': parser.encoded_span(record, offset, end_byte)})
        offset = end_byte
    require(offset == len(stdout), 'Literal segmentation does not consume complete stdout')
    require(covered, 'No complete nonempty fixed startup file in prepared evidence')
    evidence_upper = max(upper, *(Decimal(x['execution']['evidence_complete_upper_decimal_seconds']) for x in linked))
    return {'schema': SCHEMA, 'match': ('complete_fixed_file_in_prepared_result_prefix' if result['mode'] == 'prefix'
                                      else 'complete_fixed_file_in_prepared_result'),
            'mode': result['mode'], 'call_id': first[2]['call_id'], 'native_tool_call_id': target_id,
            'thread_id': identity[0], 'turn_id': identity[1], 'binding': 'finite_literal_children_unique_interval_bijection',
            'raw_call_event_index': begin, 'raw_output_event_index': end,
            'raw_call_sha256': sha(json.dumps(first[2], sort_keys=True, ensure_ascii=False).encode()),
            'raw_output_sha256': sha(json.dumps(last[2], sort_keys=True, ensure_ascii=False).encode()),
            'recipe': recipe, 'children': linked, 'records': summaries,
            'covered_segment_indices': [x['segment_index'] for x in covered], 'covered_segments': covered,
            'prepared_body_sha256': result['body_sha256'], 'prepared_body_bytes': result['body_bytes'],
            'truncation': result['truncation'], 'app_projection_equals_executor': actual_reads[target_id]['provenance']['app_projection_equals_executor'],
            'raw_output_emitted_at_ms': emission(last[1]),
            'raw_output_emission_interval': {'lower_numerator_ms': emission(last[1]), 'upper_numerator_ms': emission(last[1]) + 1, 'denominator': 1000},
            'evidence_complete_upper_decimal_seconds': str(evidence_upper),
            'evidence_complete_upper_wall_unix_s': upper_float(evidence_upper),
            'source_contract': source, 'inputs': inputs,
            'scope': 'Only complete initial fixed-file segments in observed prepared output; no repaired display, Continuity/live, suffix, attention or exact-next-request claim.'}
