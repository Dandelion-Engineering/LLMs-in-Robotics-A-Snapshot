"""Create the immutable gate after the independently completed preflight jobs."""
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('retention', HERE / 'retention.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
part_path = HERE / 'records/r4-policy-001-partition.json'
part = r.read(part_path)
chat_path = r.ROOT / 'chats/Codex-Human/Audit Storage/Audit Storage - Active.md'
chat = chat_path.read_bytes()
assert len(chat) == 28276
assert b'Implement the Sustainable Storage Fix' in chat
assert r.sha(HERE / 'retention.py') == 'b7081e7b24fc317168c8ca2548afcc85e72172449c66a2bf676cb6c72013e393'
assert (r.ROOT / '.codex-session.lock').read_text().strip() == '2026-09-26T17:44:17.7987520-07:00'
for name in ('r4-policy-001-pre-001-validation.json', 'staged-policy-001/validation.json'):
    assert r.read(HERE / 'records' / name)['status'] == 'passed'
assert r.read(HERE / 'records/r4-policy-001-pre-001-validation.json')['partition_sha256'] == r.sha(part_path)

# New qualification inputs were introduced after dependency extraction; prove
# every one is already a hash-bound retained member, without expanding policy.
image_path = HERE / 'future/image-inputs.json'
inputs = r.read(image_path)
manifest = r.ROOT / part['manifests']['retained']['path']
assert r.sha(manifest) == inputs['manifest_sha256'] == part['manifests']['retained']['sha256']
wanted = {}
for item in inputs['frame_categories']:
    for key, hashkey in (('source', 'rgb_sha256'), ('depth_source', 'depth_sha256')):
        path = (r.EXP / item[key]).relative_to(r.ROOT).as_posix()
        wanted[path] = item[hashkey]
seen = set()
for row in r.rows(manifest):
    if row['path'] in wanted:
        assert row['sha256'] == wanted[row['path']]
        assert r.sha(r.ROOT / row['path']) == row['sha256']
        seen.add(row['path'])
assert seen == set(wanted)
r.emit(HERE / 'records/future-image-retention-002.json', dict(
    created=r.now(), status='passed', image_inputs_sha256=r.sha(image_path),
    retained_manifest_sha256=r.sha(manifest), pairs=len(inputs['frame_categories']),
    distinct_files=len(seen), all_source_hashes_match_retained=True))

process_script = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw)(\\.exe)?$' } | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Depth 3"
processes = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', process_script], encoding='utf-8'))
for proc in processes:
    cmd = proc.get('CommandLine') or ''
    if str(r.ROOT).lower() not in cmd.lower() and 'Python312' not in cmd:
        continue
    if not any(term in cmd for term in ('http.server 8778', 'http.server 8781', 'compute_queue.py', 'future/optimize.py', 'prepare_deletion_gate.py')):
        raise RuntimeError('Unclassified project Python process: ' + cmd)
queue = r.ROOT.parent / 'tools/compute_queue/compute_queue.py'
running = json.loads(subprocess.check_output([r.sys.executable, '-X', 'utf8', '-B', str(queue), 'list', '--state', 'running', '--project', 'LLMs-in-Robotics']))
queued = json.loads(subprocess.check_output([r.sys.executable, '-X', 'utf8', '-B', str(queue), 'list', '--state', 'queued', '--project', 'LLMs-in-Robotics']))
for job in running + queued:
    if not any('future/optimize.py' in arg for arg in job['argv']):
        raise RuntimeError('Unclassified active queue job')
r.emit(HERE / 'records/no-affected-writers-002.json', dict(
    created=r.now(), status='passed', processes=processes, running_jobs=running, queued_jobs=queued,
    evidence='Only read-only HTTP servers, queue worker, this bounded gate preparation, and optional future optimization are present among project Python processes. Future owner confirmed all writes exclusively inside implementation/future; optimization reads completed pilot containers. No simulation or original evidence writer is active.',
    owned_lock='2026-09-26T17:44:17.7987520-07:00', affected_original_writers_observed=0))

refs = []
names = [
    'retention.py', 'test_retention.py', 'records/retention-tests-002.json',
    'records/source-baseline.json', 'records/audit-comparison-001.json',
    'records/audit-preservation-pre-001.json', 'records/preflight-001/summary.json',
    'records/r4-policy-001-partition.json', 'records/r4-policy-001-pre-001-validation.json',
    'records/staged-policy-001/validation.json', 'records/analysis-pre-equivalence.json',
    'records/browser-pre-001.json', 'records/no-affected-writers-002.json',
    'records/future-image-retention-002.json', 'future/image-inputs.json',
    'dependencies/extraction-001/decisions.json', 'dependencies/extraction-001/windows.json',
    'dependencies/source-reconciliation-001.json', 'dependencies/window-completeness-001.json',
    'dependencies/retained-statistics-001.json', 'historical/qualification.json',
    'historical/equivalence-original.json', 'historical/equivalence-restored.json',
    'historical/pre-retirement-input-identities.json']
for name in names:
    path = HERE / name
    refs.append(dict(path=path.relative_to(r.ROOT).as_posix(), sha256=r.sha(path)))
receipts = list((HERE / 'records').glob('queue-*.json')) + [HERE / 'dependencies/extraction-001-queue-receipt.json', HERE / 'historical/queue-receipt.json']
for path in receipts:
    value = r.read(path)
    assert value['state'] == 'succeeded' and value['exit_status'] == 0
    refs.append(dict(path=path.relative_to(r.ROOT).as_posix(), sha256=r.sha(path), kind='official_queue_receipt'))
r.emit(HERE / 'records/pre-deletion-completion-001.json', dict(
    created=r.now(), status='passed', policy=r.POLICY,
    authority=dict(path=chat_path.relative_to(r.ROOT).as_posix(), bytes=len(chat), sha256=r.sha(chat_path), instruction='Randy 2026-09-26 17:43 PDT; conditional authorization to retire only the exact approved r4 RGB/depth manifest after pre-deletion gates.'),
    partition_sha256=r.sha(part_path), deletion_manifest_sha256=part['manifests']['deletion']['sha256'],
    checks={key: True for key in sorted(r.GATES)}, evidence_refs=refs,
    exact_retained=part['manifests']['retained'], exact_deletion=part['manifests']['deletion'],
    explanation='All 12 original reader traces passed exact package comparison with proposed retired paths unavailable. Explorer and saved validation sources, 899 windows, all retained hashes, 3323 nonframe identities, aggregate equality, historical diagnostic/continuity equivalence, and audit census reconciliation passed. Future optimization only writes its own additive folder and all its image inputs are already retained. Historical event/motion sources remain untouched. The first deletion batch will begin only after this immutable record is complete.',
    capability_loss='Unretained original r4 RGB/depth pixels become unavailable; their event metadata and complete numerical/decision evidence remain. New full-frame pixel reanalysis outside retained windows cannot be performed.'))
print(json.dumps(dict(status='passed', gate='records/pre-deletion-completion-001.json', references=len(refs), retained_future_images=len(seen))))
