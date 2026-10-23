"""Synthetic prior-evidence counterexamples, never measured qualification."""
import copy
import unittest

from compatibility import digest
from descriptor import EXPORT_SCHEMA
from qualification import QUALIFICATION_SCHEMA, actual_absence_coverage, qualified_entry_identity
from test_compatibility import fixture as compatibility_fixture


def fixture():
    spec, observation = compatibility_fixture()
    observation.update(export_schema=EXPORT_SCHEMA, export_state='pass', compile_seal_sha256='c'*64, compiled_surface_sha256='d'*64)
    snapshot = {key: observation[key] for key in ('physical_configuration_sha256', 'scene_xml_sha256', 'source_hashes')}
    snapshot.update(physical_class_observation=observation, expected_object_ids=[r['id'] for r in observation['objects']],
                    geometry={'objects': copy.deepcopy(observation['objects'])}, exposure={'actual_cut': 'closed_grip_transfer'})
    references = [{'kind': 'prior_physical_calibration', 'artifact_id': 'synthetic-physical-evidence',
                   'sha256': 'e'*64, 'bytes_verified_by_operator': True, 'recorded_at_utc': '2020-01-01T00:00:00Z',
                   'supports': ['carry_state', 'absence_survival', 'whole_arm_payload_route', 'settled_placement', 'development_validation']}]
    cell = {'cell_id': 'synthetic-only', 'payload_template_sha256': digest(spec['templates']['part:A']),
            'envelope_basis': 'measured_before_this_intervention',
            'grip_envelope': {'kind': 'part', 'family': 'A'},
            'route_envelope': {'payload_kind': 'part', 'payload_family': 'A', 'destination': 'parking2'},
            'maximum_qualified_absence_s': 2., 'measured_state_cell_basis': 'synthetic counterexample fixture, not measurement',
            'source_scope': 'synthetic source', 'route_coverage_method': 'synthetic method',
            'route_sampling_clearance_allowance_m': .001, 'untested_combinations': 'all physical operation; synthetic test only',
            'measured_points': [{'snapshot_sha256': 'a'*64, 'physical_configuration_sha256': 'b'*64, 'physical_class_observation_sha256': 'c'*64}],
            'evidence_refs': references}
    bundle = {'schema_version': QUALIFICATION_SCHEMA, 'class_spec': spec, 'status': 'measured_development',
              'empirical_transfer_rule': 'synthetic fixture only', 'accepted_at_utc': '2020-01-02T00:00:00Z', 'cells': [cell]}
    context = {'bundle': bundle, 'frozen_bundle_sha256': digest(bundle), 'frozen_class_sha256': digest(spec),
               'freeze_utc': '2020-01-03T00:00:00Z', 'prospective_absence_bound_s': 1.,
               'verified_artifacts': {'synthetic-physical-evidence': 'e'*64}}
    entry = {'match_mode': 'qualified_class', 'qualification_cell_id': cell['cell_id'], 'qualification_role': 'grip',
             'envelope_basis': cell['envelope_basis'], 'envelope': copy.deepcopy(cell['grip_envelope']),
             'evidence_refs': copy.deepcopy(references), 'source_hashes': copy.deepcopy(snapshot['source_hashes'])}
    return entry, snapshot, context


