"""Extract a completed development screen; sampled evidence, never qualification."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys

SCHEMA = 'recovery-development-screen-1'
STATES = {
    'protected_carry_state_before_cut': 'cut',
    'protected_state_immediately_after_cancel': 'after_cancel',
    'protected_held_state_after_absence': 'after_hold',
    'protected_state_before_recovery_dispatch': 'before_recovery',
    'protected_state_after_recovery_admission': 'after_recovery_admission',
    'protected_state_after_settled_placement': 'after_placement',
}
IDENTITY = ('id', 'child_pid', 'worker_pid', 'resolved_executable', 'argv', 'cwd', 'started_at')
LIMITATION = ('Sampled outer boxes only, with no expansion or invented margin. No continuous '
              'clearance/sweep bound, global success box, qualified cell, duration guarantee or readiness pass.')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Timestamp must include a timezone')
    return parsed


def safe_relative(value):
    require(isinstance(value, str) and '\\' not in value and ':' not in value, 'Unsafe artifact path')
    path = PurePosixPath(value)
    require(value and not path.is_absolute() and '..' not in path.parts and str(path) == value,
            'Unsafe artifact path')
    return path


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


class Evidence:
    """Verify consumed bytes, bind references, and detect subsequent source changes."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.used = {}
        index, self.index_ref = self.external(self.root / 'evidence-index.json')
        require(index.get('schema_version') == SCHEMA, 'Unknown evidence index schema')
        self.entries = {}
        for entry in index['files']:
            name = str(safe_relative(entry['path']))
            require(name not in self.entries, 'Duplicate indexed artifact: ' + name)
            self.path(name)
            self.entries[name] = entry

    def path(self, name):
        path = (self.root / str(safe_relative(name))).resolve()
        require(self.root in path.parents, 'Artifact escapes screen directory')
        return path

    @staticmethod
    def signature(path):
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def remember(self, path, before, digest, size, name):
        require(self.signature(path) == before, 'Source changed while reading: ' + str(path))
        self.used[path] = before
        return {'path': name, 'sha256': digest, 'bytes': size}

    def external(self, path):
        path = Path(path).resolve()
        before = self.signature(path)
        raw = path.read_bytes()
        ref = self.remember(path, before, hashlib.sha256(raw).hexdigest(), len(raw), str(path))
        return json.loads(raw), ref

    def stream(self, name, visit=None):
        require(name in self.entries, 'Artifact absent from completed index: ' + name)
        path = self.path(name)
        before = self.signature(path)
        digest, size = hashlib.sha256(), 0
        with path.open('rb') as stream:
            if visit is None:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block); size += len(block)
            else:
                for number, raw in enumerate(stream, 1):
                    digest.update(raw); size += len(raw)
                    visit(number, raw)
        ref = self.remember(path, before, digest.hexdigest(), size, name)
        entry = self.entries[name]
        require(ref['sha256'] == entry['sha256'] and size == entry['bytes'], 'Indexed bytes differ: ' + name)
        return ref

    def json(self, name):
        # Small JSON documents only; large traces use stream().
        require(name in self.entries, 'Artifact absent from completed index: ' + name)
        value, ref = self.external(self.path(name))
        ref['path'] = name
        require(ref['sha256'] == self.entries[name]['sha256'] and ref['bytes'] == self.entries[name]['bytes'],
                'Indexed bytes differ: ' + name)
        return value, ref

    def stable(self):
        for path, before in self.used.items():
            require(self.signature(path) == before, 'Source changed during extraction: ' + str(path))


