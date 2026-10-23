"""Tiny synthetic evidence only; no live screen, queue, or physics execution."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from extract_screen import canonical, extract, SCHEMA


class ExtractorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.screen = self.root / 'screen'; self.screen.mkdir()
        self.output = self.root / 'extract'
        self.receipt = self.root / 'receipt.json'
        self.rows = [{'id': name, 'destination': destination, 'fixture': fixture,
                      'main_geom_mass_kg': .11, 'main_geom_sliding_friction': 1.3}
                     for name, destination, fixture in (
                         ('failed', 'parking1', 'construction'), ('unstarted', 'parking1', 'construction'),
                         ('deferred', 'parking1', 'independent_generator'), ('other', 'parking2', 'construction'))]
        job = {'id': 'job1', 'child_pid': 123, 'worker_pid': 22, 'resolved_executable': 'python',
               'argv': ['python', 'run_screen.py'], 'cwd': '/synthetic', 'started_at': '2026-09-23T00:00:00Z'}
        self.save(self.receipt, {**job, 'state': 'succeeded', 'exit_status': 0, 'ended_at': '2026-09-23T00:00:10Z'})
        (self.screen / 'source-bundle.zip').write_bytes(b'synthetic archive bytes, not a real physics archive')
        manifest = {'schema_version': SCHEMA, 'created_at': '2026-09-23T00:00:01Z',
            'queue': {'queue_job': job, 'job_id': 'job1'}, 'prospective_plan': {'trials': self.rows},
            'modes': ['failed', 'unstarted'], 'destination_selection': 'parking1', 'execution_phase': 'construction',
            'phase_deferred_trial_ids': ['deferred'], 'source_bundle_sha256': self.sha(self.screen / 'source-bundle.zip')}
        self.save(self.screen / 'manifest.json', manifest)
        self.save(self.screen / 'summary.json', {'schema_version': SCHEMA, 'queue_job_id': 'job1',
            'finished_at': '2026-09-23T00:00:09Z', 'attempts': [{'trial_id': 'failed', 'status': 'failed'}],
            'not_started': ['unstarted'], 'phase_deferred_trial_ids': ['deferred']})
        self.save(self.screen / 'failed/result.json', {'trial_id': 'failed', 'trial': self.rows[0],
            'status': 'failed', 'error': 'synthetic hold loss', 'details': {'all_absence_tick_hold_checks_pass': False}})
        self.save(self.screen / 'failed/compiled-properties.json', {'objects': {'A1': {
            'generator_half_open_domain_member': False, 'main_geom_mass_kg': .11,
            'compiled_body_mass_kg': .1102}}, 'all_objects_generator_domain_members': False})
        payload = {'robot': {'q': [.1, .2]}, 'contacts': {'bilateral': True}, 'payload': {'x': 1.2}}
        event = {'event_id': 6, 'event_type': 'protected_carry_state_before_cut', 'sim_time_s': 1.,
                 'wall_elapsed_s': 1.1, 'payload': payload, 'payload_sha256': hashlib.sha256(canonical(payload)).hexdigest()}
        (self.screen / 'failed/events.jsonl').write_bytes(canonical(event) + b'\n' + b'{"interrupted":')
        self.save(self.screen / 'failed/geometry-inventory.json', {'geoms': [{'geom_id': 4, 'role': 'robot',
            'body': 'arm', 'bounds_method': 'synthetic box'}], 'alignment': 'cached-state synthetic fixture'})
        samples = [self.sample(0., 0., 0., 'absence'), self.sample(.02, .025, .03, 'absence'),
                   self.sample(.02, .026, .04, 'absence'), self.sample(.1, .12, .5, 'recovery')]
        (self.screen / 'failed/whole-geometry.jsonl').write_bytes(b''.join(canonical(r) + b'\n' for r in samples))
        self.index()

    @staticmethod
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(value))

    @staticmethod
    def sample(sim, wall, x, phase):
        return {'sim_time_s': sim, 'wall_elapsed_s': wall, 'phase': phase, 'robot_and_payload_geoms': [
            {'geom_id': 4, 'position_m': [x, 0., 0.], 'outer_bounds': {'min': [x - .01, -.01, -.01],
                                                                 'max': [x + .01, .01, .01]}}]}

    def index(self):
        self.save(self.screen / 'evidence-index.json', {'schema_version': SCHEMA, 'files': [
            {'path': p.relative_to(self.screen).as_posix(), 'sha256': self.sha(p), 'bytes': p.stat().st_size}
            for p in sorted(self.screen.rglob('*')) if p.is_file() and p.name != 'evidence-index.json']})

    def test_failed_unstarted_deferred_other_and_boundary_points_remain(self):
        result = extract(self.screen, self.receipt, self.output)
        self.assertEqual([t['execution_status'] for t in result['trials']],
                         ['failed', 'not_started', 'deferred_to_other_phase', 'not_selected_for_this_screen'])
        row = json.loads((self.output / 'failed/trial.json').read_text())
        self.assertFalse(row['compiled_properties']['all_objects_generator_domain_members'])
        self.assertFalse(row['child_result']['details']['all_absence_tick_hold_checks_pass'])
        self.assertFalse(result['qualification_granted'])
        self.assertIsNone(result['global_success_box'])

    def test_full_cut_payload_and_missing_capture_and_partial_tail_retained(self):
        extract(self.screen, self.receipt, self.output)
        states = json.loads((self.output / 'failed/measured-states.json').read_text())
        self.assertEqual(states['states']['cut']['payload']['robot']['q'], [.1, .2])
        self.assertEqual(states['states']['cut']['source_ref']['line'], 1)
        self.assertEqual(states['states']['after_hold']['status'], 'not_recorded')
        self.assertEqual(states['unparsed_records'][0]['line'], 2)

    def test_sampled_union_gaps_phase_separation_and_zero_gap_motion(self):
        extract(self.screen, self.receipt, self.output)
        geom = json.loads((self.output / 'failed/sampled-geometry.json').read_text())
        arm = geom['phases']['absence']['geoms']['4']
        self.assertEqual(arm['sampled_outer_box_union_m']['min'], [-.01, -.01, -.01])
        self.assertAlmostEqual(arm['sampled_outer_box_union_m']['max'][0], .05)
        self.assertAlmostEqual(arm['maximum_adjacent_center_displacement_m'], .03)
        self.assertEqual(arm['zero_sim_gap_with_motion_count'], 1)
        self.assertAlmostEqual(geom['overall']['maximum_sim_gap_s'], .08)
        self.assertIsNone(geom['phases']['recovery']['maximum_sim_gap_s'])
        self.assertIsNone(geom['continuous_clearance_bound_m'])

    def test_running_receipt_rejected_before_screen_read(self):
        data = json.loads(self.receipt.read_text()); data['state'] = 'running'; self.save(self.receipt, data)
        with self.assertRaisesRegex(ValueError, 'Successful official'):
            extract(self.root / 'absent-screen', self.receipt, self.output)
        self.assertFalse(self.output.exists())

    def test_receipt_identity_mismatch_rejected(self):
        data = json.loads(self.receipt.read_text()); data['child_pid'] += 1; self.save(self.receipt, data)
        with self.assertRaisesRegex(ValueError, 'does not identify'):
            extract(self.screen, self.receipt, self.output)

    def test_tampered_source_has_no_extraction_completion_marker(self):
        path = self.screen / 'failed/events.jsonl'; path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Indexed bytes differ'):
            extract(self.screen, self.receipt, self.output)
        self.assertFalse((self.output / 'extraction.json').exists())

    def test_index_path_escape_rejected(self):
        data = json.loads((self.screen / 'evidence-index.json').read_text())
        data['files'].append({'path': '../outside', 'sha256': 'x', 'bytes': 0})
        self.save(self.screen / 'evidence-index.json', data)
        with self.assertRaisesRegex(ValueError, 'Unsafe artifact'):
            extract(self.screen, self.receipt, self.output)

    def test_omitted_failed_trial_rejected(self):
        path = self.screen / 'summary.json'; data = json.loads(path.read_text())
        data['attempts'] = []; self.save(path, data); self.index()
        with self.assertRaisesRegex(ValueError, 'coverage'):
            extract(self.screen, self.receipt, self.output)

    def test_existing_output_and_input_nested_output_refused(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh'):
            extract(self.screen, self.receipt, self.output)
        with self.assertRaisesRegex(ValueError, 'separate'):
            extract(self.screen, self.receipt, self.screen / 'analysis')


if __name__ == '__main__':
    unittest.main()
