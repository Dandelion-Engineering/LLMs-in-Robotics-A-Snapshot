"""Synthetic interruption and supplemental-provenance adversarial checks."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import recovery_contract as c


class DispositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.put('release.json', {'id': 'fixture'})
        self.manifest = self.put('manifest.json', {'run_id': c.ADMIN_RUN})
        receipt = self.put('receipt.json', {'id': c.ADMIN_BATCH, 'state': 'interrupted', 'exit_status': None,
            'error': 'Worker disappeared; job was not retried', 'ended_at': '2026-09-24T20:38:21Z'})
        evidence = [self.put(str(i) + '.json', {'fixture': i}) for i in range(5)]
        partial = self.root / 'raw'; partial.mkdir(); (partial / 'events.jsonl').write_bytes(b'{"partial":true}\n')
        inventory = self.put('inventory.json', {'run_id': c.ADMIN_RUN, 'root': str(partial),
            'complete_raw_result_present': False, 'files': [{**c.ref(partial / 'events.jsonl'),
                'bytes': (partial / 'events.jsonl').stat().st_size}]})
        self.value = {'schema_version': 'administrative-interruption-1', 'annex_id': c.ANNEX_ID,
            'run_id': c.ADMIN_RUN, 'release': self.release, 'manifest': self.manifest,
            'original_queue_job_id': c.ADMIN_BATCH, 'official_receipt': receipt,
            'execution_disposition': 'interrupted', 'validity': 'invalid', 'invalidity_class': 'infrastructure',
            'task_outcome': 'unknown', 'physical_ended_at': None, 'metrics': {},
            'administratively_recorded_at': '2026-09-24T21:00:00Z', 'queue_reconciled_at': '2026-09-24T20:38:21Z',
            'post_run_integrity': {'state': 'missing'}, 'supervisor_terminal': {'state': 'missing'},
            'evidence': evidence, 'partial_evidence_inventory': inventory}

    def put(self, name, value):
        path = self.root / name; path.write_text(json.dumps(value), encoding='utf-8'); return c.ref(path)

    def validate(self, value=None):
        c.validate_disposition(value or self.value, self.release, self.manifest, c.ANNEX_ID)

    def test_unknown_disposition_preserves_partial_inventory(self):
        self.validate(); c.verify_partial_inventory(self.value)

    def test_cannot_assert_success_failure_zero_metrics_or_historical_end(self):
        for key, value in [('task_outcome', 'success'), ('task_outcome', 'failure'),
                           ('metrics', {'model_calls': 0}), ('physical_ended_at', '2026-09-24T20:38:21Z'),
                           ('post_run_integrity', {'passed': True}), ('supervisor_terminal', {'state': 'available'})]:
            with self.subTest(key=key, value=value):
                changed = copy.deepcopy(self.value); changed[key] = value
                with self.assertRaises(c.ContractError): self.validate(changed)

    def test_interrupted_receipt_cannot_be_successful_zero_or_null_missing(self):
        for changes in ({'state': 'succeeded', 'exit_status': 0}, {'exit_status': 0}, {'exit_status': False}, {'id': 'another'}):
            value = copy.deepcopy(self.value); receipt = c.read(c.reference(value['official_receipt'])); receipt.update(changes)
            value['official_receipt'] = self.put('changed-receipt.json', receipt)
            with self.assertRaises(c.ContractError): self.validate(value)

    def test_exact_single_admin_identity(self):
        for key in ('run_id', 'original_queue_job_id', 'annex_id'):
            value = copy.deepcopy(self.value); value[key] += '-another'
            with self.assertRaises(c.ContractError): self.validate(value)

    def test_reconciliation_time_is_bound_but_is_not_physical_end(self):
        value = copy.deepcopy(self.value); value['queue_reconciled_at'] = 'later'
        with self.assertRaises(c.ContractError): self.validate(value)

    def test_changed_partial_bytes_are_detected(self):
        (self.root / 'raw' / 'events.jsonl').write_bytes(b'changed original evidence')
        with self.assertRaises(c.ContractError): c.verify_partial_inventory(self.value)

    def test_new_terminal_in_partial_tree_is_detected(self):
        (self.root / 'raw' / 'result.json').write_text('{}')
        with self.assertRaises(c.ContractError): c.verify_partial_inventory(self.value)

    def test_missing_required_unknown_field_is_not_inferred(self):
        value = copy.deepcopy(self.value); del value['physical_ended_at']
        with self.assertRaises(c.ContractError): self.validate(value)


class SourceTests(unittest.TestCase):
    def test_exact_archive_rejects_unreviewed_added_code_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); code = root / 'supervisor.py'; code.write_bytes(b'# fixture\n')
            bundle = root / 'bundle.zip'
            with zipfile.ZipFile(bundle, 'x') as archive: archive.write(code, code.name)
            index = root / 'index.json'
            index.write_text(json.dumps({'schema_version': 'recovery-source-index-1', 'runtime_root': str(root),
                'files': [{**c.ref(code), 'archive_path': code.name}], 'bundle': c.ref(bundle)}))
            with patch.object(c, 'HERE', root):
                c.verify_source_index(c.ref(index))
                added = root / 'new_policy.py'; added.write_text('# unauthorized')
                with self.assertRaises(c.ContractError): c.verify_source_index(c.ref(index))
                added.unlink(); code.write_text('# changed')
                with self.assertRaises(c.ContractError): c.verify_source_index(c.ref(index))

    def test_adoption_payload_cannot_change_partition_scoring_or_sources(self):
        prepared = {'status': 'prepared', 'remaining_originals': ['one'], 'invariants': {'automatic_retries': 0},
                    'source_index': {'sha256': 'a' * 64}}
        adopted = copy.deepcopy(prepared); adopted.update(status='adopted', adoption={'author': 'root'}, validation={})
        self.assertTrue(c._same_payload(prepared, adopted))
        for key, value in [('remaining_originals', ['one', 'interrupted']), ('invariants', {'automatic_retries': 1}),
                           ('source_index', {'sha256': 'b' * 64})]:
            changed = copy.deepcopy(adopted); changed[key] = value
            self.assertFalse(c._same_payload(prepared, changed))

    def test_unadopted_annex_cannot_authorize_execution(self):
        with self.assertRaisesRegex(c.ContractError, 'not adopted'):
            c.verify_adoption({'status': 'prepared'})

    def test_adoption_requires_successful_exact_validation_output_and_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); exp = root / 'experiment'; here = exp / 'Runtime Recovery 001'; here.mkdir(parents=True)
            def put(name, value):
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding='utf-8'); return c.ref(path)
            evidence = put('evidence.json', {'fixture': True})
            candidate = {'status': 'prepared', 'source_index': evidence, 'analysis_source_index': evidence}
            candidate_ref = put('candidate.json', candidate)
            argv = [str(root / 'venv' / 'Scripts' / 'python.exe'), '-X', 'utf8', '-B',
                str(here / 'prepare_recovery.py'), 'validate', '--annex', candidate_ref['path'], '--output', str(root / 'validation')]
            report = {'prepared_annex': candidate_ref, 'source_index': evidence, 'analysis_source_index': evidence,
                'queue_job_id': 'validation-job', 'queued_argv': argv, 'passed': True,
                'checks': {key: True for key in ('original_release_verified', 'same_physical_source_locations',
                    'partial_inventory_verified', 'retained_originals_verified', 'retained_selection_exactly_equal',
                    'source_diff_restricted', 'tests_passed')}, 'module_locations': evidence,
                'retained_selection_differential': evidence,
                'executions': [{'exit_status': 0, 'stdout': evidence, 'stderr': evidence}] * 2}
            receipt = {'id': 'validation-job', 'state': 'succeeded', 'exit_status': 0, 'argv': argv, 'cwd': str(root)}
            adopted = {**candidate, 'status': 'adopted', 'adoption': {'author': 'Codex session 4', 'recorded_at': 'now',
                'no_policy_or_scoring_change': True, 'authorization': 'fixture', 'contract_departure': 'explicit'},
                'validation': {'prepared_annex': candidate_ref, 'report': put('validation/validation.json', report),
                    'official_receipt': put('receipt.json', receipt)}}
            with patch.object(c, 'EXPERIMENT', exp), patch.object(c, 'HERE', here):
                c.verify_adoption(adopted)
                relocated = copy.deepcopy(adopted)
                relocated['validation']['report'] = put('elsewhere/validation.json', report)
                with self.assertRaisesRegex(c.ContractError, 'another command or output'): c.verify_adoption(relocated)
                for status in (None, False, 1):
                    bad = copy.deepcopy(adopted); invalid = {**receipt, 'exit_status': status}
                    bad['validation']['official_receipt'] = put('invalid-receipt.json', invalid)
                    with self.assertRaises(c.ContractError): c.verify_adoption(bad)
                changed = copy.deepcopy(adopted); changed['analysis_source_index'] = {'path': 'another', 'sha256': '0' * 64}
                with self.assertRaises(c.ContractError): c.verify_adoption(changed)


if __name__ == '__main__':
    unittest.main()
