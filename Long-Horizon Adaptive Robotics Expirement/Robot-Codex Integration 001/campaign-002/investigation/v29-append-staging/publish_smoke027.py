"""Publish the reviewed single failed Smoke027 metadata append exactly once."""
import json
import os
from pathlib import Path
import stage_append as s

STAGE = s.STAGE / 'smoke027-candidate-001'
EXPECTED = {'candidate-history.json': 'cc2bc83f1c7b887c3e8f16d0cab65beb509f1f7e55e44310833725000375590e', 'qa.json': '5ec67f7796072bdc5a956091a174feb85535d7986f623609c951e821f90a8238', 'staged-receipt.json': '06fd610457a8815b37992ec3e1c5a386f0a193ad65688122c826cde87630978d'}

OLD = '158d678ae62372579298b5c55677d51d0c6ad63dd7779729e58eb69bd6fa0692'
RUNS = ['RCI001-C02-' + name for name in ('smoke-027',)]


def main():
    folder = s.STAGE / 'smoke027-publication-001'
    folder.mkdir()
    qa_path = s.STAGE / 'smoke027-publication-qa.json'
    receipt_path = s.STAGE / 'smoke027-publication-receipt.json'
    pending = folder / 'history.pending'
    s.require(not qa_path.exists() and not receipt_path.exists(), 'Existing publication; reconcile without replay')
    for name, digest in EXPECTED.items():
        s.require(s.bind(STAGE / name)['sha256'] == digest, 'Reviewed candidate changed: ' + name)
    candidate = (STAGE / 'candidate-history.json').read_bytes()
    parsed = json.loads(candidate)
    rows = parsed['attempts'][-1:]
    s.require([r['run_id'] for r in rows] == RUNS, 'Unexpected append set')
    official = folder / 'official'
    official.mkdir()
    cache = {}
    for row in rows:
        s.authenticate(row, official, cache)
    before = s.HISTORY.read_bytes()
    s.require(s.sha(before) == OLD, 'Canonical history changed')
    _, old_spans, _ = s.raw_rows(before)
    _, new_spans, _ = s.raw_rows(candidate)
    s.require(len(old_spans) == 128 and len(new_spans) == 129
              and s.row_spans(new_spans[:128]) == s.row_spans(old_spans), 'Prior raw row changed')
    qa, staged = s.read(STAGE / 'qa.json'), s.read(STAGE / 'staged-receipt.json')
    s.require(qa['passed'] is True and qa['prior_raw_rows_preserved'] == 128
              and qa['active_outputs_read'] is False, 'Candidate QA differs')
    for item in qa['source_helpers']:
        s.require(s.bind(item['path']) == item, 'Report reader changed after QA')
    exports = staged['exports_before_and_after']
    s.require(len(exports) == 19 and [s.bind(v['path']) for v in exports] == exports, 'Prior exports changed')
    s.save(folder / 'intent.json', {'history_before_sha256': OLD,
        'candidate': s.bind(STAGE / 'candidate-history.json'), 'qa': s.bind(STAGE / 'qa.json'),
        'staging_receipt': s.bind(STAGE / 'staged-receipt.json'), 'publisher': s.bind(Path(__file__)),
        'official_jobs': cache, 'rows_before': 128, 'rows_after': 129})
    with qa_path.open('xb') as stream:
        stream.write((STAGE / 'qa.json').read_bytes()); stream.flush(); os.fsync(stream.fileno())
    with pending.open('xb') as stream:
        stream.write(candidate); stream.flush(); os.fsync(stream.fileno())
    s.require(s.HISTORY.read_bytes() == before, 'Concurrent history change')
    os.replace(pending, s.HISTORY)
    s.require(s.HISTORY.read_bytes() == candidate and [s.bind(v['path']) for v in exports] == exports,
              'Publication or export preservation failed')
    receipt = {'schema': 'campaign002-history-append-receipt-1', 'at': s.now(),
        'history_before': staged['prior_history'], 'history_after': s.bind(s.HISTORY),
        'rows_before': 128, 'rows_after': 129, 'prior_raw_rows_preserved': 128, 'appended': RUNS,
        'qa': s.bind(qa_path), 'staging_receipt': s.bind(STAGE / 'staged-receipt.json'),
        'official_authentication': s.bind(folder / 'intent.json'), 'exports_preserved': exports,
        'active_outputs_read': False, 'outcomes_recomputed': False}
    s.save(receipt_path, receipt)
    print(json.dumps({'history': s.bind(s.HISTORY), 'receipt': s.bind(receipt_path), 'rows': 129}))


if __name__ == '__main__':
    main()
