"""Publish the reviewed four-row initial S15 append exactly once."""
import json
import os
from pathlib import Path
import stage_append as s

STAGE = s.STAGE / 'initial-candidate-001'
EXPECTED = {
    'candidate-history.json': 'c489e16ed02b9e11f32157a44384e3d0c59cbbfd3c506cdb685f2e64b8bdf153',
    'qa.json': '68320905b3de1c8e6a0502b92e7e419bbf7db4fbacc3baf73472caaf56cd1f31',
    'staged-receipt.json': '4e99d020e91ac8225a5d56017dad1ffe6885a6e6824407e614207725d57490a8',
}
OLD = 'bb442fab8fbd4a37c7ea52f15213863da173c96f1a090fafe9d2b010139c35c5'
RUNS = ['RCI001-C02-' + name for name in ('shutdown-diagnostic-004', 'raw-preflight-019', 'transport-probe-022', 'host-probe-029')]


def main():
    folder = s.STAGE / 'initial-publication-001'
    folder.mkdir()
    qa_path = s.I / 'qualification-history-append-session15-qa.json'
    receipt_path = s.I / 'qualification-history-append-session15-receipt.json'
    pending = folder / 'history.pending'
    s.require(not qa_path.exists() and not receipt_path.exists(), 'Existing publication; reconcile without replay')
    for name, digest in EXPECTED.items():
        s.require(s.bind(STAGE / name)['sha256'] == digest, 'Reviewed candidate changed: ' + name)
    candidate = (STAGE / 'candidate-history.json').read_bytes()
    parsed = json.loads(candidate)
    rows = parsed['attempts'][-4:]
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
    s.require(len(old_spans) == 122 and len(new_spans) == 126
              and s.row_spans(new_spans[:122]) == s.row_spans(old_spans), 'Prior raw row changed')
    qa, staged = s.read(STAGE / 'qa.json'), s.read(STAGE / 'staged-receipt.json')
    s.require(qa['passed'] is True and qa['prior_raw_rows_preserved'] == 122
              and qa['active_outputs_read'] is False, 'Candidate QA differs')
    for item in qa['source_helpers']:
        s.require(s.bind(item['path']) == item, 'Report reader changed after QA')
    exports = staged['exports_before_and_after']
    s.require(len(exports) == 19 and [s.bind(v['path']) for v in exports] == exports, 'Prior exports changed')
    s.save(folder / 'intent.json', {'history_before_sha256': OLD,
        'candidate': s.bind(STAGE / 'candidate-history.json'), 'qa': s.bind(STAGE / 'qa.json'),
        'staging_receipt': s.bind(STAGE / 'staged-receipt.json'), 'publisher': s.bind(Path(__file__)),
        'official_jobs': cache, 'rows_before': 122, 'rows_after': 126})
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
        'rows_before': 122, 'rows_after': 126, 'prior_raw_rows_preserved': 122, 'appended': RUNS,
        'qa': s.bind(qa_path), 'staging_receipt': s.bind(STAGE / 'staged-receipt.json'),
        'official_authentication': s.bind(folder / 'intent.json'), 'exports_preserved': exports,
        'active_outputs_read': False, 'outcomes_recomputed': False}
    s.save(receipt_path, receipt)
    print(json.dumps({'history': s.bind(s.HISTORY), 'receipt': s.bind(receipt_path), 'rows': 126}))


if __name__ == '__main__':
    main()
