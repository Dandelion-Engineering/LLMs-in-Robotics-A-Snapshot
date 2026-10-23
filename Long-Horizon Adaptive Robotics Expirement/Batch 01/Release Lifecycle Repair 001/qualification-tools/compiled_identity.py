"""Queued two-process build-only relocation diagnostic; no steps, seeds or release creation.

The fixed public development fixture is n=3, seed/layout=0. XML path replacement
is descriptive comparison only; neither compilation nor class export is changed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
RUNTIMES = {'original': PROJECT / 'Runtime', 'relocated': PROJECT / 'Runtime 004'}
sys.path.insert(0, str(HERE / 'Calibration Tools'))
sys.path.insert(0, str(HERE / 'Recovery Qualification'))
from calibration_authority import parent_authority, child_authority, child_command
from process_caps import JobCap, join_job


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def inventory(runtime):
    paths = sorted(runtime.glob('*.py')) + sorted(p for p in (runtime/'vendor/panda').rglob('*') if p.is_file())
    if not paths or not (runtime/'cell.py').is_file():
        raise ValueError('Complete runtime/asset copy required before diagnostic')
    return {p.relative_to(runtime).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in paths}


def own_sources():
    return {str(p.resolve()): sha(p) for p in
            (Path(__file__), HERE/'Calibration Tools/calibration_authority.py', HERE/'Recovery Qualification/process_caps.py')}


def build_child(args):
    raw = Path(args.parent_manifest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.parent_manifest_sha256:
        raise ValueError('Exact parent manifest differs')
    manifest = json.loads(raw)
    join_job(manifest['probe_job_names'][args._child])
    child_authority(__file__, args._child, args.output, args.seed,
                    args.parent_manifest, args.parent_manifest_sha256)
    runtime = RUNTIMES[args._child].resolve()
    before = inventory(runtime)
    if before != manifest['runtime_inputs'][args._child] or own_sources() != manifest['helper_sources']:
        raise ValueError('Source changed before model compilation')
    sys.path.insert(0, str(runtime))
    import mujoco
    import cell
    import restart_physical_class as physical
    if Path(cell.__file__).resolve() != runtime/'cell.py' or Path(physical.__file__).resolve() != runtime/'restart_physical_class.py':
        raise ValueError('Wrong runtime imported')
    sources_before = physical.source_binding(runtime, mujoco)
    xml, registry = cell.build_scene(3, 0, layout_seed=0)
    model = mujoco.MjModel.from_xml_string(xml)
    seal = physical.seal_model(model, xml, registry, sources_before)
    spec = physical.class_spec_from_seal(seal)
    scene = physical.normalize_scene(xml, registry)
    # Make a separate descriptive XML view. Actual class/spec/seal above always
    # use the unmodified absolute mesh directory supplied by this runtime.
    comparison = ET.fromstring(xml)
    meshdir = comparison.find('compiler').get('meshdir')
    expected_meshdir = str(runtime/'vendor/panda/assets')
    if meshdir != expected_meshdir:
        raise ValueError('Unexpected compiler asset path; no arbitrary normalization')
    comparison.find('compiler').set('meshdir', '<RUNTIME>/vendor/panda/assets')
    descriptive_xml = ET.tostring(comparison, encoding='unicode')
    after = inventory(runtime)
    sources_after = physical.source_binding(runtime, mujoco)
    if before != after or sources_before != sources_after or own_sources() != manifest['helper_sources']:
        raise ValueError('Source/native identity changed during compilation')
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=False)
    for name, value in (('class-spec.json', spec), ('seal.json', seal), ('normalized-scene.json', scene),
                        ('registry.json', registry)):
        write(output/name, value)
    (output/'scene.xml').write_text(xml, encoding='utf-8')
    (output/'descriptive-path-normalized.xml').write_text(descriptive_xml, encoding='utf-8')
    result = {'runtime': str(runtime), 'sources_before': sources_before, 'sources_after': sources_after,
        'inputs_before': before, 'inputs_after': after, 'inputs_unchanged': True,
        'actual_compiler_meshdir': meshdir, 'compiled_surface_sha256': seal['compiled_surface_sha256'],
        'class_spec': spec, 'physics_steps': 0, 'renderer_created': False,
        'files': {p.name: {'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size}
                  for p in sorted(output.iterdir()) if p.is_file()}}
    write(output/'result.json', result)
    return 0


def compare(old, new, old_xml, new_xml, old_descriptive, new_descriptive):
    keys = sorted(set(old['inputs_before']) | set(new['inputs_before']))
    return {'source_and_asset_differences': [
        {'path': key, 'original': old['inputs_before'].get(key), 'relocated': new['inputs_before'].get(key)}
        for key in keys if old['inputs_before'].get(key) != new['inputs_before'].get(key)],
        'source_hashes_equal': old['sources_before'] == new['sources_before'],
        'asset_bytes_equal': old['sources_before']['robot_assets'] == new['sources_before']['robot_assets'],
        'native_build_equal': old['sources_before']['mujoco_build'] == new['sources_before']['mujoco_build'],
        'compiled_surface_equal': old['compiled_surface_sha256'] == new['compiled_surface_sha256'],
        'class_spec_equal': old['class_spec'] == new['class_spec'],
        'component_differences': {key: {'original': value, 'relocated': new['class_spec']['component_sha256'].get(key)}
             for key, value in old['class_spec']['component_sha256'].items()
             if value != new['class_spec']['component_sha256'].get(key)},
        'exact_xml_equal': old_xml == new_xml,
        'descriptive_path_normalized_xml_equal': old_descriptive == new_descriptive,
        'actual_meshdirs': [old['actual_compiler_meshdir'], new['actual_compiler_meshdir']]}


def parent(args):
    authority = parent_authority(__file__)
    output = Path(args.output).resolve()
    for protected in (*RUNTIMES.values(), HERE):
        protected = protected.resolve()
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError('Fresh output must not overlap runtime/tool sources')
    before = {key: inventory(path) for key, path in RUNTIMES.items()}
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'schema_version': 'runtime-relocation-compiled-identity-inputs-1', 'queue': authority,
        'modes': list(RUNTIMES), 'seed': 0, 'runtime_inputs': before, 'helper_sources': own_sources(),
        'fixture': {'population': 3, 'public_development_world_seed': 0, 'layout_seed': 0},
        'probe_job_names': {key: 'Local\\CodexRoboticsCompile_' + uuid.uuid4().hex for key in RUNTIMES},
        'physics_steps': 0, 'scored_inputs_read': False}
    manifest_path = output/'manifest.json'; write(manifest_path, manifest)
    for mode in RUNTIMES:
        command = child_command(sys.executable, Path(__file__).resolve(), mode, output/mode,
                                0, manifest_path, sha(manifest_path))
        cap = JobCap(manifest['probe_job_names'][mode]); process = None
        print('Compiling ' + mode + ' without stepping physics', flush=True)
        try:
            with (output/(mode+'-stdout.log')).open('xb') as stdout, (output/(mode+'-stderr.log')).open('xb') as stderr:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                try:
                    code = process.wait(timeout=90)
                except subprocess.TimeoutExpired:
                    cap.terminate()
                    if process.poll() is None: process.kill()
                    process.wait(timeout=10)
                    raise RuntimeError('Owned build-only child timed out; partial outputs retained')
                if code != 0:
                    raise RuntimeError('Build-only child failed; original logs retained: '+mode)
        finally:
            cap.close()
    old, new = [json.loads((output/name/'result.json').read_bytes()) for name in RUNTIMES]
    old_xml, new_xml = [(output/name/'scene.xml').read_text(encoding='utf-8') for name in RUNTIMES]
    old_norm, new_norm = [(output/name/'descriptive-path-normalized.xml').read_text(encoding='utf-8') for name in RUNTIMES]
    comparison = compare(old, new, old_xml, new_xml, old_norm, new_norm)
    after = {key: inventory(path) for key, path in RUNTIMES.items()}
    unchanged = before == after and manifest['helper_sources'] == own_sources()
    for label, first, second in (('actual', old_xml, new_xml), ('descriptive-path-normalized', old_norm, new_norm)):
        diff = difflib.unified_diff(first.replace('><', '>\n<').splitlines(True),
                                  second.replace('><', '>\n<').splitlines(True), fromfile='Runtime', tofile='Runtime 004')
        (output/(label+'-xml.diff')).write_text(''.join(diff), encoding='utf-8')
    report = {'schema_version': 'runtime-relocation-compiled-identity-1',
        'status': 'complete' if unchanged else 'failed', 'queue': authority,
        'completed_at': datetime.now(timezone.utc).isoformat(), 'comparison': comparison,
        'inputs_before': before, 'inputs_after': after, 'source_inputs_unchanged': unchanged,
        'helper_sources': own_sources(), 'manifest': {'path': str(manifest_path), 'sha256': sha(manifest_path)},
        'runtime_results': {name: {'path': str(output/name/'result.json'), 'sha256': sha(output/name/'result.json')}
                            for name in RUNTIMES},
        'physics_steps': 0, 'qualification_granted': False, 'relocation_waiver': False,
        'limitations': ['A single compiled public development scene; no task, trajectory, timing or qualification result.',
            'Descriptive XML path normalization never changes actual compilation or class matching.',
            'Fresh source-bound construction/validation/acceptance remains necessary.']}
    write(output/'comparison.json', report)
    if not unchanged: raise RuntimeError('Inputs changed during diagnostic')
    print(json.dumps({'output': str(output), 'comparison': comparison, 'qualification_granted': False}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--_child', choices=tuple(RUNTIMES), help=argparse.SUPPRESS)
    parser.add_argument('--seed', type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest', help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest-sha256', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args._child:
        if args.seed != 0 or not args.parent_manifest or not args.parent_manifest_sha256:
            parser.error('Child requires exact parent manifest and fixed development dispatch token')
        return build_child(args)
    return parent(args)


if __name__ == '__main__':
    raise SystemExit(main())
