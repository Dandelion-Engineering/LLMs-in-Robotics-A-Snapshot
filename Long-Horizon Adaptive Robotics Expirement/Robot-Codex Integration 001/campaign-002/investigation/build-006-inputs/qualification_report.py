"""Queued permanent qualification companion; never fabricates scored slots.

Only explicitly indexed, authenticated completed qualifications are opened.
Terminal failed jobs have a separate metadata-only branch and hash-only links;
their attempt outputs are never consumed as qualification evidence.
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


def diagnostic_links(row, artifacts, output, *, context='Qualification'):
    """Authenticate separately indexed documents without interpreting content.

    These documents may concern another run. They never enter the current
    row's assessment selection, structured analyses, checks or measurements.
    """
    items = row.get('diagnostic_analyses', [])
    if not isinstance(items, list):
        raise ValueError(context + ' diagnostics require a list of separate hash-only links')
    diagnostics, paths, labels = [], set(), set()
    artifact_paths = {Path(a['path']).resolve() for a in artifacts}
    artifact_labels = {a.get('label') for a in artifacts} | {'Original assessment'}
    for item in items:
        if (not isinstance(item, dict) or set(item) != {'label', 'path', 'sha256', 'bytes'}
                or not isinstance(item.get('path'), str) or not Path(item['path']).is_absolute()
                or type(item.get('bytes')) is not int or item['bytes'] < 0
                or not isinstance(item.get('label'), str) or not item['label'].strip()):
            raise ValueError(context + ' diagnostics require separate named analysis/diagnosis links')
        path = Path(item['path'])
        if (re.fullmatch(r'.+-(?:analysis|diagnosis)\.(?:md|json)', path.name) is None
                or path.resolve() in paths | artifact_paths or item['label'] in labels | artifact_labels):
            raise ValueError(context + ' diagnostics require separate named analysis/diagnosis links')
        paths.add(path.resolve())
        labels.add(item['label'])
        bound(item, context.lower() + ' diagnostic document; hash-only link, contents not interpreted', parse=False)
        diagnostics.append({'label': item['label'], 'href': href(path, output), 'sha256': item['sha256'],
                            'bytes': item['bytes'], 'basis': 'diagnostic_link_only'})
    return diagnostics


def failed_queue_row(row, artifacts, output):
    """Terminal execution failure metadata only; never open attempt outputs.

    Diagnostic documents are separate hash-only links. Their contents are not
    parsed into verdicts, checks, measurements, canaries or scientific outcomes.
    """
    contract = row.get('queue_failure_contract', {})
    if (contract.get('schema') != 'campaign002-failed-queue-diagnostic-1'
            or row.get('status') != 'failed' or row.get('validity') != 'unknown'
            or row.get('assessment_state') != 'not_assessed' or row.get('scorable') is not False
            or row.get('task_outcome') != 'unknown' or row.get('model_calls') is not None
            or row.get('details', {}) != {} or any(k in row for k in
                ('assessment', 'checks', 'timing', 'supervisory_timing', 'canary', 'qualification_passed',
                 'smoke_passed', 'pilot_admission', 'admission_disposition', 'preflight_contract'))):
        raise ValueError('Failed queue requires an explicit unassessed diagnostic-only contract')
    labels = {'Official queue receipt': 'official_queue_sha256',
              'Frozen attempt manifest': 'manifest_sha256', 'Frozen source snapshot': 'snapshot_sha256'}
    if len(artifacts) != 3 or {a.get('label') for a in artifacts} != set(labels):
        raise ValueError('Failed queue may index only official receipt, manifest and source snapshot; no outputs')
    indexed = {a['label']: a for a in artifacts}
    for label, key in labels.items():
        item = indexed[label]
        if type(item.get('bytes')) is not int or item.get('sha256') != contract.get(key):
            raise ValueError('Failed queue metadata binding mismatch')
        require_hash(item.get('sha256'))
    official = indexed['Official queue receipt']
    receipt = bound(official, 'terminal failed official queue receipt before any other access')
    job = receipt.get('job', receipt)
    declared = row.get('queue') or {}
    if (job.get('id') != declared.get('id') or job.get('state') != 'failed'
            or type(job.get('exit_status')) is not int or job['exit_status'] == 0
            or ('exit_status' in declared and type(declared['exit_status']) is not int)
            or any(k in declared and declared[k] != job.get(k)
                   for k in ('state', 'exit_status', 'started_at', 'ended_at'))):
        raise ValueError('Terminal official queue failed with integer nonzero exit required')
    try:
        start = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(job['ended_at'].replace('Z', '+00:00'))
        if start.tzinfo is None or end.tzinfo is None or not start <= end:
            raise ValueError('invalid terminal interval')
    except (KeyError, AttributeError, TypeError, ValueError) as error:
        raise ValueError('Failed queue requires a complete official start/end interval') from error
    manifest_item, snapshot_item = indexed['Frozen attempt manifest'], indexed['Frozen source snapshot']
    if (not Path(manifest_item['path']).name.endswith('-manifest.json')
            or Path(snapshot_item['path']).name != 'snapshot.json'):
        raise ValueError('Failed queue manifest/snapshot filenames are not explicit metadata')
    argv = job.get('argv', [])
    if (not isinstance(argv, list) or argv.count('--manifest') != 1
            or argv.index('--manifest') + 1 >= len(argv)):
        raise ValueError('Failed queue exact manifest dispatch is unavailable')
    dispatched = Path(argv[argv.index('--manifest') + 1])
    if not dispatched.is_absolute():
        if not isinstance(job.get('cwd'), str) or not Path(job['cwd']).is_absolute():
            raise ValueError('Failed queue relative manifest lacks an absolute working directory')
        dispatched = Path(job['cwd']) / dispatched
    if dispatched.resolve() != Path(manifest_item['path']).resolve():
        raise ValueError('Failed queue manifest does not match official dispatch')
    manifest = bound(manifest_item, 'failed queue declared manifest metadata only')
    snapshot = bound(snapshot_item, 'failed queue revision snapshot metadata; no source validity inferred')
    if (manifest.get('run_id') != row['run_id'] or manifest.get('framework_revision') != row['revision']
            or snapshot.get('revision') != row['revision']):
        raise ValueError('Failed queue manifest/snapshot run or revision mismatch')
    links = [{'label': a['label'], 'href': href(a['path'], output), 'sha256': a['sha256']} for a in artifacts]
    diagnostics = diagnostic_links(row, artifacts, output, context='Failed queue')
    failure = {'schema': contract['schema'], 'basis': 'official_terminal_execution_failure',
               'assessment_state': 'not_assessed', 'queue_job_id': job['id'],
               'official_queue_sha256': official['sha256'], 'official_queue_href': href(official['path'], output),
               'manifest_sha256': manifest_item['sha256'], 'snapshot_sha256': snapshot_item['sha256'],
               'diagnostic_links': diagnostics,
               'scope': 'The official queue records terminal execution failure. No assessment, timing, canary, model-call count '
                        'or scientific result is derived from failed-attempt outputs. Separate diagnostic documents are linked '
                        'by hash only; they supply no qualification verdict or scored outcome here.'}
    return {'run_id': row['run_id'], 'revision': row['revision'], 'status': 'failed',
            'assessment_schema': None, 'assessment_state': 'not_assessed', 'queue_failure': failure,
            'reason': row.get('reason'), 'model_calls': None, 'scorable': False,
            'validity': 'unknown', 'task_outcome': 'unknown',
            'started_at': job['started_at'], 'ended_at': job['ended_at'], 'job_id': job['id'],
            'queue_state': job['state'], 'queue_exit_status': job['exit_status'],
            'checks': {}, 'failed_checks': [], 'assessment_errors': {}, 'declared_details': {},
            'links': links, 'analyses': [], 'recorder_feasibility': None, 'protected_io': None,
            'pilot_admission': None, 'admission_disposition': None, 'preflight': None,
            'native_reference': None, 'recorder_subphases_declared': False,
            'timing': None, 'supervisory_timing': None}


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


def assessment_host_binding(assessment, artifacts):
    binding = assessment.get('bindings', {}).get('host_result')
    if binding:
        return binding
    # Model assessors retain a file inventory or exact path/hash map instead.
    inventory = [a for a in assessment.get('evidence_inventory', [])
                 if a.get('root') == 'protected_host' and a.get('path') == 'result.json']
    named = assessment.get('evidence_sha256', {})
    candidates = [a for a in artifacts if Path(a['path']).name == 'result.json'
                  and ('host result' in a.get('label','').lower() or Path(a['path']).parent.name == 'host')]
    matches = [a for a in candidates if
        (len(inventory) == 1 and a['sha256'] == inventory[0].get('sha256') and a['bytes'] == inventory[0].get('bytes'))
        or any(Path(p).resolve() == Path(a['path']).resolve() and digest == a['sha256'] for p,digest in named.items())]
    if len(matches) > 1 or (candidates and (inventory or named) and not matches):
        raise ValueError('Indexed protected host result lacks its exact original model-assessment binding')
    return matches[0] if matches else None


def timing_detail(assessment, artifacts, output):
    """Presentation chain only; never replaces a strict timing verdict."""
    binding = assessment_host_binding(assessment, artifacts)
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


def supervisory_detail(assessment, artifacts, owner_timing, output):
    """Explicitly indexed supervisory measurements; no inferred strict verdict."""
    binding = assessment_host_binding(assessment, artifacts)
    if not binding or owner_timing is None:
        return None
    folder = Path(binding['path']).parent / 'supervisory-diagnostics'
    matches = [item for item in artifacts if Path(item['path']).resolve() == (folder/'timing-v2.json').resolve()]
    if not matches:
        return None  # Do not discover or consume unindexed files, even if present.
    if len(matches) != 1:
        raise ValueError('Ambiguous supervisory timing metadata')
    item = matches[0]
    if type(item.get('bytes')) is not int:
        raise ValueError('Supervisory metadata requires an exact byte binding')
    metadata = bound(item, 'separate indexed supervisory persistence metadata')
    if (metadata.get('schema') != 'rci-prospective-timing-2'
            or metadata.get('loop_origin') != owner_timing.get('loop_origin')
            or metadata.get('sample_file') != 'timing-samples.bin'):
        raise ValueError('Supervisory metadata schema, clock origin or sample identity differs')
    sample = folder/'timing-samples.bin'
    entries = [entry for entry in artifacts if Path(entry['path']).resolve() == sample.resolve()]
    if (len(entries) != 1 or type(metadata.get('byte_count')) is not int
            or entries[0].get('sha256') != metadata.get('sha256')
            or entries[0].get('bytes') != metadata['byte_count']):
        raise ValueError('Supervisory sample requires matching indexed metadata and byte binding')
    bound(entries[0], 'separate supervisory sample bytes; diagnostic only', parse=False)
    return {'basis': 'indexed_supervisory_diagnostics', 'strict_verification_available': False, 'strict_passed': None,
        'metadata_href': href(item['path'], output), 'metadata_sha256': item['sha256'],
        'samples': [{'label':'Supervisory diagnostic samples', 'href':href(sample, output), 'sha256':entries[0]['sha256']}],
        **{key:metadata.get(key) for key in ('loop_origin','terminal','phases','slow_phases','slow_phases_by_name','phase_accounting')},
        'scope': 'Separate supervisory Journal/SQLite phases share the owner QPC origin while physics advances on its owner thread. '
            'Inclusive cross-thread intervals overlap and must not be added. These measurements do not establish a timing qualification.'}


def protected_io_detail(assessment, job, official):
    """Interpret this schema's passed field only as completed diagnostic integrity."""
    if assessment.get('schema') != 'rci-c02-protected-io-assessment-1':
        return None
    queue = assessment.get('official_queue')
    if (not isinstance(queue, dict) or not isinstance(queue.get('path'), str)
            or Path(queue['path']).resolve() != Path(official['path']).resolve()
            or queue.get('sha256') != official['sha256']
            or (assessment.get('queue_job_id') is not None and assessment['queue_job_id'] != job['id'])):
        raise ValueError('Protected IO assessment requires its exact bound official queue receipt')
    if (type(assessment.get('passed')) is not bool or assessment.get('qualification_passed') is not False
            or assessment.get('scorable') is not False or assessment.get('task_outcome') != 'unknown'
            or any(key in assessment for key in ('smoke_passed','diagnostic_passed','mechanical_feasibility_passed'))):
        raise ValueError('Protected IO integrity must remain separate from qualification and scoring')
    return {'basis':'original_protected_io_integrity_assessment', 'diagnostic_integrity_passed':assessment['passed'],
        'qualification_passed':False, 'scorable':False, 'task_outcome':'unknown',
        'official_queue_sha256':official['sha256'], 'queue_job_id':job['id'],
        'parity':assessment.get('parity'), 'durability_order_preserved':assessment.get('durability_order_preserved'),
        'duration_s':assessment.get('duration_s'), 'full_operation_rows':assessment.get('full_operation_rows'),
        'distributions':assessment.get('distributions', {}), 'error':assessment.get('error'),
        'result_sha256':assessment.get('result_sha256'), 'manifest_sha256':assessment.get('manifest_sha256'),
        'original_interpretation':assessment.get('interpretation'),
        'scope':'Fixed non-physics shared-durability diagnostic. Passed means completion, parity, ordering and evidence integrity only. '
            'Original per-operation latency is descriptive; no model, recovery score, timing qualification, production adoption or device-cause claim.'}


