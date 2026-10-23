"""Prepared only: defer execution until root releases the physics source hold."""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
ASSESSOR = HERE.parent / 'Batch 01/Restart Qualification Tools/assess_validation.py'
ARCHIVE = HERE / 'Dense containment optimization'
BASE_SHA = '300b32a136790802ce57781a7ee8b12e2cfe7923b8702d0d998e3c4f3e783192'
PROPOSED_SHA = 'cb1ddce3ef6a919c1df1d30cc63db55fd8fe63c2dc4a9feaafbebdc7307dd91e'
HELPER_SHA = 'c052ddff8f7aa938f760067370bdfde74234f6547b1c719f6a7dcc525dd891b4'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def baseline():
    raw = (ARCHIVE / 'original/assess_validation.py').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == BASE_SHA, 'Archived original assessor identity changed')
    tree = ast.parse(raw)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('result', 'flag', 'valid_box', 'box_union_contains', 'dense_assessment')]
    require(len(functions) == 5, 'Baseline function inventory differs')
    namespace = {'copy': copy, 'json': json, 'require': require,
                 'finite': lambda value: type(value) in (int, float) and math.isfinite(value)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<exact-source-original-subtraction>', 'exec'), namespace)
    return namespace


def proposed(original):
    installed = ASSESSOR.read_bytes()
    installed_sha = hashlib.sha256(installed).hexdigest()
    require(installed_sha in (BASE_SHA, PROPOSED_SHA), 'Installed assessor differs from both guarded states')
    staged = (ARCHIVE / 'proposed/assess_validation.py').read_bytes()
    require(hashlib.sha256(staged).hexdigest() == PROPOSED_SHA, 'Staged assessor identity changed')
    # Before application use the exact staged source; afterwards test the actual
    # installed class and dense-assessment wiring against the archived reference.
    tree = ast.parse(installed if installed_sha == PROPOSED_SHA else staged)
    reference = ast.parse((ARCHIVE / 'original/assess_validation.py').read_bytes())
    by_name = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    old = {n.name: n for n in reference.body if isinstance(n, ast.FunctionDef)}
    require(ast.dump(by_name['box_union_contains']) == ast.dump(old['box_union_contains']),
            'Original public subtraction reference changed')
    helper = (HERE / 'prepared_corridor_containment.py').read_bytes()
    require(hashlib.sha256(helper).hexdigest() == HELPER_SHA, 'Reviewed helper changed')
    helper_class = next(n for n in ast.parse(helper).body if isinstance(n, ast.ClassDef))
    require(ast.dump(by_name['PreparedCorridorContainment']) == ast.dump(helper_class), 'Integrated class differs from reviewed helper')
    expected_dense = copy.deepcopy(old['dense_assessment'])
    expected_dense.body.insert(0, ast.parse('containment = PreparedCorridorContainment(corridors, valid_box=valid_box, require=require)').body[0])
    calls = [n for n in ast.walk(expected_dense) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'box_union_contains']
    require(len(calls) == 1, 'Original dense call inventory differs')
    calls[0].func.id = 'containment'; calls[0].args = calls[0].args[:1]
    require(ast.dump(by_name['dense_assessment']) == ast.dump(expected_dense), 'Dense wiring has additional changes')
    namespace = {**original, 'np': np}
    nodes = [by_name['PreparedCorridorContainment'], by_name['dense_assessment']]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<guarded-staged-or-installed-assessor>', 'exec'), namespace)
    return namespace['PreparedCorridorContainment'], namespace['dense_assessment']


def box(lo, hi):
    return {'min': list(lo), 'max': list(hi)}


class PreparedChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = baseline()
        cls.candidate, cls.proposed_dense = proposed(cls.original)

    def compare(self, query, corridors):
        def outcome(call):
            try:
                return ('result', call())
            except (ValueError, TypeError, OverflowError) as error:
                return (type(error).__name__, str(error))
        prepared = self.candidate(corridors, valid_box=self.original['valid_box'], require=require)
        expected = outcome(lambda: self.original['box_union_contains'](query, corridors))
        self.assertEqual(expected, outcome(lambda: prepared(query)))
        self.assertEqual(expected, outcome(lambda: prepared(query)))

    def test_direct_touch_gap_and_multicover_union(self):
        query = box([0., 0., 0.], [1., 1., 1.])
        self.compare(query, [copy.deepcopy(query)])
        self.compare(query, [box([1.,0.,0.], [2.,1.,1.])])
        self.compare(query, [box([0.,0.,0.], [.5,1.,1.]), box([.5,0.,0.], [1.,1.,1.])])
        self.compare(query, [box([0.,0.,0.], [.5,1.,1.]), box([math.nextafter(.5, 1.),0.,0.], [1.,1.,1.])])

    def test_malformed_and_nonfinite_unknown_behavior(self):
        good = box([0.,0.,0.], [1.,1.,1.])
        for bad in (None, {}, [], [None], [box([0.,0.,0.], [0.,1.,1.])],
                    [box([False,0.,0.], [1.,1.,1.])], [box([0.,0.,0.], [math.nan,1.,1.])]):
            self.compare(good, bad)
        self.compare(box([0.,0.,0.], [math.inf,1.,1.]), [good])
        self.compare({'min': (0.,0.,0.), 'max': [1.,1.,1.]}, [good])

    def test_uncovered_piece_order_and_outside_filter(self):
        query = box([-2.,-2.,-2.], [2.,2.,2.])
        corridors = [box([8.,8.,8.], [9.,9.,9.]), box([-.5,-3.,-3.], [.5,3.,3.]),
                     box([-3.,-.5,-3.], [3.,.5,3.]), box([-3.,-3.,-.5], [3.,3.,.5])]
        self.compare(query, corridors)

    def test_exact_large_integer_scalar_fallback_and_signed_zero(self):
        n = 2**54
        self.compare(box([n,0,0], [n+3,2,2]), [box([n,0,0], [n+2,2,2])])
        self.compare(box([-0.,-1.,-1.], [1.,1.,1.]), [box([0.,-1.,-1.], [1.,1.,1.])])

    def test_fixed_snapshot_not_exposed_through_result(self):
        query = box([0.,0.,0.], [1.,1.,1.]); corridors = [box([2.,2.,2.], [3.,3.,3.])]
        saved = copy.deepcopy(corridors)
        prepared = self.candidate(corridors, valid_box=self.original['valid_box'], require=require)
        corridors[0]['min'][0] = -100.
        first = prepared(query)
        first['first_uncovered_box']['min'][0] = -100.
        self.assertEqual(prepared(query), self.original['box_union_contains'](query, saved))

    def test_resource_cap_precedes_late_containing_box(self):
        # 27 disjoint slabs along each axis leave 28^3 = 21,952 pieces.
        # A final enclosing box must not turn that earlier unknown into pass.
        query = box([0.,0.,0.], [56.,56.,56.])
        corridors = []
        for axis in range(3):
            for i in range(27):
                lo, hi = [0.,0.,0.], [56.,56.,56.]
                lo[axis], hi[axis] = 2.*i+1., 2.*i+2.
                corridors.append(box(lo, hi))
        corridors.append(copy.deepcopy(query))
        with self.assertRaisesRegex(ValueError, 'resource cap'):
            self.original['box_union_contains'](query, corridors)
        self.compare(query, corridors)

    def test_deterministic_mixed_overlap_examples(self):
        rng = random.Random(0)
        for _ in range(120):
            corridors = []
            for _ in range(rng.randrange(1, 15)):
                lo = [rng.randrange(-4, 5)/2 for _ in range(3)]
                corridors.append(box(lo, [v+rng.randrange(1, 6)/2 for v in lo]))
            self.compare(box([-1.,-1.,-1.], [1.,1.,1.]), corridors)

    def test_dense_record_accounting_and_lazy_invalid_corridors(self):
        query = box([0.,0.,0.], [1.,1.,1.])
        row = {'sim_time_s': .002, 'physics_timestep_s': .002,
            'interval_dense_geometry': {'geom_ids': [1, 2], 'first_sim_wall_s': [0.,0.],
                'last_sim_wall_s': [.002,.002], 'distinct_sim_time_count': 2,
                'sample_count_including_forced_duplicates': 2, 'maximum_sim_gap_s': .002,
                'maximum_wall_gap_s': .002, 'sampled_outer_box_union_m': {
                    'min': [query['min'], [False,0.,0.]], 'max': [query['max'], query['max']]}}}
        states = {'cut': {'sim_time_s': 0., 'payload': {'geometry': {'objects': []}}},
                  'after_placement': {'sim_time_s': .002}}
        class Evidence:
            def __init__(self, rows): self.rows = rows
            def json(self, name):
                return {'geoms': [{'geom_id': 1, 'role': 'robot'}, {'geom_id': 2, 'role': 'payload'}]}, {'path': name}
            def stream(self, name, visit):
                for index, value in enumerate(self.rows, 1): visit(index, json.dumps(value).encode())
                return {'path': name}
        for rows in ([], [row]):
            for corridors in ([], [query], [box([2.,2.,2.], [3.,3.,3.])]):
                expected = self.original['dense_assessment'](Evidence(rows), 'synthetic', corridors, states)
                actual = type(self).proposed_dense(Evidence(rows), 'synthetic', corridors, states)
                self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
