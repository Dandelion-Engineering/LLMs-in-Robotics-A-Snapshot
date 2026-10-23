"""Synthetic assembly/actual Runtime loader tests; no physical evidence or queue."""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

import assemble_qualification as assembly
from bundle_construction import GEOMETRY_SCOPE, PROVISIONAL_SCHEMA, SELECTION_RULE
from compatibility import digest
from test_calibration_loader import write_fixture

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size}


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size}


def fixture(root):
    source = root / 'synthetic-inputs'; source.mkdir()
    old_freeze, _, artifact, old_bundle_path = write_fixture(source)
    old = json.loads(old_bundle_path.read_text(encoding='utf-8'))
    cells = copy.deepcopy(old['cells'])
    for cell in cells:
        cell.pop('evidence_refs')
    spec_ref = write(source / 'class.json', old['class_spec'])
    construction_ref = write(source / 'construction.json', {'synthetic_only': True})
    rule = {'schema_version': PROVISIONAL_SCHEMA, 'status': 'provisional_development_rule',
        'created_at': '2020-01-02T00:00:00Z', 'destination': 'parking2', 'construction_extraction': construction_ref,
        'class_spec': {**spec_ref, 'canonical_sha256': digest(old['class_spec'])},
        'selection_rule': SELECTION_RULE, 'geometry_scope': GEOMETRY_SCOPE,
        'empirical_transfer_rule': 'Synthetic fixture only; no real support.', 'untested_combinations': ['All physics'],
        'validation_outcomes_used_for_fitting': False, 'absence': {'prospective_absence_bound_s': 1.,
            'absence_timebase': 'simulation', 'absence_endpoint': 'recover_held_admitted'},
        'payload_template_to_cell': old_freeze['restart_qualification']['payload_template_to_cell'], 'cells': cells}
    rule_ref = write(source / 'rule.json', rule)
    assessed = root / 'synthetic-assessment'; assessed.mkdir()
    job = {'id': 'synthetic-job', 'child_pid': 101, 'worker_pid': 102, 'resolved_executable': 'synthetic-python',
        'cwd': str(HERE), 'argv': ['synthetic-python', '-B', str(assembly.ASSESSOR), '--output', str(assessed)],
        'started_at': '2020-01-03T00:00:00Z'}
    receipt = {**job, 'state': 'succeeded', 'exit_status': 0, 'ended_at': '2020-01-03T00:02:00Z'}
    receipt_ref = write(source / 'assessment-receipt.json', receipt)
    names = ('validation_extraction_ref', 'validation_receipt_ref', 'extraction_receipt_ref',
             'numeric_source_ref', 'fixture_predicate_source_ref', 'compatibility_source_ref')
    refs = {name: write(source / (name + '.json'), {'synthetic_only': True, 'role': name}) for name in names}
    report = {'schema_version': 'restart-fixed-rule-validation-assessment-1', 'completed_at': '2020-01-03T00:01:00Z',
        'qualification_granted': False, 'scored_ready_claimed': False, 'assessment_queue': job,
        'rule_ref': rule_ref, 'canonical_rule_sha256': digest(rule), 'class_spec_ref': spec_ref,
        'construction_extraction_ref': construction_ref, **refs,
        'input_directories': [str(source), str(assessed)],
        'assessor_dependency_sha256': {str(assembly.ASSESSOR): ref(assembly.ASSESSOR)['sha256']},
        'assessor_sha256': ref(assembly.ASSESSOR)['sha256'],
        'construction_trials': [{'trial_id': 'construction-failed', 'child_status': 'failed'}],
        'trials': [{'trial_id': 'valid-A', 'state': 'pass'}, {'trial_id': 'valid-B', 'state': 'pass'},
                   {'trial_id': 'outside', 'state': 'fail', 'reason': 'Synthetic out-of-scope state'},
                   {'trial_id': 'unselected', 'state': 'not_selected'}],
        'selected_validation_ids': ['valid-A', 'valid-B', 'outside'],
        'finite_declared_checks_state': 'fail', 'limitations': ['Synthetic test only; continuous physics untested'],
        'consumed_files': [rule_ref, spec_ref, construction_ref, *refs.values(), ref(artifact)]}
    assessment_ref = write(assessed / 'assessment.json', report)
    acceptance = {'schema_version': assembly.ACCEPTANCE_SCHEMA, 'decision': 'accept_unchanged_provisional_rule',
        'operator': 'synthetic root', 'root_note': 'Synthetic identity test only, not real qualification.',
        'validation_review_note': 'Outside failure retained; no failure becomes a pass.',
        'accepted_at_utc': '2020-01-04T00:00:00Z', 'rule_sha256': rule_ref['sha256'],
        'assessment_sha256': assessment_ref['sha256'], 'cells': {}}
    for index, cell in enumerate(cells):
        acceptance['cells'][cell['cell_id']] = {'provisional_cell_sha256': digest(cell),
            'root_note': 'Synthetic cell only', 'validation_scope': {
                'trial_ids': ['valid-A' if index == 0 else 'valid-B'], 'note': 'Only named synthetic cell observations'},
            'support_refs': [{'artifact_id': 'synthetic-physical-evidence', **ref(artifact),
                'recorded_at_utc': '2020-01-01T00:00:00Z', 'supports': sorted(assembly.SUPPORTS),
                'reason': 'Synthetic evidence exists only to exercise exact byte binding.'}]}
    acceptance_ref = write(source / 'acceptance.json', acceptance)
    return {'rule': rule, 'rule_path': Path(rule_ref['path']), 'assessment': report,
        'assessment_path': Path(assessment_ref['path']), 'receipt_path': Path(receipt_ref['path']),
        'acceptance': acceptance, 'acceptance_path': Path(acceptance_ref['path']), 'artifact': artifact}


