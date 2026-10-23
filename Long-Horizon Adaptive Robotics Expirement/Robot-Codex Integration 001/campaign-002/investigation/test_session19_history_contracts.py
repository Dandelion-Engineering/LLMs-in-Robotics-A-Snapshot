"""Synthetic metadata-only fixtures for Session19 historical presentation."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import qualification_report as report
import qualification_qa as qa
import test_qualification_report as prior


class Session19Contracts(unittest.TestCase):
    setUp=prior.CompanionIntegrity.setUp
    tearDown=prior.CompanionIntegrity.tearDown
    save=prior.CompanionIntegrity.save
    artifact=prior.CompanionIntegrity.artifact
    failed_queue_fixture=prior.CompanionIntegrity.failed_queue_fixture
    failed_single_interrupt_fixture=prior.CompanionIntegrity.failed_single_interrupt_fixture

    def fresh_row(self):
        self.row={'run_id':self.run_id,'revision':'dev-fixture','queue':{'id':self.job['id']},
                  'reason':'Synthetic metadata only.'}

    def rebind(self):
        self.save(self.queue_path,self.job)
        artifacts=[self.artifact(self.queue_path,'Official queue receipt'),
            self.artifact(self.manifest,'Frozen attempt manifest'),self.artifact(self.snapshot,'Frozen source snapshot')]
        self.row['artifacts']=artifacts
        key='queue_completion_contract' if 'queue_completion_contract' in self.row else 'queue_failure_contract'
        self.row[key].update({k:artifacts[n]['sha256'] for n,k in enumerate(
            ['official_queue_sha256','manifest_sha256','snapshot_sha256'])})

    def diagnostic(self,version):
        self.fresh_row()
        self.failed_single_interrupt_fixture(version=3)
        old=copy.deepcopy(json.loads(Path(self.row['artifacts'][1]['path']).read_bytes()))
        rev={5:'097',6:'098'}[version];run=f'RCI001-C02-shutdown-diagnostic-{version:03d}'
        self.manifest=self.campaign/f'io-repair/shutdown-diagnostic-{version:03d}/manifest.json'
        self.snapshot=self.campaign.parent.parent/f'Architecture Map/releases/RCI001-C02-dev-{rev}/snapshot.json'
        sources=report.OBSERVED_INTERRUPT_SOURCES if version==5 else report.GRACEFUL_INTERRUPT_SOURCES
        declared={(self.campaign/n).relative_to(self.root).as_posix():v for n,v in sources.items()}
        workspace=Path(report.os.environ['LOCALAPPDATA'])/'RobotCodex/Campaign002/diagnostic'/run
        old.update(run_id=run,framework_revision='RCI001-C02-dev-'+rev,
            outer_campaign_protocol=f'RCI001-Campaign002-single-interrupt-diagnostic-v{version}',
            runtime_workspace=str(workspace),runtime_input_files=list(declared))
        self.save(self.manifest,old)
        self.save(self.snapshot,{'schema':'robot-codex-readiness-source-1','run_id':run,
            'revision':'RCI001-C02-dev-'+rev,'manifest_sha256':report.sha(self.manifest.read_bytes()),'sources':declared})
        root=self.campaign.parent/'local-evidence/campaign002/io-repair'/run
        exe=str(self.root/'venv/Scripts/python.exe')
        self.job.update(argv=[exe,'-X','utf8','-B',str(self.campaign/f'io-repair/single-interrupt-diagnostic-v{version}/run.py'),
            '--manifest',str(self.manifest),'--snapshot',str(self.snapshot),'--evidence',str(root/'orchestrator'),
            '--host-evidence',str(root/'host'),'--workspace',str(workspace)])
        self.row.update(run_id=run,revision='RCI001-C02-dev-'+rev)
        if version==5:
            self.job['argv'] += ['--observer-config-sha256','33948458d956c920ed1a24dd3f262f115b220dc0b3e113bf487ecb269ee1212c']
        else:
            self.job.update(state='succeeded',exit_status=0)
            self.row.update(status='completed',queue_completion_contract={'schema':report.COMPLETED_INTERRUPT_SCHEMA})
            self.row.pop('queue_failure_contract')
        self.rebind()

    def boundary(self):
        self.fresh_row()
        self.failed_queue_fixture()
        run='RCI001-C02-boundary-031';rev='RCI001-C02-dev-105'
        self.manifest=self.qual/'boundary-031-manifest.json'
        self.snapshot=self.campaign.parent.parent/'Architecture Map/releases'/rev/'snapshot.json'
        script=self.qual/'boundary_suite_v3.py';name=script.relative_to(self.root).as_posix()
        self.save(self.manifest,{'run_id':run,'framework_revision':rev,'stage':'diagnostic','mode':'boundary-suite',
            'qualification_stage':'no-model-isolation-control-continuity','model_turns_max':0,'runtime_input_files':[name]})
        self.save(self.snapshot,{'schema':'robot-codex-readiness-source-1','run_id':run,'revision':rev,
            'manifest_sha256':report.sha(self.manifest.read_bytes()),'sources':{name:{'sha256':'a'*64,'bytes':123}}})
        exe=str(self.root/'venv/Scripts/python.exe')
        self.job.update(cwd=str(self.root),resolved_executable=exe,
            argv=[exe,'-X','utf8','-B',str(script),'--output',str(self.campaign.parent/'local-evidence/campaign002/qualification'/run)])
        self.row.update(run_id=run,revision=rev,queue_failure_contract={'schema':report.FAILED_BOUNDARY_SCHEMA})
        self.rebind()

    def render(self,guard_reads=False):
        original=Path.read_bytes;allowed={Path(a['path']).resolve() for a in self.row['artifacts']};opened=[]
        def guarded(path):
            self.assertIn(path.resolve(),allowed);opened.append(path.resolve());return original(path)
        with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),patch.multiple(qa,CAMPAIGN=self.campaign,REPO=self.root),\
                patch.object(Path,'read_bytes',guarded if guard_reads else original):
            result=report.qualification_row(self.row,self.output)
            check=qa.completed_diagnostic_guard if 'queue_completion' in result else qa.failed_queue_guard
            self.assertEqual(check(result,self.output),[])
        if guard_reads:self.assertEqual(set(opened),allowed)
        return result

    def test_all_three_branches_read_only_three_metadata_files(self):
        for make in [lambda:self.diagnostic(5),lambda:self.diagnostic(6),self.boundary]:
            make();result=self.render(True)
            self.assertEqual(result['checks'],{});self.assertIsNone(result['model_calls'])
            self.assertIsNone(result['timing']);self.assertEqual(result['task_outcome'],'unknown')
            self.assertFalse(result['scorable'])

    def test_observer_digest_and_exact_dispatch_cannot_change(self):
        for index in [0,4,-1]:
            self.diagnostic(5);self.job['argv'][index]='wrong';self.rebind()
            with self.assertRaisesRegex(ValueError,'dispatch'):self.render()

    def test_diagnostic_sources_and_manifest_caps_fail_closed(self):
        for version in [5,6]:
            self.diagnostic(version)
            frozen=json.loads(self.snapshot.read_bytes());first=next(iter(frozen['sources']))
            frozen['sources'][first]['sha256']='0'*64;self.save(self.snapshot,frozen);self.rebind()
            with self.assertRaisesRegex(ValueError,'source'):self.render()
            self.diagnostic(version)
            value=json.loads(self.manifest.read_bytes());value['model_turns_max']=2
            self.save(self.manifest,value);self.rebind()
            with self.assertRaisesRegex(ValueError,'scope or original cap'):self.render()

    def test_completion_does_not_accept_observer_diagnostic_or_failed_exit(self):
        self.diagnostic(5)
        self.row['queue_completion_contract']=self.row.pop('queue_failure_contract')
        self.row['queue_completion_contract']['schema']=report.COMPLETED_INTERRUPT_SCHEMA
        self.row['status']='completed';self.job.update(state='succeeded',exit_status=0);self.rebind()
        with self.assertRaisesRegex(ValueError,'declared'):self.render()
        self.diagnostic(6);self.job.update(state='failed',exit_status=1);self.rebind()
        with self.assertRaisesRegex(ValueError,'succeeded'):self.render()

    def test_boundary_dispatch_snapshot_and_scope_are_exact(self):
        for mutation in ['output','revision','mode','boolean-model-count','missing-source']:
            self.boundary()
            if mutation=='output':self.job['argv'][-1]='elsewhere'
            elif mutation in ['mode','boolean-model-count']:
                value=json.loads(self.manifest.read_bytes())
                value['mode' if mutation=='mode' else 'model_turns_max']='serve' if mutation=='mode' else False
                self.save(self.manifest,value)
            else:
                value=json.loads(self.snapshot.read_bytes())
                if mutation=='revision':value['revision']='wrong'
                else:value['sources']={}
                self.save(self.snapshot,value)
            self.rebind()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.render()

    def test_unknown_rows_cannot_acquire_qualification_or_measurements(self):
        for version in [5,6]:
            for field,value in [('model_calls',1),('validity','valid'),('details',{'passed':True}),('scorable',True)]:
                self.diagnostic(version);self.row[field]=value
                with self.subTest(version=version,field=field),self.assertRaises(ValueError):self.render()

    def test_report_and_independent_guard_pin_identical_metadata_sources(self):
        self.assertEqual(report.OBSERVED_INTERRUPT_SOURCES,qa.OBSERVED_INTERRUPT_SOURCES)
        self.assertEqual(report.GRACEFUL_INTERRUPT_SOURCES,qa.GRACEFUL_INTERRUPT_SOURCES)


if __name__=='__main__':unittest.main()