def pilot_detail(assessment, row, documents, job, official):
    """Display a retained coordinator admission decision, not a new qualification."""
    if assessment.get('schema') != 'robot-codex-campaign-assessment-2':
        return None
    if any(k in assessment for k in ('qualification_passed','smoke_passed','diagnostic_passed','mechanical_feasibility_passed')):
        raise ValueError('Raw pilot cannot acquire an invented qualification verdict flag')
    contract = row.get('pilot_admission', {})
    if contract.get('schema') != 'campaign002-pilot-history-binding-1':
        raise ValueError('Pilot requires its explicit original admission disposition and verifier')
    artifacts = row['artifacts']
    def indexed(key):
        binding = contract.get(key, {})
        matches = [a for a in artifacts if Path(a['path']).resolve() == Path(binding.get('path', '')).resolve()
                   and a.get('sha256') == binding.get('sha256') and a.get('bytes') == binding.get('bytes')]
        if len(matches) != 1:
            raise ValueError('Pilot admission binding must name one exact indexed artifact: ' + key)
        return matches[0]
    disposition_item = indexed('disposition')
    verifier_item = indexed('verifier')
    assessor_item = indexed('base_assessor')
    preflight_item = indexed('preflight')
    preflight = documents.get(preflight_item['path'], {})
    if (preflight.get('schema') not in ('campaign002-final-qualification-preflight-1',
                                      'campaign002-final-qualification-continuation-preflight-1')
            or not any(Path(a.get('path', '')).resolve() == Path(verifier_item['path']).resolve()
                       and a.get('sha256') == verifier_item['sha256']
                       for a in preflight.get('orchestration_sources', []))):
        raise ValueError('Pilot admission verifier is not bound by the original coordinator preflight')
    disposition = documents.get(disposition_item['path'])
    if (not isinstance(disposition, dict) or disposition.get('run_id') != row['run_id']
            or type(disposition.get('passed')) is not bool):
        raise ValueError('Pilot original admission disposition identity/verdict differs')
    entry = disposition.get('entry', {})
    selected = {}
    for name in ('assessment', 'queue', 'manifest', 'snapshot'):
        record = entry.get(name, {})
        matches = [a for a in artifacts if Path(a['path']).resolve() == Path(record.get('path', '')).resolve()
                   and a['sha256'] == record.get('sha256')]
        if len(matches) != 1:
            raise ValueError('Pilot disposition input must match its indexed ' + name)
        selected[name] = matches[0]
    original = documents[selected['assessment']['path']]
    manifest = documents[selected['manifest']['path']]
    snapshot = documents[selected['snapshot']['path']]
    bindings = assessment.get('bindings', {})
    if (original != assessment or selected['queue'] != official
            or bindings.get('queue_receipt_sha256') != official['sha256']
            or bindings.get('manifest_sha256') != selected['manifest']['sha256']
            or bindings.get('framework_snapshot_sha256') != selected['snapshot']['sha256']
            or bindings.get('assessment_sha256') != assessor_item['sha256']
            or manifest.get('run_id') != row['run_id'] or manifest.get('framework_revision') != row['revision']
            or snapshot.get('revision') != row['revision'] or assessment.get('queue_job_id') != job['id']):
        raise ValueError('Pilot original assessor, queue or frozen input binding differs')
    source_matches = [v for name, v in snapshot.get('sources', {}).items()
                      if (REPO / name).resolve() == Path(assessor_item['path']).resolve()]
    if (len(source_matches) != 1 or source_matches[0].get('sha256') != assessor_item['sha256']
            or Path(assessor_item['path']).name != 'assess.py' or Path(verifier_item['path']).name != 'admission.py'):
        raise ValueError('Pilot base assessor must be the exact frozen source')
    archive = Path(selected['snapshot']['path']).with_name('code.zip')
    archive_hash = bindings.get('framework_archive_sha256')
    require_hash(archive_hash)
    consume(archive, 'pilot assessment-bound frozen archive; hash verification only', archive_hash, parse=False)
    # Read declared check names without executing the indexed admission code.
    tree = ast.parse(bound(verifier_item, 'original pilot admission check contract', parse=False).decode('utf-8-sig'))
    required = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PILOT_CHECKS' for t in node.targets):
            required = ast.literal_eval(node.value)
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name)
                and node.value.func.value.id == 'PILOT_CHECKS'):
            if required is None or node.value.func.attr != 'add' or len(node.value.args) != 1:
                raise ValueError('Unsupported original pilot check declaration')
            required.add(ast.literal_eval(node.value.args[0]))
    if not isinstance(required, set) or not required or not all(isinstance(x, str) for x in required):
        raise ValueError('Original pilot admission check names are unavailable')
    family = manifest.get('family')
    timing = assessment.get('campaign_timing') or {}
    eligible = (assessment.get('validity') == 'valid' and assessment.get('failed_checks') == []
        and assessment.get('task_evidence_valid') is True and assessment.get('task_outcome') in ('success', 'failure')
        and assessment.get('scorable') is False and family in ('misplaced-stock', 'blocked-insert-home')
        and assessment.get('family') == entry.get('family') == family
        and manifest.get('model') == 'gpt-6-astra' and manifest.get('effort') == 'max'
        and manifest.get('bootstrap') == 'Follow the instructions in RobotAgentPrompt.md.'
        and manifest.get('model_turns_max') == 1 and manifest.get('interruption_trigger') is None
        and manifest.get('noise_seed') == {'misplaced-stock':24102, 'blocked-insert-home':24103}.get(family)
        and all(assessment.get('checks', {}).get(k) is True for k in required)
        and timing.get('schema') == 'rci-campaign-independent-timing-2'
        and all(timing.get(k) is True for k in ('passed','scheduling_pass','resource_integrity_pass',
                                             'garbage_collection_pass','host_memory_pass')))
    if disposition['passed'] and not eligible:
        raise ValueError('Passed pilot admission contradicts its original assessment or declared checks')
    return {'basis':'original_coordinator_admission_disposition', 'admission_passed':disposition['passed'],
        'original_validity':assessment.get('validity'), 'task_evidence_valid':assessment.get('task_evidence_valid'),
        'observed_task_outcome':assessment.get('observed_task_outcome', assessment.get('task_outcome')),
        'assessed_task_outcome':assessment.get('task_outcome'), 'family':family,
        'required_admission_checks':sorted(required), 'original_admission_error':disposition.get('error'),
        'archive_path':str(archive), 'archive_sha256':archive_hash,
        'scope':'Original one-invocation pilot apparatus admission. A valid task failure can pass this contract; '
            'task outcome is shown separately. No qualification flag is invented and no scored campaign result or admission certificate is inferred.'}


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


