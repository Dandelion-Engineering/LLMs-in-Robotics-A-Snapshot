"""Additive Campaign 001 registration. No model, simulator or queue submission.

prepare creates an immutable preview; append publishes exactly that preview with
the map's optimistic store guard. Source archives and runtime labels are retained.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
EXPERIMENT = CAMPAIGN.parent.parent
REPO = EXPERIMENT.parent
MAP = EXPERIMENT / 'Architecture Map'
REVISION = 'RCI001-C01-frozen-001'
SOURCE = 'RCI001-wsl-010d'
CAMPAIGN_ID = 'RCI001-Campaign001'
PROTOCOL = 'RCI001-Campaign001-evaluation-v1'
SOURCE_COUNT = 624
spec = importlib.util.spec_from_file_location('campaign_architecture_map', MAP / 'map.py')
am = importlib.util.module_from_spec(spec)
spec.loader.exec_module(am)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return am.strict_json(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(am.json_bytes(value))


def identity(path):
    return {'path': str(Path(path).resolve(strict=True)), 'sha256': sha(path)}


def verify_identity(item):
    path = Path(item['path'])
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or sha(path) != item['sha256']:
        raise ValueError('Artifact identity mismatch: ' + str(path))
    return path


def store(root, expected):
    data, raw, errors = am.read_store(root)
    errors += am.validate_records(data, root)
    if errors:
        raise ValueError('; '.join(errors))
    current = am.store_digest(raw)
    if expected != current:
        raise ValueError('Architecture store changed; inspect current status before retrying')
    return data, raw


def common(identifier, stamp):
    return {'schema_version': am.SCHEMA, 'id': identifier, 'recorded_at': stamp,
            'author': 'Codex Campaign 001',
            'tags': ['robot-codex-integration-001', 'campaign-001', 'known-fixture-repeatability'],
            'details': {}}


def reference(root, label, path, access='operator', hash_value=None):
    return {'label': label, 'uri': Path(os.path.relpath(path, root)).as_posix(),
            'sha256': hash_value or sha(path), 'state': 'available', 'access': access, 'locator': None}


def recorded(ref):
    return {'state': 'recorded', 'refs': [ref], 'reason': None}


def certificate(path, expected):
    path = Path(path).resolve(strict=True)
    if sha(path) != expected:
        raise ValueError('Admission certificate differs from trusted SHA256')
    admission_spec = importlib.util.spec_from_file_location('campaign_registration_admission', CAMPAIGN / 'assessment/admitted.py')
    admission = importlib.util.module_from_spec(admission_spec)
    sys.path.insert(0, str(CAMPAIGN / 'assessment'))
    try:
        admission_spec.loader.exec_module(admission)
    finally:
        sys.path.remove(str(CAMPAIGN / 'assessment'))
    # Validate actual qualification evidence; a boolean claim cannot grant admission.
    cert = admission.verify_certificate(path, expected)
    if (cert.get('schema') != 'rci-campaign-scientific-admission-1'
            or cert.get('campaign_id') != CAMPAIGN_ID or cert.get('framework_revision') != SOURCE
            or cert.get('release_revision') != REVISION or cert.get('source_count') != SOURCE_COUNT):
        raise ValueError('Wrong campaign admission identity')
    artifacts = cert['artifacts']
    required = {'protocol', 'schedule', 'snapshot', 'archive', 'assessor', 'admitted_assessor',
                'timing_source', 'approval', 'storage_monitor', 'storage_policy',
                'retained_timing', 'retained_timing_queue'}
    if not required <= artifacts.keys():
        raise ValueError('Admission certificate lacks required artifacts')
    for item in artifacts.values():
        verify_identity(item)
    conditions = cert['conditions']
    if conditions.get('maximum_attempts') != 24 or any(conditions.get(key) is not True for key in (
            'no_replacements', 'no_injected_restart', 'no_tuning')):
        raise ValueError('Campaign conditions changed')
    snapshot = read(artifacts['snapshot']['path'])
    if snapshot['revision'] != SOURCE or len(snapshot['sources']) != SOURCE_COUNT:
        raise ValueError('Wrong original qualified snapshot')
    with zipfile.ZipFile(artifacts['archive']['path']) as archive:
        if len(archive.namelist()) != len(snapshot['sources']) or set(archive.namelist()) != set(snapshot['sources']):
            raise ValueError('Archive source membership differs')
        for name, item in snapshot['sources'].items():
            source = REPO / name
            if Path(name).is_absolute() or '..' in Path(name).parts or source.is_symlink():
                raise ValueError('Unsafe frozen source path')
            if not source.is_file() or source.stat().st_size != item['bytes'] or sha(source) != item['sha256']:
                raise ValueError('Qualified source changed: ' + name)
            payload = archive.read(name)
            if len(payload) != item['bytes'] or hashlib.sha256(payload).hexdigest() != item['sha256']:
                raise ValueError('Qualified archive bytes changed: ' + name)
    schedule = read(artifacts['schedule']['path'])
    slots = schedule['slots']
    if (schedule.get('source_revision') != SOURCE or schedule.get('source_snapshot_sha256') != artifacts['snapshot']['sha256']
            or schedule.get('attempt_count') != 24 or len(slots) != 24
            or [s['ordinal'] for s in slots] != list(range(1, 25))
            or [s['noise_seed'] for s in slots] != list(range(22001, 22025))
            or any(s['world_seed'] != 173 or s['maximum_model_invocations'] != 1 for s in slots)
            or len({s['run_id'] for s in slots}) != 24):
        raise ValueError('Predeclared allocation differs')
    if len(cert['attempts']) != 24 or [a['run_id'] for a in cert['attempts']] != [s['run_id'] for s in slots]:
        raise ValueError('Admission attempt order differs')
    for slot, attempt in zip(slots, cert['attempts']):
        manifest_path = verify_identity(attempt['manifest'])
        expected_path = Path(artifacts['schedule']['path']).parent / slot['manifest']
        manifest = read(manifest_path)
        if (manifest_path.resolve() != expected_path.resolve() or slot['sha256'] != attempt['manifest']['sha256']
                or attempt['ordinal'] != slot['ordinal'] or attempt['workspace'] != slot['runtime_workspace']
                or manifest['run_id'] != slot['run_id'] or manifest['family'] != slot['family']
                or manifest['seed'] != slot['world_seed'] or manifest['noise_seed'] != slot['noise_seed']
                or manifest['stage'] != 'development-only' or manifest['model'] != 'gpt-6-astra'
                or manifest['effort'] != 'max' or manifest['bootstrap'] != 'Follow the instructions in RobotAgentPrompt.md.'
                or manifest['interruption_trigger'] is not None):
            raise ValueError('Admission attempt differs from immutable schedule: ' + slot['run_id'])
    return cert, schedule


def shadow_validate(root, data, assets):
    """Validate real map records in a temporary attachment view; no map mutation."""
    with tempfile.TemporaryDirectory(prefix='rci-c01-map-validation-') as directory:
        shadow = Path(directory)
        refs = {r['uri'] for rev in data['revision'] for r in rev['attachments']}
        for name in refs:
            target = shadow / name
            target.parent.mkdir(parents=True, exist_ok=True)
            source = assets.get(name, root / name)
            # Hardlink only immutable attachments; the temporary view is read-only.
            try:
                os.link(source, target)
            except OSError:
                shutil.copyfile(source, target)
        errors = am.validate_records(data, shadow)
        if errors:
            raise ValueError('; '.join(errors))


def prepare(args):
    root = args.map_root.resolve(strict=True)
    data, _ = store(root, args.expected_sha256)
    cert, schedule = certificate(args.certificate, args.certificate_sha256)
    known = {r['id'] for records in data.values() for r in records}
    if REVISION in known or any(s['run_id'] in known for s in schedule['slots']):
        raise ValueError('Campaign revision or runs already registered; do not recreate the preview')
    original = next((r for r in data['revision'] if r['id'] == SOURCE), None)
    if original is None or original['architecture_id'] != 'RCI001':
        raise ValueError('Qualified source revision missing')
    bundle = args.output.resolve()
    bundle.mkdir(parents=True, exist_ok=False)
    payload = bundle / 'payload'
    payload.mkdir()
    stamp = now()
    final = root / 'releases' / REVISION
    mapping = {}

    def freeze(name, source):
        destination = payload / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        mapping[(final / name).relative_to(root).as_posix()] = destination
        return reference(root, name, final / name, hash_value=sha(destination))

    cert_ref = freeze('admission-certificate.json', args.certificate)
    protocol_ref = freeze('protocol.md', cert['artifacts']['protocol']['path'])
    schedule_ref = freeze('schedule.json', cert['artifacts']['schedule']['path'])
    freeze('registration-helper.py', Path(__file__))
    snapshot_path = Path(cert['artifacts']['snapshot']['path'])
    archive_path = Path(cert['artifacts']['archive']['path'])
    for path in (snapshot_path, archive_path):
        if not path.resolve().is_relative_to(root):
            raise ValueError('Original qualified source artifacts must remain inside the map')
    source_ref = reference(root, 'Unchanged original 010d source snapshot', snapshot_path)
    archive_ref = reference(root, 'Unchanged original 010d implementation archive', archive_path)
    revision = {**common(REVISION, stamp), 'architecture_id': 'RCI001', 'parent_revision_id': SOURCE,
        'status': 'frozen', 'title': 'Campaign 001 metadata freeze of exact RCI001-wsl-010d',
        'summary': 'Metadata-only evaluation admission of 624 unchanged qualified source files; known-fixture repeatability only.',
        'mechanism': original['mechanism'] + '\n\nCampaign 001 addendum: implementation, prompts and runtime development labels above remain unchanged. '
            'The outer prospective protocol registers 24 repeated attempts on two known fixtures under separate scientific admission. '
            'No held-out geometry, new framework, injected restart or causal memory comparison is claimed.',
        'attachments': [archive_ref, source_ref, cert_ref, protocol_ref, schedule_ref]}
    revision['details'] = {'campaign_id': CAMPAIGN_ID, 'metadata_only': True,
        'source_revision': SOURCE, 'source_count': SOURCE_COUNT,
        'source_snapshot_sha256': cert['artifacts']['snapshot']['sha256'],
        'certificate_sha256': args.certificate_sha256,
        'runtime_stage_preserved': 'development-only', 'protocol_id': PROTOCOL}
    records = [('revision', revision)]
    attempts = []
    for slot, attempt in zip(schedule['slots'], cert['attempts']):
        rid = slot['run_id']
        manifest_ref = freeze('manifests/' + rid + '.json', attempt['manifest']['path'])
        manifest_ref['access'] = 'evaluator_only'
        manifest = read(attempt['manifest']['path'])
        run = {**common(rid, stamp), 'revision_id': REVISION, 'stage': 'evaluation',
            'condition_id': 'fixed-fixture-fresh-invocation', 'protocol_id': PROTOCOL,
            'scenario_id': slot['family'] + '-world173', 'paired_block_id': 'unpaired-' + rid,
            'replicate': slot['within_family_replicate'], 'started_at': None, 'rerun_of_run_id': None,
            'condition_details': {'manifest': manifest, 'runtime_manifest_sha256': slot['sha256'],
                'ordinal': slot['ordinal'], 'runtime_workspace': attempt['workspace'],
                'host_stage_label_preserved': True, 'scope': schedule['estimand'],
                'pairing': 'Balanced scheduling is not a paired architecture comparison.',
                'maximum_model_invocations': 1, 'no_replacements': True,
                'evidence': attempt['evidence'], 'host_evidence': attempt['host_evidence'],
                'storage_receipt': attempt['storage_receipt']},
            'seeds': recorded(manifest_ref),
            'frozen_refs': {'code': recorded(archive_ref), 'environment': recorded(source_ref),
                'models': recorded(source_ref), 'protocol': recorded(protocol_ref),
                'scenario': recorded(manifest_ref), 'admission': recorded(cert_ref)},
            'evidence': [manifest_ref, schedule_ref, cert_ref]}
        run['details'] = {'campaign_id': CAMPAIGN_ID, 'certificate_sha256': args.certificate_sha256,
                          'source_revision': SOURCE, 'source_snapshot_sha256': source_ref['sha256']}
        records.append(('run', run))
        attempts.append({'run_id': rid, 'manifest_sha256': slot['sha256'],
                         'run_record': {'path': str(final / 'runs' / (rid + '.json')), 'sha256': None}})
    proposed = {kind: list(items) for kind, items in data.items()}
    for kind, record in records:
        proposed[kind].append(record)
        name = 'revision-record.json' if kind == 'revision' else 'runs/' + record['id'] + '.json'
        write_new(payload / name, record)
        mapping[(final / name).relative_to(root).as_posix()] = payload / name
    shadow_validate(root, proposed, mapping)
    for item in attempts:
        item['run_record']['sha256'] = sha(payload / 'runs' / (item['run_id'] + '.json'))
    binding = {'schema': 'rci-campaign-registration-1', 'campaign_id': CAMPAIGN_ID,
        'certificate_sha256': args.certificate_sha256, 'release_revision': REVISION,
        'release_snapshot': identity(snapshot_path), 'release_archive': identity(archive_path),
        'source_snapshot_sha256': source_ref['sha256'],
        'release_record': {'path': str(final / 'revision-record.json'), 'sha256': sha(payload / 'revision-record.json')},
        'map_root': str(root), 'attempts': attempts}
    write_new(payload / 'registration.json', binding)
    mapping[(final / 'registration.json').relative_to(root).as_posix()] = payload / 'registration.json'
    manifest = {'schema': 'rci-campaign-registration-preview-1', 'created_at': stamp,
        'map_root': str(root), 'store_sha256_at_prepare': args.expected_sha256,
        'certificate': identity(args.certificate),
        'files': {name: {'source': str(path.relative_to(bundle)), 'sha256': sha(path)} for name, path in mapping.items()},
        'records': [{'kind': kind, 'path': 'payload/revision-record.json' if kind == 'revision'
                     else 'payload/runs/' + record['id'] + '.json'} for kind, record in records]}
    write_new(bundle / 'preview.json', manifest)
    return {'dry_run': True, 'preview': str(bundle / 'preview.json'), 'preview_sha256': sha(bundle / 'preview.json'),
            'revision': REVISION, 'immutable_runs': 24, 'map_unchanged': True}


def append(args):
    root = args.map_root.resolve(strict=True)
    data, raw = store(root, args.expected_sha256)
    preview_path = args.preview.resolve(strict=True)
    if sha(preview_path) != args.preview_sha256:
        raise ValueError('Preview seal changed')
    preview = read(preview_path)
    if preview['schema'] != 'rci-campaign-registration-preview-1' or Path(preview['map_root']).resolve() != root:
        raise ValueError('Preview belongs to another map')
    certificate(preview['certificate']['path'], preview['certificate']['sha256'])
    assets = {}
    final = root / 'releases' / REVISION
    for name, item in preview['files'].items():
        source = (preview_path.parent / item['source']).resolve(strict=True)
        target = (root / name).resolve()
        if not source.is_relative_to(preview_path.parent) or not target.is_relative_to(final):
            raise ValueError('Preview path escape')
        if sha(source) != item['sha256']:
            raise ValueError('Immutable preview asset changed: ' + name)
        if target.exists() and sha(target) != item['sha256']:
            raise ValueError('Existing release artifact differs: ' + name)
        assets[name] = source
    records = [(r['kind'], read(preview_path.parent / r['path'])) for r in preview['records']]
    known = {r['id']: r for items in data.values() for r in items}
    proposed = {kind: list(items) for kind, items in data.items()}
    pending = []
    for kind, record in records:
        if record['id'] in known:
            if known[record['id']] != record:
                raise ValueError('Existing canonical record differs; cannot resume')
        else:
            proposed[kind].append(record)
            pending.append((kind, record))
    shadow_validate(root, proposed, assets)
    for name, source in assets.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open('xb') as out, source.open('rb') as inp:
                shutil.copyfileobj(inp, out)
    for kind, record in pending:
        am.append_record(root, kind, record, am.store_digest(raw))
        raw[am.KINDS[kind]] += (json.dumps(record, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()
    refresh(root)
    return {'appended': len(pending), 'revision': REVISION, 'registered_runs': 24,
            'registration': str(final / 'registration.json'), 'registration_sha256': sha(final / 'registration.json'),
            'store_sha256': am.store_digest(raw)}


def refresh(root):
    for command in (['build'], ['validate', '--output', 'validation.json']):
        if am.main(['--root', str(root), *command]):
            raise ValueError('Architecture Map refresh failed')


def finish(args):
    root = args.map_root.resolve(strict=True)
    data, _ = store(root, args.expected_sha256)
    run = next((r for r in data['run'] if r['id'] == args.run_id and r['revision_id'] == REVISION), None)
    if run is None:
        raise ValueError('Not a registered Campaign 001 attempt')
    if any(r['run_id'] == args.run_id for r in data['result']):
        raise ValueError('Terminal result already recorded; corrections require explicit new map records')
    # Gate queue receipt before opening an outcome or assessment artifact.
    receipt = read(args.queue_receipt) if args.queue_receipt else None
    job = receipt.get('job', receipt) if receipt is not None else None
    queue_ok = bool(job and job.get('state') == 'succeeded'
                    and type(job.get('exit_status')) is int and job['exit_status'] == 0)
    assessment = None
    if args.execution_status == 'not_run':
        if receipt is not None or args.assessment is not None:
            raise ValueError('Not-run slot must not carry execution or outcome evidence')
        validity, outcome, ended = 'unknown', 'not_assessed', None
    elif not queue_ok:
        if args.assessment is not None:
            raise ValueError('Do not read outcomes from a queue attempt without succeeded/integer exit0')
        if not job or job.get('state') not in {'failed', 'cancelled', 'canceled'} or not am.timestamp(job.get('ended_at')):
            raise ValueError('Infrastructure disposition requires official terminal failed/cancelled receipt')
        validity, outcome, ended = 'invalid', 'unknown', job['ended_at']
    else:
        if args.assessment is None:
            raise ValueError('Succeeded queue attempt requires explicit admitted assessment')
        assessment = read(args.assessment)
        if (assessment.get('schema') != 'robot-codex-campaign-admitted-assessment-1'
                or assessment.get('run_id') != args.run_id or assessment.get('queue_job_id') != job['id']
                or assessment.get('bindings', {}).get('manifest_sha256') != run['condition_details']['runtime_manifest_sha256']
                or assessment.get('bindings', {}).get('queue_receipt_sha256') != sha(args.queue_receipt)):
            raise ValueError('Assessment does not bind this registered run and queue receipt')
        admission = assessment.get('scientific_admission', {})
        if (admission.get('certificate_sha256') != run['details']['certificate_sha256']
                or admission.get('registered_release_revision') != REVISION
                or admission.get('registration_sha256') != sha(root / 'releases' / REVISION / 'registration.json')):
            raise ValueError('Assessment lacks frozen scientific admission binding')
        validity, outcome, ended = assessment['validity'], assessment['task_outcome'], job['ended_at']
        if validity == 'valid':
            if assessment.get('scorable') is not True or outcome not in {'success', 'failure'}:
                raise ValueError('Valid task outcome requires admitted scorable evidence')
        elif validity == 'invalid':
            if outcome != 'unknown':
                raise ValueError('Infrastructure-invalid assessment cannot infer task outcome')
        else:
            raise ValueError('Unrecognized completed assessment validity')
    final = root / 'releases' / REVISION / ('result-' + args.run_id)
    if final.exists():
        raise ValueError('Terminal artifact directory already exists; inspect before recovery')
    final.mkdir(parents=True)
    refs = []
    for label, source, filename in (('Official queue terminal receipt', args.queue_receipt, 'queue.json'),
                                     ('Admitted campaign assessment', args.assessment, 'assessment.json')):
        if source is not None:
            shutil.copyfile(source, final / filename)
            refs.append(reference(root, label, final / filename, 'evaluator_only'))
    disposition = {'run_id': args.run_id, 'recorded_at': now(), 'reason': args.reason,
                   'termination': args.termination, 'execution_status': args.execution_status,
                   'validity': validity, 'outcome': outcome, 'queue_success_verified': queue_ok}
    write_new(final / 'disposition.json', disposition)
    refs.append(reference(root, 'Terminal slot disposition', final / 'disposition.json'))
    result = {**common(args.run_id + '-result', now()), 'run_id': args.run_id, 'supersedes_result_id': None,
        'execution_status': args.execution_status, 'validity': validity, 'validity_reason': args.reason,
        'outcome': outcome, 'ended_at': ended, 'termination_reason': args.termination, 'metrics': [], 'evidence': refs}
    result['details'] = {'campaign_id': CAMPAIGN_ID, 'queue_success_verified': queue_ok,
        'queue_job_id': job.get('id') if job else None, 'certificate_sha256': run['details']['certificate_sha256'],
        'scope': 'Known-fixture repeatability; infrastructure-invalid/unrun slots remain in the fixed allocation.',
        'failed_checks': assessment.get('failed_checks', []) if assessment else [],
        'scorable': assessment.get('scorable', False) if assessment else False}
    write_new(final / 'result-record.json', result)
    am.append_record(root, 'result', result, args.expected_sha256)
    refresh(root)
    return {'result': result['id'], 'validity': validity, 'outcome': outcome}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-root', type=Path, default=MAP)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare', help='Write validated immutable dry-run preview only')
    p.add_argument('--certificate', type=Path, required=True)
    p.add_argument('--certificate-sha256', required=True)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('append', help='Publish exactly the reviewed preview')
    p.add_argument('--preview', type=Path, required=True)
    p.add_argument('--preview-sha256', required=True)
    p.add_argument('--expected-sha256', required=True)
    p = sub.add_parser('finish', help='Append one authentic terminal disposition')
    p.add_argument('--run-id', required=True)
    p.add_argument('--assessment', type=Path)
    p.add_argument('--queue-receipt', type=Path)
    p.add_argument('--execution-status', choices=sorted(am.ENUMS['execution_status']), required=True)
    p.add_argument('--reason', required=True)
    p.add_argument('--termination', required=True)
    p.add_argument('--expected-sha256', required=True)
    args = parser.parse_args(argv)
    print(json.dumps({'prepare': prepare, 'append': append, 'finish': finish}[args.command](args), indent=2))


if __name__ == '__main__':
    main()