def event_states(evidence, name):
    states = {label: {'status': 'not_recorded'} for label in STATES.values()}
    states['recovery_admission'] = {'status': 'not_recorded'}
    issues, selected = [], {}

    def visit(number, raw):
        locator = {'line': number, 'line_sha256': hashlib.sha256(raw).hexdigest()}
        try:
            row = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            issues.append({**locator, 'issue': 'Unparsed record: ' + str(exc)}); return
        admission = (row.get('event_type') == 'action_admission'
            and row.get('payload', {}).get('action', {}).get('operation') == 'recover_held')
        if row.get('event_type') not in STATES and not admission:
            return
        label = 'recovery_admission' if admission else STATES[row['event_type']]
        require(label not in selected, 'Duplicate measured state event: ' + label)
        require(hashlib.sha256(canonical(row['payload'])).hexdigest() == row['payload_sha256'],
                'Measured state payload hash mismatch')
        selected[label] = {**locator, 'event_id': row['event_id'], 'event_type': row['event_type'],
            'payload_sha256': row['payload_sha256'], 'sim_time_s': row.get('sim_time_s'),
            'wall_elapsed_s': row.get('wall_elapsed_s'), 'payload': row['payload']}

    ref = evidence.stream(name, visit)
    for label, row in selected.items():
        states[label] = {'status': 'recorded', **row, 'source_ref': {**ref, **{k: v for k, v in row.items()
            if k not in ('payload', 'sim_time_s', 'wall_elapsed_s')}}}
    deltas = {}
    if 'cut' in selected:
        for label in ('after_hold', 'before_recovery', 'recovery_admission'):
            if label in selected:
                deltas[label] = {field: selected[label][field] - selected['cut'][field]
                    for field in ('sim_time_s', 'wall_elapsed_s') if selected[label].get(field) is not None
                    and selected['cut'].get(field) is not None}
    return {'states': states, 'unparsed_records': issues, 'source_ref': ref,
            'event_deltas_from_rich_cut': deltas,
            'delta_scope': 'Measured event-to-event clocks; full cancellation-to-admission hold coverage is separately recorded in child_result.details.cut_to_recovery_admission'}


def finite_vector(value):
    require(isinstance(value, list) and len(value) == 3 and all(type(x) in (int, float) and math.isfinite(x)
            for x in value), 'Expected finite three-vector')
    return value


class Samples:
    def __init__(self):
        self.result = {'sample_count': 0, 'first': None, 'last': None, 'maximum_sim_gap_s': None,
                       'maximum_wall_gap_s': None, 'geoms': {}}
        self.previous = None

    def add(self, row, locator):
        now = {'sim_time_s': row['sim_time_s'], 'wall_elapsed_s': row['wall_elapsed_s'], **locator}
        stats = self.result
        stats['sample_count'] += 1
        stats['first'] = stats['first'] or now
        stats['last'] = now
        if self.previous:
            for clock in ('sim', 'wall'):
                field = 'sim_time_s' if clock == 'sim' else 'wall_elapsed_s'
                gap = now[field] - self.previous[field]
                key = 'maximum_' + clock + '_gap_s'
                stats[key] = max(stats[key] or 0., gap)
        for geom in row['robot_and_payload_geoms']:
            key = str(geom['geom_id'])
            bounds, center = geom['outer_bounds'], geom['position_m']
            if key not in stats['geoms']:
                stats['geoms'][key] = {'sample_count': 0, 'sampled_outer_box_union_m': {'min': bounds['min'][:],
                    'max': bounds['max'][:]}, 'maximum_adjacent_center_displacement_m': None,
                    'maximum_adjacent_aabb_endpoint_displacement_m': None,
                    'maximum_adjacent_center_displacement_refs': None, 'zero_sim_gap_with_motion_count': 0}
            item = stats['geoms'][key]
            item['sample_count'] += 1
            for edge, fn in (('min', min), ('max', max)):
                item['sampled_outer_box_union_m'][edge] = list(map(fn, item['sampled_outer_box_union_m'][edge], bounds[edge]))
            if self.previous:
                old = self.previous['geoms'][key]
                displacement = math.dist(center, old['position_m'])
                if item['maximum_adjacent_center_displacement_m'] is None or displacement > item['maximum_adjacent_center_displacement_m']:
                    item['maximum_adjacent_center_displacement_m'] = displacement
                    item['maximum_adjacent_center_displacement_refs'] = [self.previous['locator'], locator]
                delta = max(math.dist(bounds[edge], old['outer_bounds'][edge]) for edge in ('min', 'max'))
                item['maximum_adjacent_aabb_endpoint_displacement_m'] = max(item['maximum_adjacent_aabb_endpoint_displacement_m'] or 0., delta)
                if now['sim_time_s'] == self.previous['sim_time_s'] and (displacement > 0 or delta > 0):
                    item['zero_sim_gap_with_motion_count'] += 1
        self.previous = {**now, 'locator': locator,
                         'geoms': {str(g['geom_id']): g for g in row['robot_and_payload_geoms']}}


