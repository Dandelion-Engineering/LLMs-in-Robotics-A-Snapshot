"""Inspect only the two completed, prospectively selected first-family episodes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
INVESTIGATION = HERE.parent
CAMPAIGN = INVESTIGATION.parent
REPO = INVESTIGATION.parents[3]
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / 'first-episodes-001'
    output.mkdir(exist_ok=False)
    preparation = load(HERE / 'preparation-check-001/verification.json')
    assert preparation['passed'] is True
    assert sha(INVESTIGATION / 'build.py') == preparation['source_hashes']['build.py']
    spec = importlib.util.spec_from_file_location('first_episodes_report', INVESTIGATION / 'build.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    plan = load(CAMPAIGN / 'execution-plan.json')
    report.validate_plan(plan)
    targets = {'RCI001-C02-stock-01':'20260930T213946660895Z-49a816ac',
               'RCI001-C02-home-01':'20260930T214446477570Z-e5c34e42'}
    episodes = []
    for attempt in plan['attempts']:
        rid = attempt['run_id']
        if rid not in targets:
            continue
        result = subprocess.run([sys.executable,'-X','utf8','-B',str(QUEUE),'status',targets[rid]],
                                cwd=REPO,capture_output=True,text=True,encoding='utf-8',check=True)
        receipt = json.loads(result.stdout)
        job = receipt.get('job', receipt)
        assert job['id'] == targets[rid] and job['state'] == 'succeeded'
        assert type(job['exit_status']) is int and job['exit_status'] == 0
        (output / (rid + '-official-status.json')).write_text(result.stdout,encoding='utf-8')
        row = report.run_record(attempt, CAMPAIGN / 'execution', INVESTIGATION)
        assert row['assessment_available'] is True
        # Displayed tool choices and messages are public behavior. The existing
        # extractor excludes reasoning items and never reconstructs deliberation.
        observation_events = [e for e in row['events'] if e['kind'] == 'observation']
        row['events'] = [e for e in row['events'] if e['kind'] != 'observation']
        row['first_and_last_retained_observation'] = ([observation_events[0],observation_events[-1]]
                                                    if observation_events else [])
        episodes.append(row)
    result = {'schema':'campaign002-first-preselected-inspection-1',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'scope':'Two completed first-family episodes, selected before outcomes. Not a campaign result or replacement of its all-twenty terminal gate.',
        'episodes':episodes,'inputs':report.READS,
        'model_reasoning_items_included':False,'builder_sha256':sha(INVESTIGATION / 'build.py')}
    (output / 'inspection.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'episodes':[{'run_id':r['run_id'],'validity':r['validity'],
        'task_outcome':r['task_outcome'],'warnings':r['warnings']} for r in episodes],
        'inspection_sha256':sha(output / 'inspection.json')}))


if __name__ == '__main__':
    main()
