"""One queued, read-only extraction of the original development003 restart evidence.

Never imports the simulator/classifier, selects a replacement cut, or grants
qualification. The installed queue and canonical terminal record are required.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
INVESTIGATION = EXPERIMENT / 'Engineering Investigation'
sys.path.insert(0, str(INVESTIGATION))
import process_development as development
import continuity
from evidence_adapter import read_lines

ALLOWED_RUN_IDS = ('B01-dev-C0-010', 'B01-dev-A3-003', 'B01-dev-A3-004')
RADIUS = 5
MAX_EVENT_BYTES = 512 * 1024 * 1024
MAX_EVENTS = 250_000
MAX_RETAINED_EVENTS = 2_000


def canonical_hash(value):
    return hashlib.sha256(continuity.canonical(value)).hexdigest()


def original(event):
    return {key: value for key, value in event.items() if key != '_clock_scope'}


def read_index(path, run_id):
    """Validate the complete finite chain and retain exact physical-line identities."""
    if path.stat().st_size > MAX_EVENT_BYTES:
        raise ValueError('Declared event-byte resource cap exceeded; no partial selection')
    lines = {}
    def rows():
        with path.open('rb') as stream:
            for number, event in enumerate(read_lines(path), 1):
                if number > MAX_EVENTS:
                    raise ValueError('Declared event-count resource cap exceeded; no partial selection')
                offset = stream.tell(); raw = stream.readline()
                if not raw or not raw.endswith(b'\n'):
                    raise ValueError('Physical JSONL reader disagreement')
                if json.loads(raw.decode('utf-8')) != event:
                    raise ValueError('Physical and strict JSONL readers disagree')
                lines[number] = {'line': number, 'byte_offset': offset, 'bytes': len(raw),
                                 'line_sha256': hashlib.sha256(raw).hexdigest()}
                yield event
            if stream.read(1):raise ValueError('Physical JSONL reader has trailing data')
    return continuity.EvidenceIndex(rows(), run_id), lines


def references_request(value, ids):
    if isinstance(value, dict):
        return any((key in ('request_id', 'target_request_id', 'active_request_id') and isinstance(item, str) and item in ids)
                   or references_request(item, ids) for key, item in value.items())
    if isinstance(value, list):return any(references_request(item, ids) for item in value)
    return False


def source_archive(run, manifest, map_root):
    refs = run['frozen_refs']['code'].get('refs', [])
    if len(refs) != 1 or refs[0].get('state') != 'available':
        raise ValueError('One exact immutable registered code archive is required')
    path = development.canonical_local_path(refs[0].get('uri'), map_root)
    if path is None or not path.is_relative_to(map_root):
        raise ValueError('Registered source archive is not contained in the canonical map')
    identity = development.ref(path)
    if identity['sha256'] != refs[0].get('sha256'):
        raise ValueError('Registered source archive byte hash mismatch')
    declared = manifest.get('code_sha256')
    if not isinstance(declared, dict) or not declared:
        raise ValueError('Raw manifest has no original source identities')
    members = {}; alias_basis = None
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name, expected in declared.items():
            if not isinstance(name, str) or Path(name).name != name or names.count(name) != 1:
                raise ValueError('Missing, unsafe or ambiguous original source archive member')
            payload = archive.read(name); actual = hashlib.sha256(payload).hexdigest()
            if actual != expected:
                raise ValueError('Original manifest/source archive mismatch: ' + name)
            members[name] = {'archive': str(path), 'member': name, 'sha256': actual, 'bytes': len(payload)}
            if name == 'restart_physical_class.py':
                declaration = "sources['descriptor_exporter'] = file_sha(__file__)"
                matches = [number for number, line in enumerate(payload.decode('utf-8').splitlines(), 1)
                           if line.strip() == declaration]
                if len(matches) == 1:
                    alias_basis = {'identity_key': 'descriptor_exporter', 'archive_member': name,
                                   'source': members[name], 'line': matches[0],
                                   'function': 'source_binding', 'declaration': declaration}
    return identity, members, alias_basis


def physical_source_archive_binding(observed, members, alias_basis):
    """Compare source files only; composite binary/asset digests are not ZIP members."""
    source_rows = []; non_source_rows = []; unknown_rows = []
    if isinstance(observed, dict):
        for key, recorded in sorted(observed.items()):
            row = {'identity_key': key, 'recorded_sha256': recorded}
            if key in ('mujoco_build', 'robot_assets'):
                non_source_rows.append({**row, 'archive_comparison': 'not_applicable_to_Runtime_source_archive',
                    'verification': 'unverified_by_this_check',
                    'identity_scope': 'MuJoCo version/native-binary digest' if key == 'mujoco_build' else 'Panda asset-tree digest'})
                continue
            member = key if key.endswith('.py') and Path(key).name == key else (
                alias_basis['archive_member'] if key == 'descriptor_exporter' and alias_basis else None)
            if member is None:
                unknown_rows.append({**row, 'verification': 'unknown_identity_mapping', 'matches': None})
                continue
            reference = members.get(member)
            match = reference is not None and recorded == reference['sha256']
            source_rows.append({**row, 'archive_member': member, 'archive_source': reference, 'matches': match,
                                'verification': 'match' if match else 'mismatch_or_missing_archive_member'})
    aggregate = (False if any(not row['matches'] for row in source_rows) else
                 True if source_rows and not unknown_rows else None)
    return {'python_sources_match_archive': aggregate, 'python_source_comparisons': source_rows,
            'non_source_identities': non_source_rows, 'unknown_identity_mappings': unknown_rows,
            'descriptor_alias_mapping_basis': alias_basis,
            'scope': 'Literal Python file keys and the exporter alias declared by the original archived source only; native build/assets are retained without re-verification'}


def inspect(run_id, receipt_path, output):
    if run_id not in ALLOWED_RUN_IDS:raise ValueError('Run is outside the three declared development003 diagnostics')
    authority = development.runtime_module('release_runner')
    ownership = authority.queued_job(expected_script=__file__)
    output = Path(output).resolve(); map_root = development.MAP.resolve()
    if output.exists():raise ValueError('Output directory must be fresh')
    receipts = development.receipt_files([receipt_path], authority)
    data, map_before = development.read_map(map_root)
    registrar = development.runtime_module('record_attempt')
    storage, legacy, registration = registrar.registered_storage(run_id)
    evidence_root = Path(storage['evidence_dir']).resolve().parent
    if any(output.is_relative_to(root) for root in (map_root, evidence_root, development.RUNTIME.resolve(), HERE)) or any(part.casefold() == 'candidate_state' for part in output.parts):
        raise ValueError('Derived output must remain outside originals, source, map and candidate state')
    bound = development.verify_run(run_id, data, map_root, evidence_root, receipts)
    manifest = development.object_file(bound['root'] / 'manifest.json')
    for value in (manifest, bound['raw_result']):registrar.verify_raw_identity(value, run_id, storage, legacy)
    archive, members, alias_basis = source_archive(bound['run_record'], manifest, map_root)
    sources = {**bound['sources'], 'registration': registration, 'runtime_archive': archive,
               'original_receipt': next(iter(receipts.values()))['source']}
    # All current Python sources in the reader/runtime directories are cheap
    # operator-method identities, distinct from the immutable episode archive.
    method_paths = [Path(__file__), map_root / 'map.py', *INVESTIGATION.glob('*.py'), *development.RUNTIME.glob('*.py')]
    method_before = {str(path.resolve()): development.ref(path) for path in method_paths}
    output.mkdir(parents=True, exist_ok=False)
    development.write_once(output / 'inputs.json', {
        'schema_version': 'development003-original-restart-diagnostic-inputs-1.1', 'run_id': run_id,
        'created_at': datetime.now(timezone.utc).isoformat(), 'queue_identity': ownership,
        'sources': sources, 'method_sources_before': method_before, 'map_before': map_before,
        'registered_storage': storage, 'legacy_registration': legacy,
        'run_record': bound['run_record'], 'canonical_result': bound['canonical_result'],
        'original_receipt': next(iter(receipts.values()))['receipt'], 'runtime_archive_members': members,
        'limits': {'event_bytes': MAX_EVENT_BYTES, 'event_count': MAX_EVENTS,
                   'retained_events': MAX_RETAINED_EVENTS, 'context_radius_events': RADIUS}})
    try:
        index, lines = read_index(bound['root'] / 'events.jsonl', run_id)
        selected = set(); missing = []; checks = {}; contexts = []
        def event_ref(event):
            return {'source': sources['events.jsonl'], **lines[event['event_id']],
                    'event_id': event['event_id'], 'event_type': event['event_type'],
                    'payload_sha256': event['payload_sha256'], 'parent_ids': event['parent_ids'],
                    'sim_time_s': event['sim_time_s'], 'wall_elapsed_s': event['wall_elapsed_s'],
                    'clock_scope': event['_clock_scope']}
        def keep(events):
            selected.update(event['event_id'] for event in events)
            return [event_ref(event) for event in events]
        def context(event, role):
            eid = event['event_id']; ids = list(range(max(1, eid-RADIUS), min(len(index.events), eid+RADIUS)+1))
            selected.update(ids)
            contexts.append({'role': role, 'anchor': event_ref(event), 'event_ids': ids,
                             'before_count': eid-ids[0], 'after_count': ids[-1]-eid})
        begins = index.kind('restart_begin'); keep(begins)
        sole = begins[0] if len(begins) == 1 else None
        if sole is None:missing.append('Expected exactly one original restart_begin; found ' + str(len(begins)) + '; no cut selected')
        report = {'schema_version': 'development003-original-restart-diagnostic-1.1', 'run_id': run_id,
                  'reader_change': '1.1 separates original Python source/archive comparisons from native-build and robot-asset identities; prior outputs are unchanged',
                  'purpose': 'Inspect the original development003 restart cut; no reclassification, replacement cut, causal conclusion or qualification',
                  'restart_begin_events': [event_ref(event) for event in begins],
                  'original_manifest': manifest, 'original_raw_result': bound['raw_result'],
                  'canonical_result': bound['canonical_result'], 'missing_links': missing,
                  'consistency_checks': checks, 'contexts': contexts}
        if sole is not None:
            payload = sole['payload']; snapshot = payload.get('protected_restart_state'); decision = payload.get('restart_admissibility')
            exposure = payload.get('exposure', {}); result_exposure = bound['raw_result'].get('restart_exposure')
            development.write_once(output / 'original-restart-begin.json', original(sole))
            report['original_cut'] = {'event': event_ref(sole), 'full_payload_file': 'original-restart-begin.json',
                                      'exposure': exposure, 'recorded_admissibility': decision}
            context(sole, 'original_restart_begin')
            requests = [payload.get('active_request')]
            if isinstance(snapshot, dict):requests.append(snapshot.get('authority', {}).get('active_request'))
            request_ids = {value.get('request_id') for value in requests if isinstance(value, dict) and isinstance(value.get('request_id'), str)}
            if isinstance(exposure.get('active_request_id'), str):request_ids.add(exposure['active_request_id'])
            checks['active_request_ids_agree'] = len(request_ids) == 1
            if len(request_ids) != 1:missing.append('No single consistent active request identity; every recorded identity is retained')
            lifecycle = [event for event in index.events if (
                event['event_type'] in ('action_requested', 'action_admission', 'physical_service_event') or
                event['event_type'] == 'candidate_input' and isinstance(event['payload'], dict) and event['payload'].get('message', {}).get('type') == 'feedback')
                and references_request(event['payload'], request_ids)]
            report['request_lifecycle'] = {'request_ids': sorted(request_ids), 'events': keep(lifecycle),
                'selection': 'All matching action_requested, action_admission, physical_service_event and candidate_input feedback records; no outcome filtering'}
            for kind in ('action_requested', 'action_admission'):
                if not any(event['event_type'] == kind for event in lifecycle):missing.append('Same-request ' + kind + ' not recorded')
            dispatched = [event for event in lifecycle if event['event_type'] == 'physical_service_event' and event['payload'].get('type') == 'trajectory_dispatched']
            cancelled = [event for event in lifecycle if event['payload'].get('status') == 'cancelled']
            if not dispatched:missing.append('Same-request trajectory_dispatched not recorded')
            if not cancelled:missing.append('Same-request physical cancellation receipt not recorded; authority_revoked is a separate landmark')
            report['same_request_dispatch'] = keep(dispatched);report['same_request_cancel'] = keep(cancelled)
            for event in lifecycle:
                if event['event_type'] == 'action_admission' or event in dispatched:context(event, 'same_request_admission_or_dispatch')
            for kind in ('restart_authority_revoked', 'restart_ready'):
                all_events = index.kind(kind); linked = [event for event in all_events if sole['event_id'] in event['parent_ids']]
                report[kind] = {'direct_parent_linked': keep(linked), 'other_same_kind_events': keep([e for e in all_events if e not in linked])}
                if len(linked) != 1:missing.append(kind + ': expected one direct parent link to original cut; found ' + str(len(linked)))
                if kind == 'restart_authority_revoked' and len(linked) == 1:
                    checks['result_authority_revocation_matches_event'] = isinstance(result_exposure, dict) and result_exposure.get('authority_revocation') == linked[0]['payload']
                for event in all_events:context(event, kind)
            world = index.kind('world_snapshot')
            before = [e for e in world if e['event_id'] < sole['event_id']][-RADIUS:]
            after = [e for e in world if e['event_id'] > sole['event_id']][:RADIUS]
            report['nearby_protected_world_snapshots'] = {'before': keep(before), 'after': keep(after),
                'scope': 'Original coarse protected position/truth snapshots; no invented contact, pose, velocity or settling interpolation'}
            if not before or not after:missing.append('Protected world snapshot context missing on one side of cut')
            if isinstance(snapshot, dict):
                actual_hash = canonical_hash({key: value for key, value in snapshot.items() if key != 'snapshot_sha256'})
                checks['snapshot_content_sha256'] = actual_hash
                checks['snapshot_hash_matches_content'] = snapshot.get('snapshot_sha256') == actual_hash
                checks['classifier_matches_snapshot_hash'] = isinstance(decision, dict) and decision.get('snapshot_sha256') == actual_hash
                checks['geometry_alias_matches_snapshot'] = payload.get('protected_snapshot') == snapshot.get('geometry')
                checks['snapshot_source_hashes_match_original_archive'] = bool(snapshot.get('source_hashes')) and all(members.get(name, {}).get('sha256') == value for name, value in snapshot.get('source_hashes', {}).items())
                observed_sources = snapshot.get('physical_class_observation', {}).get('source_hashes')
                physical_binding = physical_source_archive_binding(observed_sources, members, alias_basis)
                checks['physical_class_python_source_hashes_match_original_archive'] = physical_binding['python_sources_match_archive']
                report['physical_class_source_archive_binding'] = physical_binding
                report['protected_geometry_and_contacts'] = {'snapshot_source_hashes': snapshot.get('source_hashes'),
                    'physical_class_observation': snapshot.get('physical_class_observation'),
                    'geometry': snapshot.get('geometry'), 'object_poses': snapshot.get('object_poses'),
                    'contacts': snapshot.get('contacts'), 'robot': snapshot.get('robot'), 'authority': snapshot.get('authority'),
                    'scope': 'All objects/contact records at the original cut retained, including predicates unrelated to the target; no contact or support recomputation'}
            else:missing.append('Original protected rich snapshot missing')
            if isinstance(result_exposure, dict):
                checks['result_links_original_event'] = result_exposure.get('event_id') == sole['event_id']
                checks['result_classifier_exactly_matches_cut'] = result_exposure.get('restart_admissibility') == decision
                checks['cut_classifier_canonical_sha256'] = canonical_hash(decision)
                checks['result_classifier_canonical_sha256'] = canonical_hash(result_exposure.get('restart_admissibility'))
                checks['result_snapshot_hash_matches_cut'] = isinstance(snapshot, dict) and result_exposure.get('protected_restart_state_sha256') == snapshot.get('snapshot_sha256')
                checks['result_exposure_matches_original_fields'] = all(result_exposure.get(key) == value for key, value in exposure.items())
            else:missing.append('Original raw result has no restart_exposure copy')
            try:report['recorded_predicate_integrity_reader'] = continuity.restart_admissibility(sole, index)
            except (KeyError, TypeError, ValueError) as error:
                report['recorded_predicate_integrity_reader'] = {'state': 'integrity_error', 'error': str(error), 'reassessment_performed': False}
            report['recorded_predicate_states'] = [{'name': row.get('name'), 'state': row.get('state'), 'required': row.get('required')} for row in (decision or {}).get('predicates', [])] if isinstance(decision, dict) else None
            if not isinstance(decision, dict):missing.append('Original recorded admissibility/classifier result missing')
        if len(selected) > MAX_RETAINED_EVENTS:raise ValueError('Retained-event resource cap exceeded; no favorable truncation')
        extracted = []
        with (bound['root'] / 'events.jsonl').open('rb') as source, (output / 'events-selected.jsonl').open('xb') as target:
            for out_line, eid in enumerate(sorted(selected), 1):
                info = lines[eid];source.seek(info['byte_offset']);raw = source.read(info['bytes'])
                if hashlib.sha256(raw).hexdigest() != info['line_sha256']:raise ValueError('Selected physical event line changed')
                target.write(raw);extracted.append({**event_ref(index.by_id[eid]), 'extracted_line': out_line})
        report['retained_events'] = extracted
        report['whole_chain_verified_event_count'] = len(index.events)
        development.check_sources(sources);development.check_sources(method_before)
        _, map_after = development.read_map(map_root)
        if map_after != map_before:raise ValueError('Canonical map changed during diagnostic')
        report['sources_before'] = sources;report['sources_after'] = {name: development.ref(item['path']) for name, item in sources.items()}
        report['map_before'] = map_before;report['map_after'] = map_after
        report['method_sources_before'] = method_before
        report['method_sources_after'] = {name: development.ref(item['path']) for name, item in method_before.items()}
        report['selected_event_file'] = development.ref(output / 'events-selected.jsonl')
        report['limitations'] = ['A successful extraction is not a physical or timing pass.',
            'Canonical and raw outcome records are preserved separately; neither selects a cut.',
            'No new snapshot, classifier call, threshold, future-state inference or favorable filtering.',
            'World snapshots are coarse context; only the original rich cut supplies native contacts.',
            'Five neighboring events per anchor and five world snapshots per side do not establish continuous state.']
        development.write_once(output / 'restart-diagnostic.json', report)
        development.write_once(output / 'complete.json', {'status': 'completed', 'queue_identity': ownership,
            'run_id': run_id, 'report': development.ref(output / 'restart-diagnostic.json'),
            'completed_at': datetime.now(timezone.utc).isoformat(), 'qualification_granted': False})
    except Exception as error:
        development.write_once(output / 'error.json', {'status': 'failed', 'run_id': run_id,
            'error_type': type(error).__name__, 'error': str(error), 'partial_outputs_retained': True})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', choices=ALLOWED_RUN_IDS, required=True)
    parser.add_argument('--receipt', type=Path, required=True, help='Official original development execution receipt, succeeded/0')
    parser.add_argument('--output', type=Path, required=True, help='Fresh derived output directory')
    args = parser.parse_args();inspect(args.run_id, args.receipt, args.output)
