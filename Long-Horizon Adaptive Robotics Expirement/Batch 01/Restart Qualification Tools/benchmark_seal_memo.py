"""Queue-only static compile/seal/first-export comparison; no physics or renderer.

Uses only development n3/seed0, n6/seed1, n10/seed2. This measures descriptor
export, not an actual boundary snapshot or actual-host physical timing gate.
Original and proposed exporters are retained source-bound staged copies.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[1] / 'Runtime'


def checksum(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_exporter(name, expected):
    path = HERE / 'seal-memo-stage' / (name + '.py')
    if checksum(path) != expected:
        raise ValueError('Staged exporter changed: ' + name)
    spec = importlib.util.spec_from_file_location('_static_seal_' + name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module, path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(RUNTIME))
    import release_runner
    authority = release_runner.queued_job(expected_script=Path(__file__).resolve())
    output = Path(args.output).resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError('Choose a fresh output under an existing operator directory')
    if 'candidate_state' in (part.casefold() for part in output.parts):
        raise ValueError('Benchmark output cannot be candidate state')
    manifest_path = HERE / 'seal-memo-initialization.manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    old, old_path = load_exporter('original', manifest['staged_original_lf_sha256'])
    new, new_path = load_exporter('proposed', manifest['proposed_lf_sha256'])
    import mujoco
    import cell
    from descriptor_probe import physical_configuration_hash
    tracked = [Path(__file__), manifest_path, old_path, new_path, HERE / 'descriptor_probe.py',
               HERE / 'descriptor.py', HERE / 'compatibility.py', *sorted(RUNTIME.glob('*.py'))]
    before = {str(path): checksum(path) for path in tracked}
    output.mkdir()
    rows = []
    for count, seed in ((3, 0), (6, 1), (10, 2)):
        xml, registry = cell.build_scene(n=count, seed=seed, layout_seed=seed)
        for label, exporter in (('original', old), ('proposed', new)):
            row = {'part_count': count, 'development_seed': seed, 'variant': label, 'exports': [],
                   'physical_success': 'not_assessed', 'actual_boundary_capture': False}
            try:
                started = time.perf_counter(); binding = exporter.source_binding(RUNTIME, mujoco)
                row['source_binding_wall_s'] = time.perf_counter() - started
                row['source_binding'] = binding
                started = time.perf_counter(); model = mujoco.MjModel.from_xml_string(xml)
                row['compile_wall_s'] = time.perf_counter() - started
                started = time.perf_counter(); seal = exporter.seal_model(model, xml, registry, binding)
                row['seal_wall_s'] = time.perf_counter() - started
                row['memo_present_after_seal'] = model in exporter._SURFACE_MEMOS
                identity = physical_configuration_hash(model, cell)
                for index in range(3):
                    started = time.perf_counter()
                    observation = exporter.export_observation(model, xml, registry, seal,
                        physical_configuration_sha256=identity)
                    row['exports'].append({'first_post_seal': index == 0, 'wall_s': time.perf_counter() - started,
                        'state': observation.get('export_state'), 'reason': observation.get('reason')})
                original_iterations = model.opt.iterations
                try:
                    model.opt.iterations += 1
                    row['fixed_solver_mutation_state'] = exporter.export_observation(model, xml, registry, seal,
                        physical_configuration_sha256=identity)['export_state']
                finally:
                    model.opt.iterations = original_iterations
                row['restored_state'] = exporter.export_observation(model, xml, registry, seal,
                    physical_configuration_sha256=identity)['export_state']
                row['expectations_met'] = (all(item['state'] == 'pass' for item in row['exports'])
                    and row['fixed_solver_mutation_state'] == 'unknown' and row['restored_state'] == 'pass')
                row['source_binding_unchanged'] = exporter.source_binding(RUNTIME, mujoco) == binding
                del model
            except Exception as error:
                row.update(expectations_met=False, error=type(error).__name__ + ': ' + str(error))
            rows.append(row)
    after = {str(path): checksum(path) for path in tracked}
    report = {'schema_version': 'static-first-export-seal-memo-comparison-1',
        'completed_at': datetime.now(timezone.utc).isoformat(), 'queue': authority,
        'source_hashes_before': before, 'source_hashes_after': after, 'sources_unchanged': before == after,
        'cases': rows, 'expectations_met': before == after and all(row.get('expectations_met')
            and row.get('source_binding_unchanged') for row in rows),
        'scope': 'Six static compiled models; no Cell, MjData, physics step, renderer, inference or actual cut. Fixed variant order; no physical timing claim.'}
    with (output / 'summary.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'output': str(output), 'expectations_met': report['expectations_met'], 'physical_success': 'not_assessed'}))


if __name__ == '__main__': main()
