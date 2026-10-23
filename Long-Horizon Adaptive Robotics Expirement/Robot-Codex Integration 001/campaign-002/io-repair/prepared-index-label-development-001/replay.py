"""New-source development proof; never a historical qualification reassessment."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
REPO = C.parents[2]
ROOT = C.parent / 'local-evidence/campaign002/qualification/RCI001-C02-smoke-024/orchestrator/resume'
RELEASE = C.parent.parent / 'Architecture Map/releases/RCI001-C02-dev-082'
ITEM = 'exec-76195979-2b0a-4a23-9758-34055dc23f0f'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)}


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def main():
    dest = HERE / 'replay-001'
    dest.mkdir(exist_ok=False)
    queue_argv = [sys.executable, '-X', 'utf8', '-B', str(REPO.parent/'tools/compute_queue/compute_queue.py'),
                  'status', '20260929T030751715764Z-8ed12f73']
    auth = subprocess.run(queue_argv, capture_output=True)
    (dest/'official.stdout').write_bytes(auth.stdout); (dest/'official.stderr').write_bytes(auth.stderr)
    job = json.loads(auth.stdout)
    assert auth.returncode == 0 and job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
    save(dest/'official-status.json', job)
    original_bindings = [binding(p) for p in (RELEASE/'snapshot.json',RELEASE/'code.zip',
        C/'qualification/smoke-024-assessment.json',ROOT/'client/events.jsonl',ROOT/'runtime-input-hashes.json',
        ROOT/'executor-1-capture.jsonl',ROOT/'executor-2-capture.jsonl')]
    snapshot = json.loads((RELEASE/'snapshot.json').read_text(encoding='utf-8'))
    changes = []
    with zipfile.ZipFile(RELEASE/'code.zip') as original:
        names = original.namelist()
        assert len(names) == len(set(names)) and set(names) == set(snapshot['sources'])
        entries = {}
        for name in names:
            data = original.read(name); expected = snapshot['sources'][name]
            assert sha(data) == expected['sha256'] and len(data) == expected['bytes']
            entries[name] = data
    for name in ('prepared_result_segments.py', 'test_prepared_result_segments.py', 'test_prepared_startup_segments.py'):
        path = C/'assessment'/name; relative = path.relative_to(REPO).as_posix()
        old = entries[relative]; new = path.read_bytes()
        assert old == (HERE/'baseline'/name).read_bytes()
        changes.append({'path':relative,'old_sha256':sha(old),'old_bytes':len(old),'new_sha256':sha(new),'new_bytes':len(new)})
        entries[relative] = new
    method = C/'io-repair/PREPARED_INDEX_LABELS_V1.md'
    relative = method.relative_to(REPO).as_posix()
    assert relative not in entries
    entries[relative] = method.read_bytes()
    overlay = dest/'development-source-overlay.zip'
    with zipfile.ZipFile(overlay,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in entries.items(): archive.writestr(name,data)
    with zipfile.ZipFile(overlay) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist())) == len(entries)
        assert all(archive.read(name) == data for name,data in entries.items())
    save(dest/'source-overlay.json',{'schema':'campaign002-development-source-overlay-1',
        'scope':'Only declared parser/test changes and new method over exact dev082 source archive; no frozen revision or qualification claim.',
        'original':original_bindings[:2],'overlay':binding(overlay),'original_source_count':len(snapshot['sources']),
        'overlay_source_count':len(entries),'replacements':changes,'addition':binding(method)})
    sys.path.insert(0,str(C/'assessment'))
    from prepared_startup_segments import prove_prepared_segments
    from retained_reads import process_reads
    events = [json.loads(s) for s in (ROOT/'client/events.jsonl').read_text(encoding='utf-8').splitlines()]
    event, = [e for e in events if e.get('method')=='item/completed' and e.get('params',{}).get('item',{}).get('id')==ITEM]
    assessment=json.loads((C/'qualification/smoke-024-assessment.json').read_text(encoding='utf-8'))
    old, = [p for p in assessment['literal_read_segment_evidence']['resume']['proofs'] if p['item_id']==ITEM]
    reads, integrity=process_reads(ROOT,events)
    assert integrity['verified']
    result=prove_prepared_segments(ROOT,event,events,reads,overlay,old['segments'])
    assert result['covered_segment_indices']==[0,1]
    assert result['match']=='complete_fixed_file_in_prepared_result_prefix'
    assert result['app_projection_equals_executor'] is False
    save(dest/'new-source-read-proof.json',result)
    assert original_bindings == [binding(Path(value['path'])) for value in original_bindings]
    assert assessment['smoke_passed'] is False
    save(dest/'receipt.json',{'schema':'campaign002-prepared-index-label-development-replay-1','passed':True,
        'scope':'Full helper source/capture/outer-call/child-bijection and fixed-file proof under explicit reviewed development overlay; original qualification remains failed.',
        'model_calls':0,'official_authentication':binding(dest/'official-status.json'),'original_inputs':original_bindings,
        'source_overlay':binding(dest/'source-overlay.json'),'development_proof':binding(dest/'new-source-read-proof.json'),
        'covered_files':['Tasks.md','Robot.md'],'uncovered_file':'Tools.md','original_verdict_unchanged':True,
        'replay_script':binding(Path(__file__))})
    print(json.dumps({'receipt':binding(dest/'receipt.json'),'covered_files':['Tasks.md','Robot.md'],
                      'original_qualification_unchanged':True}))


if __name__=='__main__':
    main()