class QualificationTests(unittest.TestCase):
    def state(self, entry, snapshot, context):
        return qualified_entry_identity(entry, snapshot, context)['state']

    def test_compatible_prior_cell_is_only_identity_not_physical_admission(self):
        entry, snapshot, context = fixture(); report = qualified_entry_identity(entry, snapshot, context)
        self.assertEqual(report['state'], 'pass', report)
        self.assertEqual(report['evidence_basis'], 'empirical_transfer')
        self.assertFalse(report['instance_previously_calibrated'])
        self.assertFalse(report['physical_state_predicates_evaluated'])
        self.assertEqual(report['actual_absence_coverage'], 'not_yet_observed')

    def test_class_compatibility_cannot_fill_empty_calibration(self):
        entry, snapshot, context = fixture(); context['bundle']['cells'] = []
        context['frozen_bundle_sha256'] = digest(context['bundle'])
        self.assertEqual(self.state(entry, snapshot, context), 'unknown')

    def test_absence_missing_excessive_nonfinite_or_nonpositive_is_unknown(self):
        for duration in (None, 3., float('nan'), 0., -1.):
            entry, snapshot, context = fixture(); context['prospective_absence_bound_s'] = duration
            with self.subTest(duration=duration): self.assertEqual(self.state(entry, snapshot, context), 'unknown')

    def test_absence_overrun_cannot_be_repaired_by_success(self):
        self.assertEqual(actual_absence_coverage(2.01, 2.)['state'], 'unknown')
        self.assertEqual(actual_absence_coverage(1.99, 2.)['state'], 'pass')
        self.assertEqual(actual_absence_coverage(None, 2.)['state'], 'unknown')

    def test_freeze_binding_is_independent_of_changed_evidence(self):
        entry, snapshot, context = fixture(); context['bundle']['cells'][0]['maximum_qualified_absence_s'] = 100.
        self.assertEqual(self.state(entry, snapshot, context), 'fail')
        context['frozen_bundle_sha256'] = None
        self.assertEqual(self.state(entry, snapshot, context), 'unknown')

    def test_reference_and_release_timing_must_be_prior(self):
        for case in ('accepted', 'artifact'):
            entry, snapshot, context = fixture()
            if case == 'accepted': context['bundle']['accepted_at_utc'] = '2020-01-04T00:00:00Z'
            else:
                context['bundle']['cells'][0]['evidence_refs'][0]['recorded_at_utc'] = '2020-01-04T00:00:00Z'
                entry['evidence_refs'] = copy.deepcopy(context['bundle']['cells'][0]['evidence_refs'])
            context['frozen_bundle_sha256'] = digest(context['bundle'])
            with self.subTest(case=case): self.assertEqual(self.state(entry, snapshot, context), 'unknown')

    def test_unknown_cell_destination_or_envelope_cannot_be_substituted(self):
        entry, snapshot, context = fixture(); entry['qualification_cell_id'] = 'not_measured'
        self.assertEqual(self.state(entry, snapshot, context), 'unknown')
        entry, snapshot, context = fixture(); entry['qualification_role'] = 'route'; entry['envelope'] = copy.deepcopy(context['bundle']['cells'][0]['route_envelope'])
        self.assertEqual(self.state(entry, snapshot, context), 'pass')
        entry['envelope']['destination'] = 'parking1'
        self.assertEqual(self.state(entry, snapshot, context), 'fail')

    def test_unverified_or_incomplete_measurements_stay_unknown(self):
        for case in ('bytes', 'points', 'scope', 'route', 'absence', 'validation'):
            entry, snapshot, context = fixture(); cell = context['bundle']['cells'][0]
            if case == 'bytes': context['verified_artifacts'] = {}
            if case == 'points': cell['measured_points'] = []
            if case == 'scope': cell['measured_state_cell_basis'] = ''
            if case == 'route': cell['route_sampling_clearance_allowance_m'] = None
            if case == 'absence': cell['maximum_qualified_absence_s'] = None
            if case == 'validation': cell['evidence_refs'][0]['supports'].remove('development_validation')
            context['frozen_bundle_sha256'] = digest(context['bundle'])
            with self.subTest(case=case): self.assertEqual(self.state(entry, snapshot, context), 'unknown')

    def test_missing_or_mismatched_export_state_and_capture_fail_closed(self):
        for case in ('export', 'identity', 'source', 'inventory', 'seal'):
            entry, snapshot, context = fixture(); obs = snapshot['physical_class_observation']
            if case == 'export': obs['export_state'] = 'unknown'
            if case == 'identity': snapshot['scene_xml_sha256'] = 'f'*64
            if case == 'source': snapshot['source_hashes'] = {'cell.py': 'f'*64}
            if case == 'inventory': snapshot['expected_object_ids'].pop()
            if case == 'seal': del obs['compile_seal_sha256']
            with self.subTest(case=case): self.assertNotEqual(self.state(entry, snapshot, context), 'pass')

    def test_other_cut_family_is_not_qualified_by_carry_evidence(self):
        entry, snapshot, context = fixture(); snapshot['exposure']['actual_cut'] = 'after_release'
        self.assertEqual(self.state(entry, snapshot, context), 'unknown')

    def test_nonfinite_and_malformed_support_cannot_raise_out_to_caller(self):
        entry, snapshot, context = fixture(); context['bundle']['cells'][0]['evidence_refs'][0]['supports'] = [{}]
        context['frozen_bundle_sha256'] = digest(context['bundle'])
        self.assertEqual(self.state(entry, snapshot, context), 'unknown')


if __name__ == '__main__': unittest.main()
