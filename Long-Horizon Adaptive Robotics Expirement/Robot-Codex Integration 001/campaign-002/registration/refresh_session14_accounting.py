"""Metadata-led session accounting. No queue submission or scientific reassessment.

Default invocation inventories receipt identities only. --refresh additionally
authenticates every job, consumes only succeeded/integer-zero outputs, retains
the previous bytes, and replaces the accounting after all validation succeeds.
"""
from __future__ import annotations
import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parents[2]
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'
JOB_ID = re.compile(r'\d{8}T\d{12}Z-[a-z0-9]{8}')
IMMUTABLE_QUEUE_FIELDS = ('id', 'argv', 'cwd', 'resolved_executable', 'submitted_at', 'submitting_project')
PRUNE = {'evidence', 'host', 'orchestrator', 'workspace', 'storage', '__pycache__', 'client'}


def require(value, message):
    if not value:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def identity(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'path': str(path), 'sha256': sha(data), 'bytes': len(data)}


def receipt_name(name):
    return (name in {'queue-submit.json', 'official-status.json', 'submit-receipt.json'}
            or name.endswith('-queue.json')
            or name.startswith('qualification-report-build-') and name.endswith('-submit.json'))


def queue_records(value):
    """Decode direct queue receipts and command_once's JSON stdout, never logs."""
    if not isinstance(value, dict):
        return []
    if JOB_ID.fullmatch(str(value.get('id', ''))) and isinstance(value.get('argv'), list):
        return [value]
    if type(value.get('exit_code')) is int and value['exit_code'] == 0 and isinstance(value.get('stdout'), str):
        try:
            return queue_records(json.loads(value['stdout']))
        except json.JSONDecodeError:
            return []
    return []


def discover(campaign, prior):
    """Version-independent ledgers; only named queue metadata is opened."""
    campaign = Path(campaign).resolve()
    jobs = {row['official_queue']['id']: {'receipts': [], 'prior': row}
            for row in prior['rows']}
    for part in ('qualification', 'io-repair', 'investigation', 'execution'):
        base = campaign / part
        if not base.exists():
            continue
        for folder, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in PRUNE and not d.startswith('.')
                             and not (Path(folder) / d).is_symlink()
                             and not (d.startswith('build-') and d.endswith(('-retained', '-inputs'))))
            for name in sorted(files):
                if not receipt_name(name):
                    continue
                path = Path(folder) / name
                require(not path.is_symlink(), 'Queue receipt is a symlink: ' + str(path))
                for record in queue_records(read(path)):
                    if record.get('submitting_project') != prior['inclusion_rule']['queue_project']:
                        continue
                    if stamp(record['submitted_at']) < stamp(prior['inclusion_rule']['submitted_not_before']):
                        continue
                    require(any(str(campaign).lower().replace('\\', '/') in str(arg).lower().replace('\\', '/')
                                for arg in record['argv']), 'In-scope receipt lacks campaign command path')
                    entry = jobs.setdefault(record['id'], {'receipts': [], 'prior': None})
                    if entry.get('submitted'):
                        require(all(entry['submitted'].get(k) == record.get(k) for k in IMMUTABLE_QUEUE_FIELDS),
                                'Conflicting immutable queue metadata: ' + record['id'])
                    entry['submitted'] = record
                    entry['receipts'].append(identity(path))
    return dict(sorted(jobs.items()))


def official_status(job_id, queue=QUEUE):
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(queue), 'status', job_id],
                            cwd=REPO, capture_output=True, text=True, encoding='utf-8', timeout=30)
    require(result.returncode == 0, 'Official status failed for ' + job_id)
    return json.loads(result.stdout)


