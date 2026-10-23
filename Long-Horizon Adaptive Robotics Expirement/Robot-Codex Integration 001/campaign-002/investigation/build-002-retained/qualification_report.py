"""Queued permanent qualification companion; never fabricates scored slots.

Only explicitly indexed, authenticated completed qualifications are opened.
This does not run models, replay analyses, change outcomes, or build the separate
twenty-disposition empirical report.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import re
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parents[2]
READS = []
MAX_BYTES = 128 * 1024 * 1024
RECORDER_PHASES = (
    'bridge.rgb_encode', 'bridge.depth_encode', 'bridge.recorder_image',
    'recorder.lock_acquire', 'recorder.lock_release',
    'recorder.sqlite.execute', 'recorder.sqlite.executemany', 'recorder.sqlite.executescript',
    'recorder.sqlite.commit', 'recorder.sqlite.rollback', 'recorder.sqlite.close',
    'recorder.sqlite.enter', 'recorder.sqlite.exit', 'recorder.quota_guard', 'recorder.physical_guard',
    'recorder.image', 'recorder.persist', 'recorder.motion', 'recorder.flush_motion',
    'recorder.document', 'recorder.event', 'recorder.trigger', 'recorder.close')
FEASIBILITY_ORDER = ('DELETE', 'PERSIST', 'PERSIST', 'DELETE', 'DELETE', 'PERSIST', 'PERSIST', 'DELETE')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def href(path, output):
    return quote(Path(os.path.relpath(path, output)).as_posix(), safe='/.:')


def consume(path, role, expected=None, expected_bytes=None, *, parse=True):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Missing, linked, or oversized evidence: ' + str(path))
    raw = path.read_bytes()
    if expected is not None and sha(raw) != expected:
        raise ValueError('Evidence hash mismatch: ' + str(path))
    if expected_bytes is not None and (type(expected_bytes) is not int or len(raw) != expected_bytes):
        raise ValueError('Evidence byte count mismatch: ' + str(path))
    READS.append({'path': str(path.resolve()), 'sha256': sha(raw), 'bytes': len(raw), 'role': role})
    return json.loads(raw) if parse else raw


def require_hash(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('Explicit artifact SHA-256 required')


def bound(entry, role, *, parse=True):
    require_hash(entry.get('sha256'))
    return consume(entry['path'], role, entry['sha256'], entry.get('bytes'), parse=parse)


def job_gate(row, artifacts):
    matches = [a for a in artifacts if a.get('label') == 'Official queue receipt']
    if len(matches) != 1:
        raise ValueError('Exactly one explicit official queue receipt required')
    receipt = bound(matches[0], 'official queue receipt before output access')
    job = receipt.get('job', receipt)
    if job.get('id') != row.get('queue', {}).get('id'):
        raise ValueError('Qualification queue identity differs from history')
    if row.get('status') == 'cancelled':
        if job.get('state') not in ('canceled', 'cancelled') or job.get('started_at') is not None:
            raise ValueError('Cancellation must be authenticated before start')
    elif (job.get('state') != 'succeeded' or type(job.get('exit_status')) is not int
          or job['exit_status'] != 0):
        raise ValueError('Official queue succeeded with integer exit0 required before qualification outputs')
    return job, matches[0]


def safe_child(folder, name):
    if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name:
        raise ValueError('Expected a literal evidence filename')
    return Path(folder) / name


def preflight_gate(row, artifacts):
    """A source-bound withdrawal before submission is not a queue outcome."""
    contract = row.get('preflight_contract', {})
    if (contract.get('schema') != 'campaign002-preflight-not-run-1' or row.get('queue') is not None
            or row.get('validity') != 'unknown' or row.get('assessment_state') != 'not_assessed'
            or row.get('scorable') is not False or row.get('task_outcome') != 'unknown'
            or type(row.get('model_calls')) is not int or row['model_calls'] != 0):
        raise ValueError('Explicit no-queue, unassessed preflight contract required')
    records = [a for a in artifacts if Path(a['path']).name == 'preflight-failure.json']
    manifests = [a for a in artifacts if Path(a['path']).name.endswith('-manifest.json')]
    snapshots = [a for a in artifacts if Path(a['path']).name == 'snapshot.json']
    if len(artifacts) != 3 or len(records) != 1 or len(manifests) != 1 or len(snapshots) != 1:
        raise ValueError('Preflight may link only its disposition, manifest and source snapshot; no outputs or queue receipt')
    for item, key in ((records[0], 'record_sha256'), (manifests[0], 'manifest_sha256'), (snapshots[0], 'snapshot_sha256')):
        if item.get('sha256') != contract.get(key) or type(item.get('bytes')) is not int:
            raise ValueError('Preflight artifact binding mismatch')
    record = bound(records[0], 'no-queue preflight disposition')
    if (record.get('run_id') != row['run_id'] or record.get('framework_revision') != row['revision']
            or record.get('execution_status') != 'not_run' or record.get('queue_submitted') is not False
            or record.get('scorable') is not False or record.get('task_outcome') != 'unknown'):
        raise ValueError('Preflight disposition does not prove the declared no-submission state')
    manifest = bound(manifests[0], 'unlaunched frozen manifest')
    snapshot = bound(snapshots[0], 'unlaunched source snapshot; not a source-validity pass')
    if (manifest.get('run_id') != row['run_id'] or manifest.get('framework_revision') != row['revision']
            or snapshot.get('run_id') != row['run_id'] or snapshot.get('revision') != row['revision']
            or snapshot.get('manifest_sha256') != manifests[0]['sha256']):
        raise ValueError('Preflight manifest/snapshot identity or hash mismatch')
    campaign = Path(manifests[0]['path']).parent.parent
    expected_folder = campaign / 'qualification' / row['run_id']
    expected_evidence = campaign.parent / 'local-evidence/campaign002/qualification' / row['run_id']
    short_id = row['run_id'].removeprefix('RCI001-C02-')
    if (Path(records[0]['path']).parent.resolve() != expected_folder.resolve()
            or Path(contract.get('unlaunched_evidence_path', '')).resolve() != expected_evidence.resolve()
            or expected_evidence.exists()
            or any((campaign / 'qualification' / (short_id + suffix)).exists() for suffix in ('-queue.json', '-submit.json'))
            or any((expected_folder / name).exists() for name in ('launch-intent.json', 'queue-submit.json', 'official-status.json'))):
        raise ValueError('Preflight no-launch inventory contradicts its recorded disposition')
    return {'basis': 'bound_pre_submission_disposition', 'original_record': record,
            'queue_submitted': False, 'assessment_state': 'not_assessed',
            'scope': 'No queue job or attempt output is inferred. The bound preflight disposition and unchanged manifest/snapshot document withdrawal before submission. Expected launch metadata and evidence directory are absent; frozen source validity was not established.'}


def timing_detail(assessment, artifacts, output):
    """Presentation chain only; never replaces a strict timing verdict."""
    binding = assessment.get('bindings', {}).get('host_result')
    if not binding:
        return None
    host = bound(binding, 'assessment-bound protected host result')
    if host.get('run_id') != assessment['run_id']:
        raise ValueError('Host/assessment run identity mismatch')
    record = host.get('timing_v2')
    if not isinstance(record, dict):
        return None
    path = safe_child(Path(binding['path']).parent, record.get('metadata_file'))
    require_hash(record.get('metadata_sha256'))
    metadata = consume(path, 'host-bound timing metadata; display only', record.get('metadata_sha256'))
    if metadata.get('schema') != 'rci-prospective-timing-2':
        raise ValueError('Unexpected timing metadata schema')
    if (metadata.get('sha256') != record.get('sample_sha256')
            or metadata.get('sample_count') != record.get('sample_count')
            or not metadata.get('sample_file') or metadata.get('sample_file') != record.get('sample_file')
            or metadata.get('loop_origin') != record.get('loop_origin')):
        raise ValueError('Host/sample metadata binding mismatch')
    sample_links = []
    for label, value in [('Timing samples', metadata), ('GC callback samples', metadata.get('garbage_collection')),
                         ('Native memory samples', metadata.get('host_memory'))]:
        if not isinstance(value, dict) or not value.get('sample_file'):
            continue
        sample = safe_child(path.parent, value['sample_file'])
        require_hash(value.get('sha256'))
        if type(value.get('byte_count')) is not int:
            raise ValueError('Explicit binary sample byte count required')
        consume(sample, label + '; hash verification only', value['sha256'], value['byte_count'], parse=False)
        sample_links.append({'label': label, 'href': href(sample, output), 'sha256': value['sha256']})
    independent = assessment.get('timing', assessment.get('campaign_timing'))
    if independent is not None and (not isinstance(independent, dict)
            or independent.get('metadata_sha256') != record['metadata_sha256']
            or independent.get('sample_sha256') != record['sample_sha256']):
        raise ValueError('Independent timing/host metadata binding mismatch')
    return {'basis': 'diagnostic_only' if independent is None else 'original_assessment_and_bound_metadata',
            'strict_verification_available': independent is not None,
            'strict_passed': independent.get('passed') if isinstance(independent, dict) else None,
            'strict_errors': assessment.get('errors', assessment.get('verification_errors', {})),
            'host_terminal': host.get('terminal'), 'host_error': host.get('error'),
            'metadata_href': href(path, output), 'metadata_sha256': record['metadata_sha256'],
            'samples': sample_links, 'loop_origin': metadata.get('loop_origin'),
            'terminal': metadata.get('terminal'), 'maximum_sample': metadata.get('maximum_sample'),
            'phases': metadata.get('phases', {}), 'slow_phases_by_name': metadata.get('slow_phases_by_name', {}),
            'slow_phases': metadata.get('slow_phases', []), 'phase_accounting': metadata.get('phase_accounting'),
            'garbage_collection': metadata.get('garbage_collection'), 'host_memory': metadata.get('host_memory'),
            'independent_resource_summaries': {key: independent.get(key) for key in
                ('resource_integrity_pass', 'garbage_collection_pass', 'host_memory_pass',
                 'garbage_collection', 'host_memory', 'resource_source_bindings')} if isinstance(independent, dict) else None,
            'scope': 'Hash-authenticated retained measurements. No timing, GC correlation, or memory-policy analysis is recomputed here.'}


def feasibility_detail(assessment):
    """Keep the assessor's separate synthetic rounds; no latency recomputation."""
    if 'mechanical_feasibility_passed' not in assessment:
        return None
    if (assessment.get('schema') != 'rci-recorder-journal-feasibility-assessment-1'
            or assessment.get('production_adopted') is not False
            or assessment.get('scorable') is not False or assessment.get('task_outcome') != 'unknown'
            or type(assessment.get('model_calls')) is not int or assessment['model_calls'] != 0):
        raise ValueError('Recorder feasibility must retain its no-model, no-score, no-adoption boundary')
    rounds, recovery = assessment.get('rounds'), assessment.get('recovery_checks')
    if (not isinstance(rounds, list) or len(rounds) != len(FEASIBILITY_ORDER)
            or any(not isinstance(row, dict) or type(row.get('ordinal')) is not int or row['ordinal'] != ordinal
                   or row.get('mode') != mode or type(row.get('passed')) is not bool
                   or (row.get('timing') is not None and not isinstance(row['timing'], dict))
                   for ordinal, (row, mode) in enumerate(zip(rounds, FEASIBILITY_ORDER)))):
        raise ValueError('Recorder feasibility requires all eight ordered assessment rounds')
    combinations = [(mode, stage) for mode in ('DELETE', 'PERSIST') for stage in ('before_commit', 'after_commit')]
    if (not isinstance(recovery, list) or len(recovery) != 4
            or any(not isinstance(row, dict) or row.get('mode') != mode or row.get('stage') != stage or type(row.get('passed')) is not bool
                   for row, (mode, stage) in zip(recovery, combinations))):
        raise ValueError('Recorder feasibility requires all four assessment crash copies')
    return {'basis': 'original_independent_mechanical_assessment',
            'mechanical_feasibility_passed': assessment['mechanical_feasibility_passed'],
            'rounds': rounds, 'recovery_checks': recovery, 'production_adopted': False,
            'model_calls': 0, 'scorable': False, 'task_outcome': 'unknown',
            'original_scope': assessment.get('scope'),
            'scope': 'Synthetic recorder feasibility only. Per-round descriptive latency is copied from the original assessment; no new pooling, win threshold, task performance, physics timing qualification or production adoption is inferred. API/SQL categories are inclusive and must not be summed. Crash-copy recovery does not certify power-loss behavior.'}


