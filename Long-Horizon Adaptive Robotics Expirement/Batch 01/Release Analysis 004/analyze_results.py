"""Queue-only protocol analysis with exact, independently reviewable input lineage.

This wrapper does not select results, change statistics, generate seeds or run
policies. Its completion record still requires a successful official receipt.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
RUNTIME = EXPERIMENT / 'Runtime 004'
MAP = EXPERIMENT / 'Architecture Map'
sys.path.insert(0, str(RUNTIME))
import protocol
import release_runner

SCHEMA = 'source-bound-evaluation-analysis-1'
SETTINGS = {'bootstrap_draws': 2000, 'analysis_seed': 0}


def utc():
    return datetime.now(timezone.utc).isoformat()


def ref(path):
    path = Path(path).resolve()
    before = path.stat()
    value = {'path': str(path), 'sha256': release_runner.digest(path), 'bytes': before.st_size}
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Artifact changed while hashing: ' + str(path))
    return value


def bound(reference, base):
    path = release_runner.reference(reference, base)
    actual = ref(path)
    if actual['sha256'] != reference['sha256'] or ('bytes' in reference and reference['bytes'] != actual['bytes']):
        raise ValueError('Artifact reference differs from exact bytes: ' + str(path))
    return actual


def observe_after(before):
    observed = {}
    for role, original in before.items():
        try:
            observed[role] = ref(original['path'])
        except (OSError, ValueError) as error:
            observed[role] = {'path': original['path'], 'sha256': None, 'bytes': None,
                              'error': type(error).__name__ + ': ' + str(error)}
    return observed


def load_inputs(root, selected_path, report):
    """Record inputs before use; loading never creates a release or result."""
    before = report['inputs_before']
    for role, path in (
            ('implementation', Path(__file__)), ('protocol', Path(protocol.__file__)),
            ('queue_authorization_implementation', Path(release_runner.__file__)),
            ('selected_results', selected_path), ('release', root / 'release.json')):
        before[role] = ref(path)
        report[role] = dict(before[role])
    selected = protocol._load(selected_path)
    if selected.get('schema_version') != 'selected-evaluation-results-1' or not isinstance(selected.get('results'), list):
        raise ValueError('Require the selected-evaluation-results-1 collector artifact')
    if bound(selected.get('release'), selected_path.parent) != before['release']:
        raise ValueError('Selected results are bound to a different release')
    selection = bound(selected.get('implementation'), selected_path.parent)
    if Path(selection['path']) != (HERE / 'collect_results.py').resolve():
        raise ValueError('Selected results do not identify the expected collector implementation')
    before['selection_implementation'] = selection
    report['selection_implementation'] = dict(selection)
    release = protocol._load(root / 'release.json')
    if release.get('schema_version') != protocol.SCHEMA_VERSION:
        raise ValueError('Unsupported protected release schema')
    report['release_id'] = release.get('release_id')
    for role in ('freeze_manifest', 'readiness'):
        before[role] = bound(release.get(role), root)
        report['release_authority'][role] = dict(before[role])
    freeze = protocol._load(before['freeze_manifest']['path'])
    readiness = protocol._load(before['readiness']['path'])
    if (freeze.get('release_id') != release.get('release_id')
            or readiness.get('release_id') != release.get('release_id')
            or readiness.get('freeze_sha256') != before['freeze_manifest']['sha256']):
        raise ValueError('Release/freeze/readiness identity differs')
    if freeze.get('protocol_sha256') != before['protocol']['sha256']:
        raise ValueError('Analysis protocol implementation differs from the frozen protocol')
    references = release.get('manifest_refs')
    if not isinstance(references, list):
        raise ValueError('Protected manifest references are missing')
    for declared in references:
        identity = release_runner.safe_id(declared.get('run_id'))
        role = 'manifest:' + identity
        if role in before:
            raise ValueError('Duplicate protected manifest reference')
        actual = bound(declared, root)
        if not Path(actual['path']).is_relative_to(root):
            raise ValueError('Protected manifest escaped release')
        before[role] = actual
        report['protected_manifest_refs'].append({'run_id': identity, **actual})
    manifests = protocol.load_release(root)
    if {row['run_id'] for row in manifests} != {row['run_id'] for row in report['protected_manifest_refs']}:
        raise ValueError('Protected manifest reference/run identities differ')
    for manifest, reference in zip(manifests, report['protected_manifest_refs']):
        if (manifest['run_id'] != reference['run_id'] or manifest['release_id'] != release.get('release_id')
                or manifest.get('freeze_sha256') != before['freeze_manifest']['sha256']
                or manifest.get('readiness_sha256') != before['readiness']['sha256']
                or manifest.get('artifact_hashes', {}).get('protocol_sha256') != before['protocol']['sha256']):
            raise ValueError('Protected manifest differs from release/frozen protocol authority')
    return manifests, selected['results']


def analyze_results(release_dir, selected_results, output_dir):
    ownership = release_runner.queued_job(expected_script=__file__)
    root, selected_path, output = [Path(path).resolve() for path in (release_dir, selected_results, output_dir)]
    protected = [RUNTIME, MAP, HERE, EXPERIMENT / 'Evidence' / 'raw',
                 root / 'runs', root / 'attempts', root / 'batches']
    if (output.exists() or any(output.is_relative_to(path.resolve()) for path in protected)
            or any(part.casefold() == 'candidate_state' for part in output.parts)):
        raise ValueError('Output must be fresh and outside protected source/canonical/raw/candidate evidence')
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': SCHEMA, 'status': 'failed', 'queue_job_id': ownership['id'],
              'created_at': utc(), 'completed_at': None, 'analysis_settings': dict(SETTINGS),
              'analysis': None, 'selected_results': None, 'release': None, 'protocol': None,
              'implementation': None, 'queue_authorization_implementation': None,
              'selection_implementation': None, 'release_authority': {},
              'protected_manifest_refs': [], 'inputs_before': {}, 'inputs_after': {},
              'inputs_unchanged': False, 'error': None,
              'scope': 'Exact statistical input lineage; statistics unchanged; no result selection or readiness certification',
              'official_receipt_required': True}
    failure = None
    try:
        manifests, results = load_inputs(root, selected_path, report)
        analysis = protocol.analyze(manifests, results, **SETTINGS)
        analysis_path = output / 'analysis.json'
        release_runner.write_once(analysis_path, analysis)
        report['analysis'] = ref(analysis_path)
        report['inputs_after'] = observe_after(report['inputs_before'])
        report['inputs_unchanged'] = report['inputs_after'] == report['inputs_before']
        if not report['inputs_unchanged']:
            raise ValueError('Analysis input or implementation changed during derivation')
        report['status'] = 'complete'
    except Exception as error:
        failure = error
        report['error'] = type(error).__name__ + ': ' + str(error)
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
    args = parser.parse_args(argv)
    try:
        report = analyze_results(args.release_dir, args.selected_results, args.output_dir)
    except (OSError, ValueError) as error:
        parser.exit(2, 'Refused: ' + str(error) + '\n')
    print(json.dumps({'output_dir': str(args.output_dir.resolve()), 'status': report['status'],
                      'queue_job_id': report['queue_job_id'], 'analysis': report['analysis']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
