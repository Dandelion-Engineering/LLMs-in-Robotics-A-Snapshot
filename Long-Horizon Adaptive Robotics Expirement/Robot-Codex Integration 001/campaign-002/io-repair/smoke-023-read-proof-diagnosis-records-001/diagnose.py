"""Read-only failed-qualification diagnosis; no source or verdict replacement."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from decimal import Decimal

REPO = Path(__file__).resolve().parents[5]
C = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ROOT = C.parent / 'local-evidence/campaign002/qualification/RCI001-C02-smoke-023/orchestrator/resume'
RELEASE = C.parents[1] / 'Architecture Map/releases/RCI001-C02-dev-078'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
JOB = '20260929T014234165833Z-cba1e8b0'
ASSESSMENT_SHA = 'aa0b4ceb104e4cefd6d8bac1d0fca424ae555401e7d8a3dcd2846ab0b745c733'
READS = []

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path, role):
    raw = Path(path).read_bytes()
    READS.append(dict(path=str(Path(path).resolve()), sha256=sha(raw), bytes=len(raw), role=role))
    return raw

def load(path, role):
    return json.loads(read(path, role))

def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')

def main():
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'status', JOB],
                            cwd=REPO, capture_output=True, check=False)
    assert result.returncode == 0
    job = json.loads(result.stdout)
    assert job['id'] == JOB and job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
    assert job['argv'][4] == str(C / 'harness/physical.py')
    assert job['argv'][job['argv'].index('--manifest') + 1] == str(C / 'qualification/smoke-023-manifest.json')
    save(OUT / 'official-replay-status.json', job)
    read(OUT / 'official-replay-status.json', 'fresh official successful integer-zero gate, before empirical reads')
    a_raw = read(C / 'qualification/smoke-023-assessment.json', 'unchanged failed independent qualification')
    assert sha(a_raw) == ASSESSMENT_SHA
    assessment = json.loads(a_raw)
    frozen = load(RELEASE / 'snapshot.json', 'actual dev078 source snapshot')
    archive_raw = read(RELEASE / 'code.zip', 'actual dev078 frozen source archive')
    assert sha(archive_raw) == assessment['frozen_archive_sha256']
    assert sha((RELEASE / 'snapshot.json').read_bytes()) == assessment['frozen_snapshot_sha256']
    sources = {}
    with zipfile.ZipFile(RELEASE / 'code.zip') as archive:
        for path in sorted((C / 'assessment').glob('*.py')):
            name = path.relative_to(REPO).as_posix()
            if name not in frozen['sources']:
                continue
            raw = read(path, 'frozen assessment source verified before import')
            assert frozen['sources'][name]['sha256'] == sha(raw) == sha(archive.read(name))
            sources[name] = dict(sha256=sha(raw), bytes=len(raw))
    sys.path.insert(0, str(C / 'assessment'))
    import prepared_result_segments as parser
    import prepared_startup_segments as binder
    import literal_read_segments as literal
    from retained_reads import process_reads, load_capture
    source_contract = binder.source_contract(RELEASE / 'code.zip')
    events = [json.loads(line) for line in read(ROOT / 'client/events.jsonl', 'actual native public/raw event journal').splitlines()]
    launch = load(ROOT / 'client/launch.json', 'native raw-event request receipt')
    preflight = load(ROOT / 'client/preflight.json', 'native accepted raw-event preflight receipt')
    initial_hashes = load(ROOT / 'runtime-input-hashes.json', 'prepared initial file identities')
    read(ROOT / 'runtime-before-close.json', 'source-bound literal segment file inventory')
    assert launch['experimental_raw_events_requested'] is True
    assert preflight['experimental_raw_events_requested'] is True and preflight['experimental_raw_events_thread_start_accepted'] is True
    assert preflight['preflight_passed'] is True
    raw_starts = [e for e in events if e.get('kind') == 'request' and e.get('method') == 'thread/start']
    assert len(raw_starts) == 1 and raw_starts[0]['params']['experimentalRawEvents'] is True
    target = 'exec-c1826839-35f5-46e8-a223-bfc7571da1fb'
    matches = [e for e in events if e.get('method') == 'item/completed' and e.get('params', {}).get('item', {}).get('id') == target]
    assert len(matches) == 1
    first, last = binder.outer_pair(events, matches[0])
    assert (first[0]+1, last[0]+1) == (118, 125)
    assert binder.context(first[1])[0] == preflight['thread_id']
    try:
        parser.parse_wrapper(first[2]['input'])
    except ValueError as error:
        rejection = str(error)
    else:
        raise AssertionError('Original frozen parser unexpectedly recognizes this wrapper')
    assert rejection == 'Unknown index property'
    expected_code = ('const results = await Promise.allSettled([\n'
                     '  tools.exec_command({cmd:"cat Tasks.md Robot.md Tools.md",workdir:"/workspace",max_output_tokens:15000}),\n'
                     '  tools.exec_command({cmd:"cat live/activation.json live/state.json Continuity.md",workdir:"/workspace",max_output_tokens:8500})\n'
                     ']);\nfor (let i=0;i<results.length;i++) text({i,...results[i]});\n')
    assert first[2]['input'] == expected_code
    # Analyst-specified structure for decoding observed bytes, NOT an accepted
    # source grammar or a substituted script, and never returned as qualification.
    recipe = dict(schema='prepared-wrapper-1', mode='parallel', children=[
        dict(cmd='cat Tasks.md Robot.md Tools.md', workdir='/workspace', max_output_tokens=15000),
        dict(cmd='cat live/activation.json live/state.json Continuity.md', workdir='/workspace', max_output_tokens=8500)],
        output_only=False, emission='indexed_loop', index_key='i', max_output_tokens=10000, pragma={})
    reads, integrity = process_reads(ROOT, events)
    assert integrity['verified'] is True
    requests = []
    for path in sorted(ROOT.glob('executor-*-capture.jsonl')):
        read(path, 'authenticated executor capture, replayed with unchanged frozen reader')
        rows, _, _ = load_capture(path)
        requests.extend((path.name, row) for row in rows if row.get('kind') == 'request' and row.get('message', {}).get('method') == 'process/start')
    lower, upper = Decimal(binder.emission(first[1])) / 1000, Decimal(binder.emission(last[1]) + 1) / 1000
    in_window = [(name, row) for name, row in requests if lower <= Decimal(str(row['wall_unix_s'])) < upper]
    assert len(in_window) == 2
    native = [(i, e) for i, e in enumerate(events) if e.get('method') in ('item/started', 'item/completed') and e.get('params', {}).get('item', {}).get('type') == 'commandExecution']
    inside = [(i,e) for i,e in native if first[0] < i < last[0]]
    assert len(inside) == 4
    for i, event in native:
        if event['method'] == 'item/started' and i < first[0]:
            endings = [j for j,e in native if e['method'] == 'item/completed' and e['params']['item'].get('id') == event['params']['item'].get('id')]
            assert len(endings) == 1 and i < endings[0] < first[0]
    children = []
    for index, options in enumerate(recipe['children']):
        argv = ['/usr/bin/bash', '-lc', options['cmd']]
        found = [(i,e) for i,e in inside if e['method'] == 'item/completed' and shlex.split(e['params']['item']['command']) == argv]
        assert len(found) == 1
        line, event = found[0]; tool_id = event['params']['item']['id']
        life = [(i,e) for i,e in native if e['params']['item'].get('id') == tool_id]
        assert len(life) == 2 and [e['method'] for _,e in life] == ['item/started', 'item/completed']
        assert all(first[0] < i < last[0] and binder.context(e) == binder.context(first[1]) for i,e in life)
        assert all(binder.emission(first[1]) <= binder.emission(e) <= binder.emission(last[1]) for _,e in life)
        req = [(name,row) for name,row in requests if row['message']['params'].get('metadata',{}).get('toolCallId') == tool_id]
        assert len(req) == 1 and req[0] in in_window
        stream = reads[tool_id]; provenance = stream['provenance']
        assert req[0][0] == provenance['file'] and req[0][1]['sequence'] == provenance['request_sequence']
        execution = literal.execution_proof(ROOT, event, events, stream)
        assert Decimal(str(execution['closed_wall_unix_s'])) < upper
        children.append(dict(index=index, tool_call_id=tool_id, native_start_line=life[0][0]+1, native_complete_line=line+1,
                             argv=argv, options=options, provenance=provenance, execution=execution))
    assert {row['message']['params']['metadata']['toolCallId'] for _,row in in_window} == {x['tool_call_id'] for x in children}
    decoded = parser.parse_prepared_result(last[2]['output'], recipe)
    assert decoded['mode'] == 'prefix' and len(decoded['records']) == 1
    record = decoded['records'][0]
    stdout = reads[target]['stdout'].encode()
    assert stdout.startswith(record['stdout_prefix'])
    rounding = parser.validate_prefix_rounding(record, stdout, decoded['truncation'])
    old_proof = next(p for p in assessment['literal_read_segment_evidence']['resume']['proofs'] if p['item_id'] == target)
    covered = []
    offset = 0
    for segment in old_proof['segments']:
        end = segment['end_byte']
        assert segment['start_byte'] == offset and sha(stdout[offset:end]) == segment['sha256'] == initial_hashes[segment['path']]
        assert segment['bytes'] == end-offset
        observed = end <= len(record['stdout_prefix'])
        covered.append(dict(segment, complete_in_observed_prefix=observed,
                            encoded_span=parser.encoded_span(record, offset, end) if observed else None))
        offset = end
    assert offset == len(stdout)
    assert [s['path'] for s in covered if s['complete_in_observed_prefix']] == ['Tasks.md', 'Robot.md']
    result = dict(schema='campaign002-smoke-read-proof-diagnosis-1', created_at=datetime.now(timezone.utc).isoformat(),
        run_id='RCI001-C02-smoke-023', revision=frozen['revision'], job_id=JOB,
        diagnostic_only=True, original_assessment_unchanged=True, qualification_claim=False,
        scope='Resume Tasks.md and Robot.md read evidence only; no canary, transport, task outcome or qualification reassessment.',
        original_startup={k:assessment['startup_read_evidence']['resume'][k] for k in ('Tasks.md','Robot.md')},
        original_rejections={k:old_proof[k] for k in ('prepared_tool_result_error','prepared_startup_segments_error')},
        source_parser_rejection=rejection, actual_script=first[2]['input'], actual_script_sha256=sha(first[2]['input'].encode()),
        raw_call_line=first[0]+1, raw_output_line=last[0]+1, raw_call_id=first[2]['call_id'],
        raw_call_item_sha256=sha(json.dumps(first[2],sort_keys=True,ensure_ascii=False).encode()),
        raw_output_item_sha256=sha(json.dumps(last[2],sort_keys=True,ensure_ascii=False).encode()),
        thread_id=binder.context(first[1])[0], turn_id=binder.context(first[1])[1],
        raw_call_emitted_ms=binder.emission(first[1]), raw_output_emitted_ms=binder.emission(last[1]),
        children=children, decoder_scope='Original unchanged frozen decoder plus explicit analyst recipe for byte observation; unsupported JS grammar remains rejected.',
        analyst_recipe=recipe, prepared_body_sha256=decoded['body_sha256'], prepared_body_bytes=decoded['body_bytes'],
        truncation=decoded['truncation'], observed_stdout_prefix_bytes=len(record['stdout_prefix']),
        observed_stdout_prefix_sha256=sha(record['stdout_prefix']), prefix_rounding=rounding, segments=covered,
        executor_integrity=integrity, source_contract=source_contract, assessment_source_bindings=sources, input_bindings=READS,
        conclusion='Both fixed files are completely present in the actual raw result prefix and exact authenticated child stdout. The frozen counted-loop grammar rejects the shorthand index property i. The separate app projection remains incomplete and false.',
        prospective_direction='A separately declared finite shorthand index-property template bound to the exact loop counter could address this case while preserving unique child bijection, initial-file hashes, exact UTF8 prefix boundaries, source bindings, truncation limits and all other gates. No source is changed and no historical verdict is upgraded.',
        limitations=['No claim that the model attended to or reasoned over the bytes.', 'No raw-output suffix is used or reconstructed.', 'Tools.md is not complete in this prefix; its separate later read remains the original assessment evidence.', 'No current assessor rerun or accepted proof was generated.'])
    save(C/'io-repair/smoke-023-read-proof-diagnosis.json', result)
    print(json.dumps({k:result[k] for k in ('source_parser_rejection','prepared_body_bytes','truncation','observed_stdout_prefix_bytes','segments')},indent=2))

if __name__ == '__main__':
    main()