def qualification_row(row, output):
    if row.get('status') not in ('passed', 'failed', 'cancelled', 'not_run'):
        raise ValueError('Only explicit completed qualification statuses are supported')
    artifacts = row.get('artifacts', [])
    preflight = preflight_gate(row, artifacts) if row['status'] == 'not_run' else None
    job, official = ({}, None) if preflight else job_gate(row, artifacts)  # Before any outcome read.
    links, documents = [], {}
    for item in artifacts:
        path = Path(item['path'])
        if type(item.get('bytes')) is not int:
            raise ValueError('Explicit indexed artifact byte count required')
        # A canceled run must not have an output assessment consumed.
        if row['status'] == 'cancelled' and (path.name.endswith('-assessment.json') or path.name == 'suite-result.json'):
            raise ValueError('Canceled qualification cannot consume an outcome artifact')
        raw = bound(item, 'indexed qualification artifact after queue gate', parse=False)
        links.append({'label': item['label'], 'href': href(path, output), 'sha256': item['sha256']})
        if path.suffix == '.json':
            documents[str(path)] = json.loads(raw)
    assessments = [(p, value) for p, value in documents.items() if Path(p).name.endswith('-assessment.json')]
    assessment = assessments[0][1] if len(assessments) == 1 else None
    if len(assessments) > 1:
        raise ValueError('Ambiguous qualification assessment')
    if row['run_id'] == 'RCI001-C02-smoke-001' and row['status'] != 'failed':
        raise ValueError('Original Smoke001 failure must remain failed')
    if assessment:
        if (assessment.get('run_id') != row['run_id'] or assessment.get('queue_job_id') != job['id']
                or assessment.get('framework_revision') != row['revision']):
            raise ValueError('Assessment run/revision/queue identity mismatch')
        flags = [assessment[k] for k in ('qualification_passed', 'smoke_passed', 'diagnostic_passed',
                                         'mechanical_feasibility_passed') if k in assessment]
        if len(flags) != 1 or type(flags[0]) is not bool or flags[0] != (row['status'] == 'passed'):
            raise ValueError('History status differs from original assessment verdict')
    elif row['status'] not in ('cancelled', 'not_run'):
        suites = [(Path(p), v) for p, v in documents.items() if Path(p).name == 'suite-result.json']
        argv = job.get('argv', [])
        if (len(suites) != 1 or '--output' not in argv
                or not any(suites[0][0].parent.resolve() == p.resolve() for p in
                           (Path(argv[argv.index('--output') + 1]), Path(job['cwd']) / argv[argv.index('--output') + 1]))
                or suites[0][1].get('qualified') is not (row['status'] == 'passed')):
            raise ValueError('Boundary verdict/output path is not bound to official job')
        assessment = suites[0][1]
    analyses = []
    for path, value in documents.items():
        if not Path(path).name.endswith('-analysis.json'):
            continue
        if value.get('run_id') != row['run_id'] or value.get('queue_job_id') != job['id']:
            raise ValueError('Retained analysis identity mismatch')
        proof = value.get('provenance', {}).get('official_queue_receipt', {})
        if proof.get('sha256') != official['sha256']:
            raise ValueError('Retained analysis queue hash mismatch')
        analyses.append({'href': href(path, output), 'schema': value.get('schema'),
                         'content': {k: v for k, v in value.items() if k != 'provenance'},
                         'scope': 'Original hashed analysis retained verbatim as structured data; no correlation recomputation.'})
    snapshot = next((v for p, v in documents.items() if Path(p).name == 'snapshot.json'), {})
    checks = (assessment or {}).get('checks', {})
    return {'run_id': row['run_id'], 'revision': row['revision'], 'status': row['status'],
            'reason': row.get('reason'), 'model_calls': row.get('model_calls'), 'scorable': False,
            'validity': row.get('validity', 'unknown'), 'task_outcome': 'unknown',
            'started_at': job.get('started_at'), 'ended_at': job.get('ended_at'), 'job_id': job.get('id'),
            'queue_state': job.get('state'), 'queue_exit_status': job.get('exit_status'),
            'checks': checks, 'failed_checks': [key for key, passed in checks.items() if passed is not True],
            'assessment_errors': (assessment or {}).get('errors', (assessment or {}).get('verification_errors', {})),
            'declared_details': row.get('details', {}), 'links': links, 'analyses': analyses,
            'recorder_feasibility': feasibility_detail(assessment) if assessments else None,
            'preflight': preflight,
            'recorder_subphases_declared': any(name.endswith('/harness/instrumented_recorder.py')
                                               for name in snapshot.get('sources', {})),
            'timing': timing_detail(assessment, artifacts, output) if assessments else None}


