"""QUEUE-ONLY compiled descriptor acceptance/timing probe; no physics stepping.

Submit through the shared compute queue. --output names a NEW directory.
Constructs only development models n3/seed0, n6/seed1, n10/seed2. Never creates
Cell, MjData, a renderer, a candidate or a model-inference process. Failures are
retained in summary.json and exit 0; exit status is not descriptor acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

from compatibility import digest, verify_class_compatibility
from descriptor import (UnsupportedEvidence, class_spec_from_seal, export_observation,
                        file_sha, seal_model)

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent.parent / 'Runtime'
CASES = ((3, 0), (6, 1), (10, 2))


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    # Exclusive creation preserves every attempted diagnostic artifact.
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def exception_record(error):
    message = str(error)
    if 'unsupported property' in message:
        category = 'unsupported_model_property'
    elif isinstance(error, UnsupportedEvidence):
        category = 'unsupported_or_missing_evidence'
    else:
        category = 'probe_exception'
    return {'category': category, 'exception_type': type(error).__name__, 'message': message,
            'traceback': traceback.format_exc()}


def binding(mujoco):
    """Use the actual helper files under test, not nonexistent Runtime copies.

    The logical restart_*.py labels match the proposed module roles; the manifest
    explicitly retains their current qualification-folder paths. This is a probe
    attestation, not a claim that the Runtime integration patch has been applied.
    """
    paths = {name: RUNTIME / name for name in ('cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py', 'restart_state.py')}
    paths.update({'descriptor_exporter': HERE / 'descriptor.py',
                  'restart_compatibility.py': HERE / 'compatibility.py',
                  'restart_qualification.py': HERE / 'qualification.py'})
    sources = {name: file_sha(path) for name, path in paths.items()}
    assets_root = RUNTIME / 'vendor' / 'panda'
    assets = {p.relative_to(assets_root).as_posix(): file_sha(p) for p in sorted(assets_root.rglob('*')) if p.is_file()}
    package = Path(mujoco.__file__).resolve().parent
    binaries = {p.relative_to(package).as_posix(): file_sha(p) for p in sorted(package.rglob('*'))
                if p.is_file() and p.suffix.lower() in ('.pyd', '.dll', '.so', '.dylib')}
    if not assets or not binaries:
        raise UnsupportedEvidence('asset or MuJoCo binary identity missing')
    sources['robot_assets'] = digest(assets)
    sources['mujoco_build'] = digest({'version': mujoco.__version__, 'binaries': binaries})
    manifest = {'source_hashes_for_seal': sources,
                'logical_source_paths': {key: str(path.resolve()) for key, path in paths.items()},
                'all_runtime_py_sha256': {p.name: file_sha(p) for p in sorted(RUNTIME.glob('*.py'))},
                'all_qualification_helper_py_sha256': {p.name: file_sha(p) for p in sorted(HERE.glob('*.py'))},
                'robot_assets_root': str(assets_root.resolve()), 'robot_assets_sha256': assets,
                'mujoco_package': str(package), 'mujoco_version': mujoco.__version__, 'mujoco_binaries_sha256': binaries,
                'probe_sha256': file_sha(__file__), 'python_executable': sys.executable, 'python_version': sys.version,
                'integration_state': 'helpers exercised at direct probe compilation site; Runtime hook not applied'}
    return sources, manifest


def physical_configuration_hash(model, cell_module):
    # Same exact configuration fields as current protected restart capture.
    fields = ('body_mass', 'body_inertia', 'geom_type', 'geom_size', 'geom_friction', 'geom_solref', 'geom_solimp',
              'jnt_type', 'jnt_axis', 'jnt_range', 'actuator_gainprm', 'actuator_biasprm', 'actuator_ctrlrange', 'actuator_forcerange')
    values = {name: getattr(model, name).tolist() for name in fields}
    values.update(timestep=float(model.opt.timestep), integrator=int(model.opt.integrator),
                  gravity=model.opt.gravity.tolist(), zones=cell_module.ZONES,
                  zone_halves={name: list(cell_module.zone_half(name)) for name in cell_module.ZONES})
    return digest(values)


def timed_export(model, xml, registry, seal, physical_hash):
    started = time.perf_counter()
    try:
        observation = export_observation(model, xml, registry, seal, physical_configuration_sha256=physical_hash)
        reason = observation.get('reason')
        category = ('unsupported_model_property' if isinstance(reason, str) and 'unsupported property' in reason
                    else 'evidence_unknown' if observation.get('export_state') == 'unknown' else 'accepted')
        return {'wall_s': time.perf_counter() - started, 'observation': observation, 'category': category}
    except Exception as error:
        return {'wall_s': time.perf_counter() - started, 'observation': None, 'error': exception_record(error), 'category': 'probe_exception'}


def mutation_checks(model, xml, registry, seal, physical_hash):
    """Change one fixed solver field and one permitted mark, always restore both."""
    reports = {}
    previous_iterations = int(model.opt.iterations)
    try:
        model.opt.iterations = previous_iterations + 1
        result = timed_export(model, xml, registry, seal, physical_hash)
        reports['fixed_solver_iterations'] = {**result, 'before': previous_iterations,
                                             'mutated': int(model.opt.iterations), 'expected_export_state': 'unknown'}
    finally:
        model.opt.iterations = previous_iterations
    reports['fixed_solver_iterations']['restored'] = int(model.opt.iterations) == previous_iterations
    index = seal['mark_indices'][0]
    previous_color = model.geom_rgba[index].copy()
    try:
        model.geom_rgba[index] = [1., 1., 1., 1.]
        result = timed_export(model, xml, registry, seal, physical_hash)
        reports['allowed_process_mark_toggle'] = {**result, 'geom_index': index,
                                                'before': previous_color.tolist(), 'mutated': model.geom_rgba[index].tolist(),
                                                'expected_export_state': 'pass'}
    finally:
        model.geom_rgba[index] = previous_color
    reports['allowed_process_mark_toggle']['restored'] = model.geom_rgba[index].tolist() == previous_color.tolist()
    for report in reports.values():
        report['expectation_met'] = report['restored'] and (report.get('observation') or {}).get('export_state') == report['expected_export_state']
    return reports


def run_case(output, n, seed, cell_module, mujoco, sources, reference_spec):
    directory = output / f'n{n}-development-seed{seed}'
    directory.mkdir()
    report = {'part_count': n, 'world_seed': seed, 'layout_seed': seed, 'stage': 'development_descriptor_diagnostic',
              'started_at_utc': now(), 'model_constructed': False, 'seal_accepted': False,
              'exports': [], 'mutation_checks': None, 'physical_success': 'not_assessed'}
    model = seal = None
    try:
        started = time.perf_counter()
        xml, registry = cell_module.build_scene(n=n, seed=seed, layout_seed=seed)
        report['scene_generation_wall_s'] = time.perf_counter() - started
        (directory / 'scene.xml').write_text(xml, encoding='utf-8')
        write_json(directory / 'registry.json', registry)
        report['scene_xml_sha256'] = hashlib.sha256(xml.encode()).hexdigest()
        started = time.perf_counter()
        model = mujoco.MjModel.from_xml_string(xml)
        report['compile_wall_s'] = time.perf_counter() - started
        report['model_constructed'] = True
        physical_hash = physical_configuration_hash(model, cell_module)
        report['physical_configuration_sha256'] = physical_hash
        started = time.perf_counter()
        try:
            seal = seal_model(model, xml, registry, sources)
            report['seal_wall_s'] = time.perf_counter() - started
            report['seal_accepted'] = True
            write_json(directory / 'compile-seal.json', seal)
            spec = class_spec_from_seal(seal)
            write_json(directory / 'class-spec.json', spec)
            if reference_spec is None:
                reference_spec = spec
                report['is_cross_population_reference'] = True
        except Exception as error:
            report['seal_wall_s'] = time.perf_counter() - started
            report['seal_error'] = exception_record(error)
        for index in range(3):
            attempt = timed_export(model, xml, registry, seal, physical_hash)
            attempt['attempt_index'] = index + 1
            if reference_spec is not None and attempt.get('observation') is not None:
                attempt['reference_class_compatibility'] = verify_class_compatibility(reference_spec, attempt['observation'], frozen_spec_sha256=digest(reference_spec))
            report['exports'].append(attempt)
            write_json(directory / f'export-{index+1}.json', attempt)
        baseline_passes = seal is not None and all((r.get('observation') or {}).get('export_state') == 'pass' for r in report['exports'])
        if baseline_passes:
            report['mutation_checks'] = mutation_checks(model, xml, registry, seal, physical_hash)
        else:
            report['mutation_checks'] = {'state': 'not_run_unusable_baseline',
                                         'reason': 'unknown baseline cannot establish a mutation counterexample'}
    except Exception as error:
        report['case_error'] = exception_record(error)
    finally:
        if not report['exports']:
            report['exports'] = [{'attempt_index': i + 1, 'wall_s': None, 'category': 'not_run_model_or_configuration_unavailable'} for i in range(3)]
        report['finished_at_utc'] = now()
        exports_pass = all((r.get('observation') or {}).get('export_state') == 'pass'
                           and r.get('reference_class_compatibility', {}).get('compatibility_state') == 'pass' for r in report['exports'])
        mutations = report.get('mutation_checks') or {}
        report['descriptor_checks_passed'] = (report['seal_accepted'] and exports_pass and
            all(mutations.get(key, {}).get('expectation_met') is True for key in ('fixed_solver_iterations', 'allowed_process_mark_toggle')))
        write_json(directory / 'result.json', report)
    return report, reference_spec


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='fresh output directory; run only through shared queue')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        parser.error('--output already exists; a fresh directory is required')
    output.mkdir(parents=True, exist_ok=False)
    summary = {'schema_version': 'descriptor-compile-probe-1', 'started_at_utc': now(),
               'execution_contract': 'shared compute queue only', 'cases': [], 'physical_success': 'not_assessed',
               'physics_steps': 0, 'renderers_created': 0, 'inference_processes_created': 0,
               'evaluation_seeds_generated': False, 'readiness_changed': False,
               'runtime_modified': False, 'descriptor_checks_passed': False}
    try:
        sys.path.insert(0, str(RUNTIME))
        import mujoco
        import cell
        started = time.perf_counter()
        sources, manifest = binding(mujoco)
        summary['source_binding_wall_s'] = time.perf_counter() - started
        summary['source_binding_sha256'] = digest(manifest)
        write_json(output / 'source-binding.json', manifest)
        reference = None
        for n, seed in CASES:
            report, reference = run_case(output, n, seed, cell, mujoco, sources, reference)
            summary['cases'].append(report)
        # Detect source edits while probing; never silently relabel such output
        # as an experiment frozen to the initial bytes.
        final_sources, final_manifest = binding(mujoco)
        summary['source_binding_unchanged'] = sources == final_sources and manifest == final_manifest
        if not summary['source_binding_unchanged']:
            write_json(output / 'source-binding-after.json', final_manifest)
        summary['descriptor_checks_passed'] = summary['source_binding_unchanged'] and all(r['descriptor_checks_passed'] for r in summary['cases'])
    except Exception as error:
        summary['probe_error'] = exception_record(error)
    summary['finished_at_utc'] = now()
    summary['execution_status'] = 'completed' if summary['descriptor_checks_passed'] else 'completed_with_retained_failures'
    write_json(output / 'summary.json', summary)
    print(json.dumps({'output': str(output), 'execution_status': summary['execution_status'],
                      'descriptor_checks_passed': summary['descriptor_checks_passed'],
                      'physical_success': 'not_assessed'}, sort_keys=True))
    return 0


if __name__ == '__main__': raise SystemExit(main())
