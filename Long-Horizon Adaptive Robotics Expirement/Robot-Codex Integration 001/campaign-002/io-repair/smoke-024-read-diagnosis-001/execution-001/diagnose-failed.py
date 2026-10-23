"""Read-only Smoke024 diagnosis; never invokes a qualification assessor.

The official original assessment is an input, not a file this script rewrites.
This independently compares retained byte spans without accepting a new grammar.
"""
from pathlib import Path
import base64
import hashlib
import json
import re
import sys
import zipfile

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
REPO = C.parents[2]
ROOT = C.parent / 'local-evidence/campaign002/qualification/RCI001-C02-smoke-024'
STAGE = ROOT / 'orchestrator/resume'
RELEASE = C.parent.parent / 'Architecture Map/releases/RCI001-C02-dev-082'
ITEM = 'exec-76195979-2b0a-4a23-9758-34055dc23f0f'
CALL = 'call_HCyumpn5yxTtD80RZnaUZCeO'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)}


def main():
    official = read(HERE / 'official-status.json')
    assert official['id'] == '20260929T030751715764Z-8ed12f73'
    assert official['state'] == 'succeeded' and type(official['exit_status']) is int and official['exit_status'] == 0
    assessment_path = C / 'qualification/smoke-024-assessment.json'
    assessment = read(assessment_path)
    assert sha(assessment_path.read_bytes()) == '87896350f7eb8812531146427bd541fe2356efa3f986d437fdcd4e8fa02be013'
    snapshot = read(RELEASE / 'snapshot.json')
    sources = []
    with zipfile.ZipFile(RELEASE / 'code.zip') as archive:
        for name in ('prepared_result_segments.py', 'prepared_startup_segments.py',
                     'raw_tool_result_reads.py', 'retained_reads.py', 'literal_read_segments.py',
                     'empty_startup_reads.py', 'completion_chronology.py'):
            path = C / 'assessment' / name
            relative = path.relative_to(REPO).as_posix()
            raw = path.read_bytes()
            assert archive.namelist().count(relative) == 1
            assert archive.read(relative) == raw
            expected = snapshot['sources'][relative]
            assert expected['sha256'] == sha(raw) and expected['bytes'] == len(raw)
            sources.append(binding(path))
    sys.path.insert(0, str(C / 'assessment'))
    import prepared_result_segments as parser
    import prepared_startup_segments as binder
    from retained_reads import process_reads, load_capture
    events_path = STAGE / 'client/events.jsonl'
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
    selected = [(n, e) for n, e in enumerate(events, 1)
                if e.get('method') == 'item/completed' and e.get('params', {}).get('item', {}).get('id') == ITEM]
    assert len(selected) == 1
    completed_line, event = selected[0]
    first, last = binder.outer_pair(events, event)
    assert first[2]['call_id'] == last[2]['call_id'] == CALL
    script = first[2]['input']
    try:
        parser.parse_wrapper(script)
    except ValueError as exc:
        rejection = str(exc)
    else:
        raise AssertionError('Frozen parser unexpectedly accepts actual wrapper')
    assert rejection == 'Unknown index property'
    reads, integrity = process_reads(STAGE, events)
    assert integrity['verified'] and ITEM in reads
    native = reads[ITEM]['stdout'].encode('utf-8')
    provenance = reads[ITEM]['provenance']
    projection = event['params']['item']['aggregatedOutput'].encode('utf-8')
    assert len(native) == 20920 and len(projection) == 4837 and native.endswith(projection)
    files = read(STAGE / 'runtime-before-close.json')['files']
    initial = read(STAGE / 'runtime-input-hashes.json')
    source_bytes = []
    for name in ('Tasks.md', 'Robot.md', 'Tools.md'):
        item = files[name]
        raw = base64.b64decode(item['base64'], validate=True)
        assert len(raw) == item['bytes'] and sha(raw) == item['sha256'] == item['retained_sha256'] == initial[name]
        source_bytes.append((name, raw))
    assert native == b''.join(raw for _, raw in source_bytes)
    output = last[2]['output']
    assert len(output) == 2 and all(set(item) == {'type', 'text'} and item['type'] == 'input_text' for item in output)
    header = output[0]['text'].encode('utf-8')
    assert header == b'Script completed\nWall time 0.1 seconds\nOutput:\n'
    payload = output[1]['text'].encode('utf-8')
    warning = parser.WARNING.match(payload)
    assert warning and warning.groups() == (b'11145', b'2')
    rest = payload[warning.end():]
    matches = list(parser.MARKER.finditer(rest))
    assert len(matches) == 1
    marker = matches[0]
    assert marker.group() == '…1145 tokens truncated…'.encode('utf-8')
    head, tail = rest[:marker.start()], rest[marker.end():]
    assert len(head) == len(tail) == 20000
    metadata = re.match(rb'\{"source":0,"status":"fulfilled","value":\{"chunk_id":"270e59","wall_time_seconds":0\.0084121,"exit_code":0,"original_token_count":5230,"output":"', head)
    assert metadata
    native_encoded = json.dumps(native.decode('utf-8'), ensure_ascii=False, separators=(',', ':'))[1:-1].encode('utf-8')
    observed_encoded = head[metadata.end():]
    assert native_encoded.startswith(observed_encoded)
    spans = []
    plain_offset, encoded_offset = 0, metadata.end()
    for name, raw in source_bytes:
        escaped = json.dumps(raw.decode('utf-8'), ensure_ascii=False, separators=(',', ':'))[1:-1].encode('utf-8')
        available = max(0, min(len(escaped), len(head) - encoded_offset))
        assert head[encoded_offset:encoded_offset + available] == escaped[:available]
        spans.append({'path': name, 'bytes': len(raw), 'sha256': sha(raw),
            'executor_start_byte': plain_offset, 'executor_end_byte': plain_offset + len(raw),
            'escaped_bytes': len(escaped), 'escaped_sha256': sha(escaped),
            'prepared_second_item_start_byte': warning.end() + encoded_offset,
            'prepared_second_item_observed_end_byte': warning.end() + encoded_offset + available,
            'joined_prepared_start_byte': len(header) + warning.end() + encoded_offset,
            'joined_prepared_observed_end_byte': len(header) + warning.end() + encoded_offset + available,
            'observed_escaped_prefix_bytes': available, 'complete_in_unmodified_head': available == len(escaped)})
        plain_offset += len(raw)
        encoded_offset += len(escaped)
    assert [s['complete_in_unmodified_head'] for s in spans] == [True, True, False]
    rows, delivered, capture = load_capture(STAGE / provenance['file'])
    timeline = []
    for row in rows:
        msg = row.get('message', {})
        params = msg.get('params', {})
        if params.get('processId') != provenance['process_id']:
            continue
        if msg.get('method') not in ('process/start', 'process/output', 'process/exited', 'process/closed'):
            continue
        entry = {'capture_sequence': row['sequence'], 'kind': row['kind'], 'method': msg['method'],
                 'wall_unix_s': row.get('wall_unix_s'), 'process_sequence': params.get('seq'),
                 'delivered': row['sequence'] in delivered}
        if msg['method'] == 'process/output':
            data = base64.b64decode(params['chunk'], validate=True)
            entry.update(stream=params['stream'], bytes=len(data), sha256=sha(data))
        if msg['method'] == 'process/exited':
            entry.update(exit_code=params['exitCode'], sandbox_denied=params['sandboxDenied'])
        timeline.append(entry)
    proof = next(p for p in assessment['literal_read_segment_evidence']['resume']['proofs'] if p['item_id'] == ITEM)
    result = {'schema': 'campaign002-smoke-read-diagnosis-1', 'run_id': 'RCI001-C02-smoke-024',
        'queue_job_id': official['id'], 'framework_revision': 'RCI001-C02-dev-082',
        'scope': 'Retained read-evidence diagnosis only; no qualification or task reassessment, no model calls, no grammar acceptance change.',
        'original_smoke_passed': assessment['smoke_passed'],
        'original_passed_check_count': sum(v is True for v in assessment['checks'].values()),
        'original_check_count': len(assessment['checks']),
        'original_false_checks': [k for k,v in assessment['checks'].items() if v is False],
        'startup_verified': {phase: {name: value['verified'] for name,value in assessment['startup_read_evidence'][phase].items()} for phase in ('interrupt','resume')},
        'exact_rejection': {'frozen_parser_replay': rejection,
            'original_prepared_startup_segments_error': proof['prepared_startup_segments_error'],
            'original_prepared_tool_result_error': proof['prepared_tool_result_error']},
        'selected_read': {'item_id': ITEM, 'command': event['params']['item']['command'],
            'completed_line': completed_line, 'completed_emitted_at_ms': event['emittedAtMs'],
            'executor_provenance': provenance, 'capture_timeline': timeline,
            'native_stdout_bytes': len(native), 'native_stdout_sha256': sha(native),
            'app_projection_bytes': len(projection), 'app_projection_sha256': sha(projection),
            'app_projection_is_exact_native_tail': True, 'missing_app_prefix_bytes': len(native)-len(projection)},
        'prepared_output': {'call_id': CALL, 'call_line': first[0]+1, 'output_line': last[0]+1,
            'thread_id': first[1]['params']['threadId'], 'turn_id': first[1]['params']['turnId'],
            'script': script, 'script_sha256': sha(script.encode('utf-8')),
            'joined_bytes': len(header)+len(payload), 'joined_sha256': sha(header+payload),
            'second_item_bytes': len(payload), 'second_item_sha256': sha(payload),
            'status_header_bytes': len(header), 'warning_bytes': warning.end(),
            'head_bytes': len(head), 'head_sha256': sha(head),
            'marker_bytes': len(marker.group()), 'marker_sha256': sha(marker.group()),
            'tail_bytes': len(tail), 'tail_sha256': sha(tail), 'tail_used_as_proof': False,
            'metadata_prefix_bytes': metadata.end(), 'observed_escaped_native_prefix_bytes': len(observed_encoded),
            'exact_authenticated_stdout_encoded_prefix_match': True, 'file_spans': spans},
        'interpretation': 'The complete Tasks.md and Robot.md initial bytes occur inside the native prepared result unchanged head. Current proof correctly rejects an undeclared explicit source label, while the ordinary app aggregate lacks those bytes. This is a finite grammar coverage limit, not evidence of missing Tasks/Robot bytes in the prepared model result.',
        'prospective_option': 'Declare and test a bounded explicit literal index-label class with exact bound-counter value, one original result spread, and exclusion of native/status fields and prototype-related keys. Preserve all call/process/source/index/truncation/complete-file checks and require a fresh qualification lineage. No historical verdict changes.',
        'limits': ['No attention or comprehension claim.', 'No suffix or omitted-gap reconstruction.', 'Tools.md is incomplete in this prepared head; its later separate complete read already passed.', 'The cause of the native app aggregate suffix-only projection is not established by this diagnosis.', 'No generic JavaScript evaluation or new grammar proof is performed.'],
        'input_bindings': [binding(p) for p in (HERE/'official-status.json',HERE/'authentication.json',assessment_path,
            C/'qualification/smoke-024-manifest.json',RELEASE/'snapshot.json',RELEASE/'code.zip',
            events_path,STAGE/provenance['file'],STAGE/'runtime-before-close.json',STAGE/'runtime-input-hashes.json',
            C/'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md',C/'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md')],
        'source_bindings': sources, 'diagnostic_script': binding(Path(__file__))}
    destination = HERE / 'analysis.json'
    with destination.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')
    print(json.dumps({'analysis':binding(destination),'complete_prepared_files':[s['path'] for s in spans if s['complete_in_unmodified_head']], 'spans':spans,'original_verdict_unchanged':sha(assessment_path.read_bytes()) == '87896350f7eb8812531146427bd541fe2356efa3f986d437fdcd4e8fa02be013'}))


if __name__ == '__main__':
    main()
