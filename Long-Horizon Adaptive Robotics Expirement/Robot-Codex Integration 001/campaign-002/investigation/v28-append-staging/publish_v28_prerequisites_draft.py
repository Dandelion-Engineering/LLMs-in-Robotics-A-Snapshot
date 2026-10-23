"""Publish the already reviewed three-prerequisite candidate exactly once."""
import datetime
import importlib.util
import json
import os
from pathlib import Path

IO = next(p for p in Path(__file__).resolve().parents if p.name == 'campaign-002') / 'io-repair'
spec = importlib.util.spec_from_file_location('v28_publication_control', IO / 'control_pilot_retirement_inventory_qualification.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c
I = control.C / 'investigation'
STAGE = I / 'v28-append-staging/prerequisites-001'
HISTORY = I / 'qualification-history.json'
OLD = '567ed5dad7622b2ebdaba38fd8b868a408e8285ad97af6a807253451446ece8d'
NEW = 'd47faa35394d31ad9c0dd10963d6c2be58a5abdd4ba1d1af129dde49d420b176'
JOBS = ('20260929T044038276184Z-34689449', '20260929T044647517233Z-7f498d19',
        '20260929T044654743209Z-a1e89599')
RUNS = ('RCI001-C02-raw-preflight-018', 'RCI001-C02-transport-probe-021', 'RCI001-C02-host-probe-028')


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
    stem = 'qualification-history-append-v28-prerequisites'
    records = I / 'v28-append-staging/prerequisites-publication-001'
    qa_path, receipt_path = I / (stem + '-qa.json'), I / (stem + '-receipt.json')
    pending = I / (stem + '.pending')
    c.require(not any(p.exists() for p in (records, qa_path, receipt_path, pending)),
              'Existing publication state; reconcile without retry')
    # Only metadata is accessed before these three fresh official success gates.
    jobs = [c.admission.base.queue_gate(c.official(job), job) for job in JOBS]
    candidate = c.admission.artifact({'path': str(STAGE / 'candidate-history.json'), 'sha256': NEW})
    qa = c.admission.artifact({'path': str(STAGE / 'qa.json'),
                              'sha256': 'd79f8b5e86c0271edab9b0f58f66baa0dcebe64a12c88a171667dc7df3fb44d7'})
    staged = c.admission.artifact({'path': str(STAGE / 'staged-receipt.json'),
                                  'sha256': 'e3547dda5f3aa70da5efcd830a25bb7ca58be89ac5ed652e38f668498f7812f8'})
    c.require(c.sha(HISTORY) == OLD, 'Current canonical history changed')
    before, after = HISTORY.read_bytes(), candidate.read_bytes()
    old_rows, new_rows = spans(before), spans(after)
    c.require(len(old_rows) == 115 and len(new_rows) == 118 and new_rows[:115] == old_rows
              and tuple(run for run, _ in new_rows[115:]) == RUNS, 'Raw row prefix or append set differs')
    verification, staged_value = c.read(qa), c.read(staged)
    c.require(verification['passed'] is True and verification['prior_raw_rows_preserved'] == 115
              and verification['active_outputs_read'] is False
              and verification['current_qualification_basis'] == 'RCI001-C02-pilot-stock-024'
              and verification['latest_model_qualifier'] == 'RCI001-C02-pilot-stock-024', 'Candidate QA differs')
    exports = staged_value['exports_before_and_after']
    c.require(len(exports) == 19, 'Prior export count differs')
    for item in exports:
        c.admission.artifact(item)
    c.require(c.sha(HISTORY) == OLD and c.sha(candidate) == NEW, 'Inputs changed before publication')
    c.save(records / 'intent.json', {'history_before_sha256': OLD, 'candidate': c.identity(candidate),
        'qa': c.identity(qa), 'staging_receipt': c.identity(staged), 'publisher': c.identity(Path(__file__)),
        'official_jobs': jobs, 'rows_before': 115, 'rows_after': 118})
    with qa_path.open('xb') as stream:
        stream.write(qa.read_bytes()); stream.flush(); os.fsync(stream.fileno())
    with pending.open('xb') as stream:
        stream.write(after); stream.flush(); os.fsync(stream.fileno())
    c.require(HISTORY.read_bytes() == before, 'History changed immediately before replacement')
    os.replace(pending, HISTORY)
    c.require(HISTORY.read_bytes() == after and spans(HISTORY.read_bytes())[:115] == old_rows,
              'Published bytes or prior row prefix differ')
    for item in exports:
        c.admission.artifact(item)
    result = {'schema': 'campaign002-history-append-receipt-1',
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'history_before': staged_value['prior_history'], 'history_after': c.identity(HISTORY),
        'rows_before': 115, 'rows_after': 118, 'prior_raw_rows_preserved': 115,
        'appended': list(RUNS), 'source': c.identity(Path(__file__)), 'qa': c.identity(qa_path),
        'staging_receipt': c.identity(staged), 'official_authentication': c.identity(records / 'intent.json'),
        'exports_preserved': exports, 'outcomes_recomputed': False, 'active_outputs_read': False}
    c.save(receipt_path, result)
    print(json.dumps({'history': c.identity(HISTORY), 'receipt': c.identity(receipt_path),
                      'rows': 118, 'prior_raw_rows_preserved': 115, 'exports_preserved': 19}))


if __name__ == '__main__':
    main()