def authenticate(job_id, discovered, provider):
    job = provider(job_id)
    require(job.get('id') == job_id, 'Official queue identity mismatch')
    submitted = discovered.get('submitted')
    if submitted:
        require(all(job.get(k) == submitted.get(k) for k in IMMUTABLE_QUEUE_FIELDS),
                'Official immutable queue metadata mismatch: ' + job_id)
    old = discovered.get('prior')
    if old and old.get('official_argv_sha256'):
        require(sha(canonical(job['argv'])) == old['official_argv_sha256'], 'Historical official argv changed')
    require(job.get('state') in {'queued', 'running', 'cancel_requested', 'succeeded', 'failed', 'canceled', 'cancelled'},
            'Unknown official queue state')
    return job


def succeeded(job):
    return job.get('state') == 'succeeded' and type(job.get('exit_status')) is int and job['exit_status'] == 0


def option(argv, name):
    indices = [i for i, arg in enumerate(argv) if arg == name]
    require(len(indices) <= 1, 'Duplicate command option ' + name)
    if not indices:
        return None
    require(indices[0] + 1 < len(argv), 'Missing command option value ' + name)
    return argv[indices[0] + 1]


def local_path(value, repo):
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = repo / path
    path = path.resolve()
    require(path.is_relative_to(repo.resolve()), 'Accounting input outside repository: ' + str(path))
    return path


def classify(job, entry, campaign, repo):
    argv = job['argv']
    script = next((arg for arg in argv if str(arg).endswith('.py')), '')
    name = Path(script).name
    manifest = local_path(option(argv, '--manifest'), repo)
    output = local_path(option(argv, '--evidence') or option(argv, '--output'), repo)
    run_id = option(argv, '--run-id')
    boundary_identity_from_output = False
    if not run_id and manifest is None and name in {'boundary_suite.py', 'boundary_suite_v3.py'} and output:
        expected_root = (campaign.parent / 'local-evidence/campaign002/qualification').resolve()
        # The boundary CLI deliberately takes only --output. Infer identity only
        # from its exact declared qualification root and an existing manifest;
        # inspect manifest contents only after fresh official success below.
        if output.parent == expected_root and re.fullmatch(r'RCI001-C02-boundary-\d{3}', output.name):
            candidate = campaign / 'qualification' / (output.name.removeprefix('RCI001-C02-') + '-manifest.json')
            if candidate.is_file():
                require(not candidate.is_symlink(), 'Boundary manifest is a symlink')
                run_id, manifest, boundary_identity_from_output = output.name, candidate, True
    if not run_id and manifest:
        stem = manifest.stem.removesuffix('-manifest')
        run_id = stem if stem.startswith('RCI001-C02-') else 'RCI001-C02-' + stem
        # Dispatch identity only. No failed manifest or empirical output is opened.
        diagnostic = manifest.parent.name
        wrapper = Path(script)
        if (name == 'run.py' and wrapper.parent.parent == campaign / 'io-repair'
                and re.fullmatch(r'single-interrupt-diagnostic(?:-v[23])?', wrapper.parent.name)
                and re.fullmatch(r'shutdown-diagnostic-\d{3}', diagnostic)
                and manifest == campaign / 'io-repair' / diagnostic / 'manifest.json'
                and output == campaign.parent / 'local-evidence/campaign002/io-repair' /
                    ('RCI001-C02-' + diagnostic) / 'orchestrator'):
            run_id = 'RCI001-C02-' + diagnostic
    if manifest is None and name in {'raw_event_preflight.py', 'raw_event_preflight_v2.py',
                                     'codehost_probe.py', 'codehost_transport_probe_v3.py'} and output:
        manifest = output.parent / 'manifest.json'
    if entry.get('prior'):
        run_id = entry['prior']['run_id']
    scored = any(Path(r['path']).is_relative_to(campaign / 'execution') for r in entry['receipts'])
    categories = {'raw_event_preflight.py': 'non_physics_raw_event_preflight',
                  'raw_event_preflight_v2.py': 'non_physics_raw_event_preflight',
                  'codehost_probe.py': 'non_physics_transport_diagnostic',
                  'codehost_transport_probe_v3.py': 'non_physics_transport_diagnostic',
                  'host_probe.py': 'non_model_idle_host', 'native_suite.py': 'non_model_native_reference',
                  'boundary_suite.py': 'non_model_boundary', 'boundary_suite_v3.py': 'non_model_boundary',
                  'benchmark.py': 'non_physics_durability_diagnostic',
                  'qualification_report.py': 'report_support', 'build.py': 'report_support',
                  'export_frames.py': 'report_support', 'qa.py': 'report_support'}
    category = categories.get(name, 'unclassified_queue_job')
    if name == 'physical.py':
        category = ('scored_model_slot' if scored else 'qualification_model_smoke'
                    if option(argv, '--mode') == 'smoke' else 'qualification_model_pilot')
    if entry.get('prior'):
        category = entry['prior']['category']
    return {'run_id': run_id or ('investigation' if category == 'report_support' else job['id']),
            'category': category, 'entry_point': script, 'manifest': manifest, 'output': output,
            'host_output': local_path(option(argv, '--host-evidence'), repo),
            'framework_revision': option(argv, '--framework-revision'), 'scored': scored,
            'boundary_identity_from_output': boundary_identity_from_output}


