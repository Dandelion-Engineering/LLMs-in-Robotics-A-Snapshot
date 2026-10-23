"""Publish the reviewed Native003 failed-queue candidate exactly once; never assess."""
import datetime
import importlib.util
import json
import os
from pathlib import Path

IO = next(p for p in Path(__file__).resolve().parents if p.name == 'campaign-002') / 'io-repair'
spec = importlib.util.spec_from_file_location('v28_smoke026_failed_publication_control', IO / 'control_pilot_retirement_inventory_qualification.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c
I = control.C / 'investigation'
STAGE = I / 'native003-append-staging/candidate-001'
HISTORY = I / 'qualification-history.json'
OLD = 'f46117ad3ac5ae065bb210d057fed4e48dbb0d484019165b89ea6361c0d2ba82'
NEW = 'bb442fab8fbd4a37c7ea52f15213863da173c96f1a090fafe9d2b010139c35c5'
JOBS = ('20260929T060538760771Z-877e2765',)
RUNS = ('RCI001-C02-shutdown-diagnostic-003',)


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
    stem = 'qualification-history-append-native003'
    records = I / 'native003-append-staging/publication-001'
    qa_path, receipt_path = I / (stem + '-qa.json'), I / (stem + '-receipt.json')
    pending = I / (stem + '.pending')
    c.require(not any(p.exists() for p in (records, qa_path, receipt_path, pending)),
              'Existing publication state; reconcile without retry')
    # Only metadata is accessed before this fresh official failed/integer-one gate.
    jobs = [c.official(job) for job in JOBS]
    c.require(all(job.get('state') == 'failed' and type(job.get('exit_status')) is int
                  and job['exit_status'] == 1 for job in jobs),
              'Original failed integer-one job required; no assessment permitted')
    candidate = c.admission.artifact({'path': str(STAGE / 'candidate-history.json'), 'sha256': NEW})
    qa = c.admission.artifact({'path': str(STAGE / 'qa.json'),
                              'sha256': '4f16fc9fbd89068bd782edb7cb819a269f2784ab41514276a3debbad68b64841'})
    staged = c.admission.artifact({'path': str(STAGE / 'staged-receipt.json'),
                                  'sha256': '70253b113ff924c09200a7b4328e031a2903e2327164b9bee31be323f6359538'})
    c.require(c.sha(HISTORY) == OLD, 'Current canonical history changed')
    before, after = HISTORY.read_bytes(), candidate.read_bytes()
    old_rows, new_rows = spans(before), spans(after)
    c.require(len(old_rows) == 121 and len(new_rows) == 122 and new_rows[:121] == old_rows
              and tuple(run for run, _ in new_rows[121:]) == RUNS, 'Raw row prefix or append set differs')
    selected = json.loads(after)['attempts'][-1]
    c.require(selected.get('assessment_state') == 'not_assessed' and selected.get('validity') == 'unknown'
              and selected.get('task_outcome') == 'unknown' and selected.get('model_calls') is None
              and selected.get('queue_failure_contract', {}).get('schema') == 'campaign002-failed-single-interrupt-queue-1'
              and len(selected.get('artifacts', [])) == 3 and selected.get('details') == {}
              and all(selected['queue'].get(k) == jobs[0].get(k) for k in
                      ('id', 'state', 'exit_status', 'started_at', 'ended_at')),
              'Failed queue scope or official metadata differs')
    verification, staged_value = c.read(qa), c.read(staged)
    c.require(verification['passed'] is True and verification['prior_raw_rows_preserved'] == 121
              and verification['active_outputs_read'] is False
              and verification['current_qualification_basis'] == 'RCI001-C02-shutdown-diagnostic-003'
              and verification['latest_model_qualifier'] == 'RCI001-C02-smoke-026', 'Candidate QA differs')
    exports = staged_value['exports_before_and_after']
    c.require(len(exports) == 19, 'Prior export count differs')
    for item in exports:
        c.admission.artifact(item)
    c.require(c.sha(HISTORY) == OLD and c.sha(candidate) == NEW, 'Inputs changed before publication')
    c.save(records / 'intent.json', {'history_before_sha256': OLD, 'candidate': c.identity(candidate),
        'qa': c.identity(qa), 'staging_receipt': c.identity(staged), 'publisher': c.identity(Path(__file__)),
        'official_jobs': jobs, 'rows_before': 121, 'rows_after': 122})
    with qa_path.open('xb') as stream:
        stream.write(qa.read_bytes()); stream.flush(); os.fsync(stream.fileno())
    with pending.open('xb') as stream:
        stream.write(after); stream.flush(); os.fsync(stream.fileno())
    c.require(HISTORY.read_bytes() == before, 'History changed immediately before replacement')
    os.replace(pending, HISTORY)
    c.require(HISTORY.read_bytes() == after and spans(HISTORY.read_bytes())[:121] == old_rows,
              'Published bytes or prior row prefix differ')
    for item in exports:
        c.admission.artifact(item)
    result = {'schema': 'campaign002-history-append-receipt-1',
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'history_before': staged_value['prior_history'], 'history_after': c.identity(HISTORY),
        'rows_before': 121, 'rows_after': 122, 'prior_raw_rows_preserved': 121,
        'appended': list(RUNS), 'source': c.identity(Path(__file__)), 'qa': c.identity(qa_path),
        'staging_receipt': c.identity(staged), 'official_authentication': c.identity(records / 'intent.json'),
        'exports_preserved': exports, 'outcomes_recomputed': False, 'active_outputs_read': False}
    c.save(receipt_path, result)
    print(json.dumps({'history': c.identity(HISTORY), 'receipt': c.identity(receipt_path),
                      'rows': 122, 'prior_raw_rows_preserved': 121, 'exports_preserved': 19}))


if __name__ == '__main__':
    main()
