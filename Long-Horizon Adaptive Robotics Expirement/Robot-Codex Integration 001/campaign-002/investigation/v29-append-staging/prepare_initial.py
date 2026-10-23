"""Prepare four settled S15 history rows; no active output access or publication."""
import copy
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
I = HERE.parent
C = I.parent
IO, Q = C / 'io-repair', C / 'qualification'
REPO = C.parents[2]
MAP = C.parent.parent / 'Architecture Map'
HISTORY = I / 'qualification-history.json'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
BEFORE = 'bb442fab8fbd4a37c7ea52f15213863da173c96f1a090fafe9d2b010139c35c5'
JOBS = {
    'shutdown-diagnostic-004': '20260929T172359627310Z-e9b8409e',
    'raw-preflight-019': '20260929T180901881580Z-befd36e6',
    'transport-probe-022': '20260929T181003826677Z-2b6d8f32',
    'host-probe-029': '20260929T181006445630Z-874799a7',
}


def bind(path, label=None):
    path = Path(path).resolve()
    raw = path.read_bytes()
    value = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return dict(value, label=label) if label else value


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def main():
    out = HERE / 'initial-drafts'
    out.mkdir()
    assert bind(HISTORY)['sha256'] == BEFORE
    history = json.loads(HISTORY.read_bytes())
    assert len(history['attempts']) == 122
    jobs = {}
    for short, job in JOBS.items():
        argv = [sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'status', job]
        result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8')
        save(out / (short + '-official-gate.json'), {'argv': argv, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        assert result.returncode == 0
        value = json.loads(result.stdout)
        assert value['id'] == job and value['state'] == 'succeeded' and type(value['exit_status']) is int and value['exit_status'] == 0
        jobs[short] = value
    def queue(short):
        return {k: jobs[short][k] for k in ('id', 'state', 'exit_status', 'started_at', 'ended_at')}
    def art(path, label):
        return bind(path, label)
    native = IO / 'shutdown-diagnostic-004'
    artifacts = [art(native / 'records/official-status.json', 'Official queue receipt'),
        art(native / 'manifest.json', 'Frozen attempt manifest'),
        art(MAP / 'releases/RCI001-C02-dev-092/snapshot.json', 'Frozen source snapshot')]
    row = {'run_id': 'RCI001-C02-shutdown-diagnostic-004', 'revision': 'RCI001-C02-dev-092',
        'status': 'completed', 'reason': 'The single declared ordered shutdown diagnostic completed. It is not assessed as qualification: the original socket abort was not reproduced, so the proposed error-versus-stdin-close question remains inconclusive. Separate bounded findings retain the interruption, genuine EOF and retirement observations. No scored outcome is inferred.',
        'scorable': False, 'validity': 'unknown', 'assessment_state': 'not_assessed',
        'task_outcome': 'unknown', 'model_calls': None, 'queue': queue('shutdown-diagnostic-004'),
        'details': {}, 'artifacts': artifacts,
        'queue_completion_contract': {'schema': 'campaign002-completed-unassessed-interrupt-queue-1',
            **{key: item['sha256'] for key, item in zip(
                ('official_queue_sha256', 'manifest_sha256', 'snapshot_sha256'), artifacts)}}}
    rows = [row]
    for old, new in [('raw-preflight-018', 'raw-preflight-019'), ('transport-probe-021', 'transport-probe-022'), ('host-probe-028', 'host-probe-029')]:
        row = copy.deepcopy(next(r for r in history['attempts'] if r['run_id'] == 'RCI001-C02-' + old))
        def renamed(text):
            return (text.replace(old, new).replace('dev-087', 'dev-093').replace('checks-031', 'checks-037')
                .replace('checks031', 'checks037').replace('V28 full frozen source comparison', 'V29 full frozen source comparison')
                .replace('v28-source-change-inventory-001.json', 'native-pre-exit-drain-001/source-change-inventory-001.json'))
        artifacts = [art(renamed(a['path']), renamed(a['label'])) for a in row['artifacts']]
        substitutions = {old_a['sha256']: new_a['sha256'] for old_a, new_a in zip(row['artifacts'], artifacts)}
        def rewrite(value):
            if isinstance(value, str): return substitutions.get(value, renamed(value))
            if isinstance(value, list): return [rewrite(v) for v in value]
            if isinstance(value, dict): return {k: rewrite(v) for k, v in value.items()}
            return value
        row = rewrite(row)
        row.update(run_id='RCI001-C02-' + new, revision='RCI001-C02-dev-093', queue=queue(new), artifacts=artifacts, diagnostic_analyses=[])
        artifacts.append(art(IO / 'NATIVE_PRE_EXIT_DRAIN_V1.md', 'Frozen pre-exit native transport drain method'))
        row['details']['pre_exit_drain_method_source_bound'] = True
        if 'diagnostic_contract' in row:
            by_path = {a['path']: a for a in artifacts}
            for key in ('result', 'verified_readiness_entry'):
                row['diagnostic_contract'][key] = by_path[row['diagnostic_contract'][key]['path']]
            value = json.loads(Path(row['diagnostic_contract']['result']['path']).read_bytes())
            assert value['passed'] is True and not value['errors'] and all(v is True for v in value['checks'].values())
            row['details']['checks'] = value['checks']
        row['reason'] = (new + ' passed its independently replayed prerequisite checks on frozen dev093 after the native pre-exit drain repair. '
            'This prerequisite does not qualify model cleanup or robot task performance; full fresh final qualification is still required.')
        rows.append(row)
    status = {k: history['current_status'][k] for k in ('schema', 'basis_run_id', 'basis_assessment_sha256', 'basis_queue_sha256', 'basis_kind')}
    status.update(state='qualification_in_progress', as_of=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        summary='Native004 completed as an unassessed diagnostic. Fresh Raw019, Transport022 and Host029 passed their prerequisite checks. V29 final qualification is in progress; zero scored attempts are admitted.',
        engineering_context='Original rows and nineteen exported artifacts remain unchanged. The completed diagnostic is excluded from the latest-qualifier rule. All final gates must independently pass before campaign admission.',
        artifacts=[art(IO / 'native004-diagnosis-001/FINDINGS.md', 'Bounded Native004 findings; no qualification verdict'),
                   art(IO / 'native004-diagnosis-001/observations.json', 'Bounded Native004 observations; no qualification verdict'),
                   art(IO / 'shutdown-diagnostic-004/records/diagnostic-completion.json', 'Original Native004 unassessed completion'),
                   art(Q / 'final-qualification-029-readiness.json', 'Fresh V29 prerequisite readiness')],
        active_lineage={'framework_revision': 'RCI001-C02-dev-093', 'state': 'qualification_in_progress',
            'latest_model_qualifier': 'RCI001-C02-smoke-026', 'latest_diagnostic': 'RCI001-C02-shutdown-diagnostic-004',
            'completed_prerequisites': ['RCI001-C02-' + name for name in JOBS if name != 'shutdown-diagnostic-004'],
            'final_qualification_completed': False, 'scientific_admission': False, 'scored_attempts_started': 0})
    plan = {'schema': 'campaign002-session15-history-staging-plan-1', 'coordinator': 'run_final_qualification_v29.py',
        'ledger': 'final-qualification-029', 'expected_history_sha256': BEFORE, 'expected_rows_before': 122,
        'rows': rows, 'current_status': status}
    save(out / 'plan.json', plan)
    print(json.dumps({'plan': bind(out / 'plan.json'), 'rows': [r['run_id'] for r in rows]}))


if __name__ == '__main__':
    main()
