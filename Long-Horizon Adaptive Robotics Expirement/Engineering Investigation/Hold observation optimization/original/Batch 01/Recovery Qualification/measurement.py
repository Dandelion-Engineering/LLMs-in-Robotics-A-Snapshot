"""Development-only phase selection and discrete measurement accumulators."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from fixture import retained_hold_check

EXECUTION_REVISION = 'recovery-screen-execution-2'


def provisional_identity(rule, destination):
    """Minimal launch identity/completeness checks, not numerical qualification."""
    required = ('payload_template_to_cell', 'cells', 'empirical_transfer_rule', 'untested_combinations', 'absence')
    if (rule.get('schema_version') != 'provisional-restart-class-rule-1'
            or rule.get('status') != 'provisional_development_rule' or rule.get('destination') != destination
            or rule.get('selection_rule') != 'unique_bilateral_payload_template'
            or rule.get('geometry_scope') != 'discrete_native_evaluated_states_empirical_transfer'
            or rule.get('validation_outcomes_used_for_fitting') is not False
            or not all(rule.get(k) for k in required)):
        raise ValueError('Missing or mismatched predeclared development rule')
    created = datetime.fromisoformat(rule['created_at'].replace('Z', '+00:00'))
    if created.tzinfo is None or created >= datetime.now(timezone.utc):
        raise ValueError('Provisional rule must predate validation')
    for name in ('construction_extraction', 'class_spec'):
        ref = rule.get(name, {})
        if (not isinstance(ref.get('path'), str) or not ref['path']
                or not re.fullmatch('[0-9a-f]{64}', str(ref.get('sha256')))):
            raise ValueError('Provisional source identity missing: ' + name)
    if not re.fullmatch('[0-9a-f]{64}', str(rule['class_spec'].get('canonical_sha256'))):
        raise ValueError('Provisional canonical class identity missing')
    return rule


def selected_trials(plan, destination, phase):
    if destination not in ('all', 'parking1', 'parking2') or phase not in ('construction', 'validation'):
        raise ValueError('Explicit destination and construction/validation phase required')
    fixture = 'construction' if phase == 'construction' else 'independent_generator'
    return [t for t in plan['trials'] if (destination == 'all' or t['destination'] == destination)
            and t['fixture'] == fixture]


class HoldWindow:
    def __init__(self, part_id, sim, wall):
        self.part_id = part_id
        self.data = {'start_sim_time_s': sim, 'start_wall_elapsed_s': wall,
            'last_sim_time_s': sim, 'last_wall_elapsed_s': wall,
            'observed_sim_s': 0., 'observed_wall_s': 0., 'physics_tick_checks': 0,
            'ticks_with_hold_predicate_false': 0, 'endpoint_checks': 0, 'failed_endpoint_checks': 0,
            'maximum_tick_sim_gap_s': 0., 'maximum_tick_wall_gap_s': 0.,
            'minimum_payload_center_z_m': None, 'minimum_payload_bottom_z_m': None,
            'accepted_recovery_request_id': None, 'accepted_admission_event_id': None,
            'all_recorded_hold_checks_pass': True,
            'scope': 'Unchanged contact and center-z>0.075 predicate at every physics tick and explicit endpoints; not between integration states'}

    def record(self, snapshot, sim, wall, *, tick):
        data = self.data
        if sim < data['last_sim_time_s'] or wall < data['last_wall_elapsed_s']:
            raise ValueError('Hold observation clock reversed')
        if tick:
            data['physics_tick_checks'] += 1
            data['maximum_tick_sim_gap_s'] = max(data['maximum_tick_sim_gap_s'], sim - data['last_sim_time_s'])
            data['maximum_tick_wall_gap_s'] = max(data['maximum_tick_wall_gap_s'], wall - data['last_wall_elapsed_s'])
        else:
            data['endpoint_checks'] += 1
        passed = retained_hold_check(snapshot, self.part_id)
        if not passed:
            data['ticks_with_hold_predicate_false' if tick else 'failed_endpoint_checks'] += 1
            data['all_recorded_hold_checks_pass'] = False
        item = next(o for o in snapshot['objects'] if o['id'] == self.part_id)
        for key, value in (('minimum_payload_center_z_m', item['position'][2]),
                           ('minimum_payload_bottom_z_m', item['bounds']['min'][2])):
            data[key] = value if data[key] is None else min(data[key], value)
        data.update(last_sim_time_s=sim, last_wall_elapsed_s=wall,
                    observed_sim_s=sim - data['start_sim_time_s'], observed_wall_s=wall - data['start_wall_elapsed_s'])


class DenseBounds:
    """A union of actual cached native geometry states, not continuous motion."""
    def __init__(self):
        import numpy as np
        self.np = np
        self.low = self.high = self.first = self.last = None
        self.count = self.unique_times = 0
        self.max_sim_gap = self.max_wall_gap = 0.

    def add(self, sim, wall, low, high):
        if self.last is not None:
            ds, dw = sim - self.last[0], wall - self.last[1]
            if ds < 0 or dw < 0:
                raise ValueError('Dense geometry clock reversed')
            self.max_sim_gap, self.max_wall_gap = max(self.max_sim_gap, ds), max(self.max_wall_gap, dw)
            self.unique_times += int(ds > 0)
            self.low = self.np.minimum(self.low, low)
            self.high = self.np.maximum(self.high, high)
        else:
            self.low, self.high = self.np.array(low, copy=True), self.np.array(high, copy=True)
            self.first = [sim, wall]
            self.unique_times = 1
        self.last = [sim, wall]
        self.count += 1

    def report(self, geom_ids, coarse_bounds=None):
        deficit = None
        if coarse_bounds is not None and self.low is not None:
            deficit = {'lower_m': self.np.maximum(0., coarse_bounds[0] - self.low).tolist(),
                       'upper_m': self.np.maximum(0., self.high - coarse_bounds[1]).tolist()}
        return {'geom_ids': list(geom_ids), 'sample_count_including_forced_duplicates': self.count,
            'distinct_sim_time_count': self.unique_times, 'first_sim_wall_s': self.first, 'last_sim_wall_s': self.last,
            'maximum_sim_gap_s': self.max_sim_gap, 'maximum_wall_gap_s': self.max_wall_gap,
            'sampled_outer_box_union_m': None if self.low is None else {'min': self.low.tolist(), 'max': self.high.tolist()},
            'observed_coarse_endpoint_sampling_deficit_m': deficit,
            'scope': 'Every observed native physics-tick cached-transform state plus forced endpoint samples; discrete only',
            'continuous_sweep_error_bound_m': None, 'transfer_padding_m': None}
