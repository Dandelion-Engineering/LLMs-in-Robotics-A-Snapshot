"""Declare the fresh V26 allocation only after stable development validation."""
import datetime
import importlib.util
import json
from pathlib import Path

IO = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cleanup_control', IO / 'control_epoch_readback_qualification.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c


def main():
    checks = control.CHECKS / 'test-execution.json'
    lineage = control.LINEAGE_CHECKS
    control.development_gate({'development_checks': c.identity(checks),
                              'lineage_checks': c.identity(lineage),
                              'development_source_state': c.identity(control.SOURCE_STATE)})
    stages = [
        ['native-025', 'native', 'RCI001-C02-dev-080', 24000],
        ['boundary-026', 'boundary', 'RCI001-C02-dev-081', None],
        ['smoke-024', 'smoke', 'RCI001-C02-dev-082', 24101],
        ['pilot-stock-023', 'stock', 'RCI001-C02-dev-082', 24102],
        ['pilot-home-023', 'home', 'RCI001-C02-dev-082', 24103],
    ]
    prerequisites = ['RCI001-C02-raw-preflight-016', 'RCI001-C02-transport-probe-019', control.HOST]
    ids = prerequisites + ['RCI001-C02-' + row[0] for row in stages]
    revisions = ['RCI001-C02-dev-' + str(n).zfill(3) for n in range(79, 83)]
    paths = [c.MAP / 'releases' / revision for revision in revisions]
    paths += [control.Q / ('RCI001-C02-' + name) for name in ['host-probe-026', *[row[0] for row in stages]]]
    for name in ['host-probe-026', *[row[0] for row in stages]]:
        paths += [control.Q / (name + suffix) for suffix in
                  ('-manifest.json', '-assessment.json', '-queue.json', '-submit.json')]
    runtime = Path.home() / 'AppData/Local/RobotCodex/Campaign002/qualification'
    paths += [runtime / run_id for run_id in ids]
    paths += [c.RAW / run_id for run_id in ids]
    paths += [IO / name for name in ('raw-preflight-016', 'transport-probe-019', 'v26-readiness-preflight-001.json')]
    paths += [c.LEDGER, control.Q / 'final-qualification-026-readiness.json', control.DECLARATION]
    c.require(not any(path.exists() for path in paths), 'Allocated output already exists; reconcile')
    map_files = [c.MAP / name for name in ('revisions.jsonl', 'runs.jsonl', 'results.jsonl')]
    for path in map_files:
        text = path.read_text(encoding='utf-8')
        c.require(not any('"' + identifier + '"' in text for identifier in ids + revisions),
                  'Allocated identity already registered: ' + str(path))
    absence = {
        'schema': 'campaign002-prospective-allocation-absence-1',
        'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'absent_paths': [str(path.resolve()) for path in paths],
        'absent_ids': ids + revisions,
        'map_inputs': [c.identity(path) for path in map_files],
    }
    c.save(IO / 'v26-allocation-absence-001.json', absence)
    declaration = {
        'schema': 'campaign002-prospective-qualification-allocation-1',
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'purpose': 'Qualify exact epoch-denial provenance, finite prepared-index shorthand and exclusive-writer canary semantic readback while preserving model, task, timing, isolation, byte, EOF and native cleanup gates.',
        'prior_failed_diagnostic': c.identity(IO / 'smoke-020-transport-failure-analysis.json'),
        'transport_correction_method': c.identity(IO / 'NATIVE_CLEANUP_CANCELLATION_V1.md'),
        'initial_read_evidence_method': c.identity(IO / 'READ_EVIDENCE_V3.md'),
        'prepared_startup_method': c.identity(IO / 'PREPARED_STARTUP_SEGMENTS_V1.md'),
        'prepared_startup_diagnostic': c.identity(IO / 'smoke-022-read-proof-diagnosis.json'),
        'prepared_output_source_packet': c.identity(IO / 'native-output-source-003/manifest.json'),
        'epoch_shorthand_method': c.identity(IO / 'EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md'),
        'canary_readback_method': c.identity(IO / 'CANARY_READBACK_EXCLUSIVITY_V1.md'),
        'epoch_diagnostic': c.identity(IO / 'smoke-023-transport-diagnosis.json'),
        'shorthand_diagnostic': c.identity(IO / 'smoke-023-read-proof-diagnosis.json'),
        'canary_diagnostic': c.identity(IO / 'smoke-023-canary-diagnosis.json'),
        'initial_read_diagnostic': c.identity(IO / 'smoke-021-read-proof-diagnosis.json'),
        'chronology_diagnostic': c.identity(IO / 'smoke-021-chronology-analysis.json'),
        'unchanged_scheduling_method': c.identity(IO / 'NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md'),
        'unchanged_quiescence_method': c.identity(IO / 'NATIVE_THREAD_QUIESCENCE_V1.md'),
        'unchanged_normal_closed_method': c.identity(IO / 'NORMAL_CLOSED_CANCEL_V1.md'),
        'coordinator': c.identity(control.Q / 'run_final_qualification_v26.py'),
        'anchor_revision': control.REV, 'repair_checks': control.CHECKS.name,
        'development_checks': c.identity(checks), 'lineage_checks': c.identity(lineage),
        'development_source_state': c.identity(control.SOURCE_STATE),
        'allocation_absence': c.identity(IO / 'v26-allocation-absence-001.json'),
        'prerequisites': prerequisites, 'stages': stages,
        'preservation': 'All prior failed attempts and development failures remain immutable. Smoke020 remains failed/unassessed; Smoke021 and Smoke022 remain queue-succeeded but independently failed/invalid and task unknown. Both Smoke022 Continuity reads passed; its fixed startup read aggregate failed. Smoke023 remains independently failed59/62 with transport, resumed startup and canary-proof blockers; its original response remains unknown. This prospective allocation does not qualify any stage or admit scored execution; all five fresh stages must pass independently.',
    }
    c.save(control.DECLARATION, declaration)
    control.bound_declaration()
    print(json.dumps({'declaration': c.identity(control.DECLARATION), 'absent_paths': len(paths)}))


if __name__ == '__main__':
    main()
