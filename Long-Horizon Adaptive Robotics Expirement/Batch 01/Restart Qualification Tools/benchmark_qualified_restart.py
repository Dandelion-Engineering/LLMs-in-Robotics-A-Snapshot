"""Queue-only offline qualification CPU timing; never native/physical/readiness evidence.

Final mode uses the actual loader, selection and classifier on a retained cut.
Provisional mode times only canonical rule digests and reports structural size.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
import time

import assemble_qualification as assembly

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[1] / 'Runtime'
REPETITIONS = 5
require = assembly.require
digest = assembly.digest


def checksum(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def modules():
    if str(RUNTIME) not in sys.path:
        sys.path.insert(0, str(RUNTIME))
    import restart_calibration_loader
    import restart_state
    import release_runner
    return restart_calibration_loader, restart_state, release_runner


def argument_path(job, flag):
    argv = job['argv']
    require(argv.count(flag) == 1, 'Missing or ambiguous queued argument: ' + flag)
    path = Path(argv[argv.index(flag) + 1])
    return (path if path.is_absolute() else Path(job['cwd']) / path).resolve()


def receipt_binding(inputs, path, report, queue_key, script, report_path, report_name, runner):
    receipt, ref = inputs.read(path, parse=True)
    job = report.get(queue_key)
    require(isinstance(job, dict) and all(k in job and receipt.get(k) == job[k]
            for k in assembly.QUEUE_IDENTITY), 'Official receipt differs from recorded job')
    require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int
            and receipt['exit_status'] == 0, 'Successful official receipt required')
    require(assembly.stamp(receipt['started_at']) <= assembly.stamp(report['completed_at'])
            <= assembly.stamp(receipt['ended_at']), 'Receipt does not cover completion')
    require(runner.python_entrypoint(job['argv'], job['cwd']) == script.resolve(),
            'Receipt names another implementation')
    require(argument_path(job, '--output') / report_name == Path(report_path).resolve(),
            'Receipt names another output')
    # Installed queue state is read only; no submit/status/repair command is run.
    runner.verify_queue_receipt(receipt['id'], Path(path))
    return ref


def shape(value):
    cells = value.get('cells')
    require(isinstance(cells, list) and cells and all(isinstance(c, dict) for c in cells),
            'Nonempty cell list required for size measurement')
    rows = []
    for cell in cells:
        corridors = cell.get('route_envelope', {}).get('clearance_corridors_m')
        require(isinstance(corridors, list), 'Cell has no corridor list')
        rows.append({'cell_id': cell.get('cell_id'), 'corridor_boxes': len(corridors),
                     'corridor_canonical_bytes': len(json.dumps(corridors, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('ascii'))})
    return {'cells': rows, 'total_corridor_boxes': sum(row['corridor_boxes'] for row in rows),
            'canonical_bytes': len(json.dumps(value, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode('ascii'))}


def event_encoder(inputs):
    """Extract the unchanged actual Evidence.emit method without importing Cell.

    Its sink is StringIO: includes both JSON encodings, hash and in-memory write;
    excludes operating-system storage, real flush latency and contention.
    """
    inputs.read(RUNTIME / 'experiment.py')
    tree = ast.parse((RUNTIME / 'experiment.py').read_text(encoding='utf-8'))
    canonical = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'canonical')
    evidence = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Evidence')
    emit = next(n for n in evidence.body if isinstance(n, ast.FunctionDef) and n.name == 'emit')
    inputs.read(RUNTIME / 'cell.py')
    cell_tree = ast.parse((RUNTIME / 'cell.py').read_text(encoding='utf-8'))
    dt_nodes = [n.value for n in cell_tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'DT' for t in n.targets)]
    require(len(dt_nodes) == 1, 'Native timestep source assignment is ambiguous')
    dt = ast.literal_eval(dt_nodes[0])
    require(type(dt) in (int, float) and dt > 0, 'Native timestep source is not a positive literal')
    wrapper = ast.ClassDef(name='EncodingOnly', bases=[], keywords=[], body=[emit], decorator_list=[], type_params=[])
    code = ast.fix_missing_locations(ast.Module(body=[canonical, wrapper], type_ignores=[]))
    namespace = {'json': json, 'hashlib': hashlib, 'time': time, 'DT': dt}
    exec(compile(code, str(RUNTIME / 'experiment.py'), 'exec'), namespace)
    encoder = namespace['EncodingOnly']()
    encoder.sequence = 0; encoder.lock = threading.Lock(); encoder.run_id = 'offline-qualification-benchmark'
    encoder.start = time.perf_counter()
    return encoder


def bind_accepted(args, inputs, runner):
    freeze_path = Path(args.development_freeze).resolve()
    freeze, freeze_ref = inputs.read(freeze_path, parse=True)
    require(freeze.get('schema_version') == 'development-restart-qualification-freeze-1'
            and freeze.get('stage') == 'development', 'An actual accepted development freeze is required')
    report_path = Path(args.assembly).resolve() if args.assembly else freeze_path.parent / 'assembly.json'
    report, _ = inputs.read(report_path, parse=True)
    require(report.get('schema_version') == 'restart-qualification-assembly-1'
            and report.get('status') == 'complete' and report.get('inputs_unchanged') is True
            and report.get('operator_acceptance_present') is True and report.get('loader_validation') == 'pass',
            'Completed accepted assembly with actual loader validation required')
    receipt_binding(inputs, args.assembly_receipt, report, 'assembly_queue',
                    HERE / 'assemble_qualification.py', report_path, 'assembly.json', runner)
    require(Path(report['development_freeze_path']).resolve() == freeze_path,
            'Assembly points to another freeze')
    bundle, bundle_ref = inputs.reference(freeze['restart_qualification'], freeze_path.parent, parse=True)
    require(Path(report['bundle_path']).resolve() == Path(bundle_ref['path']), 'Assembly points to another bundle')
    require(bundle.get('status') == 'measured_development' and isinstance(bundle.get('operator_acceptance'), dict),
            'Draft or missing operator acceptance cannot be benchmarked as qualified')
    for ref in report['input_refs']:
        inputs.reference(ref, report_path.parent)
    for ref in bundle['artifact_files']:
        inputs.reference(ref, Path(bundle_ref['path']).parent)
    acceptance, _ = inputs.reference(bundle['operator_acceptance_ref'], Path(bundle_ref['path']).parent, parse=True)
    require(acceptance == bundle['operator_acceptance']
            and acceptance.get('decision') == 'accept_unchanged_provisional_rule', 'Acceptance identity/decision differs')
    assessment, assessment_ref = inputs.reference(bundle['assessment_ref'], Path(bundle_ref['path']).parent, parse=True)
    require(assessment_ref == report['assessment_ref'] and digest(assessment) == bundle['assessment_canonical_sha256'],
            'Assembly and bundle assessment identities differ')
    _, assessor_receipt_ref = inputs.reference(bundle['assessment_receipt_ref'], Path(bundle_ref['path']).parent, parse=True)
    receipt_binding(inputs, assessor_receipt_ref['path'], assessment, 'assessment_queue',
                    HERE / 'assess_validation.py', assessment_ref['path'], 'assessment.json', runner)
    for path, expected in assessment['assessor_dependency_sha256'].items():
        inputs.read(path, {'sha256': expected})
    for ref in bundle['assembly_implementation_refs']:
        inputs.reference(ref, Path(bundle_ref['path']).parent)
    require(assembly.stamp(report['completed_at']) >= assembly.stamp(freeze['frozen_at']),
            'Freeze postdates assembly completion')
    return freeze, freeze_ref, bundle, bundle_ref


def retained_cut(args, inputs, bundle, bundle_path):
    states, states_ref = inputs.read(args.cut_states, parse=True)
    cut = states.get('states', {}).get('cut', {})
    require(cut.get('status') == 'recorded' and isinstance(cut.get('payload'), dict), 'Retained rich cut missing')
    snapshot = cut['payload']; locator = cut['source_ref']; events_path = Path(args.events).resolve()
    matches = []
    for ref in bundle['artifact_files']:
        path = Path(ref['path']); path = (path if path.is_absolute() else bundle_path.parent / path).resolve()
        if path == events_path:
            matches.append(ref)
    require(matches and all(ref['sha256'] == locator.get('sha256') for ref in matches),
            'Original cut event stream is not an exact verified bundle artifact')
    _, events_ref = inputs.read(events_path, matches[0])
    require(type(locator.get('line')) is int and locator['line'] > 0, 'Cut has no original line locator')
    raw = None
    with events_path.open('rb') as stream:
        for line_number, line in enumerate(stream, 1):
            if line_number == locator['line']:
                raw = line; break
    require(raw is not None and hashlib.sha256(raw).hexdigest() == locator.get('line_sha256'),
            'Original cut line differs')
    event = json.loads(raw)
    require(event['payload'] == snapshot and event['payload_sha256'] == digest(snapshot)
            and all(event.get(k) == cut.get(k) == locator.get(k) for k in ('event_id', 'event_type', 'payload_sha256')),
            'Cut payload/event identity differs from original bytes')
    require(event.get('event_type') == 'protected_carry_state_before_cut', 'Selected event is not the recorded original cut')
    require(snapshot.get('schema_version') == 'protected-restart-state-1.0'
            and snapshot.get('snapshot_sha256') == digest({k:v for k,v in snapshot.items() if k != 'snapshot_sha256'})
            and snapshot.get('exposure', {}).get('actual_cut') == 'closed_grip_transfer', 'Protected carry cut digest/scope differs')
    spec_sources = bundle['class_spec']['required_source_hashes']
    observation = snapshot.get('physical_class_observation', {})
    require(observation.get('source_hashes') == spec_sources, 'Cut and final class source identities differ')
    for name in ('cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py'):
        _, ref = inputs.read(RUNTIME / name)
        require(snapshot.get('source_hashes', {}).get(name) == spec_sources.get(name) == ref['sha256'],
                'Cut does not match current protected source: ' + name)
    for key, name in [('descriptor_exporter', 'restart_physical_class.py'),
                      *[(n,n) for n in ('restart_state.py', 'restart_compatibility.py', 'restart_qualification.py')]]:
        _, ref = inputs.read(RUNTIME / name)
        require(spec_sources.get(key) == ref['sha256'], 'Class differs from current source: ' + key)
    return snapshot, {'cut_states': states_ref, 'events': events_ref, 'cut_locator': locator}


def measure_calls(snapshot, protected, loader, state, encoder):
    rows = []; first_assessment = None
    for index in range(REPETITIONS):
        begin = time.perf_counter()
        selection = loader.select_restart_calibration(protected, snapshot)
        selected = time.perf_counter()
        assessment = state.classify_restart(snapshot, calibration=selection['calibration'],
                                            qualification_context=protected['qualification_context'])
        classified = time.perf_counter()
        if first_assessment is None:
            first_assessment = assessment
        # Temporary serialization workload only: no fabricated capture landmarks,
        # event authority, physical execution or new retained intervention event.
        payload = {'incarnation': (snapshot['authority'].get('active_request') or {}).get('incarnation'),
            'active_request': snapshot['authority'].get('active_request'), 'exposure': snapshot['exposure'],
            'protected_restart_state': snapshot, 'restart_admissibility': assessment,
            'protected_snapshot': snapshot['geometry'], 'restart_calibration': selection['calibration'],
            'restart_qualification_identity': protected['identity'],
            'restart_qualification_selection': {k:v for k,v in selection.items() if k != 'calibration'},
            'capture_landmarks': None}
        encoder.events = io.StringIO()
        encode_started = time.perf_counter()
        encoder.emit('restart_begin', payload, snapshot['capture_sim_time_s'], 'offline-benchmark')
        encoded = time.perf_counter()
        event_text = encoder.events.getvalue(); encoder.events.close()
        evidence = assessment.get('qualified_class_evidence', [])
        route = next((p for p in assessment['predicates'] if p['name'] == 'measured_recovery_route'), None)
        rows.append({'call_index': index, 'first_call_in_process': index == 0,
            'selection_wall_s': selected - begin, 'classification_wall_s': classified - selected,
            'selection_plus_classification_wall_s': classified - begin,
            'event_encoding_to_memory_wall_s': encoded - encode_started,
            'selection_state': selection['state'], 'selected_cell_id': selection.get('qualification_cell_id'),
            'assessment_state': assessment['state'], 'assessment_sha256': state.digest(assessment),
            'qualified_entry_states': [r.get('state') for r in evidence],
            'route_predicate_state': None if route is None else route['state'],
            'full_qualified_route_path_observed': selection['state'] == 'pass' and len(evidence) == 2
                and all(r.get('state') == 'pass' for r in evidence) and route is not None and route['state'] != 'unknown',
            'encoded_event_utf8_bytes': len(event_text.encode('utf-8'))})
    return rows, first_assessment


def run(args, queue_authority):
    output = Path(args.output).resolve()
    require(not output.exists() and output.parent.is_dir(), 'Output must be fresh under an existing operator directory')
    require('candidate_state' not in [p.casefold() for p in output.parts], 'Output cannot be candidate state')
    output.mkdir()
    inputs = assembly.Inputs()
    setup_started = time.perf_counter()
    report = {'schema_version': 'offline-qualified-restart-cpu-benchmark-1', 'queue': queue_authority,
        'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed', 'calls': [],
        'repetitions': REPETITIONS, 'offline_cpu_only': True, 'native_model_execution': False,
        'physics_executed': False, 'qualification_granted': False, 'scored_ready_claimed': False,
        'physical_timing_pass_claimed': False}
    try:
        for path in [Path(__file__), HERE / 'assemble_qualification.py', HERE / 'bundle_construction.py',
                     HERE / 'compatibility.py', *sorted(RUNTIME.glob('*.py'))]:
            inputs.read(path)
        if args.provisional_rule:
            rule, ref = inputs.read(args.provisional_rule, parse=True)
            require(rule.get('schema_version') == 'provisional-restart-class-rule-1'
                    and rule.get('status') == 'provisional_development_rule', 'Explicit provisional rule required')
            report.update(mode='provisional_digest_only', rule_ref=ref, shape=shape(rule),
                          full_qualified_path_measured=False, setup_wall_s=time.perf_counter()-setup_started)
            for index in range(REPETITIONS):
                started = time.perf_counter(); value = digest(rule); finished = time.perf_counter()
                report['calls'].append({'call_index': index, 'first_call_in_process': index == 0,
                                        'canonical_rule_sha256': value, 'digest_wall_s': finished - started})
            report['limitations'] = ['Shape/counts and direct canonical rule digest only; no acceptance, loader, selection, classifier, event encoding or qualification context.',
                'This cannot measure the full qualified restart path or infer its timing pass.']
        else:
            loader, state, runner = modules()
            freeze, freeze_ref, bundle, bundle_ref = bind_accepted(args, inputs, runner)
            snapshot, cut_refs = retained_cut(args, inputs, bundle, Path(bundle_ref['path']))
            started = time.perf_counter()
            verified = loader.load_restart_qualification(freeze, args.development_freeze)
            loaded = time.perf_counter(); protected = verified.as_dict(); materialized = time.perf_counter()
            encoder = event_encoder(inputs)
            report.update(mode='accepted_qualified_offline', freeze_ref=freeze_ref, bundle_ref=bundle_ref,
                cut_refs=cut_refs, shape=shape(bundle), loader_file_verification_wall_s=loaded-started,
                protected_input_materialization_wall_s=materialized-loaded,
                snapshot_sha256=snapshot['snapshot_sha256'], object_count=len(snapshot['geometry']['objects']),
                setup_wall_s=time.perf_counter()-setup_started)
            report['calls'], report['first_assessment'] = measure_calls(snapshot, protected, loader, state, encoder)
            report['full_qualified_path_measured'] = all(r['full_qualified_route_path_observed'] for r in report['calls'])
            report['limitations'] = ['Retained snapshot replay only; no live model capture, physics, renderer, inference or live restart.',
                'Five calls in one process; first is not an OS cold-cache measurement. Results are descriptive CPU wall costs.',
                'Event encoding executes the actual source-extracted Evidence.emit on StringIO; excludes disk/flush latency, contention and actual capture landmarks.',
                'File and dependency verification is setup cost outside timed classification; no live native/assets validation or physical timing threshold is claimed.',
                'Actual-host development timing with the accepted freeze remains necessary; source/class/structural validity is not timing evidence.']
        report['status'] = 'complete'
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
    before = list(inputs.refs.values()); after = []
    for ref in before:
        try:
            path = Path(ref['path'])
            after.append({'path': str(path), 'sha256': checksum(path), 'bytes': path.stat().st_size})
        except OSError as error:
            after.append({'path': ref['path'], 'error': type(error).__name__ + ': ' + str(error)})
    report.update(input_refs_before=before, input_refs_after=after, inputs_unchanged=before == after,
                  completed_at=datetime.now(timezone.utc).isoformat())
    if not report['inputs_unchanged']:
        report['status'] = 'failed'; report['integrity_error'] = 'Consumed input/source bytes changed'
    assembly.write(output / 'summary.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--development-freeze'); mode.add_argument('--provisional-rule')
    for name in ('assembly', 'assembly-receipt', 'cut-states', 'events'):
        parser.add_argument('--' + name)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    final_options = (args.assembly, args.assembly_receipt, args.cut_states, args.events)
    if args.provisional_rule and any(final_options):
        parser.error('Provisional mode accepts no final-mode inputs')
    if args.development_freeze and not all((args.assembly_receipt, args.cut_states, args.events)):
        parser.error('Final mode requires --assembly-receipt, --cut-states and --events')
    _, runner = assembly.runtime_modules()
    job = runner.queued_job(expected_script=Path(__file__).resolve())
    report = run(args, job)
    print(json.dumps({'output': str(Path(args.output).resolve()), 'status': report['status'],
                      'inputs_unchanged': report['inputs_unchanged'], 'offline_cpu_only': True}))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