def inventory_paths(campaign):
    root = campaign / 'execution'
    if not root.exists():
        return []
    return sorted(p for p in root.rglob('*') if p.is_file() and p.name in
                  ('launch-intent.json', 'queue-submit.json', 'official-status.json', 'disposition.json'))


def launch_inventory(campaign, output):
    """Observe only launch metadata, never scored outcomes or running traces."""
    operator = campaign / 'operate.py'
    raw = consume(operator, 'authorized launcher source', parse=False)
    tree = ast.parse(raw)
    start = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start')
    calls = [n for n in ast.walk(start) if isinstance(n, ast.Call)]
    intents = [n.lineno for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'save'
               and n.args and any(isinstance(x, ast.Constant) and x.value == 'launch-intent.json' for x in ast.walk(n.args[0]))]
    submits = [n.lineno for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'queue'
               and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 'submit']
    if len(intents) != 1 or len(submits) != 1 or intents[0] >= submits[0]:
        raise ValueError('Scored launcher no longer establishes intent before queue submission')
    entries = []
    for path in inventory_paths(campaign):
        raw = consume(path, 'scored launch/disposition inventory only', parse=False)
        value = json.loads(raw) if path.name != 'disposition.json' else {}
        job = value.get('job', value)
        entries.append({'file': str(path.relative_to(campaign)), 'sha256': READS[-1]['sha256'],
                        'run_id': value.get('run_id', path.parent.name),
                        'job_id': job.get('id', value.get('job_id')), 'state': job.get('state'),
                        'href': href(path, output)})
    registration_path = campaign.parent.parent / 'Architecture Map/releases/RCI001-C02-frozen-001/registration.json'
    registration = None
    if registration_path.exists():
        consume(registration_path, 'scored campaign registration inventory only', parse=False)
        registration = {'path': str(registration_path), 'sha256': READS[-1]['sha256'],
                        'href': href(registration_path, output)}
    return {'state': 'no_scored_launch_recorded' if not entries else 'scored_launch_metadata_present',
            'entries': entries, 'launch_intents': sum(e['file'].endswith('launch-intent.json') for e in entries),
            'queue_submissions': sum(e['file'].endswith('queue-submit.json') for e in entries),
            'disposition_files': sum(e['file'].endswith('disposition.json') for e in entries),
            'registration': registration,
            'operator_sha256': sha(raw), 'operator_href': href(operator, output),
            'scope': 'Hash-recorded inventory of the configured execution registry and registration; the authorized launcher writes intent before submission. Disposition bytes are inventoried without interpreting outcomes. This does not assert absence of out-of-band execution. No scored assessment or trace files are read.'}


