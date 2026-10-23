"""Retain a bounded metadata/source diagnosis; never run an assessor or launch work."""
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
C = OUT.parents[1]
R = C.parent
REPO = R.parents[1]
Q = C / 'qualification'
ROOT = R / 'local-evidence/campaign002/qualification/RCI001-C02-pilot-stock-024'
P = ROOT / 'orchestrator/pilot'
HOST = ROOT / 'host'
RELEASE = R.parent / 'Architecture Map/releases/RCI001-C02-dev-086'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def bind(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': digest(raw)}

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def rows(path):
    return [(n, json.loads(line)) for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)]

for name in ('diagnosis.json', 'diagnosis.md', 'execution.json'):
    if (OUT / name).exists():
        raise FileExistsError(OUT / name)
official = read(OUT / 'official-status.json')
job = official.get('job', official)
assert job['id'] == '20260929T041418803542Z-2f3b6425'
assert job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
assessment_path = Q / 'pilot-stock-024-assessment.json'
disposition_path = Q / 'final-qualification-027/pilot-stock-024/disposition.json'
assert bind(assessment_path)['sha256'] == 'a87dc3025fb1212b3969640eeaf185701b201ed0bf8613d443f7332697d6f126'
assert bind(disposition_path)['sha256'] == 'fc47a1e0c41bfea7eb912327432583352e9095e8887fec5242e77bbf589a439b'
assessment = read(assessment_path)
stage = read(P / 'stage-result.json')
sequence = read(ROOT / 'orchestrator/sequence-result.json')
host = read(HOST / 'result.json')
bridge = read(P / 'codehost-owner-bridge-v3.json')
snapshot = read(RELEASE / 'snapshot.json')
source_specs = [
    (C / 'assessment/assess.py', [25, 34, 71, 78, 81, 87, 592, 614]),
    (R / 'readiness-session-10/assessment/assess_smoke.py', [134, 152]),
    (R / 'readiness-session-10/assessment/assess_bootstrap.py', [90]),
    (C / 'assessment/retained_reads.py', [273]),
    (C / 'assessment/assess_smoke_v2.py', [148]),
    (C / 'assessment/test_shared_host_retirement_inventory.py', [8]),
    (C / 'harness/physical.py', [68, 79, 86, 152]),
    (C / 'harness/codehost_bridge_v3.py', []),
    (C / 'assessment/transport_integrity_v3.py', []),
]
sources = []
with zipfile.ZipFile(RELEASE / 'code.zip') as archive:
    for path, lines in source_specs:
        relative = path.relative_to(REPO).as_posix()
        raw = archive.read(relative)
        expected = snapshot['sources'][relative]
        assert digest(raw) == expected['sha256'] and len(raw) == expected['bytes']
        current = bind(path)
        assert current['sha256'] == digest(raw) and current['bytes'] == len(raw)
        sources.append({**current, 'archive_member': relative, 'lines': lines,
                        'snapshot_and_archive_and_current_equal': True})

names = ['executor-1-retirement.json', 'executor-2-retirement.json', 'codehost-owner-retirement-v3.json']
retirements = []
for name in names:
    record = read(P / name)
    final = record['observations'][-1]
    predicates = {
        'qualified_true': record.get('qualified') is True,
        'final_retired_true': final.get('retired') is True,
        'namespace_evidence_available_true': final.get('namespace_evidence_available') is True,
        'namespace_ids_nonempty': bool(final.get('namespace_ids')),
        'namespace_members_empty': final.get('namespace_members') == [],
        'outer_same_process_false': final.get('outer_same_process') is False,
    }
    assert all(predicates.values())
    retirements.append({'file': name, 'binding': bind(P / name), 'unchanged_predicate_fields': predicates,
                        'namespace_ids': final['namespace_ids'], 'outer_identity': final['identity'],
                        'observations': len(record['observations']), 'windows_exit_code': record['windows_exit_code'],
                        'normal_wait_timed_out': record['normal_wait_timed_out'],
                        'windows_wrapper_killed_after_linux_retired': record['windows_wrapper_killed_after_linux_retired'],
                        'scope': 'Direct retained-field comparison with the frozen check_retirement expression; no assessor invocation.'})
legacy_names = sorted(x.name for x in P.glob('*-retirement.json'))
assert legacy_names == sorted(names[:2])
shared = retirements[-1]['binding']
assert bridge['retirement'] == {'path': names[-1], 'sha256': shared['sha256'], 'bytes': shared['bytes']}
assert bridge['qualified'] is True and bridge['failures'] == []

history = rows(HOST / 'public-history.jsonl')
selected_history = []
for line, event in history:
    if event.get('type') in ('invocation_start-invocation', 'invocation_retire-invocation', 'episode_stopped') or event.get('event_id') == 1784:
        selected_history.append({'line': line, 'event_id': event['event_id'], 'type': event['type'],
                                 'wall_unix_s': event.get('wall_unix_s'),
                                 'reason': event.get('payload', {}).get('reason')})
