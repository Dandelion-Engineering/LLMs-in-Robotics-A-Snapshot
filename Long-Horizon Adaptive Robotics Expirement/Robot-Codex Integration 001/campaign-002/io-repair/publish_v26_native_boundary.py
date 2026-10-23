"""Publish the already reviewed native and boundary candidate exactly once."""
import datetime
import importlib.util
import json
import os
from pathlib import Path

IO = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v26_publication_control', IO / 'control_epoch_readback_qualification.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c
I = control.C / 'investigation'
STAGE = I / 'v26-append-staging/native-boundary-001'
HISTORY = I / 'qualification-history.json'
OLD = '7fd8c5eebabc67f0e65a6dd943fda1bc1b299445ef618fde68c4f1a32ab6915d'
NEW = '08c4031a2823ef9a465fe9a7d89fcc9c59b37811c1b61f98ee905a7d7bf32d04'
JOBS = ('20260929T025825672530Z-d2291210', '20260929T030655223629Z-f3fbf71e')
RUNS = ('RCI001-C02-native-025', 'RCI001-C02-boundary-026')


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
    stem = 'qualification-history-append-v26-native-boundary'
    records = I / 'v26-append-staging/native-boundary-publication-001'
    qa_path, receipt_path = I / (stem + '-qa.json'), I / (stem + '-receipt.json')
    pending = I / (stem + '.pending')
    c.require(not any(p.exists() for p in (records, qa_path, receipt_path, pending)),
              'Existing publication state; reconcile without retry')
    # Only metadata is accessed before these two fresh official success gates.
    jobs = [c.admission.base.queue_gate(c.official(job), job) for job in JOBS]
    candidate = c.admission.artifact({'path': str(STAGE / 'candidate-history.json'), 'sha256': NEW})
    qa = c.admission.artifact({'path': str(STAGE / 'qa.json'),
                              'sha256': '5d5a71505634442872279e06b4a1080b8a825bcaff67662d6188da7fbba42b1f'})
    staged = c.admission.artifact({'path': str(STAGE / 'staged-receipt.json'),
                                  'sha256': 'c36587c7815e17e80f6ff20ea89b8ba4033afe7e079d6c332f52a571e5d3115f'})
    c.require(c.sha(HISTORY) == OLD, 'Current canonical history changed')
    before, after = HISTORY.read_bytes(), candidate.read_bytes()
    old_rows, new_rows = spans(before), spans(after)
    c.require(len(old_rows) == 105 and len(new_rows) == 107 and new_rows[:105] == old_rows
              and tuple(run for run, _ in new_rows[105:]) == RUNS, 'Raw row prefix or append set differs')
    verification, staged_value = c.read(qa), c.read(staged)
    c.require(verification['passed'] is True and verification['prior_raw_rows_preserved'] == 105
              and verification['active_outputs_read'] is False
              and verification['current_qualification_basis'] == 'RCI001-C02-boundary-026'
              and verification['latest_model_qualifier'] == 'RCI001-C02-smoke-023', 'Candidate QA differs')
    exports = staged_value['exports_before_and_after']
    c.require(len(exports) == 19, 'Prior export count differs')
    for item in exports:
        c.admission.artifact(item)
    c.require(c.sha(HISTORY) == OLD and c.sha(candidate) == NEW, 'Inputs changed before publication')
    c.save(records / 'intent.json', {'history_before_sha256': OLD, 'candidate': c.identity(candidate),
        'qa': c.identity(qa), 'staging_receipt': c.identity(staged), 'publisher': c.identity(Path(__file__)),
        'official_jobs': jobs, 'rows_before': 105, 'rows_after': 107})
    with qa_path.open('xb') as stream:
        stream.write(qa.read_bytes()); stream.flush(); os.fsync(stream.fileno())
    with pending.open('xb') as stream:
        stream.write(after); stream.flush(); os.fsync(stream.fileno())
    c.require(HISTORY.read_bytes() == before, 'History changed immediately before replacement')
    os.replace(pending, HISTORY)
    c.require(HISTORY.read_bytes() == after and spans(HISTORY.read_bytes())[:105] == old_rows,
              'Published bytes or prior row prefix differ')
    for item in exports:
        c.admission.artifact(item)
    result = {'schema': 'campaign002-history-append-receipt-1',
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'history_before': staged_value['prior_history'], 'history_after': c.identity(HISTORY),
        'rows_before': 105, 'rows_after': 107, 'prior_raw_rows_preserved': 105,
        'appended': list(RUNS), 'source': c.identity(Path(__file__)), 'qa': c.identity(qa_path),
        'staging_receipt': c.identity(staged), 'official_authentication': c.identity(records / 'intent.json'),
        'exports_preserved': exports, 'outcomes_recomputed': False, 'active_outputs_read': False}
    c.save(receipt_path, result)
    print(json.dumps({'history': c.identity(HISTORY), 'receipt': c.identity(receipt_path),
                      'rows': 107, 'prior_raw_rows_preserved': 105, 'exports_preserved': 19}))


if __name__ == '__main__':
    main()
