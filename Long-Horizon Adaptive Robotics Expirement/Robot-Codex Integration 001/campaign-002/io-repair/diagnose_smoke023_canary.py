"""Read-only diagnosis of the original Smoke023 resumed canary rejection."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile

IO = Path(__file__).resolve().parent
C = IO.parent
REPO = C.parents[2]
R = C.parent
Q = C / 'qualification'
STAGE = R / 'local-evidence/campaign002/qualification/RCI001-C02-smoke-023/orchestrator/resume'
SNAPSHOT = REPO / 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-078/snapshot.json'
JOB = '20260929T014234165833Z-cba1e8b0'
ITEM = 'exec-cff19e50-e747-4213-b0b8-41e322b5eceb'


def identity(path):
    path = Path(path)
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def main():
    out = IO / 'smoke-023-canary-diagnosis.json'
    assert not out.exists()
    queue = REPO.parent / 'tools/compute_queue/compute_queue.py'
    command = [sys.executable, '-X', 'utf8', '-B', str(queue), 'status', JOB]
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, encoding='utf-8', check=True)
    job = json.loads(result.stdout)
    assert job['id'] == JOB and job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
    frozen = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    bindings = [identity(Path(__file__)), identity(SNAPSHOT), identity(SNAPSHOT.with_name('code.zip'))]
    source_bindings = []
    names = ['retained_reads.py', 'canary_exit_proof.py', 'empty_startup_reads.py', 'completion_chronology.py', 'assess_smoke_v2.py']
    with zipfile.ZipFile(SNAPSHOT.with_name('code.zip')) as archive:
        for name in names:
            path = C / 'assessment' / name
            rel = path.relative_to(REPO).as_posix()
            record = identity(path)
            assert record['sha256'] == frozen['sources'][rel]['sha256']
            assert hashlib.sha256(archive.read(rel)).hexdigest() == record['sha256']
            source_bindings.append(record)
    sys.path.insert(0, str(C / 'assessment'))
    import retained_reads as reader
    import canary_exit_proof as canary
    from empty_startup_reads import environment_proof
    from completion_chronology import completion_chronology
    receipts = []
    events_path = STAGE / 'client/events.jsonl'
    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines()]
    reads, integrity = reader.process_reads(STAGE, events)
    assert integrity['verified']
    completed = [(i, e) for i, e in enumerate(events, 1) if e.get('method') == 'item/completed' and e.get('params', {}).get('item', {}).get('id') == ITEM]
    assert len(completed) == 1
    line, event = completed[0]
    item = event['params']['item']
    read = reads[ITEM]
    provenance = read['provenance']
    rows, delivered, capture = reader.load_capture(STAGE / provenance['file'])
    request = rows[provenance['request_sequence'] - 1]
    params = request['message']['params']
    assert request['original_message_sha256'] == request['retained_message_sha256']
    assert params['metadata']['toolCallId'] == ITEM and params['argv'] == shlex.split(item['command'])
    execution = environment_proof(params)
    chronology = completion_chronology(rows, delivered, request, provenance['process_id'], event['emittedAtMs'])
    before = json.loads((STAGE / 'runtime-before-close.json').read_text(encoding='utf-8'))
    after = json.loads((STAGE / 'runtime-after-close.json').read_text(encoding='utf-8'))
    note = canary.retained_file(before, after, 'notes/resume-boundary-observation.json')
    sidecar = canary.retained_file(before, after, 'notes/resume-boundary-execution.json')
    saved = json.loads(note)
    observed = json.loads(read['stdout'])
    assert saved == observed and canary.check_document(saved)
    hashes = json.loads((STAGE / 'runtime-input-hashes.json').read_text(encoding='utf-8'))
    boundary = canary.source_proof(SNAPSHOT.with_name('code.zip'), hashes, receipts)
    fixture = canary.fixture_proof(STAGE, hashes, before, after, receipts)
    assessment = Q / 'smoke-023-assessment.json'
    original = json.loads(assessment.read_text(encoding='utf-8'))
    assert original['smoke_passed'] is False and original['checks']['resume:all_45_model_canaries_saved'] is False
    for path in [assessment, events_path, STAGE / provenance['file'], STAGE / 'runtime-before-close.json', STAGE / 'runtime-after-close.json', STAGE / 'runtime-input-hashes.json']:
        bindings.append(identity(path))
    value = {'schema': 'campaign002-smoke023-canary-diagnosis-1', 'official_command': command, 'official': job,
        'original_assessment': identity(assessment), 'original_verdict_unchanged': True,
        'item_id': ITEM, 'completed_event_physical_line': line, 'native_argv': params['argv'],
        'execution': execution, 'completion_chronology': chronology, 'executor': provenance,
        'capture': capture, 'capture_integrity': integrity, 'source_bindings': source_bindings,
        'reviewed_boundary': boundary, 'fixture': fixture,
        'observed_stdout': {'sha256': reader.sha(read['stdout'].encode()), 'bytes': len(read['stdout'].encode()),
                            'app_equals_executor': read['stdout'] == item['aggregatedOutput']},
        'retained_note': {'sha256': reader.sha(note), 'bytes': len(note), 'before_after_identical': True,
                          'json_equal_to_observed_stdout': saved == observed, 'all_45_true': True},
        'sidecar': {'sha256': reader.sha(sidecar), 'bytes': len(sidecar), 'contents': json.loads(sidecar),
                    'scope': 'Fallible retained model-writable note; not an independent child exit attestation.'},
        'existing_recipe': reader.canary_recipe(item),
        'existing_exit_recipe': canary.recognized_recipe(params['argv']),
        'finding': 'Original verifier correctly rejects an unsupported compound shell/Python readback recipe. Complete authenticated process stdout semantically equals the retained note with all 45 true checks; exact native argv uses protected canary stdout redirect followed by bounded JSON readback and a separate execution sidecar.',
        'limit': 'The process exit is the Python readback exit, not independently observed protected canary child exit. Retained sidecar is model writable. No new pass or alternate historical assessment is produced.',
        'prospective_candidate': 'A finite source-bound readback recipe may extend the existing redirect-then-read semantic JSON proof, with exact argv/AST, closed imports/environment, nonoverlapping literal paths, authenticated complete stdout and unchanged 45-check/schema comparisons. Do not infer original canary stdout bytes or child exit from reformatted output.',
        'bindings': bindings, 'additional_receipts': receipts}
    with out.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
    print(json.dumps(identity(out)))


if __name__ == '__main__':
    main()
