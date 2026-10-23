"""Append the completed comparison using the canonical Map's atomic API."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
INV = HERE.parent
C = INV.parent
REPO = C.parents[2]
MAP = REPO / 'Long-Horizon Adaptive Robotics Expirement/Architecture Map'
OUT = HERE / 'map-comparison-001'
NOTE_ID = 'RCI001-C02-terminal-investigation-001'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')

def ref(label, path):
    raw = path.read_bytes()
    return dict(label=label, uri=os.path.relpath(path, MAP).replace('\\', '/'),
                sha256=hashlib.sha256(raw).hexdigest(), state='available',
                access='operator', locator=None)

def run(name, *args):
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(MAP/'map.py'), *args],
                            cwd=REPO, capture_output=True, text=True, encoding='utf-8')
    (OUT/(name+'.stdout')).write_text(result.stdout, encoding='utf-8')
    (OUT/(name+'.stderr')).write_text(result.stderr, encoding='utf-8')
    assert result.returncode == 0, (name, result.stderr, result.stdout)
    return json.loads(result.stdout) if '--json' in args else result.stdout

def main():
    OUT.mkdir(exist_ok=False)
    verification = read(HERE/'verification-003/verification.json')
    status = read(HERE/'verification-003-official-status.json')
    assert status['state'] == 'succeeded' and type(status['exit_status']) is int and status['exit_status'] == 0
    assert verification['passed'] is True and read(HERE/'browser-001/receipt.json')['passed'] is True
    data = read(INV/'data.json')
    assert hashlib.sha256((INV/'report.html').read_bytes()).hexdigest() == verification['report_files']['report.html']['sha256']
    records = {kind: [json.loads(line) for line in (MAP/(kind+'.jsonl')).read_text(encoding='utf-8').splitlines()]
               for kind in ('revisions', 'runs', 'results', 'notes')}
    assert NOTE_ID not in {row['id'] for row in records['notes']}
    revision_ids = ['RCI001-C01-frozen-001', 'RCI001-C02-frozen-001']
    assert all(identity in {row['id'] for row in records['revisions']} for identity in revision_ids)
    sets = {revision: [row['id'] for row in records['runs'] if row['revision_id'] == revision]
            for revision in revision_ids}
    assert len(sets[revision_ids[0]]) == 24 and len(sets[revision_ids[1]]) == 20
    assert set(sets[revision_ids[1]]) == {row['run_id'] for row in data['runs']}
    all_runs = set(sum(sets.values(), []))
    result_ids = [row['id'] for row in records['results'] if row['run_id'] in all_runs]
    old_notes = (MAP/'notes.jsonl').read_bytes()
    note = dict(schema_version='architecture-map-1.0', id=NOTE_ID,
        recorded_at=datetime.now(timezone.utc).isoformat(), author='Codex',
        tags=['campaign002', 'known-fixture-repeatability', 'terminal-accounting', 'heartbeat-lease', 'no-causal-repair-claim'],
        target_ids=revision_ids + sum(sets.values(), []), claim_type='comparison',
        supersedes_note_id=None,
        body=('Campaign 002 settled all 20 original slots after an immediate infrastructure/evidence stop at ordinal 11: '
              '10 valid protected successes, no valid task failures, Home06 infrastructure-invalid with unknown task outcome, '
              'and 9 not run. All first ten attempts passed their original 41-check assessments. '
              'Campaign 001 remains 6 valid successes, 4 infrastructure-invalid and 14 not run among 24 planned slots. '
              'Both campaigns use two known fixtures; repeat trials are not new independent scenarios. '
              'All five valid blocked-home attempts first received unsupported_resumption on handback and then set up B successfully. '
              'Stock01/02 placed A1 directly in the fixture; Stock03/04/05 used parking1. '
              'These are observed strategies, not isolated mechanism effects. Home06 diagnostic host metadata reports '
              'Supervisory heartbeat lease expired and a 5.4901152-second adapter_step with a configured 2-second lease. '
              'The frozen step updates its heartbeat before draining synchronous persistence; prolonged drain is a hypothesis, '
              'not established device/scheduler causality. Separate clean process/namespace receipts do not restore missing '
              'assessment or revocation proof. No failed-task output was used to infer a recovery result. '
              'Full denominators, unresolved bounds, original images and source links are in the completed investigation. '
              'The prescribed next boundary is Randy review; no retries, replacements, lease changes or resumed campaign are authorized.'),
        details={
            'actual_run_sets': sets, 'actual_result_ids': result_ids,
            'campaign001_counts_unchanged': data['previous']['counts'], 'campaign002_counts': data['counts'],
            'independent_scenario_count': 2,
            'pairing': 'Within Campaign 002, alternating family pairs reverse order on alternate pairs. Fresh sensor seeds; no randomized or matched causal pairing between campaigns.',
            'analysis': 'Descriptive Wilson 95% intervals use only valid trials and an independence assumption, conditional on validity and early stopping. Invalid/unrun slots remain in planned operational completion and sensitivity bounds; no causal repair estimate.',
            'selection': 'Preselected first and last scheduled episode per family: Stock01/Home01 and unrun Stock10/Home10. Outcome-selected Home06 is the first distinct infrastructure category. No valid task failure occurred. Rejected first handback is the sole distinct unexpected valid category, represented by Home01 and inventoried across all five valid Home episodes.',
            'exclusions': 'No slot excluded from planned denominators. Home06 failed outputs and all not-run outcomes excluded from empirical outcome consumption; bounded infrastructure metadata diagnosed separately.',
            'source_freeze': 'Report edits are outside the frozen 974-source apparatus inventory; scored implementation and stopping rules unchanged.',
            'limitations': ['Two known simulated fixtures; no unseen-task, physical-transfer or deployment claim.',
                           'Model messages do not prove post-handback success; protected independent evaluation does.',
                           'Clean native exit is not complete scientific admission; Home06 remains invalid/unknown.']},
        evidence=[ref(label, path) for label, path in [
            ('Completed actual-results investigation', INV/'report.html'),
            ('All twenty dispositions and frozen Campaign 001 comparison', INV/'data.json'),
            ('Hash-bound report provenance', INV/'provenance.json'),
            ('Original immediate stop accounting', C/'execution/campaign-stop.json'),
            ('Outcome-selected Home06 infrastructure investigation', INV/'home06-investigation.md'),
            ('Bounded Home06 infrastructure inspection', HERE/'home06-diagnostic-001/inspection.json'),
            ('Authenticated valid behavior category inventory', HERE/'behavior-category-inventory.json'),
            ('Final artifact verification', HERE/'verification-003/verification.json'),
            ('Actual browser verification', HERE/'browser-001/receipt.json'),
            ('Terminal qualification history companion', INV/'session19-history-001/candidate-005/html/qualification-report.html')]])
    save(OUT/'note.json', note)
    before = run('status-before', 'status', '--json')
    run('append', 'append', 'note', '--input', str(OUT/'note.json'), '--expected-sha256', before['store_sha256'])
    new_notes = (MAP/'notes.jsonl').read_bytes()
    assert new_notes.startswith(old_notes)
    assert len(new_notes.splitlines()) == len(old_notes.splitlines()) + 1
    run('build', 'build')
    run('validate', 'validate', '--output', 'validation.json')
    lookup = run('lookup', 'lookup', '--kind', 'note', '--id', NOTE_ID, '--json')
    after = run('status-after', 'status', '--json')
    save(OUT/'receipt.json', dict(passed=True, note_id=NOTE_ID,
        previous_notes_sha256=hashlib.sha256(old_notes).hexdigest(),
        notes_sha256=hashlib.sha256(new_notes).hexdigest(), original_notes_prefix_preserved=True,
        appended_rows=1, store_before=before, store_after=after, lookup=lookup,
        evidence=[ref('Registered note input', OUT/'note.json'), ref('Map validation', MAP/'validation.json')]))
    print(json.dumps({'passed': True, 'note_id': NOTE_ID, 'runs_compared': len(all_runs)}))

if __name__ == '__main__':
    main()
