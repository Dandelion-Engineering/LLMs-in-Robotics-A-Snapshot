"""Queue-only actual-cover geometry-kernel comparison; never classification.

Fixed: parking1, groups A1/B10, 50 mm bins, 10 mm proposed diagnostic padding,
five paired timings per actual same-group cut scene, one untimed count pair.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import textwrap
import time

import pending_route_validation as proposal

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RUNTIME = PROJECT / 'Runtime'
GROUPS = ('A1', 'B10')
WIDTH_M = .05
PADDING_M = .01
REPEATS = 5
CANDIDATE_SHA256 = 'd5f354c60af83c6f9d32f6b43a893c19486ddcb1f8d2f85c78f526fe48d0273c'


def require(value, reason):
    if not value:
        raise ValueError(reason)


def file_ref(path):
    path = Path(path).resolve(); before = path.stat()
    with path.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'File changed while hashing')
    return {'path': str(path), 'sha256': checksum, 'bytes': after.st_size}


def kernel_functions(source):
    """Compile only validators and the two exact blocker blocks; no route gate."""
    candidate = proposal.candidate_source(source)
    require(hashlib.sha256(candidate.encode()).hexdigest() == CANDIDATE_SHA256, 'Candidate identity differs')
    names = {'number', 'vector', 'valid_box', 'overlaps'}
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in names]
    require({n.name for n in nodes} == names, 'Geometry validator inventory differs')
    common = ("    if not isinstance(corridors,list) or not corridors or any(not valid_box(b) for b in corridors):\n"
              "        raise ValueError('Malformed kernel corridor input')\n")
    functions = {}
    for name, block in (('original', proposal.OLD), ('validated_once', proposal.NEW)):
        code = ('def kernel(snapshot,obj,corridors):\n' + common
                + textwrap.indent(textwrap.dedent(block), '    ') + '    return blockers\n')
        namespace = {'math': math}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<geometry validators only>', 'exec'), namespace)
        exec(compile(code, '<' + name + ' blocker kernel only>', 'exec'), namespace)
        functions[name] = {'namespace': namespace, 'call': namespace['kernel'], 'source': code,
                           'source_sha256': hashlib.sha256(code.encode()).hexdigest()}
    return functions


def counted(function, snapshot, payload, corridors):
    namespace = function['namespace']; original = namespace['valid_box']
    count = {'total': 0, 'corridor': 0, 'object': 0}
    corridor_ids = {id(box) for box in corridors}
    object_ids = {id(o.get('bounds')) for o in snapshot['geometry']['objects'] if o['id'] != payload['id']}
    def valid(box):
        count['total'] += 1
        count['corridor'] += id(box) in corridor_ids
        count['object'] += id(box) in object_ids
        return original(box)
    namespace['valid_box'] = valid
    try:
        blockers = function['call'](snapshot, payload, corridors)
    finally:
        namespace['valid_box'] = original
    return {'blocker_ids': blockers, 'valid_box_calls': count}


def benchmark(functions, objects, payload_id, corridors):
    snapshot, payload = {'geometry': {'objects': objects}}, {'id': payload_id}
    counts = {name: counted(fn, snapshot, payload, corridors) for name, fn in functions.items()}
    repeats = []
    for index in range(REPEATS):
        order = ('original', 'validated_once') if index % 2 == 0 else ('validated_once', 'original')
        measurements = {}
        for name in order:
            wall = time.perf_counter(); cpu = time.process_time()
            blockers = functions[name]['call'](snapshot, payload, corridors)
            cpu_end = time.process_time(); wall_end = time.perf_counter()
            measurements[name] = {'wall_s': wall_end-wall, 'cpu_s': cpu_end-cpu, 'blocker_ids': blockers}
        repeats.append({'repeat': index+1, 'execution_order': list(order), 'measurements': measurements,
            'exact_outputs_equal': measurements['original']['blocker_ids'] == measurements['validated_once']['blocker_ids']})
    baseline = counts['original']['blocker_ids']
    return {'timed_pairs': repeats, 'untimed_validation_counts': counts,
        'all_outputs_exactly_equal': counts['validated_once']['blocker_ids'] == baseline
            and all(row['exact_outputs_equal'] and all(m['blocker_ids'] == baseline for m in row['measurements'].values())
                    for row in repeats),
        'summary': {name: {clock: {'minimum': min(values), 'median': sorted(values)[len(values)//2],
                                  'maximum': max(values)}
                    for clock in ('wall_s', 'cpu_s')
                    for values in [[row['measurements'][name][clock] for row in repeats]]}
                    for name in functions}}


def same_ref(actual, expected):
    return (actual['sha256'] == expected['sha256'] and
            Path(actual['path']).resolve() == Path(expected['path']).resolve() and
            ('bytes' not in expected or actual['bytes'] == expected['bytes']))


def run(args, authority, dependencies):
    import assess_validation as assessment
    output = Path(args.output).resolve()
    require(not output.exists(), 'Fresh output required')
    compact_path = Path(args.compact_report).resolve()
    # Refuse an incomplete/failed compact run before its cover files are read.
    receipt = json.loads(Path(args.compact_receipt).read_bytes())
    require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int
            and receipt['exit_status'] == 0, 'Successful official compact receipt required')
    source = assessment.CompletedExtraction(args.construction_extraction, args.screen_receipt, args.extraction_receipt)
    require(source.manifest['execution_phase'] == 'construction', 'Construction inputs only')
    for base in (source.base, source.evidence.root, compact_path.parent, PROJECT/'Runtime', PROJECT/'Batch 01'):
        base = base.resolve()
        require(output != base and base not in output.parents and output not in base.parents, 'Output overlaps protected input/source')
    require('candidate_state' not in [p.casefold() for p in output.parts], 'Candidate state output forbidden')
    compact, compact_ref = source.evidence.external(compact_path)
    compact_receipt, compact_receipt_ref = source.evidence.external(args.compact_receipt)
    assessment.successful_receipt(compact_receipt, compact.get('queue'), compact['completed_at'])
    require(compact.get('schema_version') == 'compact-construction-corridor-diagnostic-1'
            and compact.get('status') == 'complete' and compact.get('source_inputs_unchanged') is True
            and compact['destination'] == 'parking1', 'Incomplete or wrong-destination compact diagnostic')
    from release_runner import python_entrypoint
    job = compact['queue']; argv = job['argv']
    require(python_entrypoint(argv, job['cwd']) == PROJECT/'Engineering Investigation/compact_construction_corridors.py',
            'Compact receipt names another helper')
    require(argv.count('--output') == 1, 'Ambiguous compact output argument')
    recorded_output = Path(argv[argv.index('--output')+1])
    recorded_output = recorded_output if recorded_output.is_absolute() else Path(job['cwd'])/recorded_output
    require(compact_path == recorded_output.resolve()/'compact-corridors.json', 'Compact path differs from official output')
    for name, expected in (('construction_extraction_ref', source.ref), ('screen_receipt_ref', source.receipt_ref),
                           ('extraction_receipt_ref', source.extraction_receipt_ref)):
        require(same_ref(compact[name], expected), 'Compact extraction/receipt binding differs: '+name)
    require(compact['inputs_before'] == compact['inputs_after'], 'Compact source hold failed')
    for expected in compact['inputs_after'].values():
        require(file_ref(expected['path']) == expected, 'Compact source dependency changed')
    code, code_ref = source.source('Runtime/restart_state.py')
    raw = proposal.TARGET.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == proposal.BASE_SHA256
            and code_ref['sha256'] == proposal.BASE_SHA256, 'Archived/current Runtime kernel source differs')
    functions = kernel_functions(raw.decode('utf-8'))
    declarations = [{'trial_id': identity, 'declaration': declaration,
                     'execution_status': source.entries[identity]['execution_status'],
                     'kernel_benchmarked': False} for identity, declaration in source.declared.items()]
    by_id = {row['trial_id']: row for row in declarations}
    results = []
    for group_id in GROUPS:
        matches = [g for g in compact['payload_location_groups'] if g['payload_location_group'] == group_id]
        require(len(matches) == 1, 'Missing or ambiguous declared payload group')
        group = matches[0]
        require(group['all_declared_group_routes_included'] and group['all_available_group_cut_scenes_included'],
                'Incomplete compact group retained; benchmark cannot silently omit it')
        choices = [c for c in group['candidates'] if c['bin_width_m'] == WIDTH_M]
        require(len(choices) == 1, 'Missing/ambiguous fixed 50 mm cover')
        choice = choices[0]
        cover, cover_ref = source.evidence.external(choice['cover_ref']['path'])
        require(same_ref(cover_ref, choice['cover_ref']) and cover['bin_width_m'] == WIDTH_M
                and cover['payload_location_group'] == group_id and cover['containment']['state'] == 'pass',
                'Cover identity/containment differs')
        require(len(cover['covers']) == choice['cover_box_count'], 'Cover count differs')
        corridors = [{'min': [v-PADDING_M for v in record['box']['min']],
                      'max': [v+PADDING_M for v in record['box']['max']]} for record in cover['covers']]
        scenes = group['cut_scene_trial_ids']
        require(scenes and len(scenes) == len(set(scenes)) and
                scenes == [r['cut_trial_id'] for r in choice['actual_cut_scene_comparisons']], 'Cut scene coverage differs')
        comparisons = {r['cut_trial_id']: r for r in choice['actual_cut_scene_comparisons']}
        group_result = {'payload_location_group': group_id, 'cover_ref': cover_ref, 'cover_box_count': len(corridors),
            'bin_width_m': WIDTH_M, 'diagnostic_uniform_padding_m': PADDING_M,
            'padded_corridors_sha256': assessment.digest(corridors), 'scenes': []}
        results.append(group_result)
        for identity in scenes:
            require(identity in source.selected and source.declared[identity]['destination'] == 'parking1', 'Cut scene not declared construction')
            row = source.trial(identity); cut = row['states']['cut']; child = row.get('child_result') or {}
            require((child.get('details') or {}).get('picked_visible_part_id') == group_id, 'Actual cut payload group differs')
            require(cut['payload']['snapshot_sha256'] == comparisons[identity]['cut_snapshot_sha256']
                    and cut['source_ref'] == comparisons[identity]['cut_source_ref'], 'Compact cut snapshot binding differs')
            objects = cut['payload']['geometry']['objects']
            require(sum(o['id'] == group_id for o in objects) == 1, 'Cut payload inventory differs')
            by_id[identity].update(kernel_benchmarked=True, child_status=child.get('status'), child_error=child.get('error'),
                physical_predicates_passed=(child.get('details') or {}).get('physical_predicates_passed'),
                timing=child.get('timing'), all_objects_generator_domain_members=(row.get('compiled_properties') or {}).get('all_objects_generator_domain_members'))
            group_result['scenes'].append({'trial_id': identity, 'cut_source_ref': cut['source_ref'],
                'snapshot_sha256': cut['payload']['snapshot_sha256'], 'trial_ref': row['consumed_ref'],
                'other_object_count': len(objects)-1, 'cut_objects_sha256': assessment.digest(objects),
                **benchmark(functions, objects, group_id, corridors)})
    source.evidence.stable()
    inputs_before = list(source.evidence.consumed.values())
    inputs_after = [file_ref(ref['path']) for ref in inputs_before]
    require(all(same_ref(after, before) for before, after in zip(inputs_before, inputs_after)), 'Benchmark inputs changed')
    after = {str(path): file_ref(path) for path in dependencies}
    require(after == authority['source_before'], 'Benchmark helper/Runtime source changed')
    return {'schema_version': 'route-blocker-kernel-benchmark-1', 'completed_at': datetime.now(timezone.utc).isoformat(),
        'queue': authority['queue'], 'status': 'complete', 'source_before': authority['source_before'], 'source_after': after,
        'inputs_before': inputs_before, 'inputs_after': inputs_after, 'inputs_and_sources_unchanged': True,
        'compact_report_ref': compact_ref, 'compact_receipt_ref': compact_receipt_ref, 'runtime_source_ref': code_ref,
        'runtime_base_sha256': proposal.BASE_SHA256, 'unapplied_candidate_sha256': CANDIDATE_SHA256,
        'kernel_sources': {name: {k: value[k] for k in ('source', 'source_sha256')} for name, value in functions.items()},
        'timed_pairs_per_scene': REPEATS, 'untimed_count_pairs_per_scene': 1,
        'order_rule': 'original first on odd pairs, validated_once first on even pairs; one preceding untimed count pair',
        'trials': declarations, 'groups': results,
        'all_outputs_exactly_equal': all(scene['all_outputs_exactly_equal'] for g in results for scene in g['scenes']),
        'scope': 'Geometry blocker kernel plus common one-time corridor validity check only. No _route, calibration, classification, accepted bundle, native model or physics.',
        'diagnostic_padding_is_selected_transfer_rule': False, 'qualification_granted': False, 'readiness_granted': False,
        'limitations': ['Timings exclude evidence verification, source compilation, input preparation, validation-count instrumentation and file output.',
                       'Full route/classifier/bundle hashing and process restart costs are not measured.',
                       'Five warm paired timings are a bounded local comparison, not a performance guarantee.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('compact-report', 'compact-receipt', 'construction-extraction', 'screen-receipt', 'extraction-receipt', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(RUNTIME))
    import release_runner
    queue = release_runner.queued_job(expected_script=__file__)
    import assess_validation as assessment
    dependencies = [Path(__file__).resolve(), Path(proposal.__file__).resolve(), proposal.TARGET.resolve(),
        Path(assessment.__file__).resolve(), Path(assessment.reader.__file__).resolve(),
        HERE/'compatibility.py', HERE/'bundle_construction.py', Path(release_runner.__file__).resolve(),
        PROJECT/'Engineering Investigation/compact_construction_corridors.py']
    source_before = {str(path): file_ref(path) for path in dependencies}
    report = run(args, {'queue': queue, 'source_before': source_before}, dependencies)
    assessment.reader.write(Path(args.output)/'kernel-benchmark.json', report)
    require(report['all_outputs_exactly_equal'], 'Kernel output mismatch; retained report is non-authorizing')
    print(json.dumps({'output': str(Path(args.output).resolve()), 'all_outputs_exactly_equal': True, 'qualification_granted': False}))


if __name__ == '__main__':
    main()
