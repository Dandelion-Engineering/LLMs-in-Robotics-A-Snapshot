"""Publish the already reviewed three-prerequisite candidate exactly once."""
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
STAGE = I / 'v26-append-staging/prerequisites-002'
HISTORY = I / 'qualification-history.json'
OLD = 'ad51bea18ad83aa5d38cdbe55fbeda60fe1116229cd41a419f0244b55b07a6e4'
NEW = '7fd8c5eebabc67f0e65a6dd943fda1bc1b299445ef618fde68c4f1a32ab6915d'
JOBS = ('20260929T024905690549Z-a4b9b69a', '20260929T025008552255Z-ec16a678',
        '20260929T025331329803Z-28fc8ae2')
RUNS = ('RCI001-C02-raw-preflight-016', 'RCI001-C02-transport-probe-019', 'RCI001-C02-host-probe-026')


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
    stem = 'qualification-history-append-v26-prerequisites'
    records = I / 'v26-append-staging/prerequisites-publication-001'
    qa_path, receipt_path = I / (stem + '-qa.json'), I / (stem + '-receipt.json')
    pending = I / (stem + '.pending')
    c.require(not any(p.exists() for p in (records, qa_path, receipt_path, pending)),
              'Existing publication state; reconcile without retry')
    # Only metadata is accessed before these three fresh official success gates.
    jobs = [c.admission.base.queue_gate(c.official(job), job) for job in JOBS]
    candidate = c.admission.artifact({'path': str(STAGE / 'candidate-history.json'), 'sha256': NEW})
    qa = c.admission.artifact({'path': str(STAGE / 'qa.json'),
                              'sha256': 'c26abdbab255fe9e94e743216106c5bc28afe99a8f54e57aae6eb74bccde8428'})
    staged = c.admission.artifact({'path': str(STAGE / 'staged-receipt.json'),
                                  'sha256': '00463f1771758ec91c9dbedef614004ecf17ed23746231a1f97e72785ecf9ac9'})
    c.require(c.sha(HISTORY) == OLD, 'Current canonical history changed')
    before, after = HISTORY.read_bytes(), candidate.read_bytes()
    old_rows, new_rows = spans(before), spans(after)
    c.require(len(old_rows) == 102 and len(new_rows) == 105 and new_rows[:102] == old_rows
              and tuple(run for run, _ in new_rows[102:]) == RUNS, 'Raw row prefix or append set differs')
    verification, staged_value = c.read(qa), c.read(staged)
    c.require(verification['passed'] is True and verification['prior_raw_rows_preserved'] == 102
              and verification['active_outputs_read'] is False
              and verification['current_qualification_basis'] == 'RCI001-C02-smoke-023'
              and verification['latest_model_qualifier'] == 'RCI001-C02-smoke-023', 'Candidate QA differs')
    exports = staged_value['exports_before_and_after']
    c.require(len(exports) == 19, 'Prior export count differs')
    for item in exports:
        c.admission.artifact(item)
    c.require(c.sha(HISTORY) == OLD and c.sha(candidate) == NEW, 'Inputs changed before publication')
    c.save(records / 'intent.json', {'history_before_sha256': OLD, 'candidate': c.identity(candidate),
        'qa': c.identity(qa), 'staging_receipt': c.identity(staged), 'publisher': c.identity(Path(__file__)),
        'official_jobs': jobs, 'rows_before': 102, 'rows_after': 105})
    with qa_path.open('xb') as stream:
        stream.write(qa.read_bytes()); stream.flush(); os.fsync(stream.fileno())
    with pending.open('xb') as stream:
        stream.write(after); stream.flush(); os.fsync(stream.fileno())
    c.require(HISTORY.read_bytes() == before, 'History changed immediately before replacement')
    os.replace(pending, HISTORY)
    c.require(HISTORY.read_bytes() == after and spans(HISTORY.read_bytes())[:102] == old_rows,
              'Published bytes or prior row prefix differ')
    for item in exports:
        c.admission.artifact(item)
    result = {'schema': 'campaign002-history-append-receipt-1',
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'history_before': staged_value['prior_history'], 'history_after': c.identity(HISTORY),
        'rows_before': 102, 'rows_after': 105, 'prior_raw_rows_preserved': 102,
        'appended': list(RUNS), 'source': c.identity(Path(__file__)), 'qa': c.identity(qa_path),
        'staging_receipt': c.identity(staged), 'official_authentication': c.identity(records / 'intent.json'),
        'exports_preserved': exports, 'outcomes_recomputed': False, 'active_outputs_read': False}
    c.save(receipt_path, result)
    print(json.dumps({'history': c.identity(HISTORY), 'receipt': c.identity(receipt_path),
                      'rows': 105, 'prior_raw_rows_preserved': 102, 'exports_preserved': 19}))


if __name__ == '__main__':
    main()
