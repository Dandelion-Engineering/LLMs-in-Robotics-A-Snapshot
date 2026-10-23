"""Publish the reviewed two-row native and boundary S15 append exactly once."""
import json
import os
from pathlib import Path
import stage_append as s

STAGE = s.STAGE / 'native-boundary-candidate-001'
EXPECTED = {'candidate-history.json': '158d678ae62372579298b5c55677d51d0c6ad63dd7779729e58eb69bd6fa0692', 'qa.json': '624dc461a5523de1d0c7f4c324326eb025ed8345560bfc3775d98f239d150c9b', 'staged-receipt.json': '5f228ecc26348614113d067ef04915bb276368f4018fb1f1b81d573fc1972df6'}

OLD = 'c489e16ed02b9e11f32157a44384e3d0c59cbbfd3c506cdb685f2e64b8bdf153'
RUNS = ['RCI001-C02-' + name for name in ('native-028', 'boundary-029')]


def main():
    folder = s.STAGE / 'native-boundary-publication-001'
    folder.mkdir()
    qa_path = s.STAGE / 'native-boundary-publication-qa.json'
    receipt_path = s.STAGE / 'native-boundary-publication-receipt.json'
    pending = folder / 'history.pending'
    s.require(not qa_path.exists() and not receipt_path.exists(), 'Existing publication; reconcile without replay')
    for name, digest in EXPECTED.items():
        s.require(s.bind(STAGE / name)['sha256'] == digest, 'Reviewed candidate changed: ' + name)
    candidate = (STAGE / 'candidate-history.json').read_bytes()
    parsed = json.loads(candidate)
    rows = parsed['attempts'][-2:]
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
    s.require(len(old_spans) == 126 and len(new_spans) == 128
              and s.row_spans(new_spans[:126]) == s.row_spans(old_spans), 'Prior raw row changed')
    qa, staged = s.read(STAGE / 'qa.json'), s.read(STAGE / 'staged-receipt.json')
    s.require(qa['passed'] is True and qa['prior_raw_rows_preserved'] == 126
              and qa['active_outputs_read'] is False, 'Candidate QA differs')
    for item in qa['source_helpers']:
        s.require(s.bind(item['path']) == item, 'Report reader changed after QA')
    exports = staged['exports_before_and_after']
    s.require(len(exports) == 19 and [s.bind(v['path']) for v in exports] == exports, 'Prior exports changed')
    s.save(folder / 'intent.json', {'history_before_sha256': OLD,
        'candidate': s.bind(STAGE / 'candidate-history.json'), 'qa': s.bind(STAGE / 'qa.json'),
        'staging_receipt': s.bind(STAGE / 'staged-receipt.json'), 'publisher': s.bind(Path(__file__)),
        'official_jobs': cache, 'rows_before': 126, 'rows_after': 128})
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
        'rows_before': 126, 'rows_after': 128, 'prior_raw_rows_preserved': 126, 'appended': RUNS,
        'qa': s.bind(qa_path), 'staging_receipt': s.bind(STAGE / 'staged-receipt.json'),
        'official_authentication': s.bind(folder / 'intent.json'), 'exports_preserved': exports,
        'active_outputs_read': False, 'outcomes_recomputed': False}
    s.save(receipt_path, receipt)
    print(json.dumps({'history': s.bind(s.HISTORY), 'receipt': s.bind(receipt_path), 'rows': 128}))


if __name__ == '__main__':
    main()