def geometry_summary(evidence, inventory_name, trace_name):
    inventory, inventory_ref = evidence.json(inventory_name)
    ids = [g['geom_id'] for g in inventory['geoms']]
    require(len(ids) == len(set(ids)) and ids, 'Empty/duplicate geometry inventory')
    overall, phases, issues = Samples(), {}, []
    previous_time = None

    def visit(number, raw):
        nonlocal previous_time
        locator = {'line': number, 'line_sha256': hashlib.sha256(raw).hexdigest()}
        try:
            row = json.loads(raw)
            times = [row['sim_time_s'], row['wall_elapsed_s']]
            require(all(type(x) in (int, float) and math.isfinite(x) for x in times), 'Nonfinite clock')
            require(previous_time is None or all(x >= y for x, y in zip(times, previous_time)), 'Clock moved backward')
            geoms = row['robot_and_payload_geoms']
            require(len(geoms) == len(ids) and {g['geom_id'] for g in geoms} == set(ids), 'Incomplete/duplicate geometry row')
            for geom in geoms:
                finite_vector(geom['position_m'])
                lo, hi = (finite_vector(geom['outer_bounds'][edge]) for edge in ('min', 'max'))
                require(all(a <= b for a, b in zip(lo, hi)), 'Reversed outer bounds')
            require(row['phase'] in ('pickup', 'absence', 'recovery', 'settling'), 'Unknown phase')
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
            issues.append({**locator, 'issue': 'Unsummarized record: ' + str(exc)}); return
        previous_time = times
        overall.add(row, locator)
        phases.setdefault(row['phase'], Samples()).add(row, locator)

    trace_ref = evidence.stream(trace_name, visit)
    return {'status': 'sampled_only', 'limitation': LIMITATION, 'inventory': inventory,
            'inventory_ref': inventory_ref, 'trace_ref': trace_ref, 'overall': overall.result,
            'phases': {phase: samples.result for phase, samples in phases.items()}, 'unsummarized_records': issues,
            'gap_scope': 'Adjacent accepted complete records; all listed geoms share these measured gaps. Skipped records are listed.',
            'adjacent_aabb_endpoint_definition': 'max(Euclidean delta of min corner, Euclidean delta of max corner); not a surface-motion bound',
            'continuous_clearance_bound_m': None, 'margin_added_m': None, 'qualified_cell_created': False}