def native_reference_detail(assessment):
    if assessment.get('schema') != 'campaign002-native-assessment-1':
        return None
    rows = assessment.get('rows', [])
    if (len(rows) != 6 or len({r.get('run_id') for r in rows}) != 6
            or any(not isinstance(r.get('run_id'), str) or type(r.get('passed')) is not bool
                   or not isinstance(r.get('checks'), dict) for r in rows)):
        raise ValueError('Native assessment requires its six separate reference cases')
    cases = []
    for row in rows:
        timing = row.get('timing')
        replay = (timing or {}).get('replayed_timing', {})
        cases.append({'run_id':row['run_id'], 'family':row.get('family'), 'passed':row['passed'],
            'checks':row['checks'], 'errors':row.get('errors', {}), 'terminal':row.get('terminal'),
            'observed_reference_task_outcome':row.get('independent_outcome', {}).get('independent_task_outcome'),
            'timing_summary': None if timing is None else {
                'passed':timing.get('passed'), 'maximum_lag_s':replay.get('maximum_lag_s'),
                'outside_rtf_tolerance_windows':replay.get('outside_rtf_tolerance_windows'),
                'complete_wall_windows':replay.get('complete_wall_windows'),
                'resource_integrity_pass':timing.get('resource_integrity_pass'),
                'garbage_collection_pass':timing.get('garbage_collection_pass'),
                'host_memory_pass':timing.get('host_memory_pass')}})
    return {'cases':cases, 'scope':'Original independent native-reference assessment, with each case preserved separately. Reference task completion does not override a strict timing failure and is not a scored model recovery. Missing older resource fields remain unavailable.'}


