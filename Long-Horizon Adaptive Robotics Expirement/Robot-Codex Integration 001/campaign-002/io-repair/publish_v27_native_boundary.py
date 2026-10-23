"""Publish the already reviewed native and boundary candidate exactly once."""
import datetime
import importlib.util
import json
import os
from pathlib import Path

IO = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v27_native_boundary_publication_control', IO / 'control_prepared_index_label_qualification.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c
I = control.C / 'investigation'
STAGE = I / 'v27-append-staging/native-boundary-001'
HISTORY = I / 'qualification-history.json'
OLD = '9973018f0347576af7c4598b070fe4d431236d697f8c9614e0c4b3f9613635c2'
NEW = 'bed5a7900692eaf4cb1c2dd9978a9de6947360182998a75b620a5059b19daf45'
JOBS = ('20260929T035108044594Z-0996c06c', '20260929T035938575014Z-eec4e520')
RUNS = ('RCI001-C02-native-026', 'RCI001-C02-boundary-027')


def spans(raw):
    text = raw.decode('utf-8')
    marker = '"attempts": ['
    c.require(text.count(marker) == 1, 'Ambiguous row array')
    pos, rows, decoder = text.index(marker) + len(marker), [], json.JSONDecoder()
    while True:
        while text[pos].isspace() or text[pos] == ',':
            pos += 1
        if text[pos] == ']':
            return rows
        value, end = decoder.raw_decode(text, pos)
        rows.append((value['run_id'], text[pos:end].encode('utf-8')))
        pos = end


def main():
    stem = 'qualification-history-append-v27-native-boundary'
    records = I / 'v27-append-staging/native-boundary-publication-001'
    qa_path, receipt_path = I / (stem + '-qa.json'), I / (stem + '-receipt.json')
    pending = I / (stem + '.pending')
    c.require(not any(p.exists() for p in (records, qa_path, receipt_path, pending)),
              'Existing publication state; reconcile without retry')
    # Only metadata is accessed before these two fresh official success gates.
    jobs = [c.admission.base.queue_gate(c.official(job), job) for job in JOBS]
    candidate = c.admission.artifact({'path': str(STAGE / 'candidate-history.json'), 'sha256': NEW})
    qa = c.admission.artifact({'path': str(STAGE / 'qa.json'),
                              'sha256': '5cb5ea4cc68c744a98893f73b6d2b090a3ee3f87e7cd23a39fe8cf5ae78cac45'})
    staged = c.admission.artifact({'path': str(STAGE / 'staged-receipt.json'),
                                  'sha256': 'a70e7ef8a8d6c39945afeefd1e333c35412f286462114523c4dc82d0fb602cd9'})
    c.require(c.sha(HISTORY) == OLD, 'Current canonical history changed')
    before, after = HISTORY.read_bytes(), candidate.read_bytes()
    old_rows, new_rows = spans(before), spans(after)
    c.require(len(old_rows) == 111 and len(new_rows) == 113 and new_rows[:111] == old_rows
              and tuple(run for run, _ in new_rows[111:]) == RUNS, 'Raw row prefix or append set differs')
    verification, staged_value = c.read(qa), c.read(staged)
    c.require(verification['passed'] is True and verification['prior_raw_rows_preserved'] == 111
              and verification['active_outputs_read'] is False
              and verification['current_qualification_basis'] == 'RCI001-C02-boundary-027'
              and verification['latest_model_qualifier'] == 'RCI001-C02-smoke-024', 'Candidate QA differs')
    exports = staged_value['exports_before_and_after']
    c.require(len(exports) == 19, 'Prior export count differs')
    for item in exports:
        c.admission.artifact(item)
    c.require(c.sha(HISTORY) == OLD and c.sha(candidate) == NEW, 'Inputs changed before publication')
    c.save(records / 'intent.json', {'history_before_sha256': OLD, 'candidate': c.identity(candidate),
        'qa': c.identity(qa), 'staging_receipt': c.identity(staged), 'publisher': c.identity(Path(__file__)),
        'official_jobs': jobs, 'rows_before': 111, 'rows_after': 113})
    with qa_path.open('xb') as stream:
        stream.write(qa.read_bytes()); stream.flush(); os.fsync(stream.fileno())
    with pending.open('xb') as stream:
        stream.write(after); stream.flush(); os.fsync(stream.fileno())
    c.require(HISTORY.read_bytes() == before, 'History changed immediately before replacement')
    os.replace(pending, HISTORY)
    c.require(HISTORY.read_bytes() == after and spans(HISTORY.read_bytes())[:111] == old_rows,
              'Published bytes or prior row prefix differ')
    for item in exports:
        c.admission.artifact(item)
    result = {'schema': 'campaign002-history-append-receipt-1',
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'history_before': staged_value['prior_history'], 'history_after': c.identity(HISTORY),
        'rows_before': 111, 'rows_after': 113, 'prior_raw_rows_preserved': 111,
        'appended': list(RUNS), 'source': c.identity(Path(__file__)), 'qa': c.identity(qa_path),
        'staging_receipt': c.identity(staged), 'official_authentication': c.identity(records / 'intent.json'),
        'exports_preserved': exports, 'outcomes_recomputed': False, 'active_outputs_read': False}
    c.save(receipt_path, result)
    print(json.dumps({'history': c.identity(HISTORY), 'receipt': c.identity(receipt_path),
                      'rows': 113, 'prior_raw_rows_preserved': 111, 'exports_preserved': 19}))


if __name__ == '__main__':
    main()