def invocation_receipts(root, bind):
    receipts = []
    if root is None or not root.exists():
        return receipts
    for path in sorted(root.rglob('client/result.json')):
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), 'Invocation outside evidence root')
        value = read(path)
        events = path.with_name('events.jsonl')
        require(events.is_file() and not events.is_symlink(), 'Invocation events absent')
        starts = []
        with events.open(encoding='utf-8') as stream:
            for line, text in enumerate(stream, 1):
                event = json.loads(text)
                if event.get('kind') == 'request' and event.get('method') == 'turn/start':
                    starts.append({'line': line, 'request_id': event.get('id')})
        started = value.get('model_started') is True
        require(started == bool(starts), 'Client result/start-request accounting disagreement')
        bind(path); bind(events)
        receipts.append({'phase': path.parent.parent.relative_to(root).as_posix(), 'model_started': started,
                         'turn_start_requests': len(starts), 'request_records': starts,
                         'client_result_ref': str(path), 'events_ref': str(events)})
    return receipts


def consume_success(job, info, campaign, bind):
    """Only caller with an authenticated successful job may enter this function."""
    require(succeeded(job), 'Empirical input blocked by official queue gate')
    result = {'empirical_results_consumed': False}
    manifest = info['manifest']
    if manifest and manifest.exists():
        data = read(manifest); bind(manifest)
        if info.get('boundary_identity_from_output'):
            require(data.get('run_id') == info['run_id'], 'Boundary manifest/output run identity mismatch')
        result['framework_revision'] = data.get('framework_revision', info['framework_revision'])
        result['run_id'] = data.get('run_id', info['run_id'])
    category, output = info['category'], info['output']
    if category in {'qualification_model_smoke', 'qualification_model_pilot', 'scored_model_slot'}:
        receipts = invocation_receipts(output, bind)
        result.update(model_invocation_receipts=receipts,
                      known_model_invocations_started=sum(x['turn_start_requests'] for x in receipts) if receipts else None,
                      model_count_basis='Protected turn/start requests plus client model_started, after fresh official success; not exact generations or billing.')
    run_id = result.get('run_id', info['run_id'])
    short = run_id.removeprefix('RCI001-C02-')
    paths = []
    if info['scored']:
        paths.append(campaign / 'execution' / run_id / 'assessment.json')
    elif category.startswith('non_physics_') and output:
        paths.append(campaign / 'io-repair' / (short + '-assessment.json')
                     if category == 'non_physics_durability_diagnostic' else output / 'result.json')
    elif category == 'non_model_boundary' and output:
        paths.append(output / 'suite-result.json')
    elif category != 'report_support':
        paths.append(campaign / 'qualification' / (short + '-assessment.json'))
    for path in paths:
        if not path.exists():
            continue
        value = read(path); bind(path)
        require(value.get('run_id', run_id) == run_id, 'Assessment run identity mismatch')
        result['empirical_results_consumed'] = True
        flags = {k: value[k] for k in ('passed', 'qualified', 'diagnostic_passed', 'qualification_passed', 'smoke_passed',
                                      'validity', 'task_evidence_valid', 'task_outcome') if k in value}
        result['retained_assessment_fields'] = flags
        booleans = [v for k, v in flags.items() if k.endswith('passed') or k == 'qualified']
        result['qualification_or_diagnostic_status'] = ('passed' if booleans and all(v is True for v in booleans)
                                                       else 'failed' if any(v is False for v in booleans) else 'assessed')
    # The final admission disposition takes precedence over a raw suite flag.
    dispositions = list((campaign / 'qualification').glob('final-qualification-*/' + short + '/disposition.json'))
    require(len(dispositions) <= 1, 'Ambiguous final admission disposition')
    for path in dispositions:
        value = read(path)
        require(value.get('run_id') == run_id, 'Disposition run identity mismatch')
        bind(path)
        result['qualification_or_diagnostic_status'] = 'passed' if value.get('passed') is True else 'failed'
        result['admission_error'] = value.get('error')
    return result


