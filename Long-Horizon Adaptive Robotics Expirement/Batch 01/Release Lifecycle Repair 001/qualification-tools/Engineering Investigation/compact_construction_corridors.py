"""Queue-only fixed compact corridor comparisons from a completed construction.

No parameter selection, pruning search, continuous-sweep bound or qualification.
Every retained interval box is assigned by its original center and contained in
its geometry/bin hull. Binning never rounds the box coordinates themselves.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
TOOLS = HERE.parent / 'Restart Qualification Tools'
sys.path.insert(0, str(TOOLS))
import assess_validation as assessment

BIN_WIDTHS_M = (.01, .02, .05)
PADDINGS_M = (0., .001, .002, .003, .005, .010)
CHUNK = 4096  # Memory bound only; no numerical or geometric meaning.


def require(condition, reason):
    if not condition: raise ValueError(reason)


def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def ref(path):
    path = Path(path).resolve(); before = path.stat()
    with path.open('rb') as stream: value = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), 'File changed while hashing')
    return {'path': str(path), 'sha256': value, 'bytes': after.st_size}


def volume(box): return math.prod(b - a for a, b in zip(box['min'], box['max']))


def bin_key(geometry, box, width):
    require(assessment.valid_box(box), 'Invalid interval box')
    return (geometry, *(math.floor((a + b) / 2 / width) for a, b in zip(box['min'], box['max'])))


class Cover:
    def __init__(self, width):
        require(width in BIN_WIDTHS_M, 'Only the three fixed bin widths are supported')
        self.width, self.buckets, self.input_count = width, {}, 0

    def add(self, geometry, box, source):
        key = bin_key(geometry, box, self.width); amount = volume(box)
        value = self.buckets.get(key)
        if value is None:
            value = {'box': {k: list(box[k]) for k in ('min', 'max')}, 'input_count': 0,
                     'sum_input_box_volume_m3': 0., 'largest_input_box_volume_m3': 0., 'first_source_ref': source}
            self.buckets[key] = value
        for axis in range(3):
            value['box']['min'][axis] = min(value['box']['min'][axis], box['min'][axis])
            value['box']['max'][axis] = max(value['box']['max'][axis], box['max'][axis])
        value['input_count'] += 1; self.input_count += 1
        value['sum_input_box_volume_m3'] += amount
        value['largest_input_box_volume_m3'] = max(value['largest_input_box_volume_m3'], amount)

    def merge(self, other):
        require(self.width == other.width, 'Bin widths differ')
        for key, incoming in other.buckets.items():
            if key not in self.buckets:
                self.buckets[key] = incoming
            else:
                existing = self.buckets[key]
                existing['box'] = {k: [fn(a, b) for a, b in zip(existing['box'][k], incoming['box'][k])]
                                   for k, fn in (('min', min), ('max', max))}
                existing['input_count'] += incoming['input_count']
                existing['sum_input_box_volume_m3'] += incoming['sum_input_box_volume_m3']
                existing['largest_input_box_volume_m3'] = max(existing['largest_input_box_volume_m3'], incoming['largest_input_box_volume_m3'])
        self.input_count += other.input_count

    def contains_assigned(self, geometry, box):
        value = self.buckets.get(bin_key(geometry, box, self.width))
        return value is not None and all(value['box']['min'][i] <= box['min'][i]
            and box['max'][i] <= value['box']['max'][i] for i in range(3))

    def records(self):
        return [{'geometry_key': key[0], 'center_bin': list(key[1:]), **value}
                for key, value in sorted(self.buckets.items())]


def volume_report(records, padding):
    padded = [{'min': [v-padding for v in row['box']['min']], 'max': [v+padding for v in row['box']['max']]} for row in records]
    volumes = [volume(box) for box in padded]
    upper = [max(0., v-row['largest_input_box_volume_m3']) for row, v in zip(records, volumes)]
    lower = [max(0., v-row['sum_input_box_volume_m3']) for row, v in zip(records, volumes)]
    return {'summed_cover_box_volume_m3': math.fsum(volumes),
        'summed_input_box_volume_m3': math.fsum(row['sum_input_box_volume_m3'] for row in records),
        'added_union_volume_m3': None,
        'added_union_volume_lower_bound_m3': 0., 'added_union_volume_upper_bound_m3': math.fsum(upper),
        'per_bin_added_volume_lower_bound_sum_m3': math.fsum(lower),
        'per_bin_added_volume_upper_bound_sum_m3': math.fsum(upper),
        'volume_scope': 'Float64 algebraic bounds, not certified interval arithmetic. Added exact union volume is not computed. Per-bin bounds compare hull to its assigned input-box union; sums may overlap, so only the summed upper bound bounds global added space. Input and cover volume sums are not union volumes.'}


def archived_overlap(source):
    expected = ast.parse("def overlaps(a,b):return valid_box(a) and valid_box(b) and all(min(a['max'][i],b['max'][i])-max(a['min'][i],b['min'][i])>1e-6 for i in range(3))").body[0]
    actual = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'overlaps']
    require(len(actual) == 1 and ast.dump(actual[0]) == ast.dump(expected), 'Archived Runtime overlap formula changed; vector comparison unsupported')
    return assessment.numeric_functions(source)['overlaps']


def compare(records, objects, overlaps):
    require(records and all(assessment.valid_box(row['box']) for row in records), 'Nonempty valid cover required')
    require(all(isinstance(o.get('id'), str) and assessment.valid_box(o.get('bounds')) for o in objects), 'Invalid other movable cut body')
    require(len({o['id'] for o in objects}) == len(objects), 'Duplicate other movable body ID')
    low = np.asarray([r['box']['min'] for r in records], dtype=float)
    high = np.asarray([r['box']['max'] for r in records], dtype=float)
    other_low = np.asarray([o['bounds']['min'] for o in objects], dtype=float).reshape(-1, 3)
    other_high = np.asarray([o['bounds']['max'] for o in objects], dtype=float).reshape(-1, 3)
    reports = []
    for padding in PADDINGS_M:
        strict = runtime = 0; blockers = set(); minimum = None; witness = first = None
        for start in range(0, len(records), CHUNK):
            if not objects: break
            depths = np.minimum(high[start:start+CHUNK, None, :] + padding, other_high[None, :, :]) - np.maximum(low[start:start+CHUNK, None, :] - padding, other_low[None, :, :])
            strict += int(np.all(depths > 0., axis=2).sum())
            hit = np.all(depths > 1e-6, axis=2)
            runtime += int(hit.sum())
            blockers.update(objects[i]['id'] for i in np.flatnonzero(hit.any(axis=0)))
            if first is None and hit.any():
                i, j = np.argwhere(hit)[0]; index = start + int(i); j = int(j)
                expanded = {'min': (low[index]-padding).tolist(), 'max': (high[index]+padding).tolist()}
                require(overlaps(expanded, objects[j]['bounds']), 'Vector/scalar archived overlap disagreement')
                first = {'cover_index': index, 'geometry_key': records[index]['geometry_key'], 'center_bin': records[index]['center_bin'],
                         'object_id': objects[j]['id'], 'axis_overlap_m': depths[i, j].tolist()}
            separations = -depths.min(axis=2)
            i, j = np.unravel_index(separations.argmin(), separations.shape)
            value = float(separations[i, j]); index = start + int(i); j = int(j)
            if minimum is None or value < minimum:
                minimum = value
                witness = {'cover_index': index, 'geometry_key': records[index]['geometry_key'], 'center_bin': records[index]['center_bin'],
                    'object_id': objects[j]['id'], 'original_cover_box': records[index]['box'],
                    'expanded_cover_box': {'min': (low[index]-padding).tolist(), 'max': (high[index]+padding).tolist()},
                    'other_body_bounds': objects[j]['bounds'], 'axis_overlap_m': depths[i, j].tolist()}
        reports.append({'uniform_padding_m': padding, 'cover_box_count': len(records), 'other_body_count': len(objects),
            'pair_comparisons': len(records)*len(objects), 'strict_interior_intersection_pairs': strict,
            'runtime_overlap_pairs': runtime, 'runtime_blocker_ids': sorted(blockers), 'first_runtime_overlap': first,
            'minimum_signed_axis_separation_m': minimum, 'minimum_separation_witness': witness,
            'gap_scope': 'Minimum over pairs of maximum signed axis gap, negative for interior overlap; not mesh distance.',
            'volume': volume_report(records, padding), 'padding_selected': False})
    return reports


def collect_intervals(source, row, output):
    identity = row['trial_id']; start = row['states']['cut']['sim_time_s']; end = row['states']['after_placement']['sim_time_s']
    require(math.isfinite(start) and math.isfinite(end) and start <= end, 'Invalid cut/placement interval')
    inventory, inventory_ref = source.evidence.json(identity + '/geometry-inventory.json')
    geoms = inventory['geoms']; ids = [g['geom_id'] for g in geoms]
    require(len(ids) == len(set(ids)) and {'robot', 'payload'} <= {g['role'] for g in geoms}, 'Incomplete geometry inventory')
    keys = [digest(g) for g in geoms]
    require(len(keys) == len(set(keys)), 'Ambiguous geometry identity')
    name = identity + '/whole-geometry.jsonl'; entry = source.evidence.entries[name]
    trace_ref = {'path': name, 'sha256': entry['sha256'], 'bytes': entry['bytes']}
    covers = {width: Cover(width) for width in BIN_WIDTHS_M}
    audit = output / (identity + '-interval-inputs.jsonl')
    stats = {'interval_count': 0, 'input_box_count': 0, 'tick_count_and_gap_checks_pass': True,
             'first_sim_time_s': None, 'last_sim_time_s': None, 'physics_timestep_s': None,
             'maximum_dense_sim_gap_s': 0., 'maximum_dense_wall_gap_s': 0.}
    with audit.open('x', encoding='utf-8', newline='\n') as stream:
        def visit(line, raw):
            value = json.loads(raw); dense = value['interval_dense_geometry']
            first, last = dense['first_sim_wall_s'], dense['last_sim_wall_s']
            if last[0] < start or first[0] > end: return
            require(dense['geom_ids'] == ids, 'Dense/inventory geometry IDs differ')
            dt = value['physics_timestep_s']; require(math.isfinite(dt) and dt > 0, 'Invalid timestep')
            require(stats['physics_timestep_s'] in (None, dt), 'Timestep changed')
            stats['physics_timestep_s'] = dt; previous = stats['last_sim_time_s']
            stats['tick_count_and_gap_checks_pass'] &= (dense['maximum_sim_gap_s'] <= dt+1e-9
                and abs((dense['distinct_sim_time_count']-1)*dt-(last[0]-first[0])) <= 1e-9
                and (previous is None or first[0] <= previous+1e-9))
            stats['interval_count'] += 1
            stats['first_sim_time_s'] = first[0] if stats['first_sim_time_s'] is None else stats['first_sim_time_s']
            stats['last_sim_time_s'] = last[0]
            for clock in ('sim', 'wall'):
                stats['maximum_dense_'+clock+'_gap_s'] = max(stats['maximum_dense_'+clock+'_gap_s'], dense['maximum_'+clock+'_gap_s'])
            bounds = dense['sampled_outer_box_union_m']
            require(len(bounds['min']) == len(bounds['max']) == len(ids), 'Dense box count differs')
            locator = {**trace_ref, 'line': line, 'line_sha256': hashlib.sha256(raw).hexdigest(),
                       'trial_id': identity, 'interval_sim_wall_s': [first, last]}
            for i, key in enumerate(keys):
                box = {k: bounds[k][i] for k in ('min', 'max')}
                for cover in covers.values(): cover.add(key, box, {**locator, 'geom_id': ids[i]})
                stats['input_box_count'] += 1
            stream.write(json.dumps({'source_ref': locator, 'geometry_keys': keys, 'boxes': bounds}, sort_keys=True, allow_nan=False)+'\n')
        source.evidence.stream(name, visit)
    require(stats['input_box_count'] > 0, 'No interval boxes intersect cut through placement')
    stats['cut_to_placement_covered'] = stats['first_sim_time_s'] <= start and stats['last_sim_time_s'] >= end
    return covers, {'statistics': stats, 'inventory_ref': inventory_ref, 'geometry_inventory': dict(zip(keys, geoms)),
                    'trace_ref': trace_ref, 'input_audit_ref': ref(audit)}


def verify_containment(covers, audit_refs):
    checked = failed = 0; first_failure = None
    for expected in audit_refs:
        path = Path(expected['path']); require(ref(path) == expected, 'Input audit changed before containment')
        with path.open('r', encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                for i, key in enumerate(row['geometry_keys']):
                    box = {k: row['boxes'][k][i] for k in ('min', 'max')}
                    for width, cover in covers.items():
                        checked += 1
                        if not cover.contains_assigned(key, box):
                            failed += 1; first_failure = first_failure or {'bin_width_m': width, 'box': box, 'source_ref': row['source_ref'], 'geometry_key': key}
        require(ref(path) == expected, 'Input audit changed during containment')
    require(all(cover.input_count*len(covers) == checked for cover in covers.values()), 'Containment input counts differ')
    return {'state': 'pass' if failed == 0 and checked else 'fail', 'checked_assignments': checked,
            'failed_assignments': failed, 'first_failure': first_failure, 'comparison_epsilon_m': 0.,
            'scope': 'Every original input box is contained in its assigned final same-geometry bin hull; no coordinate rounding'}


def derive(extraction, screen_receipt, extraction_receipt, destination, output):
    source = assessment.CompletedExtraction(extraction, screen_receipt, extraction_receipt)
    require(source.manifest['execution_phase'] == 'construction', 'Construction only; no validation inputs')
    output = Path(output).resolve(); require(not output.exists(), 'Fresh output required')
    for base in (source.base, source.evidence.root, PROJECT/'Runtime 004', PROJECT/'Architecture Map', PROJECT/'Batch 01', HERE):
        base = base.resolve(); require(output != base and base not in output.parents and output not in base.parents, 'Output overlaps input/protected source')
    require(not any(p.casefold() == 'candidate_state' for p in output.parts), 'Candidate state output forbidden')
    code, code_ref = source.source('Runtime 004/restart_state.py'); overlaps = archived_overlap(code)
    output.mkdir(parents=True, exist_ok=False)
    rows, groups = [], {}
    for identity, declaration in source.declared.items():
        require(isinstance(identity, str) and re.fullmatch('[A-Za-z0-9_-]+', identity), 'Unsafe trial output identity')
        report = {'trial_id': identity, 'declaration': declaration, 'execution_status': source.entries[identity]['execution_status'],
                  'selected_construction': identity in source.selected and declaration['destination'] == destination}
        rows.append(report)
        if not report['selected_construction']: continue
        try:
            row = source.trial(identity); child = row.get('child_result') or {}; details = child.get('details') or {}
            payload = details.get('picked_visible_part_id')
            require(isinstance(payload, str) and re.fullmatch('[A-Za-z0-9_-]+', payload), 'Actual selected payload location unavailable or unsafe')
            report.update(payload_location_group=payload, trial_ref=row['consumed_ref'], child_status=child.get('status'),
                child_error=child.get('error'), physical_predicates_passed=details.get('physical_predicates_passed'), timing=child.get('timing'),
                parent_attempt=row.get('parent_attempt'), all_objects_generator_domain_members=(row.get('compiled_properties') or {}).get('all_objects_generator_domain_members'))
            group = groups.setdefault(payload, {'covers': {w: Cover(w) for w in BIN_WIDTHS_M}, 'audits': [], 'scenes': [], 'geometry': {}, 'included': []})
            cut = row['states']['cut']; snapshot = cut['payload']
            identities = [o['id'] for o in snapshot['geometry']['objects']]
            require(len(identities) == len(set(identities)) and identities.count(payload) == 1, 'Cut payload/body identity inventory differs')
            objects = [o for o in snapshot['geometry']['objects'] if o['id'] != payload]
            require(all(assessment.valid_box(o['bounds']) for o in objects), 'Invalid actual other movable cut body')
            group['scenes'].append({'trial_id': identity, 'objects': objects, 'source_ref': cut['source_ref'], 'snapshot_sha256': snapshot['snapshot_sha256']})
            report['cut_scene_available'] = True
            trial_covers, metadata = collect_intervals(source, row, output)
            for width, cover in trial_covers.items(): group['covers'][width].merge(cover)
            group['audits'].append(metadata['input_audit_ref']); group['included'].append(identity)
            group['geometry'].update(metadata['geometry_inventory'])
            report.update(diagnostic_state='measured_discrete_only', **metadata)
        except (ValueError, KeyError, TypeError, OSError, IndexError) as error:
            report.update(diagnostic_state='unknown', reason=type(error).__name__+': '+str(error))
            partial = output/(identity+'-interval-inputs.jsonl')
            if partial.is_file():
                report['partial_input_audit'] = {**ref(partial), 'excluded_from_compact_covers': True}
    results = []
    unassigned = [r['trial_id'] for r in rows if r['selected_construction'] and not r.get('payload_location_group')]
    for payload, group in groups.items():
        report = {'payload_location_group': payload, 'included_trial_ids': group['included'],
            'all_declared_group_routes_included': not unassigned and all(r.get('diagnostic_state') == 'measured_discrete_only'
                and r['statistics']['cut_to_placement_covered'] and r['statistics']['tick_count_and_gap_checks_pass']
                for r in rows if r.get('payload_location_group') == payload),
            'unassigned_selected_trial_ids': unassigned,
            'all_available_group_cut_scenes_included': not unassigned and all(r.get('cut_scene_available') is True
                for r in rows if r.get('payload_location_group') == payload),
            'cut_scene_trial_ids': [s['trial_id'] for s in group['scenes']], 'candidates': []}
        results.append(report)
        if not group['audits']:
            report.update(state='unknown', reason='No complete interval input; failed group retained'); continue
        report['containment'] = verify_containment(group['covers'], group['audits'])
        require(report['containment']['state'] == 'pass', 'Final compact hull lost an input box')
        for width, cover in group['covers'].items():
            records = cover.records(); path = output / (payload+'-bin-'+str(int(width*1000))+'mm.json')
            assessment.reader.write(path, {'payload_location_group': payload, 'bin_width_m': width,
                'geometry_inventory': group['geometry'], 'input_box_count': cover.input_count, 'covers': records,
                'containment': report['containment'], 'coordinate_quantization_applied': False, 'continuous_sweep_claimed': False})
            report['candidates'].append({'bin_width_m': width, 'input_box_count': cover.input_count,
                'cover_box_count': len(records), 'cover_ref': ref(path), 'containment': report['containment'],
                'actual_cut_scene_comparisons': [{'cut_trial_id': scene['trial_id'], 'cut_source_ref': scene['source_ref'],
                    'cut_snapshot_sha256': scene['snapshot_sha256'], 'padding_comparisons': compare(records, scene['objects'], overlaps)} for scene in group['scenes']],
                'bin_width_selected': False})
    source.evidence.stable()
    return {'schema_version': 'compact-construction-corridor-diagnostic-1', 'completed_at': datetime.now(timezone.utc).isoformat(),
        'construction_extraction_ref': source.ref, 'screen_receipt_ref': source.receipt_ref,
        'extraction_receipt_ref': source.extraction_receipt_ref, 'overlap_formula_source_ref': code_ref,
        'consumed_files': list(source.evidence.consumed.values()), 'destination': destination, 'trials': rows,
        'payload_location_groups': results, 'bin_widths_m': BIN_WIDTHS_M, 'paddings_m': PADDINGS_M,
        'selected_trial_count': sum(r['selected_construction'] for r in rows),
        'unassigned_selected_trial_ids': unassigned,
        'all_selected_trials_processed': any(r['selected_construction'] for r in rows)
            and all(r.get('diagnostic_state') == 'measured_discrete_only' for r in rows if r['selected_construction']),
        'qualification_granted': False, 'readiness_granted': False, 'parameter_selected': False,
        'continuous_clearance_bound_m': None,
        'limitations': ['Every original interval box is covered; bin hulls can add unmeasured false space.',
            'Native discrete cached-transform bounds only; original one-step alignment and sampling limitations remain.',
            'Other movable bodies use each same-location construction cut scene; no world/self-mesh collision proof.',
            'A1, B10 and B2 remain separate; no unseen location or Cartesian-product state transfer is inferred.',
            'Physical failures, missing traces and host timing failures remain in the trial records; no outcome is upgraded.',
            'Volume reports are bounds and overlapping box sums, not an exact union-volume computation.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('construction-extraction', 'screen-receipt', 'extraction-receipt', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--destination', choices=('parking1', 'parking2'), required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(PROJECT/'Runtime 004'))
    import release_runner
    queue = release_runner.queued_job(expected_script=__file__)
    dependencies = [Path(__file__), Path(assessment.__file__), Path(assessment.reader.__file__),
        TOOLS/'compatibility.py', TOOLS/'bundle_construction.py', Path(release_runner.__file__)]
    before = {str(p.resolve()): ref(p) for p in dependencies}
    report = derive(args.construction_extraction, args.screen_receipt, args.extraction_receipt, args.destination, args.output)
    after = {str(p.resolve()): ref(p) for p in dependencies}
    report.update(queue=queue, inputs_before=before, inputs_after=after, source_inputs_unchanged=before == after,
                  status='complete' if before == after else 'failed', error=None if before == after else 'Diagnostic helper dependency changed')
    assessment.reader.write(Path(args.output)/'compact-corridors.json', report)
    require(before == after, 'Diagnostic helper dependency changed')
    print(json.dumps({'output': str(Path(args.output).resolve()), 'qualification_granted': False}))


if __name__ == '__main__': main()