chronology = []
for relative, kinds in [('client/events.jsonl', {'client_finishing_before_close', 'client_shutdown'}),
                        ('codehost-transport-v3.jsonl', {'namespace_finished', 'namespace_output_closed', 'retirement_started', 'closed'})]:
    for line, event in rows(P / relative):
        if event.get('kind') in kinds:
            chronology.append({'file': relative, 'line': line,
                               **{k: event[k] for k in ('sequence', 'kind', 'wall_unix_s', 'monotonic_s', 'exit_code', 'qualified', 'failures') if k in event}})
outcome = assessment['recovery_and_task_outcome']
guard_fields = {
    'host_exit_code': sequence.get('host_exit_code'),
    'forced_host_exit': sequence.get('forced_host_exit'),
    'host_execution_completed': host.get('execution_completed'),
    'host_error': host.get('error'), 'host_terminal': host.get('terminal'),
    'already_retained_independent_outcome': outcome.get('independent_task_outcome'),
    'accepted_handback_corresponds_to_owner_transfer': outcome.get('accepted_handback_corresponds_to_owner_transfer'),
    'owner_transfer_event_ids': outcome.get('owner_transfer_event_ids'),
    'scope': 'Existing assessment/host fields used only to explain lifecycle branch dependencies; not a new task assessment or promoted task result.'}
inputs = [OUT/'official-status.json', OUT/'authentication.json', assessment_path, disposition_path,
          Q/'pilot-stock-024-manifest.json', Q/'pilot-stock-024-queue.json', RELEASE/'snapshot.json',
          RELEASE/'code.zip', RELEASE/'manifest.json', P/'stage-result.json',
          ROOT/'orchestrator/sequence-result.json', HOST/'result.json', HOST/'public-history.jsonl',
          P/'codehost-owner-bridge-v3.json', P/'codehost-transport-v3.jsonl',
          P/'client/events.jsonl', P/'client/result.json', P/'client/native-quiescence.json'] + [P/n for n in names]
bindings = [bind(path) for path in inputs]
report = {
    'schema': 'campaign002-pilot-retirement-inventory-diagnosis-1',
    'created_at': datetime.now(timezone.utc).isoformat(),
    'run_id': 'RCI001-C02-pilot-stock-024', 'queue_job_id': job['id'],
    'scope': 'Read-only infrastructure diagnosis after fresh official success/int0 authentication; no assessor execution, task reassessment, live namespace probe, retry, or historical verdict mutation.',
    'original_result': {k: assessment[k] for k in ('validity', 'task_outcome', 'failed_checks', 'task_evidence_valid', 'scorable')},
    'original_check_counts': {'true': sum(v is True for v in assessment['checks'].values()), 'total': len(assessment['checks'])},
    'original_admission': {'passed': False, 'error': read(disposition_path)['error']},
    'finding': 'Pilot inspection delegates to the legacy filename glob and omits the present, qualified, independently bound v3 codehost retirement receipt. The resulting false namespace flag also blocks the existing successful_terminal_host_closure branch.',
    'legacy_inventory': {'pattern': '*-retirement.json', 'matched_names': legacy_names, 'count': len(legacy_names), 'codehost_match_present': False,
                         'omitted_exact_file': names[-1], 'existing_smoke_adapter_includes_exact_file': True},
    'retirement_receipts': retirements,
    'bridge_binding': {'qualified': bridge['qualified'], 'exit_code': bridge['exit_code'], 'failures': bridge['failures'], 'retirement': bridge['retirement']},
    'original_independent_transport_proof': {'passed': assessment['transport_lifecycle']['passed'],
                                             'retirement': assessment['transport_lifecycle']['retirement'],
                                             'client_quiescence_passed': assessment['transport_lifecycle']['client_quiescence']['passed']},
    'original_lifecycle': assessment['lifecycle'], 'terminal_branch_retained_guard_fields': guard_fields,
    'protected_history_chronology': selected_history, 'retained_client_transport_chronology': chronology,
    'stage_summary': {k: stage.get(k) for k in ('success', 'all_namespaces_retired', 'cleanup_clean', 'durable_retention_verified', 'watchdog_errors', 'retirement_error', 'old_token_check_error')},
    'chronology_interpretation': 'Protected episode stop precedes client finishing and codehost retirement. The launcher attempts operator retirement and old-token status only after Runtime.model returns. Its connection-refused errors remain genuine missing explicit-retirement/late-403 receipts; no request timestamp was retained for those exceptions.',
    'cleanup_concern': 'All three retained final observations report their identified outer process absent and known namespace empty. No retained evidence here supports a live leaked namespace. This is not a present-time global OS census; no cleanup process was launched.',
    'supported_prospective_repair': 'Add the exact existing codehost-owner-retirement-v3.json filename to the pilot adapter inventory, using the unchanged check_retirement expression and existing source/integrity gates. Keep the existing terminal-host-closure branch and missing explicit/403 limitation unchanged. Test the actual pilot entry point and malformed/missing/unqualified receipts. Fresh declared source/full qualification is required; this diagnosis does not upgrade Stock024.',
    'input_bindings': bindings, 'frozen_source_bindings': sources,
    'unknowns': ['Exact wall times of late failed operator requests are not retained.', 'No present-time whole-machine namespace census was performed.', 'No new scientific task outcome was calculated.']}
