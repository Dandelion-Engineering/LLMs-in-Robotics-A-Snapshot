"""Select original and explicitly authorized administrative-continuation evidence.

Original 004 helpers are imported unchanged. An administrative projection is
never written as a canonical result or a protected supervisor terminal.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
RUNTIME = EXPERIMENT / 'Runtime 004'
RECOVERY = EXPERIMENT / 'Runtime Recovery 001'
MAP = EXPERIMENT / 'Architecture Map'
LEGACY_PATH = HERE.parent / 'Release Analysis 004' / 'collect_results.py'
SCHEMA = 'selected-evaluation-results-administrative-1'


def load_module(name, path):
    existing = sys.modules.get(name)
    if existing is not None:
        if Path(existing.__file__).resolve() != Path(path).resolve():
            raise ValueError('Module identity already belongs to another source: ' + name)
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


legacy = load_module('release_analysis_004_original_collector', LEGACY_PATH)
protocol, release_runner = legacy.protocol, legacy.release_runner
if (Path(protocol.__file__).resolve() != RUNTIME / 'protocol.py'
        or Path(release_runner.__file__).resolve() != RUNTIME / 'release_runner.py'):
    raise ValueError('Original collector resolved a substituted Runtime implementation')
read, ref = legacy.read, legacy.ref
current_result, selected_flat, verified_terminal = legacy.current_result, legacy.selected_flat, legacy.verified_terminal


def verify_annex(path, release_dir=None, require_adopted=True):
    contract = load_module('release_analysis_005_recovery_contract', RECOVERY / 'recovery_contract.py')
    return contract.verify_annex(path, release_dir=release_dir, require_adopted=require_adopted)


def identity(reference, base):
    """Verify exact bytes while allowing optional byte counts in a reference."""
    if not isinstance(reference, dict):
        raise ValueError('Missing exact authority/evidence reference')
    path = release_runner.reference(reference, Path(base))
    actual = ref(path)
    if 'bytes' in reference and reference['bytes'] != actual['bytes']:
        raise ValueError('Reference byte count differs')
    return actual


def same_reference(reference, expected, base):
    actual = identity(reference, base)
    if any(actual[key] != expected[key] for key in ('path', 'sha256')):
        raise ValueError('Reference identifies different authority or evidence')
    return actual


def aware_timestamp(value, label):
    if not isinstance(value, str):
        raise ValueError(label + ' must be an actual timezone-bearing recording time')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError(label + ' lacks a timezone')
    return parsed


def administrative_spec(verified, run_id):
    rows = verified['annex'].get('administrative_dispositions', [])
    matches = [row for row in rows if row.get('run_id') == run_id]
    if len(matches) != 1:
        raise ValueError('Annex requires one exact administrative disposition declaration')
    return matches[0]


def administrative_result(root, run_id, notes, verified, controls):
    """Only the adopted annex's exact canonical decision may project a result."""
    spec = administrative_spec(verified, run_id)
    base = Path(verified['annex_ref']['path']).parent
    disposition_ref = identity(spec['disposition_ref'], base)
    controls[disposition_ref['path']] = disposition_ref
    disposition = read(disposition_ref['path'])
    if disposition != verified['dispositions'][run_id]:
        raise ValueError('Disposition differs from independently verified annex evidence')
    if disposition.get('run_id') != run_id or disposition.get('annex_id') != verified['annex'].get('annex_id'):
        raise ValueError('Administrative disposition identity differs')
    if (disposition.get('execution_disposition') != 'interrupted'
            or disposition.get('validity') != 'invalid'
            or disposition.get('invalidity_class') != 'infrastructure'
            or disposition.get('task_outcome') != 'unknown'
            or disposition.get('physical_ended_at', 'absent') is not None
            or disposition.get('post_run_integrity') != {'state': 'missing'}
            or disposition.get('supervisor_terminal') != {'state': 'missing'}
            or disposition.get('metrics') != {}):
        raise ValueError('Administrative interruption cannot invent outcome, clocks or integrity')
    aware_timestamp(disposition.get('administratively_recorded_at'), 'Administrative recording time')
    receipt_ref = identity(disposition['official_receipt'], Path(disposition_ref['path']).parent)
    controls[receipt_ref['path']] = receipt_ref
    receipt = read(receipt_ref['path'])
    if (receipt.get('id') != disposition.get('original_queue_job_id')
            or receipt.get('state') != 'interrupted'
            or 'exit_status' not in receipt or receipt['exit_status'] is not None):
        raise ValueError('Administrative interruption requires original interrupted/null receipt')
    candidates = [note for note in notes if note.get('details', {}).get('provenance_kind') == 'administrative_interruption'
                  and run_id in note.get('target_ids', [])]
    if len(candidates) != 1 or candidates[0].get('id') != spec.get('expected_canonical_note_id'):
        raise ValueError('Administrative interruption lacks its unique exact canonical note')
    note = candidates[0]
    if note.get('claim_type') != 'decision' or note.get('supersedes_note_id') is not None or note.get('target_ids') != [run_id]:
        raise ValueError('Administrative authority requires its exact unsuperseded decision note')
    if any(other.get('supersedes_note_id') == note['id'] for other in notes):
        raise ValueError('Administrative decision was superseded; explicit annex revision required')
    aware_timestamp(note.get('recorded_at'), 'Canonical note recording time')
    detail = note['details']
    same_reference(detail.get('administrative_disposition_ref'), disposition_ref, MAP)
    same_reference(detail.get('recovery_annex_ref'), verified['annex_ref'], MAP)
    if (root / 'attempts' / run_id / 'terminal.json').exists():
        raise ValueError('Administrative and protected terminal dispositions conflict')
    result = {'run_id': run_id, 'stage': 'evaluation', 'execution_status': 'aborted',
              'validity': 'invalid', 'invalidity_class': 'infrastructure', 'infrastructure_invalid': True,
              'validity_reason': 'Administrative interruption; original supervisor terminal and post-run integrity are missing',
              'outcome': 'unknown', 'ended_at': None,
              'termination_reason': 'administrative_interruption_without_supervisor_terminal',
              'completion_time_s': None, 'wall_duration_s': None, 'model_calls': None, 'total_tokens': None,
              'provenance_kind': 'administrative_interruption', 'selected_canonical_note_id': note['id'],
              'physical_ended_at': None, 'administratively_recorded_at': disposition['administratively_recorded_at'],
              'post_run_integrity': {'state': 'missing'}, 'official_queue_state': 'interrupted',
              'official_queue_exit_status': None}
    provenance = {'run_id': run_id, 'provenance_kind': 'administrative_interruption',
                  'selected_note': copy.deepcopy(note), 'administrative_disposition': disposition_ref,
                  'recovery_annex_ref': copy.deepcopy(verified['annex_ref']), 'official_queue_receipt': receipt_ref,
                  'supervisor_terminal': None, 'original_post_run_integrity': {'state': 'missing'}}
    return result, provenance


