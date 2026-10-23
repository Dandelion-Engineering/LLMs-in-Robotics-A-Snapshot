"""Synthetic admission checks only; these never import or call the coordinator."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import run_block
from freeze import validate_allocation
from common import sha
from runtime_limits import apply_limits
from scheduler import Schedule


class AdmissionChecks(unittest.TestCase):
    def setUp(self):
        self.original=run_block.AREA
        self.temp=tempfile.TemporaryDirectory(prefix='admission-fixture-',dir=self.original)
        self.root=Path(self.temp.name).resolve()
        assert self.root.is_relative_to(self.original.resolve())
        run_block.AREA=self.root/'scored'
        self.folder=self.root/'release';self.path=self.folder/'blocks/B01/manifest.json'
        self.allocation=dict(schema='campaign003-scored-allocation-1',id='synthetic-test',encounters_per_block=3,
            no_replacements=True,task_failure_policy='stop_this_block_continue_next_independent_block',
            infrastructure_failure_policy='stop_campaign_remaining_slots_not_run',
            capacity_failure_policy='stop_admission_preserve_evidence_no_reserve_relaxation',
            independent_unit='persistent_block',rationale='Synthetic fixture only',runtime_storage_basis='not experimental data',
            blocks=[dict(id='B01',seed=173,noise_seed=101,schedule_seed=201),dict(id='B02',seed=173,noise_seed=102,schedule_seed=202)])
        self.write(self.folder/'allocation.json',self.allocation)
        self.audit=self.root/'pilot/receipt.json';self.status=self.root/'pilot/official-status.json'
        self.write(self.audit,dict(passed=True,qualification_complete=True,measurements=dict(terminal_appends=3)))
        self.write(self.status,dict(state='succeeded',exit_status=0))
        self.manifest=dict(stage='reviewed_campaign',revision_id='synthetic',run_id='synthetic-B01-attempt',
            encounter_limit=3,no_replacement=True,
            model=dict(name='gpt-6-astra',effort='max',auth='chatgpt',bootstrap='Follow the instructions in RobotAgentPrompt.md.',fallback=False),
            apparatus_manifest=apply_limits(dict(run_id='synthetic-B01-attempt',seed=173,noise_seed=101,schedule_seed=201,
                encounters=3,initial_order=Schedule(201,3).current,mode='serve',stage='reviewed_campaign'),'reviewed_campaign'),
            output=str(run_block.AREA/'evidence/synthetic-B01-attempt'),
            allocation_reference=dict(path=str(self.folder/'allocation.json'),sha256=sha(self.folder/'allocation.json'),block_id='B01',replicate=1),
            prerequisite_audit=dict(path=str(self.audit),sha256=sha(self.audit),official_status_path=str(self.status),official_status_sha256=sha(self.status)))
        self.seal()

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')

    def seal(self):
        self.write(self.path,self.manifest)
        self.write(self.folder/'freeze-receipt.json',dict(revision_id='synthetic',scored_model_calls_at_freeze=0,
            qualified_pilot_sources_unchanged=True,allocation_sha256=sha(self.folder/'allocation.json'),
            manifests={'blocks/B01/manifest.json':sha(self.path)}))

    def tearDown(self):
        run_block.AREA=self.original
        # Recursive cleanup is restricted to this newly created fixture directory.
        assert self.root.is_relative_to(self.original.resolve()) and self.root.name.startswith('admission-fixture-')
        self.temp.cleanup()

    def test_valid_first_block_declaration_without_any_launch(self):
        self.assertEqual(run_block.check_manifest(self.path)['run_id'],'synthetic-B01-attempt')

    def test_changed_manifest_and_existing_attempt_are_refused(self):
        self.manifest['model']['name']='other';self.write(self.path,self.manifest)
        with self.assertRaises(AssertionError):run_block.check_manifest(self.path)
        self.manifest['model']['name']='gpt-6-astra';self.seal()
        Path(self.manifest['output']).mkdir(parents=True)
        with self.assertRaises(AssertionError):run_block.check_manifest(self.path)

    def test_even_resealed_unapproved_model_or_limits_are_refused(self):
        self.manifest['model']['fallback']=True;self.seal()
        with self.assertRaises(AssertionError):run_block.check_manifest(self.path)
        self.manifest['model']['fallback']=False;self.manifest['apparatus_manifest']['model_timeout_s']=3601;self.seal()
        with self.assertRaises(AssertionError):run_block.check_manifest(self.path)

    def test_failed_pilot_and_boolean_exit_code_are_refused(self):
        self.write(self.audit,dict(passed=True,qualification_complete=False,measurements=dict(terminal_appends=1)))
        self.manifest['prerequisite_audit']['sha256']=sha(self.audit);self.seal()
        with self.assertRaises(AssertionError):run_block.check_manifest(self.path)
        self.write(self.audit,dict(passed=True,qualification_complete=True,measurements=dict(terminal_appends=3)))
        self.write(self.status,dict(state='succeeded',exit_status=False))
        self.manifest['prerequisite_audit'].update(sha256=sha(self.audit),official_status_sha256=sha(self.status));self.seal()
        with self.assertRaises(AssertionError):run_block.check_manifest(self.path)

    def test_replacements_and_duplicate_replicates_are_refused(self):
        value=copy.deepcopy(self.allocation);value['no_replacements']=False
        with self.assertRaises(AssertionError):validate_allocation(value)
        value=copy.deepcopy(self.allocation);value['blocks'][1]['noise_seed']=101
        with self.assertRaises(AssertionError):validate_allocation(value)


if __name__=='__main__':unittest.main()
