"""Prepare and validate the authorized V25 history append; never publish exports."""
from pathlib import Path
import copy
import datetime
import hashlib
import importlib.util
import json
import sys

STAGE = Path(__file__).resolve().parent
I = STAGE.parent
C = I.parent
IO = C / 'io-repair'
Q = C / 'qualification'
REPO = C.parents[2]
HISTORY = I / 'qualification-history.json'
OLD_SHA = '44f1d84fab0d5bf515aa0f7b552dde567ee49be3fdd8900e029f728c224f2a69'
SNAP_SHA = '10bc9fea95804c0707264a608881cab94b67cac65582e4c57bdf8cbc9c877a0e'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def save(name, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    with (STAGE / name).open('xb') as file:
        file.write(raw)
    return bind(STAGE / name)


def bind(path, label=None):
    path = Path(path).resolve()
    assert path.is_file() and not path.is_symlink(), path
    raw = path.read_bytes()
    value = {'path': str(path), 'sha256': sha(raw), 'bytes': len(raw)}
    return dict(label=label, **value) if label else value


def raw_rows(raw):
    text = raw.decode('utf-8')
    marker = '"attempts": ['
    assert text.count(marker) == 1
    pos = text.index(marker) + len(marker)
    result = []
    decoder = json.JSONDecoder()
    while True:
        while text[pos].isspace() or text[pos] == ',':
            pos += 1
        if text[pos] == ']':
            return text, result, pos
        value, end = decoder.raw_decode(text, pos)
        result.append((value['run_id'], text[pos:end].encode('utf-8'), pos, end))
        pos = end


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def main():
    original = HISTORY.read_bytes()
    assert sha(original) == OLD_SHA
    history = json.loads(original)
    text, spans, close_index = raw_rows(original)
    assert len(spans) == len(history['attempts']) == 96
    with (STAGE / 'prior-history.json').open('xb') as file:
        file.write(original)
    old_exports = read(I / 'qualification-history-append-v24-prerequisites-receipt.json')['exports_before_and_after']
    assert len(old_exports) == 19
    exports = [bind(value['path']) for value in old_exports]
    assert exports == old_exports
    snapshot_path = C.parent.parent / 'Architecture Map/releases/RCI001-C02-dev-075/snapshot.json'
    snapshot_binding = bind(snapshot_path)
    assert snapshot_binding['sha256'] == SNAP_SHA
    snapshot = read(snapshot_path)
    assert snapshot['revision'] == 'RCI001-C02-dev-075'
    official = {}
    for short in ('raw015', 'transport018', 'host025'):
        proof = read(STAGE / (short + '-official.json'))
        job = proof['official']
        assert proof['exit_code'] == 0
        assert job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
        official[short] = job
    save('intent.json', {
        'schema': 'campaign002-history-append-intent-1', 'at': NOW,
        'scope': 'Append only the three settled V25 prerequisites after fresh official gates; no exports, outcome replays, accounting or map mutation.',
        'prior_history': bind(HISTORY), 'prior_rows': 96,
        'prior_raw_row_sha256': [{'run_id': rid, 'sha256': sha(raw), 'bytes': len(raw)} for rid, raw, *_ in spans],
        'exports_before': exports,
        'fresh_official_authentication': [bind(STAGE / (short + '-official.json')) for short in official],
        'snapshot': snapshot_binding,
    })

    def clone(old_id, new_id):
        row = copy.deepcopy(next(value for value in history['attempts'] if value['run_id'] == old_id))
        row['run_id'] = new_id
        row['revision'] = 'RCI001-C02-dev-075'
        replacements = [(old_id, new_id), (old_id.removeprefix('RCI001-C02-'), new_id.removeprefix('RCI001-C02-')),
                        ('RCI001-C02-dev-071', 'RCI001-C02-dev-075'), ('checks-026', 'checks-027'),
                        ('checks026', 'checks027'), ('v24-source-change-inventory-001', 'v25-source-change-inventory-001'),
                        ('V24 full source inventory', 'V25 full source inventory'), ('Host024', 'Host025')]
        artifacts = []
        for item in row['artifacts']:
            path, label = item['path'], item['label']
            for before, after in replacements:
                path, label = path.replace(before, after), label.replace(before, after)
            artifacts.append(bind(path, label))
        artifacts.append(bind(IO / 'PREPARED_STARTUP_SEGMENTS_V1.md', 'Frozen complete startup-file prepared-result segment method'))
        for item in artifacts:
            if item['label'].startswith('Frozen ') and Path(item['path']).suffix == '.md':
                entry = snapshot['sources'][Path(item['path']).relative_to(REPO).as_posix()]
                assert all(entry[key] == item[key] for key in ('sha256', 'bytes')), item
        row['artifacts'] = artifacts
        row['diagnostic_analyses'] = [
            bind(IO / 'smoke-022-read-proof-diagnosis.json', 'Prior Smoke022 read-proof diagnosis; no revised verdict'),
            bind(IO / 'smoke-022-read-proof-diagnosis.md', 'Prior Smoke022 read-proof diagnosis narrative; no revised verdict'),
        ]
        row['details']['frozen_inventory_includes_prepared_startup_method'] = True
        return row

    def queue(row, job):
        row['queue'] = {key: job[key] for key in ('id', 'state', 'exit_status', 'started_at', 'ended_at')}
        stored = read(next(item['path'] for item in row['artifacts'] if item['label'] == 'Official queue receipt'))
        stored = stored.get('job', stored)
        assert all(stored[key] == job[key] for key in ('id', 'state', 'exit_status', 'started_at', 'ended_at', 'argv', 'cwd'))

    def artifact(row, label):
        return next(item for item in row['artifacts'] if item['label'] == label)

    raw = clone('RCI001-C02-raw-preflight-014', 'RCI001-C02-raw-preflight-015')
    queue(raw, official['raw015'])
    raw['reason'] = ('The frozen dev075 no-model raw-event metadata prerequisite passed all four independent checks with its verified readiness entry and successful finish retained. '
                     'This establishes option acceptance and bounded no-model native cleanup/barrier evidence only. It does not establish active model cancellation, raw tool payload delivery, model reading, physics timing, full qualification or a task outcome; earlier failures remain unchanged.')
    transport = clone('RCI001-C02-transport-probe-017', 'RCI001-C02-transport-probe-018')
    queue(transport, official['transport018'])
    transport['reason'] = ('The frozen dev075 three-case no-model channel diagnostic passed with independent replay retained in its verified readiness entry. '
                           'Multi-channel transport satisfied its ordinary proof; foreign-owner and partial-frame cases verified expected rejection and retirement and remain production-unqualified. '
                           'This prerequisite is not native-pool reproduction, active model cancellation, model reading, physics timing, full qualification or a robot task outcome. Earlier failures remain unchanged.')
    for row in (raw, transport):
        row['diagnostic_contract']['result'] = artifact(row, 'Original no-model diagnostic result')
        row['diagnostic_contract']['verified_readiness_entry'] = artifact(row, 'Verified readiness entry')
        result = read(row['diagnostic_contract']['result']['path'])
        assert result['passed'] is True and result['run_id'] == row['run_id'] and result['framework_revision'] == row['revision']
        assert result['snapshot_sha256'] == SNAP_SHA and result['checks'] and all(v is True for v in result['checks'].values())
        assert type(result['model_calls']) is int and result['model_calls'] == 0 and result['physical_simulation'] is False
        assert result['errors'] == {}
        row['details']['checks'] = result['checks']
        finish = read(artifact(row, 'Original diagnostic finish receipt')['path'])
        assert type(finish['exit_code']) is int and finish['exit_code'] == 0
    transport_result = read(transport['diagnostic_contract']['result']['path'])
    assert [case['case'] for case in transport_result['cases']] == ['multi_channel', 'foreign_owner', 'in_flight_eof']
    for declared, actual in zip(transport['details']['cases'], transport_result['cases']):
        assert actual['passed'] is True and actual['production_qualified'] is declared['production_qualified']
        if actual['case'] != 'multi_channel':
            proof = actual['transport_proof']
            assert proof['expected_failure_verified'] is True and proof['diagnostic_only'] is True and proof['ordinary_transport_passed'] is False

    host = clone('RCI001-C02-host-probe-024', 'RCI001-C02-host-probe-025')
    queue(host, official['host025'])
    host['reason'] = ('The original 240-second idle host prerequisite assessment passed all eight checks on frozen dev075. '
                      'This is no-model infrastructure/timing evidence, not model-loaded timing, full final qualification or a task result. Earlier failed qualifiers and diagnostics remain unchanged.')
    host['details']['known_limit'] = ('Idle host prerequisite only. V25 readiness and launch metadata are retained; no active qualifier empirical output was read for this append. Full qualification and scientific admission remain incomplete.')
    for label, key in [('Original host diagnostic assessment', 'assessment_sha256'), ('Official queue receipt', 'official_queue_sha256'),
                       ('Frozen host prerequisite manifest', 'manifest_sha256'), ('Frozen source snapshot', 'snapshot_sha256')]:
        host['host_prerequisite_contract'][key] = artifact(host, label)['sha256']
    assessment = read(artifact(host, 'Original host diagnostic assessment')['path'])
    assert assessment['diagnostic_passed'] is True and len(assessment['checks']) == 8 and all(v is True for v in assessment['checks'].values())
    assert assessment['errors'] == {}
    settlement = Q / 'RCI001-C02-host-probe-025/settle-receipt.json'
    assert read(settlement)['exit_code'] == 0
    host['artifacts'].append(bind(settlement, 'Original host diagnostic settlement receipt'))
    rows = [raw, transport, host]
    for row in rows:
        save(row['run_id'] + '.json', row)

    status = copy.deepcopy(history['current_status'])
    status['state'] = 'qualification_in_progress'
    status['as_of'] = NOW
    status['summary'] = ('V25 raw-event, synthetic transport and idle-host prerequisites passed on frozen dev075. The full five-stage coordinator has begun with Native024; its active empirical outputs were not read for this history append. '
                         'Smoke022 remains the latest completed model qualifier and retains its original failed startup-read verdict. Full qualification and scored admission remain incomplete.')
    status['engineering_context'] = ('The new source-bound prepared startup segment evidence method credits only complete fixed-file bytes under its declared proof. '
                                     'Passing no-model prerequisites does not establish model reading or model-loaded timing. Earlier failed attempts and all registered dispositions remain unchanged.')
    readiness = bind(Q / 'final-qualification-025-readiness.json', 'V25 source-bound prerequisite readiness')
    assert readiness['sha256'] == '1cbb530e9663ba168bc49370aba0f0a228e57cf3603fc24d59552a959bd0c736'
    preflight_path = Q / 'final-qualification-025/preflight.json'
    preflight = read(preflight_path)
    assert preflight['source_snapshot']['sha256'] == SNAP_SHA and preflight['readiness_sha256'] == readiness['sha256']
    native_submit = Q / 'final-qualification-025/native-024/submit-receipt.json'
    submit_receipt = read(native_submit)
    assert submit_receipt['exit_code'] == 0
    active = json.loads(submit_receipt['stdout'])
    assert active['id'] == '20260929T013308751885Z-c9990e81' and active['state'] == 'running'
    previous = status['active_lineage']
    status['active_lineage'] = {
        'framework_revision': 'RCI001-C02-dev-075',
        'coordinator': bind(Q / 'run_final_qualification_v25.py', 'Declared V25 final qualification coordinator'),
        'state': 'v25_coordinator_started_native024_pending_independent_assessment',
        'latest_completed_prerequisite': host['run_id'], 'latest_model_qualifier': 'RCI001-C02-smoke-022',
        'completed_prerequisites': [row['run_id'] for row in rows], 'completed_qualifiers': [],
        'active_qualifier': {'run_id': 'RCI001-C02-native-024', 'revision': 'RCI001-C02-dev-076',
                             'job_id': active['id'], 'queue_state_at_submission': active['state'],
                             'submitted_at': active['submitted_at'], 'started_at': active['started_at'],
                             'assessment_state': 'pending_unread', 'empirical_outputs_read': False,
                             'queue_submission_receipt': bind(native_submit, 'Native024 submission metadata only')},
        'fresh_final_stage_allocation': ['RCI001-C02-' + stage[0] for stage in read(readiness['path'])['stages']],
        'stage_revisions': ['RCI001-C02-dev-076', 'RCI001-C02-dev-077', 'RCI001-C02-dev-078'],
        'final_qualification_completed': False, 'scientific_admission': False, 'scored_attempts_started': 0,
        'previous_failed_qualifier': previous['failed_qualifier'],
        'previous_unlaunched_pilot_allocations': previous['unlaunched_pilot_allocations'],
        'readiness': readiness, 'preflight': bind(preflight_path, 'V25 completed source and prerequisite preflight'),
    }
    for item in [readiness, bind(preflight_path, 'V25 completed source and prerequisite preflight'),
                 bind(Q / 'final-qualification-025/coordinator-launch-intent.json', 'V25 coordinator launch intent'),
                 bind(IO / 'PREPARED_STARTUP_SEGMENTS_V1.md', 'V25 frozen complete startup-file prepared-result segment method'),
                 bind(IO / 'checks-027/repair-test-receipt.json', 'V25 source-bound checks027 repair test receipt'),
                 bind(IO / 'v25-source-change-inventory-001.json', 'V25 full source inventory; no task-performance claim')]:
        assert not any(old['path'] == item['path'] for old in status['artifacts'])
        status['artifacts'].append(item)

    # Splice additions into the original array; every prior raw object remains identical.
    insertion = ',\n' + ',\n'.join('    ' + json.dumps(row, indent=2, ensure_ascii=False).replace('\n', '\n    ') for row in rows)
    end_last = spans[-1][3]
    candidate = text[:end_last] + insertion + text[end_last:]
    old_time = json.dumps(history['updated_at'], ensure_ascii=False)
    assert candidate.count('"updated_at": ' + old_time) == 1
    candidate = candidate.replace('"updated_at": ' + old_time, '"updated_at": ' + json.dumps(NOW), 1)
    marker = '"current_status": '
    assert candidate.count(marker) == 1
    start = candidate.index(marker) + len(marker)
    _, end = json.JSONDecoder().raw_decode(candidate, start)
    replacement = json.dumps(status, indent=2, ensure_ascii=False).replace('\n', '\n  ')
    candidate = (candidate[:start] + replacement + candidate[end:]).encode('utf-8')
    parsed = json.loads(candidate)
    _, new_spans, _ = raw_rows(candidate)
    assert len(new_spans) == 99 and [(r, b) for r, b, *_ in new_spans[:96]] == [(r, b) for r, b, *_ in spans]
    assert parsed['attempts'][:96] == history['attempts']
    with (STAGE / 'candidate-history.json').open('xb') as file:
        file.write(candidate)

    report = module('v25_history_report', I / 'qualification_report.py')
    qa = module('v25_history_qa', I / 'qualification_qa.py')
    rendered = [report.qualification_row(row, I) for row in parsed['attempts']]
    for row in rendered:
        if row.get('diagnostic_result') is not None:
            qa.no_model_diagnostic_guard(row, I)
        elif row.get('host_prerequisite') is not None:
            qa.host_prerequisite_guard(row, I)
        elif row.get('queue_failure') is not None:
            qa.failed_queue_guard(row, I)
    inventory = report.launch_inventory(C, I)
    current = report.current_status_detail(status, rendered, parsed, inventory, C, I)
    assert current['basis_run_id'] == 'RCI001-C02-smoke-022'
    assert report.latest_completed_qualifier(rendered)['run_id'] == 'RCI001-C02-smoke-022'
    assert inventory['entries'] == [] and inventory['registration'] is None
    assert all(row['scorable'] is False for row in rendered)
    assert [bind(item['path']) for item in exports] == exports
    assert HISTORY.read_bytes() == original
    assert all('RCI001-C02-native-024' not in item['path'] for item in report.READS)
    validation = {
        'schema': 'campaign002-history-current-status-qa-1', 'at': NOW,
        'candidate_history': bind(STAGE / 'candidate-history.json'), 'history_rows': 99,
        'prior_raw_rows_preserved': 96, 'new_rows_verified': [row['run_id'] for row in rows],
        'current_basis': current['basis_run_id'], 'latest_model_qualifier': 'RCI001-C02-smoke-022',
        'latest_completed_prerequisite': host['run_id'], 'active_qualifier_metadata_only': status['active_lineage']['active_qualifier'],
        'scored_launch_inventory': inventory,
        'evidence_links': sum(len(row['links']) + len(row.get('diagnostic_links', [])) for row in rendered),
        'pending_qualification_outputs_read': False, 'outcomes_recomputed': False,
        'exports_rebuilt': False, 'preserved_exports': exports,
        'source_helper_bindings': [bind(I / 'qualification_report.py'), bind(I / 'qualification_qa.py')],
        'authenticated_reader_inputs': report.READS,
    }
    save('qa.json', validation)
    save('staged-receipt.json', {
        'schema': 'campaign002-history-staged-append-receipt-1', 'at': NOW,
        'prior_history': bind(HISTORY), 'candidate_history': bind(STAGE / 'candidate-history.json'),
        'rows_before': 96, 'rows_after': 99,
        'appended': [{'run_id': rid, 'sha256': sha(raw), 'bytes': len(raw)} for rid, raw, *_ in new_spans[96:]],
        'qa': bind(STAGE / 'qa.json'), 'exports_before_and_after': exports,
        'canonical_history_written': False, 'active_outputs_read': False,
    })
    print(json.dumps({'candidate': bind(STAGE / 'candidate-history.json'), 'qa': bind(STAGE / 'qa.json'),
                      'rows': 99, 'prior_raw_rows_preserved': 96, 'links': validation['evidence_links'], 'exports_unchanged': 19}, indent=2))


if __name__ == '__main__':
    main()