def footprint(root, excluded=()):
    """Logical size only: never open evidence content to measure storage."""
    root = Path(root).resolve(); excluded = [Path(p).resolve() for p in excluded]
    entries, errors = [], []
    def skip(path):
        return path.is_symlink() or any(path == x or path.is_relative_to(x) for x in excluded)
    if root.exists():
        for folder, dirs, files in os.walk(root, followlinks=False, onerror=lambda e: errors.append(str(e))):
            dirs[:] = sorted(d for d in dirs if not skip(Path(folder) / d))
            for name in sorted(files):
                p = Path(folder) / name
                if skip(p):
                    continue
                try:
                    entries.append((p.relative_to(root).as_posix(), p.stat().st_size))
                except OSError as error:
                    errors.append(str(error))
    entries.sort()
    return {'path': str(root), 'exists': root.exists(), 'files': len(entries),
            'logical_bytes': sum(size for _, size in entries),
            'path_size_manifest_sha256': sha(canonical(entries)), 'errors': errors,
            'scope': 'Non-atomic stat-only retained logical bytes; no outcome, peak, allocated-block or causal-growth claim.'}


def diagnostic_start_inputs(campaign, jobs, prior, bind):
    """Explicit retained-diagnosis observations only; never failed raw outputs.

    A model_started Boolean supplies one observed model-start lower bound. It
    does not supply a literal turn/start-request count or billing total.
    """
    records = copy.deepcopy(prior.get('diagnostic_observed_model_starts', {}))
    baseline = prior.get('diagnostic_observed_model_starts_baseline',
                         prior['totals'].get('diagnostic_only_observed_turn_start_requests', 0))
    require(type(baseline) is int and baseline >= 0, 'Invalid diagnostic model-start baseline')
    legacy_jobs = {r['official_queue']['id'] for r in prior['rows']
                   if r.get('diagnostic_only_accounting', {}).get('observed_turn_start_requests', 0)}
    seen = set()
    for path in sorted((campaign / 'registration').glob('diagnostic-start-input-*.json')):
        value = read(path)
        require(value.get('schema') == 'campaign002-diagnostic-start-accounting-1', 'Unknown diagnostic input schema')
        jid = value.get('queue_job_id')
        require(jid in jobs and jid not in seen and jid not in legacy_jobs, 'Duplicate or undiscovered diagnostic start')
        seen.add(jid)
        fresh, original = jobs[jid], value.get('official_status', {})
        require(fresh.get('state') == 'failed' and type(fresh.get('exit_status')) is int and fresh['exit_status'] == 1,
                'Diagnostic model-start input requires fresh failed/integer-one official status')
        require(all(fresh.get(k) == original.get(k) for k in (*IMMUTABLE_QUEUE_FIELDS, 'state', 'exit_status', 'started_at', 'ended_at')),
                'Diagnostic official status binding differs')
        require(bool(fresh.get('started_at')) and bool(fresh.get('ended_at')), 'Diagnostic job is not terminal')
        reference = value.get('diagnostic_analysis', {})
        analysis_path = Path(reference.get('path', '')).resolve()
        require(analysis_path.is_relative_to((campaign / 'io-repair').resolve()) and not analysis_path.is_symlink(),
                'Diagnostic analysis outside declared repair artifacts')
        require(identity(analysis_path) == reference, 'Diagnostic analysis hash binding differs')
        analysis = read(analysis_path)
        require(analysis.get('queue_job_id') == jid and analysis.get('client_completion', {}).get('model_started') is True,
                'Diagnostic model-start observation differs')
        observation = value.get('observation', {})
        require(observation == {'json_pointer':'/client_completion/model_started', 'value':True,
                                'observed_model_starts_lower_bound':1, 'scope':'diagnostic_only',
                                'qualification':'unassessed', 'task_outcome':'unknown'},
                'Diagnostic observation contract differs')
        binding = bind(path); bind(analysis_path)
        record = {'queue_job_id':jid, 'observed_model_starts_lower_bound':1,
                  'input':binding, 'diagnostic_analysis':reference, 'observation':observation,
                  'scope':'Retained failed-job diagnostic metadata only; no empirical qualification, task score, literal request count or exact billing.'}
        if jid in records: require(records[jid] == record, 'Prior diagnostic model-start binding changed')
        records[jid] = record
    # Every preserved explicit observation must still have its immutable input.
    require(set(records) <= seen, 'Previously bound diagnostic-start input is missing')
    return baseline, records


