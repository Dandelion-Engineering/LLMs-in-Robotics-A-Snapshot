"""New checker/source overlay against old evidence; never qualification reuse."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

OUT = Path(__file__).resolve().parent
C = OUT.parents[1]
REPO = C.parents[2]
OLD = C.parents[1] / 'Architecture Map/releases/RCI001-C02-dev-078'
STAGE = C.parent / 'local-evidence/campaign002/qualification/RCI001-C02-smoke-023/orchestrator/resume'
JOB = '20260929T014234165833Z-cba1e8b0'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def binding(path):
    raw = Path(path).read_bytes()
    return dict(path=str(Path(path).resolve()), sha256=sha(raw), bytes=len(raw))

def save(path, obj):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=False)
        stream.write('\n')

def main():
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'status', JOB],
                            cwd=REPO, capture_output=True, check=False)
    assert result.returncode == 0
    job = json.loads(result.stdout)
    assert job['id'] == JOB and job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
    assert job['argv'][job['argv'].index('--manifest')+1] == str(C/'qualification/smoke-023-manifest.json')
    save(OUT / 'replay-official-status.json', job)
    assessment_path = C / 'qualification/smoke-023-assessment.json'
    original = binding(assessment_path)
    assert original['sha256'] == 'aa0b4ceb104e4cefd6d8bac1d0fca424ae555401e7d8a3dcd2846ab0b745c733'
    assessment = json.loads(assessment_path.read_bytes())
    snapshot = binding(OLD/'snapshot.json')
    archive = binding(OLD/'code.zip')
    assert snapshot['sha256'] == assessment['frozen_snapshot_sha256']
    assert archive['sha256'] == assessment['frozen_archive_sha256']
    assert assessment['smoke_passed'] is False
    replacements = [C/'assessment'/name for name in ('prepared_result_segments.py',
                    'test_prepared_result_segments.py','test_prepared_startup_segments.py')]
    replacements.append(C/'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md')
    changed = {p.relative_to(REPO).as_posix(): p.read_bytes() for p in replacements}
    with zipfile.ZipFile(OLD/'code.zip') as source:
        old_names = source.namelist()
        assert len(set(old_names)) == len(old_names)
        old_bindings = {name: dict(sha256=sha(source.read(name)), bytes=len(source.read(name)))
                        for name in changed if name in old_names}
        with zipfile.ZipFile(OUT/'development-source-overlay.zip', 'x', zipfile.ZIP_DEFLATED) as overlay:
            for name in old_names:
                overlay.writestr(name, changed.get(name, source.read(name)))
            for name, raw in changed.items():
                if name not in old_names:
                    overlay.writestr(name, raw)
    overlay = binding(OUT/'development-source-overlay.zip')
    declaration = dict(schema='campaign002-development-source-overlay-1', diagnostic_only=True,
        frozen_revision=False, old_snapshot=snapshot, old_archive=archive, overlay_archive=overlay,
        replaced_or_added={name:dict(before=old_bindings.get(name), after=dict(sha256=sha(raw),bytes=len(raw)))
                           for name,raw in changed.items()},
        scope='Only declared parser/test updates plus prospective method; all other archive entries copied byte-exact. Not a registered/frozen revision.')
    save(OUT/'development-source-overlay.json', declaration)
    sys.path.insert(0, str(C/'assessment'))
    import prepared_startup_segments as binder
    from retained_reads import process_reads
    events = [json.loads(line) for line in (STAGE/'client/events.jsonl').read_bytes().splitlines()]
    target = 'exec-c1826839-35f5-46e8-a223-bfc7571da1fb'
    selected = [e for e in events if e.get('method') == 'item/completed'
                and e.get('params',{}).get('item',{}).get('id') == target]
    assert len(selected) == 1
    reads, integrity = process_reads(STAGE, events)
    assert integrity['verified'] is True
    old_proof = next(p for p in assessment['literal_read_segment_evidence']['resume']['proofs'] if p['item_id']==target)
    proof = binder.prove_prepared_segments(STAGE, selected[0], events, reads,
                                           OUT/'development-source-overlay.zip', old_proof['segments'])
    assert proof['covered_segment_indices'] == [0,1]
    assert [p['path'] for p in proof['covered_segments']] == ['Tasks.md','Robot.md']
    assert proof['app_projection_equals_executor'] is False
    assert proof['recipe']['index_key'] == 'i' and proof['recipe']['emission'] == 'indexed_loop'
    assert proof['mode'] == 'prefix' and proof['truncation']['suffix_consumed_as_evidence'] is False
    assert proof['prepared_body_sha256'] == 'f2cb7cc5d941e61af1d36b80f2fffac18aff2e051ffed2ea8c49eefcf6c90925'
    assert binding(assessment_path) == original
    assert binding(OLD/'snapshot.json') == snapshot and binding(OLD/'code.zip') == archive
    assert all(sha(p.read_bytes()) == sha(changed[p.relative_to(REPO).as_posix()]) for p in replacements)
    save(OUT/'smoke023-development-replay.json', dict(schema='campaign002-prepared-shorthand-development-replay-1',
        development_check_passed=True, qualification_claim=False, original_smoke_passed=False,
        original_assessment=original, old_snapshot=snapshot, old_archive=archive,
        development_overlay=binding(OUT/'development-source-overlay.json'),
        official_status=binding(OUT/'replay-official-status.json'), actual_events=binding(STAGE/'client/events.jsonl'),
        proof=proof, scope='Prospective unchanged binder plus new finite shorthand parser. Development evidence only; historical false verdict and incomplete app display preserved.'))
    print(json.dumps(dict(development_check_passed=True, covered=['Tasks.md','Robot.md'],
                         old_assessment_unchanged=True, app_projection_equals_executor=False,
                         proof_mode=proof['mode'], result=binding(OUT/'smoke023-development-replay.json')),indent=2))

if __name__ == '__main__':
    main()