def analysis_queue_binding(value, official, job):
    provenance = value.get('provenance', {})
    named = provenance.get('official_queue_receipt')
    if named is not None:
        if not isinstance(named, dict) or named.get('sha256') != official['sha256']:
            raise ValueError('Retained analysis queue hash mismatch')
        return
    matches = [v for v in provenance.get('bindings', []) if isinstance(v, dict)
               and (REPO / v.get('path', '')).resolve() == Path(official['path']).resolve()]
    if (len(matches) != 1 or matches[0].get('sha256') != official['sha256']
            or matches[0].get('bytes') != official['bytes'] or value.get('official_receipt') != job):
        raise ValueError('Retained analysis queue path/hash/receipt mismatch')


def admission_disposition_detail(row, documents, official):
    binding = row.get('admission_disposition')
    if binding is None:
        return None
    matches = [a for a in row['artifacts'] if Path(a['path']).resolve() == Path(binding.get('path','')).resolve()
               and a['sha256'] == binding.get('sha256') and a['bytes'] == binding.get('bytes')]
    if len(matches) != 1:
        raise ValueError('Original admission disposition requires one exact indexed binding')
    value = documents.get(matches[0]['path'], {})
    if (value.get('run_id') != row['run_id'] or type(value.get('passed')) is not bool
            or value['passed'] is not (row['status'] == 'passed')):
        raise ValueError('History status differs from original coordinator admission disposition')
    selected = {}
    for key in ('manifest','snapshot','queue','assessment'):
        item = value.get('entry', {}).get(key, {})
        entries = [a for a in row['artifacts'] if Path(a['path']).resolve() == Path(item.get('path','')).resolve()
                   and a['sha256'] == item.get('sha256')]
        if len(entries) != 1:
            raise ValueError('Original admission disposition input differs: ' + key)
        selected[key] = entries[0]
    manifest = documents[selected['manifest']['path']]
    snapshot = documents[selected['snapshot']['path']]
    raw = documents[selected['assessment']['path']]
    if (selected['queue'] != official or manifest.get('run_id') != row['run_id']
            or manifest.get('framework_revision') != row['revision'] or snapshot.get('revision') != row['revision']):
        raise ValueError('Original admission disposition manifest/revision/queue differs')
    flags = [raw[k] for k in ('qualified','qualification_passed','smoke_passed') if k in raw]
    if len(flags) != 1 or type(flags[0]) is not bool or (value['passed'] and not flags[0]):
        raise ValueError('Original admission cannot promote a failed or unknown raw suite verdict')
    return {'basis':'original_coordinator_admission_disposition', 'admission_passed':value['passed'],
            'original_raw_passed':flags[0], 'error':value.get('error'),
            'disposition_sha256':matches[0]['sha256'],
            'scope':'Raw suite checks and the final source-bound admission decision remain separate. '
                    'A completed passing suite can still fail admission; this report does not rerun that decision.'}