def refresh_assessment(data):
    current = write(data['assessment_path'], data['assessment'])
    data['acceptance']['assessment_sha256'] = current['sha256']
    write(data['acceptance_path'], data['acceptance'])


def archived_sources(data):
    """Actual assessment reference shape; contents remain synthetic only."""
    members = {'numeric_source_ref': ('Runtime/restart_state.py', b'# synthetic numerical source\r\n'),
        'fixture_predicate_source_ref': ('Batch 01/Recovery Qualification/fixture.py', b'# synthetic predicate\n'),
        'compatibility_source_ref': ('Runtime/restart_compatibility.py', b'# synthetic compatibility\n')}
    archive = data['rule_path'].parent / 'source-bundle.zip'
    removed = {data['assessment'][name]['path'] for name in members}
    with zipfile.ZipFile(archive, 'w') as bundle:
        for member, raw in members.values():
            bundle.writestr(member, raw)
    for name, (member, raw) in members.items():
        data['assessment'][name] = {'archive': str(archive), 'member': member,
                                    'sha256': hashlib.sha256(raw).hexdigest()}
    data['assessment']['consumed_files'] = [item for item in data['assessment']['consumed_files']
                                          if item['path'] not in removed] + [ref(archive)]
    refresh_assessment(data)
    return archive, members