def verify_recovery_binding(root, manifest, terminal, evidence, history, verified):
    """Additional operator authority never substitutes for original hash checks."""
    expected = verified['annex_ref']
    same_reference(terminal.get('recovery_annex_ref'), expected, root)
    source_index = verified['source_index_ref']
    same_reference(terminal.get('recovery_source_index_ref'), source_index, root)
    for name in ('batch_plan', 'batch_finished', 'finalization'):
        record = read(evidence[name]['path'])
        same_reference(record.get('recovery_annex_ref'), expected, root)
        same_reference(record.get('recovery_source_index_ref'), source_index, root)
    for record in history:
        same_reference(record.get('details', {}).get('recovery_annex_ref'), expected, MAP)
        same_reference(record.get('details', {}).get('recovery_source_index_ref'), source_index, MAP)
    # The exact revision field is retained by the new execution authority.
    revision = terminal.get('revision_id')
    if not isinstance(revision, str) or not revision or revision != verified['annex']['revision_ids'].get(manifest['architecture']):
        raise ValueError('Recovery terminal lacks its new revision identity')
    registration = root / 'attempts' / terminal['run_id'] / 'registered.json'
    registered = read(registration)
    if registered.get('run_id') != terminal['run_id'] or registered.get('revision_id') != revision:
        raise ValueError('Recovery terminal differs from pre-execution revision registration')
    same_reference(registered.get('recovery_annex_ref'), expected, root)
    same_reference(registered.get('recovery_source_index_ref'), source_index, root)
    for record in history:
        if record.get('details', {}).get('revision_id') != revision:
            raise ValueError('Canonical recovery result differs from its new revision')
    return ref(registration)


