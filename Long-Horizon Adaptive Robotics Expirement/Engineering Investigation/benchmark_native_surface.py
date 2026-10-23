"""Queue-owned, build-only CPU benchmark. No mj_step, Cell, sensors or policies."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import traceback
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
RUNTIME = PROJECT / 'Runtime'
STAGE = HERE / 'Native surface optimization'
sys.path.insert(0, str(RUNTIME))
import release_runner


def utc(): return datetime.now(timezone.utc).isoformat()


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def source_inventory():
    paths = set(RUNTIME.glob('*.py'))
    paths.update(path for path in (RUNTIME / 'vendor/panda').rglob('*') if path.is_file())
    paths.update([Path(__file__), STAGE / 'manifest.json', STAGE / 'Runtime/restart_physical_class.py',
                  STAGE / 'original/Runtime/restart_physical_class.py'])
    return {str(path.resolve()): ref(path) for path in sorted(paths)}


def run(output, repeats):
    ownership = release_runner.queued_job(expected_script=__file__)
    if not 1 <= repeats <= 30: raise ValueError('Use 1 to 30 paired warm repetitions')
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to((PROJECT / 'Evidence/derived').resolve()):
        raise ValueError('Output must be fresh beneath Evidence/derived')
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema_version': 'static-native-surface-benchmark-1', 'status': 'failed',
        'queue_job_id': ownership['id'], 'created_at': utc(), 'finished_at': None,
        'inputs_before': source_inventory(), 'inputs_after': None, 'inputs_unchanged': False,
        'model_count': 1, 'population': 10, 'world_seed': 0, 'simulation_steps': 0,
        'state': 'one generated model, native forward initialization only, no Cell/planner/sensor',
        'repeat_count': repeats, 'results': {}, 'error': None,
        'interpretation': 'CPU cost and exact output equivalence only; no physics success or real-time qualification',
        'official_receipt_required': True}
    failure = None
    try:
        import mujoco
        import numpy as np
        import cell as cell_module
        import restart_state
        from evaluator import IndependentEvaluator
        old_path = STAGE / 'original/Runtime/restart_physical_class.py'
        new_path = STAGE / 'Runtime/restart_physical_class.py'
        manifest = json.loads((STAGE / 'manifest.json').read_text(encoding='utf-8'))
        guards = manifest['changed'][0]
        if (ref(old_path)['sha256'] != guards['before_sha256']
                or ref(new_path)['sha256'] != guards['staged_sha256']
                or ref(RUNTIME / 'restart_physical_class.py')['sha256'] != guards['before_sha256']):
            raise ValueError('Benchmark original/staged/current exporter identities differ')
        original, proposed = load('benchmark_original_export', old_path), load('benchmark_proposed_export', new_path)
        sources = original.source_binding(RUNTIME, mujoco)
        xml, registry = cell_module.build_scene(10, seed=0, layout_seed=0)
        model = mujoco.MjModel.from_xml_string(xml)
        seal = original.seal_model(model, xml, registry, sources)
        data = mujoco.MjData(model)
        data.qpos[:7] = cell_module.HOME; data.qpos[7:9] = .04
        data.ctrl[:7] = cell_module.HOME; data.ctrl[7] = 255
        mujoco.mj_forward(model, data)
        fixture = SimpleNamespace(model=model, data=data, xml=xml, registry=registry, restart_physical_seal=seal,
            evaluator=IndependentEvaluator(), truth={}, station={'busy': False, 'ready': True},
            active_request=None, motion=[], segment=None, cycle=None, inspection_due=None, inspection=None,
            tcp=model.site('tcp').id, plan_generation=1, lease_deadline=None, direct_command=None,
            plan_future=None, pending_plan_generation=None, direct_plan_future=None, direct_plan_generation=None,
            _setup_wait=None, detection_time=0., last_sensor_result=None)
        kwargs = dict(zones=cell_module.ZONES, zone_half=cell_module.zone_half,
                      exposure={'actual_cut': 'static_cpu_benchmark'}, source_hashes=sources)
        # Warm the evaluator's geometry index cache equally before timed calls.
        fixture.evaluator.snapshot_cell(fixture, zones=cell_module.ZONES, zone_half=cell_module.zone_half)
        def state():
            return {'time': float(data.time), 'qpos': data.qpos.tolist(), 'qvel': data.qvel.tolist(),
                    'ctrl': data.ctrl.tolist(), 'xpos': data.xpos.tolist(), 'geom_xpos': data.geom_xpos.tolist(),
                    'geom_xmat': data.geom_xmat.tolist(), 'ncon': int(data.ncon),
                    'model_sha256': original.digest(original._model_surface(model, seal['mark_indices']))}
        before_state = state()
        physical_hash = '1' * 64
        def invoke(module, scope):
            if scope == 'class_export':
                return module.export_observation(model, xml, registry, seal, physical_configuration_sha256=physical_hash)
            prior = restart_state.export_observation
            restart_state.export_observation = module.export_observation
            try: return restart_state.capture_restart_state(fixture, **kwargs)
            finally: restart_state.export_observation = prior
        for scope in ('class_export', 'rich_capture'):
            expected = invoke(original, scope)
            if (expected if scope == 'class_export' else expected['physical_class_observation'])['export_state'] != 'pass':
                raise ValueError('Benchmark fixture must have a valid original export')
            block = {name: {'first_call': None, 'warm_pairs': []} for name in ('original', 'proposed')}
            def timed(module, label):
                wall, cpu = time.perf_counter(), time.process_time()
                value = invoke(module, scope)
                cpu_s, wall_s = time.process_time() - cpu, time.perf_counter() - wall
                if value != expected: raise ValueError('Actual output differs: ' + scope + '/' + label)
                return {'wall_s': wall_s, 'cpu_s': cpu_s, 'output_sha256': hashlib.sha256(canonical(value)).hexdigest()}
            proposed._SURFACE_MEMOS.clear()
            for name, module in (('original', original), ('proposed', proposed)):
                block[name]['first_call'] = timed(module, name)
            for index in range(repeats):
                order = [('original', original), ('proposed', proposed)]
                if index % 2: order.reverse()
                for name, module in order:
                    # The pair emulates consecutive rich calls, without removing
                    # fresh checks or changing any native/authority state.
                    pair = [timed(module, name), timed(module, name)]
                    block[name]['warm_pairs'].append(pair)
            for name in block:
                rows = [item for pair in block[name]['warm_pairs'] for item in pair]
                block[name]['warm_summary'] = {
                    'calls': len(rows), 'wall_median_s': statistics.median(r['wall_s'] for r in rows),
                    'wall_min_s': min(r['wall_s'] for r in rows), 'wall_max_s': max(r['wall_s'] for r in rows),
                    'cpu_median_s': statistics.median(r['cpu_s'] for r in rows)}
            save(output / (scope + '-original.json'), expected)
            save(output / (scope + '-proposed.json'), invoke(proposed, scope))
            report['results'][scope] = block
        report['state_before_sha256'] = hashlib.sha256(canonical(before_state)).hexdigest()
        report['state_after_sha256'] = hashlib.sha256(canonical(state())).hexdigest()
        report['native_state_unchanged'] = report['state_before_sha256'] == report['state_after_sha256']
        if not report['native_state_unchanged']: raise ValueError('Native state changed during benchmark')
        report['all_outputs_exactly_equal'] = True
        report['native_package'] = {'version': mujoco.__version__, 'source_binding': sources}
        report['status'] = 'complete'
    except BaseException as error:
        failure = error
        report['error'] = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
    finally:
        report['inputs_after'] = source_inventory()
        report['inputs_unchanged'] = report['inputs_before'] == report['inputs_after']
        if not report['inputs_unchanged']:
            report['status'] = 'failed'
            if failure is None: failure = ValueError('Source changed during benchmark')
        report['finished_at'] = utc(); save(output / 'benchmark.json', report)
    if failure is not None: raise failure
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--repeats', type=int, default=8)
    args = parser.parse_args()
    result = run(args.output, args.repeats)
    print(json.dumps({'status': result['status'], 'queue_job_id': result['queue_job_id'],
                      'all_outputs_exactly_equal': result['all_outputs_exactly_equal']}))
