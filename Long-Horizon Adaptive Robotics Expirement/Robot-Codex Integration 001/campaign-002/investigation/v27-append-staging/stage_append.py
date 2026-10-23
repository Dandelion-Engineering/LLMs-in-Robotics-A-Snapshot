"""Stage an explicitly selected V27 history append; never publish or rebuild.

The caller supplies a hash-bound plan only after root authorizes the particular
settled rows. Row drafts use the existing history schema; original report/QA
readers validate them after fresh queue authentication. No verdict is inferred
from queue exit alone. Import and --help do not read any evidence.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

STAGE = Path(__file__).resolve().parent
I = STAGE.parent
C = I.parent
Q = C / 'qualification'
IO = C / 'io-repair'
REPO = C.parents[2]
HISTORY = I / 'qualification-history.json'
BASELINE = STAGE / 'baseline-row-spans.json'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
PYTHON = REPO / 'venv/Scripts/python.exe'
LEDGER = Q / 'final-qualification-027'
PLAN_SCHEMA = 'campaign002-v27-history-staging-plan-1'
BASELINE_SHA = 'dd4dc9414c705c20d102544ebee6a1093f3bb1b390e6b3346124d287d9319576'
ALLOCATIONS = (
    ('raw-preflight-017', '083', 'raw_event_preflight_diagnostic'),
    ('transport-probe-020', '083', 'transport_probe_diagnostic'),
    ('host-probe-027', '083', 'host_prerequisite_diagnostic'),
    ('native-026', '084', 'native'),
    ('boundary-027', '085', 'boundary'),
    ('smoke-025', '086', 'smoke'),
    ('pilot-stock-024', '086', 'stock'),
    ('pilot-home-024', '086', 'home'),
)
METHODS = ('EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md', 'CANARY_READBACK_EXCLUSIVITY_V1.md',
           'PREPARED_INDEX_LABELS_V1.md')
ACTIVE = {'queued', 'running', 'cancel_requested'}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_bytes())


def bind(path):
    path = Path(path).resolve()
    require(path.is_file() and not path.is_symlink(), 'Missing or linked input: ' + str(path))
    raw = path.read_bytes()
    return {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}


def save(path, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    with Path(path).open('xb') as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    return bind(path)


def raw_rows(raw):
    text = raw.decode('utf-8')
    marker = '"attempts": ['
    require(text.count(marker) == 1, 'Ambiguous attempts array')
    pos, result, decoder = text.index(marker) + len(marker), [], json.JSONDecoder()
    while True:
        while text[pos].isspace() or text[pos] == ',':
            pos += 1
        if text[pos] == ']':
            return text, result, pos
        value, end = decoder.raw_decode(text, pos)
        result.append((value['run_id'], text[pos:end].encode('utf-8'), pos, end))
        pos = end


def row_spans(spans):
    return [{'run_id': run, 'sha256': sha(raw), 'bytes': len(raw)} for run, raw, *_ in spans]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def authenticate(row, folder, cache):
    """Read live official metadata before opening any corresponding outputs."""
    if row.get('status') == 'not_run':
        require(row.get('preflight_contract') is not None, 'Unlaunched row needs its existing contract')
        return None
    job_id = row.get('queue', {}).get('id')
    require(isinstance(job_id, str) and re.fullmatch(r'[0-9]{8}T[0-9]+Z-[0-9a-f]+', job_id),
            'Explicit official job identity required')
    if job_id not in cache:
        argv = [str(PYTHON), '-X', 'utf8', '-B', str(QUEUE), 'status', job_id]
        started = now()
        result = subprocess.run(argv, cwd=REPO, capture_output=True, text=True, encoding='utf-8',
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        proof = {'schema': 'campaign002-history-fresh-official-1', 'command': argv,
                 'started_at': started, 'ended_at': now(), 'exit_code': result.returncode,
                 'stdout': result.stdout, 'stderr': result.stderr}
        if result.returncode == 0:
            value = json.loads(result.stdout)
            proof['official'] = value.get('job', value)
        save(folder / (job_id + '.json'), proof)
        require(result.returncode == 0, 'Official status query failed; no outcome access')
        cache[job_id] = proof['official']
    job = cache[job_id]
    require(job.get('id') == job_id and job.get('state') not in ACTIVE,
            'Wrong or active official job; outputs remain unread')
    if 'queue_failure_contract' in row:
        require(job.get('state') == 'failed' and type(job.get('exit_status')) is int
                and job['exit_status'] != 0, 'Failed row requires exact failed integer exit')
    elif row.get('status') == 'cancelled':
        require(job.get('state') in ('canceled', 'cancelled') and job.get('started_at') is None,
                'Only authenticated cancellation before start is supported')
    else:
        require(job.get('state') == 'succeeded' and type(job.get('exit_status')) is int
                and job['exit_status'] == 0, 'Succeeded and genuine integer exit0 required before outputs')
    require(all(job.get(k) == v for k, v in row.get('queue', {}).items()),
            'History draft differs from fresh official queue metadata')
    return job


def guarded_reader(report, successful):
    """Deny all V27 raw/assessment reads without a successful fresh job gate."""
    consume = report.consume
    def guarded(path, *args, **kwargs):
        path = Path(path).resolve()
        for short, _, _ in ALLOCATIONS:
            run = 'RCI001-C02-' + short
            if run in successful:
                continue
            roots = [C.parent / 'local-evidence/campaign002/qualification' / run,
                     IO / short / 'evidence']
            forbidden = [Q / (short + '-assessment.json')]
            require(path not in [p.resolve() for p in forbidden]
                    and not any(path.is_relative_to(p.resolve()) for p in roots),
                    'Active, unselected, or failed raw outcome access is forbidden: ' + str(path))
        return consume(path, *args, **kwargs)
    report.consume = guarded


def stage(plan_path, plan_sha256, batch):
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', batch) is not None, 'Safe exclusive batch name required')
    require(re.fullmatch(r'[0-9a-f]{64}', plan_sha256) is not None, 'Caller-held plan SHA256 required')
    plan_raw = Path(plan_path).read_bytes()
    require(sha(plan_raw) == plan_sha256, 'Append plan changed')
    plan = json.loads(plan_raw)
    correction = plan.get('staging_correction')
    if correction is not None:
        require(isinstance(correction, dict) and bind(correction['path']) == correction
                and Path(correction['path']).resolve().is_relative_to(STAGE.resolve()),
                'Staging correction must bind an unchanged local receipt')
    require(plan.get('schema') == PLAN_SCHEMA and plan.get('coordinator') == 'run_final_qualification_v27.py'
            and plan.get('ledger') == 'final-qualification-027', 'Wrong source/lineage staging plan')
    original = HISTORY.read_bytes()
    require(sha(original) == plan.get('expected_history_sha256'), 'History changed; no stale append')
    history = json.loads(original)
    text, spans, _ = raw_rows(original)
    baseline = read(BASELINE)
    require(baseline['history']['sha256'] == BASELINE_SHA and len(baseline['rows']) == 108
            and row_spans(spans[:108]) == baseline['rows'], 'Original108 raw row spans changed')
    require(len(spans) == plan.get('expected_rows_before'), 'Wrong current row count')
    exports = baseline['exports']
    require(len(exports) == 19, 'Nineteen original exports required')
    rows = plan.get('rows')
    require(isinstance(rows, list) and rows, 'Explicit settled row drafts required')
    allocated = {'RCI001-C02-' + short: (revision, kind, n)
                 for n, (short, revision, kind) in enumerate(ALLOCATIONS)}
    ids = [row.get('run_id') for row in rows]
    require(len(set(ids)) == len(ids) and all(run in allocated for run in ids)
            and not set(ids) & {run for run, *_ in spans}, 'Wrong or already indexed allocation')
    require([allocated[run][2] for run in ids] == sorted(allocated[run][2] for run in ids),
            'Rows must follow declared order')
    for row in rows:
        revision, kind, _ = allocated[row['run_id']]
        require(row.get('revision') == 'RCI001-C02-dev-' + revision
                and row.get('scorable') is False and row.get('task_outcome') == 'unknown',
                'Revision or non-scored evidence scope differs')
        if 'queue_failure_contract' not in row:
            if kind.endswith('_diagnostic'):
                require(row.get('attempt_kind') == kind, 'Prerequisite classification differs')
            else:
                if kind in ('stock', 'home'):
                    require(row.get('pilot_admission', {}).get('schema') ==
                            'campaign002-pilot-history-binding-1' and 'admission_disposition' not in row,
                            'Pilot must retain the existing pilot-specific admission binding')
                    item = row['pilot_admission'].get('disposition', {})
                else:
                    item = row.get('admission_disposition', {})
                expected = LEDGER / row['run_id'].removeprefix('RCI001-C02-') / 'disposition.json'
                require(Path(item.get('path', '')).resolve() == expected.resolve(),
                        'Original V27 admission disposition required')
    status = plan.get('current_status')
    require(isinstance(status, dict) and status.get('state') in
            ('qualification_in_progress', 'qualification_failed_blocked'),
            'This staging helper does not declare scored admission or campaign completion')
    output = STAGE / batch
    output.mkdir()  # Existing or ambiguous batch is never retried.
    auth_dir = output / 'official'
    auth_dir.mkdir()
    with (output / 'prior-history.json').open('xb') as file:
        file.write(original)
    save(output / 'intent.json', {'schema': 'campaign002-history-staging-intent-1', 'at': now(),
         'plan': bind(plan_path), 'prior_history': bind(HISTORY), 'append_only': ids,
         'source': bind(Path(__file__)), 'canonical_write_supported': False})
    jobs = {}
    # Authenticate all indexed jobs before report readers hash any attempt outputs.
    for row in [*history['attempts'], *rows]:
        authenticate(row, auth_dir, jobs)
    require([bind(v['path']) for v in exports] == exports, 'Original export binding changed')
    report = module('v27_history_report', I / 'qualification_report.py')
    qa = module('v27_history_qa', I / 'qualification_qa.py')
    successful = {row['run_id'] for row in [*history['attempts'], *rows]
                  if (row.get('queue') or {}).get('id') in jobs
                  and jobs[row['queue']['id']].get('state') == 'succeeded'
                  and type(jobs[row['queue']['id']].get('exit_status')) is int
                  and jobs[row['queue']['id']]['exit_status'] == 0}
    guarded_reader(report, successful)
    for row in [*history['attempts'], *rows]:
        if row.get('status') == 'not_run':
            continue
        receipts = [a for a in row['artifacts'] if a.get('label') == 'Official queue receipt']
        require(len(receipts) == 1, 'Exactly one retained official receipt required')
        stored = report.bound(receipts[0], 'fresh/retained official correspondence before outputs')
        stored = stored.get('job', stored)
        fresh = jobs[row['queue']['id']]
        require(all(stored.get(key) == fresh.get(key) for key in
                    ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd')),
                'Stored receipt differs from freshly authenticated job')
    for row in rows:
        snapshots = [a for a in row['artifacts'] if Path(a['path']).name == 'snapshot.json']
        require(len(snapshots) == 1, 'Exactly one frozen stage snapshot required')
        snapshot = report.bound(snapshots[0], 'source snapshot after fresh queue gate')
        require(snapshot.get('revision') == row['revision'], 'Stage snapshot revision differs')
        for name in METHODS:
            path = IO / name
            item = bind(path)
            require(snapshot.get('sources', {}).get(path.relative_to(REPO).as_posix()) ==
                    {k: item[k] for k in ('sha256', 'bytes')}, 'Frozen new method binding differs')
    rendered = [report.qualification_row(row, I) for row in [*history['attempts'], *rows]]
    for row in rendered:
        if row.get('diagnostic_result') is not None:
            qa.no_model_diagnostic_guard(row, I)
        elif row.get('host_prerequisite') is not None:
            qa.host_prerequisite_guard(row, I)
        elif row.get('queue_failure') is not None:
            qa.failed_queue_guard(row, I)
    updated = now()
    insertion = ',\n' + ',\n'.join('    ' + json.dumps(row, indent=2, ensure_ascii=False)
                                    .replace('\n', '\n    ') for row in rows)
    candidate = text[:spans[-1][3]] + insertion + text[spans[-1][3]:]
    previous_time = '"updated_at": ' + json.dumps(history['updated_at'], ensure_ascii=False)
    require(candidate.count(previous_time) == 1, 'Ambiguous updated_at')
    candidate = candidate.replace(previous_time, '"updated_at": ' + json.dumps(updated), 1)
    marker = '"current_status": '
    require(candidate.count(marker) == 1, 'Ambiguous current_status')
    start = candidate.index(marker) + len(marker)
    _, end = json.JSONDecoder().raw_decode(candidate, start)
    candidate = (candidate[:start] + json.dumps(status, indent=2, ensure_ascii=False)
                 .replace('\n', '\n  ') + candidate[end:]).encode('utf-8')
    parsed = json.loads(candidate)
    _, new_spans, _ = raw_rows(candidate)
    require(len(new_spans) == len(spans) + len(rows) and row_spans(new_spans[:len(spans)]) == row_spans(spans)
            and parsed['attempts'][:len(spans)] == history['attempts'], 'Existing row changed')
    inventory = report.launch_inventory(C, I)  # Metadata only; never discovers model-stage output.
    require(inventory['entries'] == [] and inventory['registration'] is None,
            'This pre-admission helper requires zero scored launches')
    current = report.current_status_detail(status, rendered, parsed, inventory, C, I)
    require(current['basis_run_id'] == report.latest_completed_qualifier(rendered)['run_id'],
            'Current basis must follow the existing prerequisite-exclusion rule')
    require(all(row['scorable'] is False for row in rendered), 'History qualifier became scored')
    require(HISTORY.read_bytes() == original and [bind(v['path']) for v in exports] == exports,
            'Concurrent history/export mutation; candidate not emitted')
    with (output / 'candidate-history.json').open('xb') as file:
        file.write(candidate)
    latest_models = [row for row in rendered if re.fullmatch(r'RCI001-C02-(?:smoke|pilot-(?:stock|home))-\d+', row['run_id'])]
    latest_model = max(latest_models, key=lambda row: row.get('ended_at') or '')['run_id']
    qa_binding = save(output / 'qa.json', {'schema': 'campaign002-history-current-status-qa-1',
        'passed': True, 'at': now(), 'rows_before': len(spans), 'rows_after': len(new_spans),
        'current_qualification_basis': current['basis_run_id'], 'latest_model_qualifier': latest_model,
        'prior_raw_rows_preserved': len(spans), 'new_rows_verified': ids,
        'staging_correction': correction,
        'preserved_exports': exports, 'authenticated_reader_inputs': report.READS,
        'source_helpers': [bind(I / 'qualification_report.py'), bind(I / 'qualification_qa.py')],
        'active_outputs_read': False, 'outcomes_recomputed': False, 'exports_rebuilt': False})
    receipt = save(output / 'staged-receipt.json', {'schema': 'campaign002-history-staged-append-receipt-1',
        'at': now(), 'prior_history': bind(HISTORY), 'candidate_history': bind(output / 'candidate-history.json'),
        'rows_before': len(spans), 'rows_after': len(new_spans), 'qa': qa_binding,
        'staging_correction': correction,
        'appended': row_spans(new_spans[len(spans):]), 'exports_before_and_after': exports,
        'official_authentication': [bind(p) for p in sorted(auth_dir.glob('*.json'))],
        'canonical_history_written': False, 'accounting_mutated': False, 'map_mutated': False})
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--batch', required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.plan, args.plan_sha256, args.batch), indent=2))


if __name__ == '__main__':
    main()
