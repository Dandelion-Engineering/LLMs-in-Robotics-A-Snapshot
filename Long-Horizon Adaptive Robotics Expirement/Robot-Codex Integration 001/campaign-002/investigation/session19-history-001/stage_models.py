"""Stage completed final-model qualification rows with original pilot contracts.

Every official job must succeed before any assessment or output is opened.
No qualification verdict is recomputed and canonical history is never written.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import stage_rows as base

HERE = Path(__file__).resolve().parent


def bindings():
    return {str(p.resolve()): base.digest(p) for p in [Path(__file__), HERE/'stage_rows.py',
        base.I/'qualification_report.py', base.I/'qualification_qa.py']}


def row_for(short, rev, kind, ledger, job):
    row = base.row_for(short, rev, kind, ledger, job)
    if kind != 'pilot':
        return row
    disposition = row.pop('admission_disposition')
    d = base.read(disposition['path'])
    entry = d['entry']
    a = base.read(entry['assessment']['path'])
    assert d['passed'] is True
    assert a['checks']['actual_model_started'] is True
    assert a['checks']['one_uninterrupted_orchestrated_invocation'] is True
    row['model_calls'] = 1
    artifacts = {x['path']: x for x in row['artifacts']}

    def add(path, label, expected=None, expected_bytes=None):
        item = base.artifact(path, label)
        if expected is not None:
            assert item['sha256'] == expected
        if expected_bytes is not None:
            assert item['bytes'] == expected_bytes
        old = artifacts.get(item['path'])
        if old is not None:
            assert old['sha256'] == item['sha256'] and old['bytes'] == item['bytes']
            return old
        artifacts[item['path']] = item
        return item

    row['pilot_admission'] = {
        'schema': 'campaign002-pilot-history-binding-1',
        'disposition': add(disposition['path'], 'Original pilot admission disposition', disposition['sha256']),
        'verifier': add(base.C/'admission.py', 'Original pilot admission verifier'),
        'base_assessor': add(base.C/'assessment/assess.py', 'Original frozen pilot base assessor', a['bindings']['assessment_sha256']),
        'preflight': add(base.Q/('final-qualification-'+ledger)/'preflight.json', 'Original coordinator preflight')
    }
    snapshot = Path(entry['snapshot']['path'])
    add(snapshot.with_name('code.zip'), 'Original frozen source archive', a['bindings']['framework_archive_sha256'])
    roots = {'orchestrator': Path(entry['evidence']), 'protected_host': Path(entry['host_evidence'])}
    for item in a['evidence_inventory']:
        root = roots[item['root']].resolve()
        path = (root/item['path']).resolve()
        assert path.is_relative_to(root)
        add(path, 'Original assessed pilot input: '+item['root']+'/'+item['path'], item['sha256'], item['bytes'])
    row['artifacts'] = list(artifacts.values())
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['submit', 'run'])
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    plan = args.plan.resolve()
    value = base.read(plan)
    assert value['schema'] == 'campaign002-explicit-terminal-history-selection-1'
    out = HERE/value['directory']
    assert out.parent == HERE and not out.exists()
    assert base.digest(base.HISTORY) == value['history_sha256']
    intent = HERE/(value['directory']+'-intent.json')
    if args.action == 'submit':
        base.save(intent, {'plan_sha256': base.digest(plan), 'sources': bindings(), 'created_at': datetime.now(timezone.utc).isoformat()})
        cmd = [sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()), 'run', '--plan', str(plan)]
        job = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(base.QUEUE), 'submit',
            '--project', 'LLMs-in-Robotics', '--cwd', str(base.REPO), '--', *cmd], text=True, encoding='utf-8'))
        base.save(HERE/(value['directory']+'-submit.json'), job)
        print(json.dumps({'job_id': job['id'], 'state': job['state']}))
        return
    bound = base.read(intent)
    assert bound['sources'] == bindings() and bound['plan_sha256'] == base.digest(plan)
    jobs = {}
    for short, rev, kind, ledger in value['allocations']:
        assert kind in ['smoke', 'pilot']
        stored = base.read(base.metadata_paths(short, kind)[0])
        fresh = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(base.QUEUE), 'status', stored['id']], text=True, encoding='utf-8'))
        assert all(stored.get(k) == fresh.get(k) for k in ['id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd'])
        assert fresh['state'] == 'succeeded' and type(fresh['exit_status']) is int and fresh['exit_status'] == 0
        jobs[short] = fresh
    out.mkdir()
    base.save(out/'fresh-official.json', {'checked_at': datetime.now(timezone.utc).isoformat(), 'jobs': jobs})
    report = base.load('final_model_history_report', base.I/'qualification_report.py')
    rows = []
    for short, rev, kind, ledger in value['allocations']:
        row = row_for(short, rev, kind, ledger, jobs[short])
        display = report.qualification_row(row, base.I)
        assert display['status'] == row['status'] and display['task_outcome'] == 'unknown' and display['scorable'] is False
        if kind == 'pilot':
            assert display['pilot_admission']['admission_passed'] is True
            assert display['model_calls'] == 1
        base.save(out/(short+'.json'), row)
        rows.append(row)
    assert base.digest(base.HISTORY) == value['history_sha256'] and bindings() == bound['sources']
    base.save(out/'rows.json', rows)
    base.save(out/'verification.json', {'passed': True, 'rows': len(rows), 'run_ids': [r['run_id'] for r in rows],
        'sources': bound['sources'], 'history_unchanged': True, 'canonical_history_written': False,
        'active_outputs_read': False, 'outcomes_recomputed': False, 'reader_inputs': report.READS})
    print(json.dumps({'passed': True, 'rows': len(rows)}))


if __name__ == '__main__':
    main()
