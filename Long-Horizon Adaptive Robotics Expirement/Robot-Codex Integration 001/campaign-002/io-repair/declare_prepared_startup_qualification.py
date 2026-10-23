"""Declare the fresh V25 allocation only after stable development validation."""
import datetime
import importlib.util
import json
from pathlib import Path

IO = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cleanup_control', IO / 'control_prepared_startup_qualification.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c


def main():
    checks = control.CHECKS / 'test-execution.json'
    c.require(c.read(checks)['passed'] is True, 'Full development checks failed')
    lineage = IO / 'prepared-startup-lineage-development-001/final-checks-002/receipt.json'
    c.require(c.read(lineage)['passed'] is True, 'Current lineage checks failed')
    for name, binding in c.read(lineage)['source_bindings'].items():
        path = control.C / name
        c.require(c.sha(path) == binding['sha256'] and path.stat().st_size == binding['bytes'],
                  'Lineage source changed: ' + name)
    stages = [
        ['native-024', 'native', 'RCI001-C02-dev-076', 24000],
        ['boundary-025', 'boundary', 'RCI001-C02-dev-077', None],
        ['smoke-023', 'smoke', 'RCI001-C02-dev-078', 24101],
        ['pilot-stock-022', 'stock', 'RCI001-C02-dev-078', 24102],
        ['pilot-home-022', 'home', 'RCI001-C02-dev-078', 24103],
    ]
    prerequisites = ['RCI001-C02-raw-preflight-015', 'RCI001-C02-transport-probe-018', control.HOST]
    ids = prerequisites + ['RCI001-C02-' + row[0] for row in stages]
    revisions = ['RCI001-C02-dev-' + str(n).zfill(3) for n in range(75, 79)]
    paths = [c.MAP / 'releases' / revision for revision in revisions]
    paths += [control.Q / ('RCI001-C02-' + name) for name in ['host-probe-025', *[row[0] for row in stages]]]
    for name in ['host-probe-025', *[row[0] for row in stages]]:
        paths += [control.Q / (name + suffix) for suffix in ('-manifest.json', '-assessment.json')]
    runtime = Path.home() / 'AppData/Local/RobotCodex/Campaign002/qualification'
    paths += [runtime / run_id for run_id in ids]
    paths += [c.RAW / run_id for run_id in ids]
    paths += [IO / name for name in ('raw-preflight-015', 'transport-probe-018', 'v25-readiness-preflight-001.json')]
    paths += [c.LEDGER, control.Q / 'final-qualification-025-readiness.json', control.DECLARATION]
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
    c.save(IO / 'v25-allocation-absence-001.json', absence)
    declaration = {
        'schema': 'campaign002-prospective-qualification-allocation-1',
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'purpose': 'Qualify source-bound complete fixed-file segments in prepared results while preserving initial Continuity proofs, model behavior, native cleanup, timing, byte, EOF, ownership, isolation and task gates.',
        'prior_failed_diagnostic': c.identity(IO / 'smoke-020-transport-failure-analysis.json'),
        'transport_correction_method': c.identity(IO / 'NATIVE_CLEANUP_CANCELLATION_V1.md'),
        'initial_read_evidence_method': c.identity(IO / 'READ_EVIDENCE_V3.md'),
        'prepared_startup_method': c.identity(IO / 'PREPARED_STARTUP_SEGMENTS_V1.md'),
        'prepared_startup_diagnostic': c.identity(IO / 'smoke-022-read-proof-diagnosis.json'),
        'prepared_output_source_packet': c.identity(IO / 'native-output-source-003/manifest.json'),
        'initial_read_diagnostic': c.identity(IO / 'smoke-021-read-proof-diagnosis.json'),
        'chronology_diagnostic': c.identity(IO / 'smoke-021-chronology-analysis.json'),
        'unchanged_scheduling_method': c.identity(IO / 'NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md'),
        'unchanged_quiescence_method': c.identity(IO / 'NATIVE_THREAD_QUIESCENCE_V1.md'),
        'unchanged_normal_closed_method': c.identity(IO / 'NORMAL_CLOSED_CANCEL_V1.md'),
        'coordinator': c.identity(control.Q / 'run_final_qualification_v25.py'),
        'anchor_revision': control.REV, 'repair_checks': control.CHECKS.name,
        'development_checks': c.identity(checks), 'lineage_checks': c.identity(lineage),
        'allocation_absence': c.identity(IO / 'v25-allocation-absence-001.json'),
        'prerequisites': prerequisites, 'stages': stages,
        'preservation': 'All prior failed attempts and development failures remain immutable. Smoke020 remains failed/unassessed; Smoke021 and Smoke022 remain queue-succeeded but independently failed/invalid and task unknown. Both Smoke022 Continuity reads passed; its fixed startup read aggregate failed. This prospective allocation does not qualify any stage or admit scored execution; all five fresh stages must pass independently.',
    }
    c.save(control.DECLARATION, declaration)
    control.bound_declaration()
    print(json.dumps({'declaration': c.identity(control.DECLARATION), 'absent_paths': len(paths)}))


if __name__ == '__main__':
    main()