def build(index_path, output, *, campaign=CAMPAIGN, previous=None):
    READS.clear()
    output = Path(output)
    index = consume(index_path, 'explicit completed qualification history')
    if index.get('schema') != 'campaign002-qualification-history-1':
        raise ValueError('Wrong qualification history schema')
    ids = [r['run_id'] for r in index.get('attempts', [])]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Nonempty unique qualification identities required')
    rows = [qualification_row(row, output) for row in index['attempts']]
    prior_path = Path(previous) if previous else campaign.parent / 'campaign-001/investigation/data.json'
    prior = consume(prior_path, 'immutable Campaign001 report data')
    counts = prior.get('counts', {}).get('all scheduled slots', {})
    if (len(prior.get('runs', [])), counts.get('valid'), counts.get('successes'), counts.get('invalid'), counts.get('not_run')) != (24, 6, 6, 4, 14):
        raise ValueError('Campaign001 frozen counts differ')
    inventory = launch_inventory(campaign, output)
    data = {'schema': 'campaign002-qualification-investigation-1', 'built_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'Permanent apparatus qualification companion; not a scored campaign report or completion of the qualification goal.',
            'qualification_state': 'preserved_qualification_history',
            'history': rows, 'history_href': href(index_path, output), 'scored_launch_inventory': inventory,
            'previous': {'counts': counts, 'report_href': href(prior_path.with_name('report.html'), output),
                         'data_href': href(prior_path, output)}, 'recorder_phase_catalog': list(RECORDER_PHASES),
            'empirical_report_href': href(campaign / 'investigation/report.html', output)
                if (campaign / 'investigation/report.html').is_file() else None,
            'empirical_outcome_rows': 0, 'source_sha256': sha(Path(__file__).read_bytes())}
    template = (HERE / 'qualification_template.html').read_text(encoding='utf-8')
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('</', '<\\/').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    html = template.replace('/*__QUALIFICATION_DATA__*/{}', encoded)
    if html == template:
        raise ValueError('Missing qualification template insertion point')
    # Detect concurrent campaign launch metadata changes before publishing status.
    if [str(p.relative_to(campaign)) for p in inventory_paths(campaign)] != [e['file'] for e in inventory['entries']]:
        raise ValueError('Scored launch inventory changed during report build')
    for entry in inventory['entries']:
        if sha((campaign / entry['file']).read_bytes()) != entry['sha256']:
            raise ValueError('Scored launch metadata changed during report build')
    registration = inventory['registration']
    registration_path = campaign.parent.parent / 'Architecture Map/releases/RCI001-C02-frozen-001/registration.json'
    if registration_path.exists() != (registration is not None) or (registration is not None
            and sha(registration_path.read_bytes()) != registration['sha256']):
        raise ValueError('Scored registration changed during report build')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'qualification-report.html').write_text(html, encoding='utf-8', newline='\n')
    (output / 'qualification-data.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    provenance = {'schema': 'campaign002-qualification-provenance-1', 'built_at': data['built_at'],
        'builder_sha256': data['source_sha256'], 'template_sha256': sha(template.encode()), 'report_sha256': sha(html.encode()),
        'data_sha256': sha((output / 'qualification-data.json').read_bytes()),
        'inputs': list(READS), 'outcomes_recomputed': False, 'scored_outcome_files_read': 0,
        'running_qualification_outputs_read': 0, 'campaign001_writes': 0}
    (output / 'qualification-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    return {'report': str(output / 'qualification-report.html'), 'qualifications': len(rows),
            'scored_launch_state': inventory['state'], 'scored_outcome_rows': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, default=HERE / 'qualification-history.json')
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--qa', action='store_true', help='Run companion integrity/static QA after queued generation')
    args = parser.parse_args()
    result = build(args.history.resolve(), args.output.resolve())
    if args.qa:
        import qualification_qa
        result['qa'] = qualification_qa.verify(args.output.resolve())
        (args.output / 'qualification-qa.json').write_text(json.dumps(result['qa'], indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
