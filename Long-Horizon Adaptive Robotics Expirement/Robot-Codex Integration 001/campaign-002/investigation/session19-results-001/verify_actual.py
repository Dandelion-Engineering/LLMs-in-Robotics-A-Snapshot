"""Queued final artifact verification against terminal metadata and exact bytes."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
INVESTIGATION = HERE.parent
CAMPAIGN = INVESTIGATION.parent
REPO = INVESTIGATION.parents[3]
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'
TERMINAL = {'completed','failed','timed_out','aborted','not_run','cancelled','canceled'}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def binding(path):
    raw = path.read_bytes()
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def verify(directory):
    output = HERE / directory
    assert output.parent == HERE and not output.exists()
    plan = load(CAMPAIGN / 'execution-plan.json')
    stop = load(CAMPAIGN / 'execution/campaign-stop.json')
    assert stop['planned'] == 20 and stop['remaining_admission_authorized'] is False
    assert len(plan['attempts']) == 20
    dispositions, receipts, forbidden_roots = [], {}, []
    for attempt in plan['attempts']:
        folder = CAMPAIGN / 'execution' / attempt['run_id']
        disposition = load(folder / 'disposition.json')
        assert all(disposition[k] == attempt[k] for k in ('ordinal','run_id','family'))
        assert disposition['execution_status'] in TERMINAL
        dispositions.append(disposition)
        if disposition['execution_status'] == 'not_run':
            assert not (folder / 'queue-submit.json').exists()
            forbidden_roots.extend([Path(attempt['evidence']),Path(attempt['host_evidence']),folder/'assessment.json'])
            continue
        submitted = load(folder / 'queue-submit.json')
        job_id = submitted.get('job',submitted)['id']
        result = subprocess.run([sys.executable,'-X','utf8','-B',str(QUEUE),'status',job_id],
                                cwd=REPO,capture_output=True,text=True,encoding='utf-8',check=True)
        receipt = json.loads(result.stdout)
        job = receipt.get('job',receipt)
        assert job['id'] == job_id and job['state'] in {'succeeded','failed','cancelled','canceled'}
        receipts[job_id] = receipt
        if job['state'] != 'succeeded' or type(job['exit_status']) is not int or job['exit_status'] != 0:
            assert disposition['scorable'] is False
            forbidden_roots.extend([Path(attempt['evidence']),Path(attempt['host_evidence']),folder/'assessment.json'])
    # All twenty actual terminal identities and official job states precede report reads.
    data = load(INVESTIGATION / 'data.json')
    provenance = load(INVESTIGATION / 'provenance.json')
    qa = load(INVESTIGATION / 'qa.json')
    assert data['complete'] is True and len(data['runs']) == 20
    assert [r['run_id'] for r in data['runs']] == [r['run_id'] for r in dispositions]
    assert binding(INVESTIGATION / 'report.html')['sha256'] == provenance['report_sha256'] == qa['report_sha256']
    assert all(value is True for value in qa['checks'].values())
    source_bindings = [provenance['builder'],provenance['template']]
    for item in provenance['inputs'] + source_bindings:
        path = Path(item['path']).resolve()
        assert not any(path == forbidden.resolve() or path.is_relative_to(forbidden.resolve())
                       for forbidden in forbidden_roots), 'Failed or unrun outcome consumed: ' + str(path)
        actual = binding(path)
        assert actual['sha256'] == item['sha256'], 'Input hash changed: ' + str(path)
        if 'bytes' in item:
            assert actual['bytes'] == item['bytes']
    for family in ('misplaced-stock','blocked-insert-home','all scheduled slots'):
        rows = dispositions if family == 'all scheduled slots' else [r for r in dispositions if r['family'] == family]
        expected = {'planned':len(rows),'valid':sum(r.get('scorable') is True for r in rows),
            'successes':sum(r.get('scorable') is True and r['task_outcome'] == 'success' for r in rows),
            'failures':sum(r.get('scorable') is True and r['task_outcome'] == 'failure' for r in rows),
            'invalid':sum(r['validity'] == 'invalid' for r in rows),
            'not_run':sum(r['execution_status'] == 'not_run' for r in rows)}
        assert all(data['counts'][family][key] == value for key,value in expected.items()), family
    previous = data['previous']['counts']['all scheduled slots']
    assert tuple(previous[k] for k in ('planned','valid','successes','invalid','not_run')) == (24,6,6,4,14)
    output.mkdir()
    result = {'schema':'campaign002-final-artifact-verification-1',
        'verified_at':datetime.now(timezone.utc).isoformat(),'passed':True,
        'counts':data['counts'],'queue_states':dict(Counter(r.get('job',r)['state'] for r in receipts.values())),
        'official_jobs':receipts,'input_entries_verified':len(provenance['inputs']),
        'original_dispositions':[binding(CAMPAIGN/'execution'/r['run_id']/'disposition.json') for r in dispositions],
        'report_files':{name:binding(INVESTIGATION/name) for name in ('report.html','data.json','provenance.json','qa.json')},
        'episode_explanations':[binding(p) for p in sorted(INVESTIGATION.glob('*-investigation.md'))],
        'failed_or_unrun_outcomes_consumed':False,'campaign001_reclassified':False,
        'scope':'Artifact, count and provenance verification; browser controls and learning quality require the separate visible-interface pass.'}
    (output / 'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'counts':data['counts'],'output':str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True)
    args = parser.parse_args()
    verify(args.directory)