def qualification_row(row, output):
    if row.get('status') not in ('passed', 'failed', 'cancelled', 'not_run'):
        raise ValueError('Only explicit completed qualification statuses are supported')
    artifacts = row.get('artifacts', [])
    if 'queue_failure_contract' in row:
        return failed_queue_row(row, artifacts, output)
    preflight = preflight_gate(row, artifacts) if row['status'] == 'not_run' else None
    job, official = ({}, None) if preflight else job_gate(row, artifacts)  # Before any outcome read.
    diagnostics = diagnostic_links(row, artifacts, output)
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
    protected_io = protected_io_detail(assessment, job, official) if assessment else None
    pilot = pilot_detail(assessment, row, documents, job, official) if assessment else None
    admission = admission_disposition_detail(row, documents, official)
    if assessment:
        if (assessment.get('run_id') != row['run_id']
                or (protected_io is None and assessment.get('queue_job_id') != job['id'])
                or assessment.get('framework_revision') != row['revision']):
            raise ValueError('Assessment run/revision/queue identity mismatch')
        flags = ([pilot['admission_passed']] if pilot is not None else
                 [protected_io['diagnostic_integrity_passed']] if protected_io is not None else
                 [assessment[k] for k in ('qualification_passed', 'smoke_passed', 'diagnostic_passed',
                                         'mechanical_feasibility_passed') if k in assessment])
        if (len(flags) != 1 or type(flags[0]) is not bool
                or (admission is None and flags[0] != (row['status'] == 'passed'))):
            raise ValueError('History status differs from original assessment verdict')
    elif row['status'] not in ('cancelled', 'not_run'):
        suites = [(Path(p), v) for p, v in documents.items() if Path(p).name == 'suite-result.json']
        argv = job.get('argv', [])
        if (len(suites) != 1 or '--output' not in argv
                or not any(suites[0][0].parent.resolve() == p.resolve() for p in
                           (Path(argv[argv.index('--output') + 1]), Path(job['cwd']) / argv[argv.index('--output') + 1]))
                or type(suites[0][1].get('qualified')) is not bool
                or (admission is None and suites[0][1]['qualified'] is not (row['status'] == 'passed'))):
            raise ValueError('Boundary verdict/output path is not bound to official job')
        assessment = suites[0][1]
    analyses = []
    for path, value in documents.items():
        if not Path(path).name.endswith('-analysis.json'):
            continue
        if value.get('run_id') != row['run_id'] or value.get('queue_job_id') != job['id']:
            raise ValueError('Retained analysis identity mismatch')
        analysis_queue_binding(value, official, job)
        analyses.append({'href': href(path, output), 'schema': value.get('schema'),
                         'content': {k: v for k, v in value.items() if k != 'provenance'},
                         'scope': 'Original hashed analysis retained verbatim as structured data; no correlation recomputation.'})
    snapshot = next((v for p, v in documents.items() if Path(p).name == 'snapshot.json'), {})
    checks = dict((assessment or {}).get('checks', {}))
    native = native_reference_detail(assessment) if assessments else None
    if native:
        for case in native['cases']:
            checks.update({case['run_id'] + '::' + key: passed for key, passed in case['checks'].items()})
    timing = timing_detail(assessment, artifacts, output) if assessments else None
    supervisory = supervisory_detail(assessment, artifacts, timing, output) if assessments else None
    if supervisory:
        links.append({'label':'Separate supervisory persistence metadata', 'href':supervisory['metadata_href'],
                      'sha256':supervisory['metadata_sha256']})
        links.extend(supervisory['samples'])
    if pilot:
        links.append({'label':'Pilot assessment-bound frozen archive', 'href':href(pilot['archive_path'], output),
                      'sha256':pilot['archive_sha256']})
    return {'run_id': row['run_id'], 'revision': row['revision'], 'status': row['status'],
            'assessment_schema': (assessment or {}).get('schema'),
            'reason': row.get('reason'), 'model_calls': row.get('model_calls'), 'scorable': False,
            'validity': row.get('validity', 'unknown'), 'task_outcome': 'unknown',
            'started_at': job.get('started_at'), 'ended_at': job.get('ended_at'), 'job_id': job.get('id'),
            'queue_state': job.get('state'), 'queue_exit_status': job.get('exit_status'),
            'checks': checks, 'failed_checks': [key for key, passed in checks.items() if passed is not True],
            'assessment_errors': (assessment or {}).get('errors', (assessment or {}).get('verification_errors', {})),
            'declared_details': row.get('details', {}), 'links': links, 'analyses': analyses,
            'diagnostic_links': diagnostics,
            'recorder_feasibility': feasibility_detail(assessment) if assessments else None,
            'protected_io': protected_io,
            'pilot_admission': pilot,
            'admission_disposition': admission,
            'preflight': preflight,
            'native_reference': native,
            'recorder_subphases_declared': any(name.endswith('/harness/instrumented_recorder.py')
                                               for name in snapshot.get('sources', {})),
            'timing': timing, 'supervisory_timing': supervisory}


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