raw = (json.dumps(report, indent=2, ensure_ascii=False) + '\n').encode()
(OUT/'diagnosis.json').write_bytes(raw)
md = '''# Stock024 retirement inventory diagnosis

The original Stock024 assessment remains **invalid / task unknown**: 36 of 38 checks passed; `all_namespace_retirements_observed` and `qualified_lifecycle_end_observed` failed. The queue succeeded with integer exit 0. This packet is an additive infrastructure diagnosis, not a new qualification or task assessment.

The frozen pilot adapter delegates to legacy `inspect_stage`, whose `*-retirement.json` inventory finds only the two executor receipts. It omits the actual `codehost-owner-retirement-v3.json`. The current smoke adapter already explicitly includes that exact filename. All three actual receipts satisfy every unchanged `check_retirement` field predicate. The v3 bridge binds the omitted receipt exactly (SHA256 `e3fccebaa0ad81f3362939113d2a62c5bcd796d089a01e1fdc228abd713fad36`, 2,693 bytes), reports qualified true/no failures, and the original independent transport proof passed.

The inherited false namespace flag then blocks the existing successful-terminal-host-closure branch. Its other guard fields are already retained: one invocation start (event 32), clean host exit 0, protected episode stop event 2162 after ownership transfer event 1784, and the original assessor's corresponding outcome/transfer fields. These are inspected only to explain the lifecycle branch; no new task result is asserted.

Protected episode stop occurred at wall 1790655470.5351577. Client finishing was recorded at 1790655484.6389372 (client line 537); namespace finished at 1790655484.6860933, namespace output closed at 1790655485.0023773, retirement started at 1790655485.0060728, and qualified bridge closure at 1790655485.257911 (ledger 234–238). The launcher makes its late operator retirement/status requests after Runtime.model returns. Both encountered connection refusal. Those missing explicit-retirement and late HTTP403 receipts remain missing; their exact request times were not retained. The existing terminal-host branch explicitly preserves this limitation and needs no changed criterion.

Each of the three final retirement observations reports the identified outer process absent and the identified namespace empty, with evidence available and Windows wrapper exit 0. No retained evidence here indicates a live leaked namespace. This was not a present-time global process/namespace census, and no cleanup action was performed.

The supported prospective repair is to include the exact v3 receipt filename in the pilot adapter, retain the unchanged retirement predicate and source/integrity gates, and exercise missing/malformed/unqualified receipts through the actual pilot entry point. A new declared source and qualification lineage are required. Do not broaden the glob, manufacture HTTP403, or promote this historical result.

## Source and evidence

- [Full hash-bound diagnosis](diagnosis.json), [fresh official status](official-status.json), [authentication receipt](authentication.json).
- [Pilot adapter](../../assessment/assess.py):25–35,71–103; [legacy inventory](../../../readiness-session-10/assessment/assess_smoke.py):134,152; [unchanged retirement predicate](../../../readiness-session-10/assessment/assess_bootstrap.py):90–96.
- [Existing smoke adapter](../../assessment/assess_smoke_v2.py):148–152; [read proof upgrade](../../assessment/retained_reads.py):273 onward (does not replace retirements); [launcher](../../harness/physical.py):68–88.
- The JSON binds original assessment, admission disposition, all three retirement receipts, bridge/ledger, client lifecycle files, host chronology, and dev086 snapshot/archive. Every listed source matches the frozen snapshot, archived bytes, and current bytes at collection. Original input hashes were checked again after writing this packet.
'''
(OUT/'diagnosis.md').write_text(md, encoding='utf-8', newline='\n')
for binding in bindings + sources:
    current = bind(Path(binding['path']))
    assert current['sha256'] == binding['sha256'] and current['bytes'] == binding['bytes']
execution = {'schema': 'campaign002-diagnostic-collection-1', 'passed': True,
             'original_inputs_unchanged': True, 'source_count': len(sources), 'input_count': len(bindings),
             'collector': bind(Path(__file__)), 'outputs': [bind(OUT/'diagnosis.json'), bind(OUT/'diagnosis.md')],
             'scope': 'Metadata and archived source inspection only; no assessment functions executed.'}
(OUT/'execution.json').write_text(json.dumps(execution, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({'passed': True, 'source_count': len(sources), 'input_count': len(bindings),
                  'outputs': execution['outputs'], 'execution': bind(OUT/'execution.json')}, indent=2))
