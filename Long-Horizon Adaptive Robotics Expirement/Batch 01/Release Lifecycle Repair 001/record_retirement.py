"""Record r3 retirement from canonical metadata only; never inspect seed files."""
import datetime
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent.parent
sys.path.insert(0, str(EXP / 'Runtime'))
import release_runner


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    job = release_runner.queued_job(Path(__file__))
    root = EXP / 'Evidence/releases/batch01-eval-r3'
    release = read(root / 'release.json')
    stopped_path = EXP / 'Evidence/release-series/batch01-eval-r3-series-001/stopped.json'
    stopped = read(stopped_path)
    diagnostic_path = EXP / 'Evidence/derived/r3-timeout-incident-001/diagnostic.json'
    diagnostic = read(diagnostic_path)
    assert diagnostic['recorded_owned_inference_timeout_confirmed'] is True
    assert diagnostic['inputs_unchanged'] is True
    assert diagnostic['post_run_integrity']['passed'] is True
    planned = [row['run_id'] for row in release['manifest_refs']]
    assert len(planned) == len(set(planned)) == 264
    finalized, receipts, batch_refs = [], [], []
    for batch in stopped['completed_batches']:
        marker = Path(batch['finalized_marker'])
        assert ref(marker)['sha256'] == batch['finalized_marker_sha256']
        final = read(marker)
        finalized.extend(final['run_ids'])
        batch_refs.append(ref(marker))
        for key in ('run_job', 'finalize_job'):
            receipt = Path(batch[key]['receipt_path'])
            assert ref(receipt)['sha256'] == batch[key]['receipt_sha256']
            value = read(receipt)
            assert value['state'] == 'succeeded' and type(value['exit_status']) is int and value['exit_status'] == 0
            receipts.append(ref(receipt))
    terminal_paths = {p.parent.name: p for p in (root / 'attempts').glob('*/terminal.json')}
    assert set(terminal_paths) == set(finalized) and len(finalized) == 5
    attempted = [run for run in planned if run in terminal_paths]
    unlaunched = [run for run in planned if run not in terminal_paths]
    assert len(unlaunched) == 259
    assert all(not (root / 'attempts' / run).exists() for run in unlaunched)
    diagnostic_receipt = EXP / 'Evidence/queue-receipts' / (diagnostic['queue_job_id'] + '.json')
    dr = read(diagnostic_receipt)
    assert dr['state'] == 'succeeded' and type(dr['exit_status']) is int and dr['exit_status'] == 0
    result = {
        'schema_version': 'batch01-lifecycle-incident-retirement-1',
        'recorded_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'queue_job_id': job['id'], 'operator': 'Codex root, continuing session 4',
        'decision': 'Retire r3 after a confirmed common timeout lifecycle bug. Preserve all original files and five canonical attempts; do not retry, reclassify, or continue this release. Prepare a separate Runtime 004 and full fresh r4 comparison after actual qualification and verification.',
        'retired_release': ref(root / 'release.json'), 'coordinator_stop': ref(stopped_path),
        'diagnostic': ref(diagnostic_path), 'diagnostic_receipt': ref(diagnostic_receipt),
        'finalized_batches': batch_refs, 'official_receipts': receipts,
        'attempted_count': 5, 'attempted_run_ids': attempted,
        'canonical_terminals': [ref(terminal_paths[run]) for run in attempted],
        'unlaunched_count': 259, 'unlaunched_run_ids': unlaunched,
        'incident_interpretation': 'A 30-second inference timeout intentionally clears the owned server process before termination finishes. The supervisor observes no expected PID before collecting the timeout, misclassifying the configured request-budget failure as missing infrastructure observation. The recorded later model_error confirms intentional timeout shutdown. This is a systematic lifecycle defect, not an isolated host incident.',
        'prospective_change': 'Publish authoritative thread-safe timeout lifecycle provenance before clearing the process. Count an active request-budget timeout as an explicit failed policy attempt. Preserve genuine sampled cap breaches, unexplained process loss, and unavailable evidence as infrastructure failures. Preserve completion and late-call accounting. No grace period, restart or inference-budget increase.',
        'scope': [
            'Original Runtime, r3 indexes, freeze, readiness, controls, receipts, attempts and failures stay byte-identical.',
            'New Runtime 004 changes only lifecycle supervision and its regressions; physical helpers, policies, prompts, model, budgets, evaluator, matrix, trace slots and statistics are retained.',
            'Pinned large vendor assets share immutable hard links; never overwrite either alias. This is storage reuse, not an independent backup.',
            'Absolute meshdir is part of the physical class identity. Build and compare actual compiled models, then repeat the same seven A-only construction and six validation worlds at the new Runtime path under unchanged numerical rules. Previously inspected worlds are not held-out evidence.',
            'Run the actual persistent/no-persistence common A3 validation pair after source closure; retain all failures. No automatic retries.',
            'Use a fresh complete 264-attempt release only after evidence-bound readiness. Concealed seeds are not inspected or reused; scored outcomes do not tune policies.',
            'Historical engineering hours remain unmeasured; no time-ceiling compliance claim is introduced.'
        ]
    }
    output = HERE / 'retirement-r3-and-r4-decision-001.json'
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'record': ref(output), 'attempted': 5, 'unlaunched': 259}))


if __name__ == '__main__':
    main()