def extract(screen, receipt_path, output, extraction_queue=None):
    screen, output = Path(screen).resolve(), Path(output).resolve()
    require(not output.exists(), 'Extraction output must be fresh')
    require(screen != output and screen not in output.parents and output not in screen.parents,
            'Output must be separate from input evidence')
    # Check the supplied terminal receipt before reading any screen artifacts.
    receipt_raw = Path(receipt_path).read_bytes()
    receipt = json.loads(receipt_raw)
    require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int
            and receipt['exit_status'] == 0, 'Successful official screen queue receipt required')
    end = stamp(receipt['ended_at'])
    evidence = Evidence(screen)
    receipt, receipt_ref = evidence.external(receipt_path)
    require(hashlib.sha256(receipt_raw).hexdigest() == receipt_ref['sha256'], 'Receipt changed')
    manifest, manifest_ref = evidence.json('manifest.json')
    summary, summary_ref = evidence.json('summary.json')
    require(manifest.get('schema_version') == summary.get('schema_version') == SCHEMA, 'Unknown screen schema')
    require(all(k in receipt and receipt[k] == manifest['queue']['queue_job'].get(k) for k in IDENTITY),
            'Receipt does not identify the recorded screen job')
    require(receipt['id'] == manifest['queue']['job_id'] == summary['queue_job_id'], 'Queue identity mismatch')
    require(stamp(receipt['started_at']) <= stamp(manifest['created_at']) <= stamp(summary['finished_at']) <= end,
            'Screen completion is not covered by the terminal receipt')
    plan, modes = manifest['prospective_plan'], manifest['modes']
    declared = [t['id'] for t in plan['trials']]
    require(len(declared) == len(set(declared)) and all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,179}', t) for t in declared),
            'Invalid/duplicate declared trial identifiers')
    selection = manifest['destination_selection']
    phase = manifest.get('execution_phase')
    require(phase in (None, 'construction', 'validation'), 'Unknown execution phase')
    fixture = {'construction': 'construction', 'validation': 'independent_generator'}.get(phase)
    require(selection in ('all', 'parking1', 'parking2') and modes == [t['id'] for t in plan['trials']
            if (selection == 'all' or t['destination'] == selection) and (fixture is None or t['fixture'] == fixture)],
            'Declared destination/phase selection mismatch')
    deferred = manifest.get('phase_deferred_trial_ids', [])
    if phase is not None:
        require(deferred == [t['id'] for t in plan['trials'] if t['id'] not in modes
            and (selection == 'all' or t['destination'] == selection)]
            and deferred == summary.get('phase_deferred_trial_ids'), 'Deferred phase coverage mismatch')
    attempted = [a['trial_id'] for a in summary['attempts']]
    require(attempted == modes[:len(attempted)] and summary['not_started'] == modes[len(attempted):],
            'Terminal summary does not preserve complete selected trial coverage')
    bundle_ref = evidence.stream('source-bundle.zip')
    require(bundle_ref['sha256'] == manifest['source_bundle_sha256'], 'Source archive identity mismatch')
    rule, rule_ref = None, None
    if phase == 'validation':
        rule, rule_ref = evidence.json('provisional-rule.json')
        require(rule == manifest['provisional_rule'] and rule_ref['sha256'] == manifest['provisional_rule_ref']['sha256']
                and stamp(rule['created_at']) < stamp(manifest['created_at']), 'Provisional rule identity/order mismatch')
    attempts = {a['trial_id']: a for a in summary['attempts']}
    rows = []
    output.mkdir(parents=True, exist_ok=False)
    for index, trial in enumerate(plan['trials']):
        identity = trial['id']
        attempt = attempts.get(identity)
        row = {'trial_id': identity, 'declaration': trial,
               'declaration_ref': {**manifest_ref, 'json_pointer': '/prospective_plan/trials/' + str(index)},
               'execution_status': ('deferred_to_other_phase' if identity in deferred else
                                    'not_selected_for_this_screen' if identity not in modes else
                                    'not_started' if attempt is None else attempt['status']),
               'parent_attempt': attempt, 'artifact_refs': {}, 'measured_states': {'status': 'not_recorded'},
               'geometry': {'status': 'not_recorded'}, 'child_result': None,
               'construction': None, 'compiled_properties': None}
        if attempt is not None:
            # Partial evidence is retained even when the parent could not accept a child result.
            for name in ('probe-manifest.json', 'construction.json', 'compiled-properties.json', 'result.json',
                         'protected-class-spec.json', 'dense-geometry-summary.json'):
                relative = identity + '/' + name
                if relative not in evidence.entries:
                    continue
                value, ref = evidence.json(relative)
                row['artifact_refs'][name] = ref
                if name == 'probe-manifest.json':
                    require(value['trial'] == trial and value['parent_manifest_sha256'] == manifest_ref['sha256'], 'Probe identity mismatch')
                    row['probe_manifest'] = value
                elif name == 'result.json':
                    require(value['trial_id'] == identity and value['trial'] == trial, 'Child result identity mismatch')
                    if attempt.get('result_path'):
                        require(attempt['result_path'] == relative and attempt['result_sha256'] == ref['sha256']
                                and attempt['status'] == value['status'], 'Parent/child result mismatch')
                    row['child_result'] = value
                elif name in ('construction.json', 'compiled-properties.json'):
                    row['construction' if name == 'construction.json' else 'compiled_properties'] = value
                else:
                    row[name[:-5].replace('-', '_')] = value
            if attempt.get('result_path'):
                require(row['child_result'] is not None, 'Accepted child result missing')
            for name in ('generator-world.xml', 'fixture-world.xml', 'world-0.xml'):
                relative = identity + '/' + name
                if relative in evidence.entries:
                    row['artifact_refs'][name] = evidence.stream(relative)
            events = identity + '/events.jsonl'
            if events in evidence.entries:
                state_data = event_states(evidence, events)
                states_file = identity + '/measured-states.json'
                write(output / states_file, state_data)
                row['measured_states'] = {'output_path': states_file, 'source_ref': state_data['source_ref'],
                    'capture_status': {k: v['status'] for k, v in state_data['states'].items()},
                    'unparsed_records': state_data['unparsed_records']}
            inventory, trace = identity + '/geometry-inventory.json', identity + '/whole-geometry.jsonl'
            if inventory in evidence.entries and trace in evidence.entries:
                geometry_file = identity + '/sampled-geometry.json'
                measured = geometry_summary(evidence, inventory, trace)
                write(output / geometry_file, measured)
                row['geometry'] = {'status': 'sampled_only', 'output_path': geometry_file,
                    'trace_ref': measured['trace_ref'], 'inventory_ref': measured['inventory_ref'],
                    'sample_count': measured['overall']['sample_count'], 'unsummarized_records': measured['unsummarized_records']}
            elif inventory in evidence.entries or trace in evidence.entries:
                row['geometry'] = {'status': 'incomplete_artifacts', 'present_refs': [evidence.stream(p)
                    for p in (inventory, trace) if p in evidence.entries]}
        write(output / identity / 'trial.json', row)
        rows.append({'trial_id': identity, 'execution_status': row['execution_status'], 'path': identity + '/trial.json'})
    evidence.stable()
    result = {'schema_version': 'recovery-screen-extraction-1', 'completed_at': datetime.now(timezone.utc).isoformat(),
        'source_screen': str(screen), 'source_receipt': receipt, 'receipt_ref': receipt_ref, 'manifest_ref': manifest_ref,
        'summary_ref': summary_ref, 'evidence_index_ref': evidence.index_ref, 'source_bundle_ref': bundle_ref,
        'provisional_rule': rule, 'provisional_rule_ref': rule_ref,
        'source_summary': summary, 'trials': rows, 'extraction_queue': extraction_queue,
        'extractor_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'verification_scope': 'Indexed bytes consumed by this extractor and source archive; unconsumed cameras/logs remain indexed but are not rehashed.',
        'validation_scope': 'independent_generator denotes an independent declared world draw. Rule-validation independence additionally requires a rule fixed before that phase; world seeds alone do not establish it.',
        'limitation': LIMITATION, 'qualification_granted': False, 'scored_ready_claimed': False,
        'continuous_clearance_bound_m': None, 'global_success_box': None}
    write(output / 'extraction.json', result)  # Completion marker; absent after any extraction failure.
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screen', required=True)
    parser.add_argument('--queue-receipt', required=True, help='Independent official succeeded/0 receipt for the screen job')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Runtime'))
    from release_runner import queued_job
    job = queued_job(expected_script=__file__)
    result = extract(args.screen, args.queue_receipt, args.output, extraction_queue=job)
    print(json.dumps({'output': str(Path(args.output).resolve()), 'declared_trials': len(result['trials']),
                      'qualification_granted': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