class AssemblyTests(unittest.TestCase):
    def assemble(self, data, output, accepted=True):
        return assembly.assemble(data['rule_path'], data['assessment_path'], data['receipt_path'], output,
            acceptance_path=data['acceptance_path'] if accepted else None)

    def test_explicit_acceptance_loads_in_actual_runtime_with_unchanged_cells_and_all_outcomes(self):
        with TemporaryDirectory(dir=HERE) as directory:
            root = Path(directory); data = fixture(root)
            report = self.assemble(data, root / 'assembled')
            self.assertEqual(report['loader_validation'], 'pass')
            self.assertFalse(report['qualification_granted_by_assembler'])
            bundle = json.loads(Path(report['bundle_path']).read_text(encoding='utf-8'))
            self.assertNotIn('assessment', bundle)
            self.assertNotIn('provisional_rule', bundle)
            self.assertEqual(bundle['assessment_ref'], ref(data['assessment_path']))
            self.assertEqual(bundle['provisional_rule_ref'], ref(data['rule_path']))
            self.assertEqual(bundle['assessment_canonical_sha256'], digest(data['assessment']))
            self.assertEqual(bundle['provisional_rule_canonical_sha256'], digest(data['rule']))
            self.assertEqual(json.loads(Path(bundle['assessment_ref']['path']).read_text(encoding='utf-8')), data['assessment'])
            self.assertEqual(bundle['assessment_summary']['finite_declared_checks_state'], 'fail')
            self.assertEqual([row['trial_id'] for row in bundle['assessment_trial_index']['trials']],
                             [row['trial_id'] for row in data['assessment']['trials']])
            inventory = {row['path']: row['sha256'] for row in bundle['artifact_files']}
            self.assertEqual(inventory[str(data['assessment_path'])], bundle['assessment_ref']['sha256'])
            self.assertEqual(inventory[str(data['rule_path'])], bundle['provisional_rule_ref']['sha256'])
            for original, actual in zip(data['rule']['cells'], bundle['cells']):
                self.assertEqual({k: actual[k] for k in original}, original)
                self.assertTrue(actual['evidence_refs'][0]['bytes_verified_by_operator'])
            loader, _ = assembly.runtime_modules()
            path = Path(report['development_freeze_path']); freeze = json.loads(path.read_text(encoding='utf-8'))
            loaded = loader.load_restart_qualification(freeze, path).as_dict()
            self.assertEqual(loaded['payload_template_to_cell'], data['rule']['payload_template_to_cell'])
            self.assertEqual(loaded['absence'], data['rule']['absence'])

    def test_without_acceptance_only_drafts_exist_and_actual_loader_refuses(self):
        with TemporaryDirectory(dir=HERE) as directory:
            root = Path(directory); data = fixture(root)
            report = self.assemble(data, root / 'draft', accepted=False)
            self.assertEqual(report['loader_validation'], 'not_run_draft')
            self.assertFalse(report['operator_acceptance_present'])
            self.assertTrue(report['bundle_path'].endswith('qualification.draft.json'))
            loader, _ = assembly.runtime_modules()
            path = Path(report['development_freeze_path']); freeze = json.loads(path.read_text(encoding='utf-8'))
            with self.assertRaises(loader.CalibrationInputError): loader.load_restart_qualification(freeze, path)

    def test_modified_rule_or_accepted_cell_digest_is_rejected(self):
        for change in ('rule', 'cell'):
            with self.subTest(change=change), TemporaryDirectory(dir=HERE) as directory:
                root = Path(directory); data = fixture(root)
                if change == 'rule':
                    data['rule']['cells'][0]['grip_envelope']['jaw_width_m'][1] += 1
                    write(data['rule_path'], data['rule'])
                else:
                    first = next(iter(data['acceptance']['cells'].values()))
                    first['provisional_cell_sha256'] = 'f' * 64
                    write(data['acceptance_path'], data['acceptance'])
                with self.assertRaises(ValueError): self.assemble(data, root / 'refused')
                self.assertFalse((root / 'refused').exists())

    def test_missing_or_unsupported_acceptance_and_support_are_not_inferred_from_status(self):
        for change in ('decision', 'note', 'support', 'scope', 'time', 'bytes', 'inventory', 'sources'):
            with self.subTest(change=change), TemporaryDirectory(dir=HERE) as directory:
                root = Path(directory); data = fixture(root)
                decision = next(iter(data['acceptance']['cells'].values()))
                if change == 'decision': data['acceptance']['decision'] = 'looks_good'
                if change == 'note': data['acceptance'].pop('root_note')
                if change == 'support': decision['support_refs'][0]['supports'].remove('development_validation')
                if change == 'scope': decision['validation_scope']['trial_ids'] = ['unknown']
                if change == 'time': data['acceptance']['accepted_at_utc'] = '2020-01-01T00:00:00Z'
                if change == 'bytes': data['artifact'].write_text('modified', encoding='utf-8')
                if change == 'inventory': data['assessment']['consumed_files'] = []
                if change == 'sources': data['assessment'].pop('assessor_dependency_sha256')
                if change in ('inventory', 'sources'):
                    updated = write(data['assessment_path'], data['assessment'])
                    data['acceptance']['assessment_sha256'] = updated['sha256']
                write(data['acceptance_path'], data['acceptance'])
                with self.assertRaises(ValueError): self.assemble(data, root / 'refused')

    def test_forged_receipt_or_output_binding_is_rejected(self):
        for change in ('status', 'identity', 'output'):
            with self.subTest(change=change), TemporaryDirectory(dir=HERE) as directory:
                root = Path(directory); data = fixture(root)
                receipt = json.loads(data['receipt_path'].read_text(encoding='utf-8'))
                if change == 'status': receipt['exit_status'] = 1
                if change == 'identity': receipt['id'] = 'different'
                if change == 'output':
                    receipt['argv'][-1] = str(root / 'unrelated')
                    data['assessment']['assessment_queue']['argv'] = receipt['argv']
                    write(data['assessment_path'], data['assessment'])
                write(data['receipt_path'], receipt)
                with self.assertRaises(ValueError): self.assemble(data, root / 'refused')

    def test_loader_rejects_changed_completed_bundle_and_missing_retained_evidence(self):
        for change in ('bundle', 'evidence'):
            with self.subTest(change=change), TemporaryDirectory(dir=HERE) as directory:
                root = Path(directory); data = fixture(root); report = self.assemble(data, root / 'assembled')
                loader, _ = assembly.runtime_modules()
                path = Path(report['development_freeze_path']); freeze = json.loads(path.read_text(encoding='utf-8'))
                if change == 'bundle':
                    bundle_path = Path(report['bundle_path']); bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
                    bundle['cells'][0]['route_envelope']['joint_start_ranges_rad'][0] = [-100, 100]
                    write(bundle_path, bundle)
                else: data['artifact'].unlink()
                with self.assertRaises(loader.CalibrationInputError): loader.load_restart_qualification(freeze, path)

    def test_missing_loader_fields_are_not_manufactured(self):
        with TemporaryDirectory(dir=HERE) as directory:
            root = Path(directory); data = fixture(root)
            data['rule']['cells'][0].pop('maximum_qualified_absence_s')
            new_rule = write(data['rule_path'], data['rule'])
            data['assessment']['rule_ref'] = new_rule
            data['assessment']['canonical_rule_sha256'] = digest(data['rule'])
            data['assessment']['consumed_files'][0] = new_rule
            new_assessment = write(data['assessment_path'], data['assessment'])
            data['acceptance']['rule_sha256'] = new_rule['sha256']
            data['acceptance']['assessment_sha256'] = new_assessment['sha256']
            first = data['rule']['cells'][0]
            data['acceptance']['cells'][first['cell_id']]['provisional_cell_sha256'] = digest(first)
            write(data['acceptance_path'], data['acceptance'])
            with self.assertRaises(ValueError): self.assemble(data, root / 'refused')
            self.assertFalse((root / 'refused/assembly.json').exists())

    def test_actual_shaped_archived_sources_bind_and_preserve_member_provenance(self):
        with TemporaryDirectory(dir=HERE) as directory:
            root = Path(directory); data = fixture(root)
            archive, members = archived_sources(data)
            report = self.assemble(data, root / 'assembled')
            self.assertEqual(report['loader_validation'], 'pass')
            bundle = json.loads(Path(report['bundle_path']).read_text(encoding='utf-8'))
            self.assertEqual(bundle['archive_member_refs'], report['archive_member_refs'])
            actual = {item['member']: item for item in bundle['archive_member_refs']}
            self.assertEqual(set(actual), {member for member, _ in members.values()})
            for member, raw in members.values():
                self.assertEqual(actual[member], {'archive': str(archive.resolve()), 'member': member,
                    'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'archive_ref': ref(archive)})
            inventory = {item['path']: item['sha256'] for item in bundle['artifact_files']}
            self.assertEqual(inventory[str(archive.resolve())], ref(archive)['sha256'])
            for original, actual_cell in zip(data['rule']['cells'], bundle['cells']):
                self.assertEqual({key: actual_cell[key] for key in original}, original)

    def test_archive_and_member_tampering_are_independently_rejected(self):
        for change in ('archive_bytes', 'member_bytes_rebound_archive'):
            with self.subTest(change=change), TemporaryDirectory(dir=HERE) as directory:
                root = Path(directory); data = fixture(root)
                archive, members = archived_sources(data)
                if change == 'archive_bytes':
                    archive.write_bytes(b'changed archive')
                else:
                    with zipfile.ZipFile(archive, 'w') as bundle:
                        for index, (member, raw) in enumerate(members.values()):
                            bundle.writestr(member, raw + b'# tampered\n' if index == 0 else raw)
                    data['assessment']['consumed_files'][-1] = ref(archive)
                    refresh_assessment(data)
                with self.assertRaisesRegex(ValueError, 'Input hash differs|Archive member hash differs'):
                    self.assemble(data, root / 'refused')
                self.assertFalse((root / 'refused').exists())

    def test_archived_sources_require_consumed_archive_and_unique_exact_member(self):
        for change in ('unconsumed', 'missing_member', 'duplicate_member', 'mixed_reference'):
            with self.subTest(change=change), TemporaryDirectory(dir=HERE) as directory:
                root = Path(directory); data = fixture(root)
                archive, members = archived_sources(data)
                if change == 'unconsumed':
                    data['assessment']['consumed_files'].pop()
                if change == 'missing_member':
                    data['assessment']['numeric_source_ref']['member'] = 'Runtime/missing.py'
                if change == 'duplicate_member':
                    member, raw = members['numeric_source_ref']
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore', UserWarning)
                        with zipfile.ZipFile(archive, 'a') as bundle:
                            bundle.writestr(member, raw)
                    data['assessment']['consumed_files'][-1] = ref(archive)
                if change == 'mixed_reference':
                    data['assessment']['numeric_source_ref']['path'] = str(archive)
                refresh_assessment(data)
                with self.assertRaises(ValueError):
                    self.assemble(data, root / 'refused')
                self.assertFalse((root / 'refused').exists())


if __name__ == '__main__': unittest.main()