def collect(root, records, *, notes=None, annex_path=None, complete=False):
    root = Path(root).resolve(); records = list(records); notes = list(notes or [])
    release_source = ref(root / 'release.json')
    manifests = protocol.load_release(root)
    plans = {m['run_id']: m for m in manifests}
    if len(plans) != len(manifests):
        raise ValueError('Duplicate planned identity')
    if any(row.get('run_id') not in plans for row in records):
        # A whole canonical map contains other releases; callers pass only this release below.
        records = [row for row in records if row.get('run_id') in plans]
    verified = None
    retained, allowed, administrative = set(plans), set(), set()
    if annex_path is not None:
        verified = verify_annex(annex_path, release_dir=root, require_adopted=True)
        if Path(verified['root']).resolve() != root:
            raise ValueError('Recovery annex belongs to another release directory')
        retained, allowed, administrative = [set(verified[key]) for key in
            ('retained_run_ids', 'allowed_run_ids', 'administrative_run_ids')]
        if retained & allowed or retained & administrative or allowed & administrative or retained | allowed | administrative != set(plans):
            raise ValueError('Recovery partition is not disjoint and complete')
    typed = [note for note in notes if note.get('details', {}).get('provenance_kind') == 'administrative_interruption'
             and set(note.get('target_ids', [])) & set(plans)]
    if any(set(note.get('target_ids', [])) != {rid} for note in typed for rid in note.get('target_ids', []) if rid in plans):
        raise ValueError('Administrative note has ambiguous targets')
    if any(not set(note.get('target_ids', [])) <= administrative for note in typed):
        raise ValueError('Administrative note is not authorized by this annex')
    release = read(root / 'release.json')
    manifest_hashes = {read(root / item['path'])['run_id']: item['sha256'] for item in release['manifest_refs']}
    controls = {release_source['path']: release_source, str(LEGACY_PATH): ref(LEGACY_PATH), str(Path(__file__).resolve()): ref(__file__)}
    if verified:
        authority = identity(verified['annex_ref'], Path(annex_path).resolve().parent)
        controls[authority['path']] = authority
        source_index = identity(verified['source_index_ref'], Path(annex_path).resolve().parent)
        controls[source_index['path']] = source_index
        contract_path = RECOVERY / 'recovery_contract.py'
        if contract_path.is_file():
            controls[str(contract_path)] = ref(contract_path)
    results, provenance, missing = [], [], []
    normal_count = recovery_count = administrative_count = 0
    for manifest in manifests:
        rid = release_runner.safe_id(manifest['run_id'])
        terminal_path = root / 'attempts' / rid / 'terminal.json'
        canonical = [record for record in records if record.get('run_id') == rid]
        if rid in administrative:
            if canonical or terminal_path.exists():
                raise ValueError('Administrative interruption conflicts with a canonical result or terminal')
            selected, evidence = administrative_result(root, rid, notes, verified, controls)
            results.append(selected); provenance.append(evidence); administrative_count += 1
            continue
        if not terminal_path.is_file():
            if canonical:
                raise ValueError('Canonical result exists without terminal evidence: ' + rid)
            if verified and rid in retained:
                raise ValueError('Retained original terminal is missing: ' + rid)
            missing.append({'run_id': rid, 'reason': 'No retained terminal attempt',
                            'attempt_directory_exists': terminal_path.parent.exists()})
            continue
        terminal, evidence = verified_terminal(root, rid, release_source['sha256'], manifest_hashes[rid])
        assessment, history = current_result(records, rid)
        initial = next(row for row in history if row.get('supersedes_result_id') is None)
        if initial.get('details', {}).get('terminal_sha256') != evidence['terminal']['sha256']:
            raise ValueError('Canonical history lacks exact original terminal binding')
        if assessment.get('execution_status') not in protocol.TERMINAL:
            raise ValueError('Selected result is not terminal')
        if rid in allowed:
            registration = verify_recovery_binding(root, manifest, terminal, evidence, history, verified)
            controls[registration['path']] = registration
            kind = 'annex_authorized_terminal'; recovery_count += 1
        else:
            if terminal.get('recovery_annex_ref') is not None or any(row.get('details', {}).get('recovery_annex_ref') is not None for row in history):
                raise ValueError('Original terminal cannot acquire recovery authority implicitly')
            kind = 'original_finalized_terminal'; normal_count += 1
        results.append(selected_flat(terminal, assessment))
        provenance.append({'run_id': rid, 'provenance_kind': kind, 'selected_assessment': assessment,
                           'canonical_history_ids': [row['id'] for row in history], **evidence,
                           **({'recovery_annex_ref': copy.deepcopy(verified['annex_ref'])} if rid in allowed else {})})
        for name in ('terminal', 'batch_plan', 'batch_finished', 'finalization', 'official_queue_receipt'):
            controls[evidence[name]['path']] = evidence[name]
    if complete and missing:
        raise ValueError('Full release incomplete: ' + str(len(missing)) + ' original dispositions missing')
    for original in controls.values():
        if ref(original['path']) != original:
            raise ValueError('Evidence changed during collection')
    if verified:
        after = verify_annex(annex_path, release_dir=root, require_adopted=True)
        if after != verified:
            raise ValueError('Recovery authority changed during collection')
    for rid in administrative | {item['run_id'] for item in missing}:
        if (root / 'attempts' / rid / 'terminal.json').exists():
            raise ValueError('Previously absent terminal appeared during collection')
    return {'schema_version': SCHEMA, 'created_at': datetime.now(timezone.utc).isoformat(),
            'release': release_source, 'implementation': ref(__file__), 'legacy_implementation': ref(LEGACY_PATH),
            'recovery_annex_ref': None if verified is None else copy.deepcopy(verified['annex_ref']),
            'recovery_source_index_ref': None if verified is None else copy.deepcopy(verified['source_index_ref']),
            'results': results, 'provenance': provenance, 'missing': missing,
            'counts': {'planned': len(manifests), 'original_finalized': normal_count,
                       'annex_finalized': recovery_count, 'administrative_interruption': administrative_count,
                       'selected_for_analysis': len(results), 'missing_disposition': len(missing)},
            'complete_disposition_accounting': not missing,
            'control_sources': list(controls.values()),
            'scope': 'Original result selection plus separately verified administrative projections; no fabricated supervisor terminals or original result mutation'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', required=True, type=Path)
    parser.add_argument('--annex', type=Path)
    parser.add_argument('--map-root', type=Path, default=MAP)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--complete', action='store_true')
    args = parser.parse_args(argv)
    ownership = release_runner.queued_job(expected_script=__file__)
    output = args.output.resolve(); map_root = args.map_root.resolve(); root = args.release_dir.resolve()
    protected = (map_root, RUNTIME, RECOVERY, HERE, root / 'runs', root / 'attempts', root / 'batches')
    if output.exists() or any(output.is_relative_to(path) for path in protected) or any(p.casefold() == 'candidate_state' for p in output.parts):
        raise ValueError('Output must be fresh and outside original/source/canonical/candidate evidence')
    sources = {kind: ref(map_root / (kind + '.jsonl')) for kind in ('results', 'notes')}
    rows = {kind: [json.loads(line) for line in Path(source['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
            for kind, source in sources.items()}
    report = collect(root, rows['results'], notes=rows['notes'], annex_path=args.annex, complete=args.complete)
    if any(ref(source['path']) != source for source in sources.values()):
        raise ValueError('Canonical map changed during selection')
    report.update(canonical_results_source=sources['results'], canonical_notes_source=sources['notes'], queue_job_id=ownership['id'])
    output.parent.mkdir(parents=True, exist_ok=True)
    release_runner.write_once(output, report)
    print(json.dumps({'output': str(output), 'counts': report['counts'], 'complete': report['complete_disposition_accounting']}))


if __name__ == '__main__':
    main()
