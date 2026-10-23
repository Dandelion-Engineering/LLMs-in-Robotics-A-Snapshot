"""DEFERRED during physical work. Pure bounded comparison; no Runtime import."""
import ast
import copy
import hashlib
import math
import unittest

import pending_route_validation as proposal


def box(low=0., high=1.):
    return {'min': [low] * 3, 'max': [high] * 3}


def fixture():
    payload = {'id': 'held', 'kind': 'part', 'family': 'A', 'bounds': box(.1, .2)}
    envelope = {'operation': 'recover_held', 'destination': 'parking1', 'tcp_start_m': box(),
        'destination_region_m': box(), 'joint_start_ranges_rad': [[-1., 1.]] * 7,
        'joint_velocity_ranges_rad_s': [[-1., 1.]] * 7, 'maximum_abs_finger_velocity_m_s': .1,
        'clearance_corridors_m': [box()], 'payload_kind': 'part', 'payload_family': 'A'}
    snapshot = {'robot': {'tcp_position_world_m': [.5] * 3, 'joint_position_rad': [0.] * 7,
                         'joint_velocity_rad_s': [0.] * 7, 'finger_velocity_m_s': [0.] * 2},
                'geometry': {'zones': {'parking1': copy.deepcopy(envelope['destination_region_m'])},
                             'objects': [payload, {'id': 'other', 'bounds': box(2., 3.)}]}}
    return [{'envelope': envelope}], snapshot, payload, ['parking1']


def namespace(source):
    names = {'number', 'vector', 'valid_box', 'overlaps', 'inside', '_route'}
    tree = ast.parse(source)
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != names:
        raise AssertionError('Source function inventory differs')
    space = {'math': math, '_calibration': lambda entry, snapshot, **kwargs: (
        entry.get('synthetic_calibration_state', 'pass'), 'unchanged synthetic gate')}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<pure route comparison>', 'exec'), space)
    return space


class RouteValidationProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installed = proposal.TARGET.read_bytes()
        archive = proposal.HERE / 'source-archive' / ('restart_state.' + proposal.BASE_SHA256 + '.py')
        cls.raw = archive.read_bytes() if archive.exists() else cls.installed
        cls.original = cls.raw.decode('utf-8')
        cls.candidate = proposal.candidate_source(cls.original)

    def compare(self, args, **kwargs):
        old, new = namespace(self.original), namespace(self.candidate)
        outcomes = []
        for functions in (old, new):
            try:
                outcomes.append(('value', functions['_route'](*args, **kwargs)))
            except Exception as error:
                outcomes.append(('error', type(error), str(error)))
        self.assertEqual(outcomes[0], outcomes[1])
        return outcomes[1]

    def test_strict_overlap_threshold_all_axes_and_blocker_sort_duplicate_ids(self):
        for axis in range(3):
            for upper, expected in [(0., False), (math.nextafter(1e-6, 0.), False),
                                    (1e-6, False), (math.nextafter(1e-6, math.inf), True)]:
                with self.subTest(axis=axis, upper=upper):
                    args = fixture(); bounds = box(-1., .5); bounds['max'][axis] = upper
                    args[1]['geometry']['objects'][1]['bounds'] = bounds
                    result = self.compare(args)[1]
                    self.assertEqual(result[2][0]['blocker_ids'], ['other'] if expected else [])
        args = fixture()
        args[1]['geometry']['objects'] = [{'id': 'held'}, {'id': 'z', 'bounds': box(.2, .3)},
            {'id': 'a', 'bounds': box(.2, .3)}, {'id': 'a', 'bounds': box(.3, .4)},
            {'id': 'far', 'bounds': box(2., 3.)}]
        self.assertEqual(self.compare(args)[1][2][0]['blocker_ids'], ['a', 'a', 'z'])

    def test_malformed_nonfinite_and_type_cases_preserve_outcomes(self):
        malformed = [None, [], (), '', {}, {'min': [0.] * 3}, {'min': [0., 0.], 'max': [1.] * 3},
            {'min': [0.] * 3, 'max': [0.] * 3}, {'min': [1.] * 3, 'max': [0.] * 3}]
        for value in [float('nan'), float('inf'), -float('inf'), True, False, '0', None, 10 ** 400]:
            bounds = box(); bounds['min'][0] = value; malformed.append(bounds)
        malformed.append({'min': (0., 0., 0.), 'max': (1., 1., 1.)})
        for bounds in malformed:
            with self.subTest(bounds=repr(bounds)):
                args = fixture(); args[1]['geometry']['objects'][1]['bounds'] = bounds
                self.compare(args)
                args = fixture(); args[0][0]['envelope']['clearance_corridors_m'] = [bounds]
                self.compare(args)
        for corridors in [None, [], (), '', {}, [box(), None]]:
            args = fixture(); args[0][0]['envelope']['clearance_corridors_m'] = corridors
            self.compare(args)
        for objects in [[{'bounds': box()}], [{'id': 'other'}], [None]]:
            args = fixture(); args[1]['geometry']['objects'] = objects
            self.compare(args)

    def test_calibration_malformed_route_and_same_cell_gates_remain_first(self):
        for state in ('unknown', 'fail'):
            args = fixture(); args[0][0]['synthetic_calibration_state'] = state
            args[1]['geometry']['objects'] = [None]
            self.assertEqual(self.compare(args)[0], 'value')
        args = fixture(); args[0][0]['envelope']['clearance_corridors_m'] = []
        args[1]['geometry']['objects'] = [None]
        self.assertEqual(self.compare(args)[1][0], 'unknown')
        args = fixture(); args[0][0].update(match_mode='qualified_class', qualification_cell_id='one')
        args[1]['geometry']['objects'] = [None]
        self.assertEqual(self.compare(args, grip_entry={'match_mode': 'qualified_class',
                                                     'qualification_cell_id': 'another'})[1][0], 'unknown')

    def test_validation_reused_only_inside_call_without_caching_snapshot(self):
        args = fixture(); corridors = [box(i, i+1.) for i in range(4)]
        args[0][0]['envelope']['clearance_corridors_m'] = corridors
        args[1]['geometry']['objects'][1]['bounds'] = box(20., 21.)
        objects = [{'id': str(i), 'bounds': box(10.+i, 10.5+i)} for i in range(3)]
        args[1]['geometry']['objects'] += objects
        for source, expected_object_checks, expected_corridor_checks in [(self.original, 4, 5), (self.candidate, 1, 1)]:
            space = namespace(source); valid = space['valid_box']; counts = {}
            def counted(bounds):
                counts[id(bounds)] = counts.get(id(bounds), 0) + 1
                return valid(bounds)
            space['valid_box'] = counted
            space['_route'](*args)
            for other in objects:
                self.assertEqual(counts[id(other['bounds'])], expected_object_checks)
            # Four other objects include the original synthetic 'other'.
            for corridor in corridors:
                self.assertEqual(counts[id(corridor)], expected_corridor_checks)
        space = namespace(self.candidate)
        before = space['_route'](*args)
        objects[0]['bounds'] = box(.2, .3)
        after = space['_route'](*args)
        self.assertNotEqual(before, after)
        self.assertIn('0', after[2][0]['blocker_ids'])

    def test_exact_base_and_only_route_block_changed(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), proposal.BASE_SHA256)
        with self.assertRaises(ValueError): proposal.candidate_source(self.original + '\n')
        newline = '\r\n' if '\r\n' in self.original else '\n'
        self.assertEqual(self.candidate.replace(proposal.NEW.replace('\n', newline),
                                               proposal.OLD.replace('\n', newline), 1), self.original)
        self.assertEqual(proposal.TARGET.read_bytes(), self.installed)

    def test_installed_source_is_exact_approved_candidate_or_unchanged_base(self):
        self.assertIn(self.installed, (self.raw, self.candidate.encode('utf-8')))
        if self.installed != self.raw:
            self.assertEqual(hashlib.sha256(self.installed).hexdigest(),
                             'd5f354c60af83c6f9d32f6b43a893c19486ddcb1f8d2f85c78f526fe48d0273c')


if __name__ == '__main__':
    unittest.main()