def build_refresh(prior, discovered, campaign, repo, provider=official_status, output_reader=consume_success):
    started = now()
    jobs = {jid: authenticate(jid, entry, provider) for jid, entry in discovered.items()}
    cutoff = now()  # all required official authentication precedes every outcome read
    current = {}
    def bind(path):
        item = identity(path); current[str(Path(path).resolve())] = item; return item
    diagnostic_baseline, diagnostic_records = diagnostic_start_inputs(campaign, jobs, prior, bind)
    result = copy.deepcopy(prior)
    rows, excluded, revisions = [], [], set()
    for jid, entry in discovered.items():
        job = jobs[jid]; info = classify(job, entry, campaign, repo)
        row = copy.deepcopy(entry.get('prior') or {})
        row.update({k: info[k] for k in ('run_id', 'category', 'entry_point', 'framework_revision')
                    if info[k] is not None})
        row.update(official_queue={k: job.get(k) for k in ('id', 'state', 'exit_status', 'submitted_at', 'started_at', 'ended_at')},
                   official_metadata_canonical_sha256=sha(canonical(job)), official_argv_sha256=sha(canonical(job['argv'])),
                   official_status_authenticated_at=cutoff, empirical_results_consumed=False,
                   qualification_or_diagnostic_status='outcome_not_consumed', model_invocation_receipts=[],
                   known_model_invocations_started=None)
        for receipt in entry['receipts']:
            current[receipt['path']] = receipt
        before = set(current)
        if succeeded(job):
            row.update(output_reader(job, info, campaign, bind))
            if info['category'] not in {'qualification_model_smoke', 'qualification_model_pilot', 'scored_model_slot', 'unclassified_queue_job'}:
                row['known_model_invocations_started'] = 0
                row['model_count_basis'] = 'Declared no-model command; no task success or billing inference.'
            if row.get('framework_revision'):
                revisions.add(row['framework_revision'])
        elif info['output']:
            excluded.append(info['output'])
        if not succeeded(job) and info['host_output']:
            excluded.append(info['host_output'])
        if not succeeded(job) and entry.get('prior'):
            # Preserve previously bound diagnostic-only observations, never reopen failed outputs.
            for key, value in entry['prior'].items():
                if 'diagnostic' in key and key not in {'qualification_or_diagnostic_status'}:
                    row[key] = copy.deepcopy(value)
        if jid in diagnostic_records:
            row['diagnostic_model_start_accounting'] = copy.deepcopy(diagnostic_records[jid])
        row['source_refs'] = list(dict.fromkeys(row.get('source_refs', []) + [r['path'] for r in entry['receipts']] + sorted(set(current) - before)))
        if job.get('started_at') and job.get('ended_at'):
            row['queue_wall_s'] = (stamp(job['ended_at']) - stamp(job['started_at'])).total_seconds()
            require(row['queue_wall_s'] >= 0, 'Negative queue duration')
        else:
            row['queue_wall_s'] = None
        if info['output']:
            row['evidence_directory'] = str(info['output'])
            if succeeded(job):
                row['current_retained_evidence_storage'] = footprint(info['output'])
            else:
                row.pop('current_retained_evidence_storage', None)
        rows.append(row)
    for path in (campaign / 'investigation/qualification-history.json', Path(__file__)):
        if path.exists(): bind(path)
    for path in sorted((campaign / 'qualification').glob('final-qualification-*-readiness.json')):
        bind(path)  # hash only: no unsatisfied/running outcomes are read
    result['rows'] = rows
    totals = copy.deepcopy(prior['totals'])
    terminal = [r for r in rows if r['queue_wall_s'] is not None]
    model = [r for r in rows if r['category'] in {'qualification_model_smoke', 'qualification_model_pilot', 'scored_model_slot'}]
    assessable = sum(r.get('known_model_invocations_started') or 0 for r in model if succeeded(r['official_queue']))
    diagnostic = prior['totals'].get('diagnostic_only_observed_turn_start_requests', 0)
    diagnostic_model_starts = diagnostic_baseline + sum(r['observed_model_starts_lower_bound'] for r in diagnostic_records.values())
    by_category = Counter()
    for row in terminal: by_category[row['category']] += row['queue_wall_s']
    totals.update(official_jobs=len(rows), queue_states=dict(Counter(r['official_queue']['state'] for r in rows)),
                  jobs_by_category=dict(Counter(r['category'] for r in rows)),
                  terminal_queue_wall_s=sum(r['queue_wall_s'] for r in terminal), terminal_queue_wall_s_by_category=dict(by_category),
                  queue_failed_jobs=sum(r['official_queue']['state'] in ('failed', 'canceled', 'cancelled') for r in rows),
                  successful_queue_jobs_with_failed_qualification=sum(succeeded(r['official_queue']) and r['qualification_or_diagnostic_status'] == 'failed' for r in rows),
                  known_qualification_model_invocations_started=sum(r.get('known_model_invocations_started') or 0 for r in model if r['category'] != 'scored_model_slot' and succeeded(r['official_queue'])),
                  known_scored_model_invocations_started=sum(r.get('known_model_invocations_started') or 0 for r in model if r['category'] == 'scored_model_slot' and succeeded(r['official_queue'])),
                  unknown_model_invocation_jobs=[r['official_queue']['id'] for r in model if r.get('known_model_invocations_started') is None],
                  model_invocations_started_total=None, diagnostic_only_observed_turn_start_requests=diagnostic,
                  observed_turn_start_requests_from_assessable_and_diagnostic_receipts=assessable + diagnostic,
                  diagnostic_only_observed_model_starts_lower_bound=diagnostic_model_starts,
                  observed_model_starts_lower_bound_from_assessable_and_diagnostic_receipts=assessable + diagnostic_model_starts,
                  diagnostic_model_start_scope='Legacy literal diagnostic requests are included once in the model-start baseline; additional keyed model_started observations add only to the model-start lower bound, never literal request totals or billing.',
                  successful_queue_jobs_with_unconsumed_outcome=[r['official_queue']['id'] for r in rows if succeeded(r['official_queue']) and not r['empirical_results_consumed'] and r['category'] != 'report_support'],
                  model_calls_scope='Successful-queue protected start receipts and separately preserved diagnostic-only starts are an observed lower bound. Exact all-service generations, billing and task success are unknown.',
                  scored_slots_started_in_recorded_registry=sum(r['category'] == 'scored_model_slot' and bool(r['official_queue'].get('started_at')) for r in rows))
    registration = local_path(prior.get('scored_registry_inventory', {}).get('frozen_scored_registration_path'), repo)
    registered = []
    if registration and registration.exists():
        value = read(registration); bind(registration)
        registered = [x['run_id'] for x in value['attempts']]
        require(len(registered) == len(set(registered)), 'Duplicate registered scored slot')
    totals['scored_slots_registered'] = len(registered)
    result['scored_registry_inventory'] = {
        'observed_at': cutoff, 'execution_root': str(campaign / 'execution'),
        'frozen_scored_registration_path': str(registration) if registration else None,
        'frozen_scored_registration_exists': bool(registration and registration.exists()),
        'registered_run_ids': registered,
        'recognized_metadata_files': sorted({r['path'] for entry in discovered.values() for r in entry['receipts']
                                            if Path(r['path']).is_relative_to(campaign / 'execution')}),
        'scope': 'Registration is declared slot inventory, not launch or outcome. Starts are official started_at observations; no out-of-band completeness claim.'}
    result['totals'] = totals
    accounting = campaign / 'registration/session14-accounting.json'
    excluded += [accounting, accounting.with_suffix('.tmp')]
    roots = [campaign, campaign.parent / 'local-evidence/campaign002']
    release_root = campaign.parents[1] / 'Architecture Map/releases'
    measured_start = now()
    release_stats = []
    for revision in sorted(revisions):
        release = release_root / revision
        if release.exists():
            for path in (release / 'snapshot.json', release / 'code.zip'):
                if path.exists(): bind(path)
            release_stats.append(footprint(release))
    capacity = shutil.disk_usage(repo)
    result['storage'] = {'measurement_started_at': measured_start, 'method': 'Scoped os.walk/stat only; sorted relative-path/size hash. Exclude symlinks, active/failed output roots and accounting itself.',
                         'current_directory_snapshots': [footprint(p, excluded) for p in roots],
                         'completed_session14_revision_snapshots': release_stats,
                         'completed_revision_logical_bytes': sum(x['logical_bytes'] for x in release_stats),
                         'excluded_active_or_failed_output_roots': [str(p) for p in excluded],
                         'native_C_free_bytes': capacity.free, 'native_C_total_bytes': capacity.total,
                         'native_C_used_bytes': capacity.used, 'measurement_ended_at': now(),
                         'scope': 'Campaign, local evidence and release roots are disjoint. Per-job footprints overlap these roots and must not be added. Non-atomic logical retained bytes, not peak/full-machine growth or causal session consumption; external workspaces/caches/services excluded.'}
    history = copy.deepcopy(prior.get('prior_accounting_checkpoints', []))
    history.append({'as_of': prior.get('as_of'), 'totals': copy.deepcopy(prior['totals']), 'storage': copy.deepcopy(prior['storage']),
                    'source_binding_count': len(prior['source_bindings']), 'scope': 'Previous cutoff; totals are not additive.'})
    result['prior_accounting_checkpoints'] = history
    # Never overwrite a historical identity of a mutable path.
    for key, value in current.items(): result['source_bindings'].setdefault(key, value)
    active = [r for r in rows if r['official_queue']['state'] in {'queued', 'running', 'cancel_requested'}]
    result['queue_occupancy_at_cutoff'] = {'cutoff': cutoff, 'accounted_job_count': len(rows),
        'active_accounted_jobs': [r['official_queue']['id'] for r in active], 'terminal_occupancy_s': totals['terminal_queue_wall_s'],
        'active_elapsed_s_lower_bound': {r['official_queue']['id']: max(0, (stamp(cutoff)-stamp(r['official_queue']['started_at'])).total_seconds()) for r in active if r['official_queue'].get('started_at')},
        'scope': 'Deduplicated discovered jobs only; ended_at minus started_at, excluding queue waiting, coordinator/local-test time and other projects. No global idle claim.'}
    result.update(as_of=cutoff, last_refreshed_at=now(), official_status_authenticated_at=cutoff, provisional=True)
    result['refresh_provenance'] = {'refresh_started_at': started, 'official_status_authenticated_at': cutoff,
        'official_statuses': jobs, 'current_bindings': current, 'original_source_bindings_preserved': True,
        'original_source_binding_count': prior.get('refresh_provenance', {}).get('original_source_binding_count', len(prior['source_bindings'])),
        'prior_refresh_source_binding_count': len(prior['source_bindings']),
        'discovery': 'Named direct/wrapped queue receipts under qualification, io-repair, investigation and execution; fixed prior job IDs retained; versions need no hard-coded update.'}
    result['diagnostic_observed_model_starts_baseline'] = diagnostic_baseline
    result['diagnostic_observed_model_starts'] = diagnostic_records
    result['limitations'] = ['Official succeeded/integer-zero authenticates execution, not qualification or task success.',
        'Only successful jobs supply new empirical outcomes or invocation receipts; failed diagnostic-only starts use preserved accounting or explicit hash-bound diagnosis inputs after fresh terminal authentication. Literal requests and model-start lower bounds remain distinct.',
        'Exact model generations and billing remain unknown; observed starts are a lower bound.',
        'Queue execution occupancy excludes waiting, coordinator process time, local tests and other projects.',
        'All historical bindings and session13 baseline are preserved; earlier cutoff totals are not additive.',
        'Storage is scoped, stat-only and non-atomic; no peak or full-machine growth claim.',
        'Unclassified commands and absent successful-job outcomes remain explicitly unconsumed; no fabricated passing result.']
    return result


