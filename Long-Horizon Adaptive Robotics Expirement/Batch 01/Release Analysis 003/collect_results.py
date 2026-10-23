"""Select finalized evaluation results without discarding corrections or failures.

Operator only. This never launches physics, draws seeds or rewrites evidence.
Missing attempts remain missing; a complete matrix is required by --complete.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
RUNTIME = EXPERIMENT / 'Runtime'
MAP = EXPERIMENT / 'Architecture Map'
sys.path.insert(0, str(RUNTIME))
import protocol
import release_runner


def read(path):
    return protocol._load(path)


def ref(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def current_result(records, run_id):
    rows = [r for r in records if r.get('run_id') == run_id]
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate result record identity')
    ids = {r['id'] for r in rows}
    if any(r.get('supersedes_result_id') is not None and r['supersedes_result_id'] not in ids for r in rows):
        raise ValueError('Supersession crosses run or lacks its predecessor')
    superseded = {r.get('supersedes_result_id') for r in rows}
    leaves = [r for r in rows if r['id'] not in superseded]
    if len(leaves) != 1:
        raise ValueError('Expected one unambiguous current canonical result for ' + run_id)
    # A unique leaf alone does not rule out a disconnected cycle.
    lookup = {r['id']: r for r in rows}
    seen = set(); row = leaves[0]
    while row is not None:
        if row['id'] in seen:
            raise ValueError('Cyclic result supersession')
        seen.add(row['id'])
        row = lookup.get(row.get('supersedes_result_id'))
    if seen != ids:
        raise ValueError('Disconnected or branched result history')
    return leaves[0], [r for r in rows if r['id'] in seen]


def selected_flat(terminal, assessment):
    """Canonical outcome controls; raw independent_success cannot override it."""
    raw = terminal['result']
    if raw.get('run_id') != terminal.get('run_id') or assessment.get('run_id') != raw.get('run_id'):
        raise ValueError('Terminal/canonical run mismatch')
    if raw.get('stage') != 'evaluation' or raw.get('execution_status') not in protocol.TERMINAL:
        raise ValueError('Original terminal must explicitly identify terminal evaluation execution')
    result = {k: assessment.get(k) for k in ('run_id', 'execution_status', 'validity',
              'validity_reason', 'outcome', 'ended_at', 'termination_reason')}
    result['stage'] = 'evaluation'
    for key in ('failure_class', 'invalidity_class', 'infrastructure_invalid'):
        result[key] = assessment.get('details', {}).get(key, raw.get(key))
    metrics = {}
    aliases = {'completion_time': 'completion_time_s', 'duration': 'wall_duration_s'}
    for metric in assessment.get('metrics', []):
        key = aliases.get(metric['name'], metric['name'])
        if key in ('completion_time_s', 'wall_duration_s', 'model_calls', 'total_tokens'):
            if key in metrics:
                raise ValueError('Ambiguous canonical metric ' + key)
            if metric.get('value') is not None and not protocol._numeric(metric['value']):
                raise ValueError('Nonfinite/negative canonical metric ' + key)
            if metric.get('value') is not None and key.endswith('_s') and metric.get('unit') != 's':
                raise ValueError('Canonical clock metric requires seconds')
            metrics[key] = metric.get('value')
    corrected = assessment.get('supersedes_result_id') is not None
    for key in ('completion_time_s', 'wall_duration_s', 'model_calls', 'total_tokens'):
        result[key] = metrics[key] if key in metrics else (None if corrected else raw.get(key))
    if result['outcome'] != 'success':
        result['completion_time_s'] = None
    breached = (release_runner.integrity_breach(terminal)
                or terminal.get('post_run_integrity', {}).get('passed') is False)
    if breached:
        result.update(validity='invalid', invalidity_class='infrastructure', infrastructure_invalid=True,
                      validity_reason='Protected terminal integrity check failed; original task result retained separately')
    # Missing post-run integrity cannot be silently upgraded by a map assessment.
    elif terminal.get('post_run_integrity', {}).get('passed') is not True:
        result.update(validity='unknown', validity_reason='Post-run integrity evidence unavailable')
    if protocol._infra_invalid(raw) or assessment.get('details', {}).get('infrastructure_invalid') is True:
        result.update(validity='invalid', invalidity_class='infrastructure', infrastructure_invalid=True)
    if terminal.get('excluded_from_primary_by_prior_review') is True:
        result.update(infrastructure_invalid=True, invalidity_class='infrastructure',
                      primary_exclusion_reason='Whole paired block excluded by prior retained incident review')
    result['selected_canonical_result_id'] = assessment['id']
    return result


def verified_terminal(root, run_id, release_hash, manifest_hash):
    release_runner.safe_id(run_id)
    path = (root / 'attempts' / run_id / 'terminal.json').resolve()
    if not path.is_relative_to(root):
        raise ValueError('Attempt path escaped release')
    terminal = read(path); source = ref(path)
    if (terminal.get('run_id') != run_id or terminal.get('release_sha256') != release_hash
            or terminal.get('manifest_sha256') != manifest_hash):
        raise ValueError('Terminal differs from protected release/manifest')
    job = release_runner.safe_id(terminal.get('queue_job_id'))
    batch = root / 'batches' / job
    planned, finished, finalized = [read(batch / name) for name in ('planned.json', 'finished.json', 'finalized.json')]
    receipt_path = batch / 'official-queue-status.json'; receipt = read(receipt_path)
    if any(obj.get('queue_job_id') != job for obj in (planned, finished, finalized)):
        raise ValueError('Batch job identities differ')
    if planned.get('release_sha256') != release_hash or run_id not in planned.get('selected_run_ids', []):
        raise ValueError('Attempt is not bound to batch plan')
    if run_id not in finished.get('terminal_run_ids', []) or run_id not in finalized.get('run_ids', []):
        raise ValueError('Attempt lacks explicit terminal finalization')
    if (receipt.get('id') != job or receipt.get('state') != 'succeeded'
            or type(receipt.get('exit_status')) is not int or receipt['exit_status'] != 0
            or ref(receipt_path)['sha256'] != finalized.get('official_queue_receipt_sha256')):
        raise ValueError('Official finalization receipt is missing or changed')
    matches = [r for r in finished.get('terminal_refs', []) if r.get('run_id') == run_id]
    if len(matches) != 1 or release_runner.reference(matches[0], root) != path:
        raise ValueError('Terminal lacks exact batch reference')
    raw_ref = terminal.get('supervisor_result_ref')
    if raw_ref:
        raw_path = release_runner.reference(raw_ref, path.parent)
        if read(raw_path) != terminal['result']:
            raise ValueError('Immutable raw result differs from terminal')
    provenance = {'terminal': source, 'batch_plan': ref(batch / 'planned.json'),
                  'batch_finished': ref(batch / 'finished.json'), 'finalization': ref(batch / 'finalized.json'),
                  'official_queue_receipt': ref(receipt_path), 'supervisor_result': raw_ref,
                  'prior_continuation': copy.deepcopy(terminal.get('continuation'))}
    return terminal, provenance


def collect(root, records, *, complete=False):
    root = Path(root).resolve(); release_source = ref(root / 'release.json')
    manifests = protocol.load_release(root)
    release = read(root / 'release.json')
    manifest_hashes = {read(root / r['path'])['run_id']: r['sha256'] for r in release['manifest_refs']}
    results = []; provenance = []; missing = []
    for manifest in manifests:
        rid = release_runner.safe_id(manifest['run_id']); terminal_path = root / 'attempts' / rid / 'terminal.json'
        if not terminal_path.is_file():
            if any(r.get('run_id') == rid for r in records):
                raise ValueError('Canonical result exists without terminal evidence: ' + rid)
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
        results.append(selected_flat(terminal, assessment))
        provenance.append({'run_id': rid, 'selected_assessment': assessment,
                           'canonical_history_ids': [row['id'] for row in history], **evidence})
    if complete and missing:
        raise ValueError('Full release incomplete: ' + str(len(missing)) + ' terminal attempts missing')
    for evidence in provenance:
        for key in ('terminal', 'batch_plan', 'batch_finished', 'finalization', 'official_queue_receipt'):
            if ref(evidence[key]['path']) != evidence[key]:
                raise ValueError('Evidence changed during collection')
    if ref(root / 'release.json') != release_source:
        raise ValueError('Release changed during collection')
    return {'schema_version': 'selected-evaluation-results-1', 'created_at': datetime.now(timezone.utc).isoformat(),
            'release': release_source, 'results': results, 'provenance': provenance, 'missing': missing,
            'counts': {'planned': len(manifests), 'selected_terminal': len(results), 'missing_terminal': len(missing)},
            'complete_terminal_accounting': not missing,
            'scope': 'Canonical outcome selection with protected integrity propagation; no original result mutation'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--complete', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(MAP) or output.is_relative_to(RUNTIME) or any(p.casefold() == 'candidate_state' for p in output.parts):
        raise ValueError('Output must be fresh and outside canonical/source/candidate data')
    map_path = MAP / 'results.jsonl'; map_source = ref(map_path)
    records = [json.loads(line) for line in map_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    report = collect(args.release_dir, records, complete=args.complete)
    if ref(map_path) != map_source:
        raise ValueError('Canonical map changed during selection')
    report['canonical_results_source'] = map_source; report['implementation'] = ref(__file__)
    output.parent.mkdir(parents=True, exist_ok=True)
    release_runner.write_once(output, report)
    print(json.dumps({'output': str(output), 'counts': report['counts'], 'complete': report['complete_terminal_accounting']}))


if __name__ == '__main__':
    main()