def current_status_detail(closeout, rows, index, inventory, campaign, output):
    if closeout is None:
        return None
    states = {'qualification_failed_blocked', 'qualification_in_progress',
              'qualified_campaign_in_progress', 'campaign_terminal'}
    state = closeout.get('state')
    basis = next((row for row in rows if row['run_id'] == closeout.get('basis_run_id')), None)
    queue_basis = (basis is not None and basis.get('queue_failure') is not None
                   and state in ('qualification_failed_blocked', 'qualification_in_progress')
                   and closeout.get('basis_assessment_sha256') is None
                   and closeout.get('basis_queue_sha256') == basis['queue_failure']['official_queue_sha256'])
    if (closeout.get('schema') != 'campaign002-qualification-closeout-status-1' or state not in states
            or basis is None or (not queue_basis and not any(a['sha256'] == closeout.get('basis_assessment_sha256')
                and (a['href'].endswith('-assessment.json') or
                     (basis.get('assessment_schema') == 'campaign002-boundary-suite-1' and a['href'].endswith('suite-result.json')))
                for a in basis['links']))):
        raise ValueError('Qualification closeout must bind its original failed assessment or completed latest qualifier')
    if queue_basis and basis is not next((r for r in reversed(rows) if r['status'] in ('passed', 'failed')), None):
        raise ValueError('Failed-queue current status must bind the latest completed attempt')
    if state == 'qualification_failed_blocked':
        if basis['status'] != 'failed':
            raise ValueError('Qualification closeout must bind its original failed assessment')
    elif basis is not next((r for r in reversed(rows) if r['status'] in ('passed','failed')), None):
        raise ValueError('Current status must bind the latest completed qualifier')
    value = dict(closeout, links=[], current_for_launch_inventory=(not inventory['entries']
                 if state in ('qualification_failed_blocked','qualification_in_progress') else True))
    if queue_basis:
        value['basis_kind'] = 'official_terminal_execution_failure_without_assessment'
        value['links'].append({'label': 'Official terminal failed queue receipt; no assessment',
                               'href': basis['queue_failure']['official_queue_href'],
                               'sha256': basis['queue_failure']['official_queue_sha256']})
    for item in closeout.get('artifacts', []):
        if type(item.get('bytes')) is not int:
            raise ValueError('Closeout document byte binding required')
        bound(item, 'bound current-status context document', parse=False)
        value['links'].append({'label':item['label'], 'href':href(item['path'], output), 'sha256':item['sha256']})
    def document(key, label):
        item = closeout.get(key)
        if not isinstance(item, dict) or type(item.get('bytes')) is not int:
            raise ValueError('Current status requires explicit path/hash/bytes binding: ' + key)
        result = bound(item, 'current-status ' + key)
        value['links'].append({'label':label, 'href':href(item['path'], output), 'sha256':item['sha256']})
        return result
    if state in ('qualified_campaign_in_progress','campaign_terminal'):
        ledger = document('final_ledger', 'Completed final qualification ledger')
        if ledger.get('schema') != 'campaign002-final-qualification-completed-1' or len(ledger.get('pilots', [])) != 2:
            raise ValueError('Current status requires the complete five-stage final ledger')
        entries = [ledger.get(k, {}) for k in ('native','boundary','smoke')] + ledger['pilots']
        history_matches = []
        for entry in entries:
            candidates = [r for r in index['attempts'] if all(any(
                Path(a['path']).resolve() == Path(entry.get(k, {}).get('path', '')).resolve()
                and a['sha256'] == entry.get(k, {}).get('sha256') for a in r['artifacts'])
                for k in ('manifest','snapshot','queue','assessment'))]
            if len(candidates) != 1 or candidates[0]['status'] != 'passed':
                raise ValueError('Final ledger requires five exact passed history bindings')
            history_matches.append(candidates[0]['run_id'])
        if (len(set(history_matches)) != 5 or basis['run_id'] != history_matches[-1]
                or {p.get('family') for p in ledger['pilots']} != {'misplaced-stock','blocked-insert-home'}):
            raise ValueError('Final ledger stage identities or family coverage differ')
        kinds = ['campaign002-native-assessment-1','campaign002-boundary-suite-1',
                 'robot-codex-physical-smoke-assessment-2'] + ['robot-codex-campaign-assessment-2'] * 2
        if any(next(r for r in rows if r['run_id'] == identity).get('assessment_schema') != kind
               for identity,kind in zip(history_matches,kinds)):
            raise ValueError('Final ledger stages do not preserve native/boundary/smoke/pilot roles')
        value['final_qualification_run_ids'] = history_matches
    if state == 'campaign_terminal':
        plan = document('terminal_plan', 'Exact terminal campaign plan')
        attempts = plan.get('attempts', [])
        expected = {f'RCI001-C02-{f}-{n:02}' for f in ('stock','home') for n in range(1,11)}
        if (plan.get('schema') != 'campaign002-execution-plan-1' or plan.get('campaign_id') != 'RCI001-Campaign002'
                or len(attempts) != 20 or [a.get('ordinal') for a in attempts] != list(range(1,21))
                or {a.get('run_id') for a in attempts} != expected
                or any(a.get('family') != ('misplaced-stock' if '-stock-' in a['run_id'] else 'blocked-insert-home') for a in attempts)
                or Path(closeout['terminal_plan']['path']).resolve() != (campaign/'execution-plan.json').resolve()):
            raise ValueError('Terminal current status requires the exact twenty-slot plan')
        stop = document('terminal_stop', 'Original campaign terminal stop accounting')
        after = stop.get('stop_after_ordinal')
        if (stop.get('schema') != 'campaign002-stop-1' or stop.get('planned') != 20
                or stop.get('remaining_admission_authorized') is not False or type(after) is not int or not 1 <= after <= 20
                or Path(closeout['terminal_stop']['path']).resolve() != (campaign/'execution/campaign-stop.json').resolve()):
            raise ValueError('Terminal current status requires exact original stop accounting')
        dispositions = closeout.get('terminal_dispositions', [])
        if len(dispositions) != 20:
            raise ValueError('Terminal current status requires all twenty disposition bindings')
        for attempt, item in zip(attempts, dispositions):
            if (type(item.get('bytes')) is not int or Path(item.get('path','')).resolve() !=
                    (campaign/'execution'/attempt['run_id']/'disposition.json').resolve()):
                raise ValueError('Terminal disposition path/bytes differ from the plan')
            disposition = bound(item, 'terminal disposition metadata; no outcome assessment read')
            if (any(disposition.get(k) != attempt.get(k) for k in ('run_id','ordinal','family'))
                    or disposition.get('execution_status') not in {'completed','failed','timed_out','aborted','not_run','cancelled','canceled'}
                    or (attempt['ordinal'] > after and disposition.get('execution_status') != 'not_run')):
                raise ValueError('Terminal disposition is pending, mismatched or contradicts the stop')
            value['links'].append({'label':attempt['run_id']+' terminal disposition', 'href':href(item['path'], output), 'sha256':item['sha256']})
        value['terminal_disposition_count'] = 20
    value['scope'] = ('Status describes retained qualification decisions and launch/terminal metadata only. '
                      'No scientific admission certificate is reverified and no scored outcomes are read or recomputed here.')
    return value


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
    closeout = current_status_detail(index.get('current_status'), rows, index, inventory, campaign, output)
    data = {'schema': 'campaign002-qualification-investigation-1', 'built_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'Permanent apparatus qualification companion; not a scored campaign report or completion of the qualification goal.',
            'qualification_state': closeout['state'] if closeout and closeout['current_for_launch_inventory'] else 'preserved_qualification_history',
            'qualification_closeout': closeout,
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