def retain_checkpoint(path):
    path = Path(path); data = path.read_bytes()
    cutoff = re.sub(r'[^A-Za-z0-9]', '', str(json.loads(data).get('as_of', 'legacy')))
    target = path.parent / ('session14-accounting-checkpoint-' + cutoff + '-' + sha(data)[:20] + '.json')
    if target.exists():
        require(target.read_bytes() == data, 'Checkpoint collision')
    else:
        with target.open('xb') as stream: stream.write(data)
    return identity(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Authenticate/read allowed outcomes and atomically refresh; omitted means metadata inventory only.')
    args = parser.parse_args()
    path = HERE / 'session14-accounting.json'; old_bytes = path.read_bytes(); prior = json.loads(old_bytes)
    discovered = discover(CAMPAIGN, prior)
    if not args.refresh:
        print(json.dumps({'mode': 'metadata_inventory_only', 'job_count': len(discovered),
                          'new_job_ids': [k for k,v in discovered.items() if not v['prior']],
                          'empirical_outputs_read': False, 'writes': False}, indent=2)); return
    result = build_refresh(prior, discovered, CAMPAIGN, REPO)
    require(path.read_bytes() == old_bytes, 'Accounting changed during refresh; refusing replacement')
    checkpoint = retain_checkpoint(path)
    result['prior_accounting_checkpoints'][-1].update(accounting_sha256=sha(old_bytes), checkpoint=checkpoint)
    result['refresh_provenance'].update(previous_accounting_sha256=sha(old_bytes), previous_accounting_checkpoint=checkpoint)
    sweep = {'created_at': result['as_of'], 'official_statuses': result['refresh_provenance']['official_statuses']}
    receipt = HERE / ('session14-accounting-official-statuses-' + sha(canonical(sweep))[:20] + '.json')
    with receipt.open('x', encoding='utf-8', newline='\n') as stream: json.dump(sweep, stream, indent=2); stream.write('\n')
    result['refresh_provenance']['official_status_sweep_receipt'] = identity(receipt)
    temp = path.with_suffix('.tmp')
    with temp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    require(path.read_bytes() == old_bytes, 'Accounting changed before replacement')
    os.replace(temp, path)
    print(json.dumps({'accounting': identity(path), 'checkpoint': checkpoint, 'totals': result['totals']}, indent=2))


if __name__ == '__main__':
    main()
