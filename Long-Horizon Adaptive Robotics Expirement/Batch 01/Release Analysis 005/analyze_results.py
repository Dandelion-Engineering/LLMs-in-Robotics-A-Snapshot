"""Queue-only administrative-continuation lineage; original statistics unchanged."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import importlib.util
import sys

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('release_analysis_005_collector', HERE / 'collect_results.py')
collector = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = collector
_spec.loader.exec_module(collector)
EXPERIMENT, RUNTIME, RECOVERY, MAP = collector.EXPERIMENT, collector.RUNTIME, collector.RECOVERY, collector.MAP
protocol, release_runner = collector.protocol, collector.release_runner
queue_authority = collector.load_module('release_analysis_005_queue_authority', RECOVERY / 'recovery_runner.py')
SCHEMA = 'source-bound-administrative-evaluation-analysis-1'
SETTINGS = {'bootstrap_draws': 2000, 'analysis_seed': 0}


def utc():
    return datetime.now(timezone.utc).isoformat()


def ref(path):
    path = Path(path).resolve(); before = path.stat()
    value = {'path': str(path), 'sha256': release_runner.digest(path), 'bytes': before.st_size}
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Artifact changed while hashing: ' + str(path))
    return value


def bound(reference, base):
    if not isinstance(reference, dict):
        raise ValueError('Missing exact source reference')
    path = release_runner.reference(reference, base); actual = ref(path)
    if actual['sha256'] != reference['sha256'] or ('bytes' in reference and reference['bytes'] != actual['bytes']):
        raise ValueError('Artifact reference differs from exact bytes')
    return actual


def observe_after(before):
    after = {}
    for role, original in before.items():
        try:
            after[role] = ref(original['path'])
        except (OSError, ValueError) as error:
            after[role] = {'path': original['path'], 'sha256': None, 'bytes': None,
                           'error': type(error).__name__ + ': ' + str(error)}
    return after


def load_inputs(root, selected_path, report, annex_path=None):
    before = report['inputs_before']
    for role, path in (('implementation', Path(__file__)), ('protocol', Path(protocol.__file__)),
                       ('queue_authorization_implementation', Path(queue_authority.__file__)),
                       ('selected_results', selected_path), ('release', root / 'release.json')):
        before[role] = ref(path); report[role] = dict(before[role])
    selected = protocol._load(selected_path)
    if selected.get('schema_version') != collector.SCHEMA or not isinstance(selected.get('results'), list):
        raise ValueError('Require the administrative collector artifact')
    if bound(selected.get('release'), selected_path.parent) != before['release']:
        raise ValueError('Selected results belong to another release')
    for role, expected in (('selection_implementation', HERE / 'collect_results.py'),
                           ('legacy_selection_implementation', collector.LEGACY_PATH)):
        key = 'implementation' if role == 'selection_implementation' else 'legacy_implementation'
        actual = bound(selected.get(key), selected_path.parent)
        if Path(actual['path']) != expected.resolve():
            raise ValueError('Selected results identify a substituted collector')
        before[role] = actual; report[role] = actual
    release = protocol._load(root / 'release.json')
    if release.get('schema_version') != protocol.SCHEMA_VERSION:
        raise ValueError('Unsupported original release schema')
    report['release_id'] = release.get('release_id')
    for role in ('freeze_manifest', 'readiness'):
        before[role] = bound(release.get(role), root)
        report['release_authority'][role] = dict(before[role])
    freeze, readiness = [protocol._load(before[role]['path']) for role in ('freeze_manifest', 'readiness')]
    if (freeze.get('release_id') != release.get('release_id')
            or readiness.get('release_id') != release.get('release_id')
            or readiness.get('freeze_sha256') != before['freeze_manifest']['sha256']):
        raise ValueError('Original release/freeze/readiness identity differs')
    if freeze.get('protocol_sha256') != before['protocol']['sha256']:
        raise ValueError('Analysis differs from original frozen numerical protocol')
    for declared in release.get('manifest_refs', []):
        rid = release_runner.safe_id(declared.get('run_id')); role = 'manifest:' + rid
        if role in before:
            raise ValueError('Duplicate original manifest reference')
        actual = bound(declared, root)
        if not Path(actual['path']).is_relative_to(root):
            raise ValueError('Protected manifest escaped release')
        before[role] = actual; report['protected_manifest_refs'].append({'run_id': rid, **actual})
    manifests = protocol.load_release(root)
    refs = {item['run_id']: item for item in report['protected_manifest_refs']}
    if {m['run_id'] for m in manifests} != set(refs):
        raise ValueError('Original manifest inventory differs')
    for manifest in manifests:
        if (manifest.get('release_id') != release.get('release_id')
                or manifest.get('freeze_sha256') != before['freeze_manifest']['sha256']
                or manifest.get('readiness_sha256') != before['readiness']['sha256']
                or manifest.get('artifact_hashes', {}).get('protocol_sha256') != before['protocol']['sha256']):
            raise ValueError('Original manifest authority changed')
    selection_annex = selected.get('recovery_annex_ref')
    if selection_annex is not None:
        before['recovery_annex'] = bound(selection_annex, selected_path.parent)
        if annex_path is not None and ref(annex_path) != before['recovery_annex']:
            raise ValueError('Requested annex differs from selected evidence authority')
        annex_path = Path(before['recovery_annex']['path'])
        report['recovery_annex_ref'] = before['recovery_annex']
    elif annex_path is not None:
        raise ValueError('Selected evidence does not bind the requested annex')
    rows = {}
    for kind in ('results', 'notes'):
        role = 'canonical_' + kind + '_source'
        before[role] = bound(selected.get(role), selected_path.parent)
        if Path(before[role]['path']) != (MAP / (kind + '.jsonl')).resolve():
            raise ValueError('Selected evidence does not bind the actual canonical map')
        rows[kind] = [json.loads(line) for line in Path(before[role]['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    # Reproduce source selection; a hand-edited projection cannot become bound analysis.
    recomputed = collector.collect(root, rows['results'], notes=rows['notes'], annex_path=annex_path, complete=False)
    for key in ('release', 'results', 'provenance', 'missing', 'counts', 'complete_disposition_accounting',
                'recovery_annex_ref', 'recovery_source_index_ref', 'control_sources'):
        if selected.get(key) != recomputed.get(key):
            raise ValueError('Selected administrative evidence cannot be reproduced: ' + key)
    for number, source in enumerate(recomputed['control_sources']):
        before['selection_control:' + str(number)] = bound(source, root)
    report['disposition_counts'] = recomputed['counts']
    report['complete_disposition_accounting'] = recomputed['complete_disposition_accounting']
    return manifests, selected['results']


def analyze_results(release_dir, selected_results, output_dir, *, annex_path=None):
    ownership = queue_authority.queued_job(expected_script=__file__)
    root, selected_path, output = [Path(path).resolve() for path in (release_dir, selected_results, output_dir)]
    protected = (RUNTIME, RECOVERY, MAP, HERE, EXPERIMENT / 'Evidence' / 'raw', root / 'runs', root / 'attempts', root / 'batches')
    if output.exists() or any(output.is_relative_to(p.resolve()) for p in protected) or any(p.casefold() == 'candidate_state' for p in output.parts):
        raise ValueError('Output must be fresh and outside original/source/canonical/candidate evidence')
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': SCHEMA, 'status': 'failed', 'queue_job_id': ownership['id'],
              'created_at': utc(), 'completed_at': None, 'analysis_settings': dict(SETTINGS),
              'analysis': None, 'selected_results': None, 'release': None, 'protocol': None,
              'implementation': None, 'queue_authorization_implementation': None,
              'selection_implementation': None, 'legacy_selection_implementation': None,
              'release_authority': {}, 'recovery_annex_ref': None, 'protected_manifest_refs': [],
              'inputs_before': {}, 'inputs_after': {}, 'inputs_unchanged': False, 'error': None,
              'scope': 'Source-verified administrative projections; original numerical statistics unchanged; no fabricated supervisor terminal or readiness certification',
              'official_receipt_required': True}
    failure = None
    try:
        manifests, results = load_inputs(root, selected_path, report, annex_path)
        analysis = protocol.analyze(manifests, results, **SETTINGS)
        path = output / 'analysis.json'; release_runner.write_once(path, analysis)
        report['analysis'] = ref(path)
        report['inputs_after'] = observe_after(report['inputs_before'])
        report['inputs_unchanged'] = report['inputs_after'] == report['inputs_before']
        if not report['inputs_unchanged']:
            raise ValueError('Analysis input or implementation changed during derivation')
        report['status'] = 'complete'
    except Exception as error:
        failure = error; report['error'] = type(error).__name__ + ': ' + str(error)
        report['inputs_after'] = observe_after(report['inputs_before'])
        report['inputs_unchanged'] = bool(report['inputs_before']) and report['inputs_after'] == report['inputs_before']
    report['completed_at'] = utc()
    release_runner.write_once(output / 'analysis-provenance.json', report)
    if failure is not None:
        raise failure
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', required=True, type=Path)
    parser.add_argument('--selected-results', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--annex', type=Path)
    args = parser.parse_args(argv)
    try:
        report = analyze_results(args.release_dir, args.selected_results, args.output_dir, annex_path=args.annex)
    except (OSError, ValueError) as error:
        parser.exit(2, 'Refused: ' + str(error) + '\n')
    print(json.dumps({'output_dir': str(args.output_dir.resolve()), 'status': report['status'],
                      'queue_job_id': report['queue_job_id'], 'analysis': report['analysis']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
