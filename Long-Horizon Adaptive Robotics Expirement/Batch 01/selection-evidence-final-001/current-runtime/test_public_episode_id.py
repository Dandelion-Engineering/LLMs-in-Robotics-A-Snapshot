"""Synthetic identity/dispatch regressions; no physics, inference or queue jobs."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import experiment
import protocol
import release_runner as runner
import sandbox
from test_experiment import Clock, FakeResourceSampler, ImmediateExecutor, fake_cell


class PublicEpisodeIdentityTests(unittest.TestCase):
    def context(self,root,condition='persistent',**changes):
        manifest={'release_id':'identity-fixture','paired_block_id':'identity-fixture-short-nominal-rep1',
                  'run_id':'identity-fixture-short-nominal-rep1-A1-'+condition,'architecture':'A1',
                  'parts':3,'cap_s':.3,'condition':condition,'scenario':'nominal',
                  'seeds':{'world_seed':112233445566,'layout_seed':223344556677,
                           'noise_seed':334455667788,'policy_seed':44556677}}
        manifest.update(changes)
        # Synthetic issued-context fixture, never a release/readiness authorizer.
        return runner.VerifiedEvaluationContext(Path(root),json.dumps(manifest),'r'*64,'m'*64,
            'synthetic-queue','synthetic-time','{}',runner._AUTHORITY)

    def test_all_72_planned_controls_share_their_matched_identity(self):
        slots=protocol.public_run_slots('identity-fixture')
        controls=[m for m in slots if m['condition']=='no-persistence']
        self.assertEqual(len(slots),264);self.assertEqual(len(controls),72)
        identities={}
        for m in slots:
            key=(m['paired_block_id'],m['architecture'])
            value=runner.matched_public_episode_id(m['release_id'],*key)
            if key in identities:self.assertEqual(value,identities[key])
            identities[key]=value
        self.assertEqual(len(set(identities.values())),192)

    def test_distinct_case_replicate_entrant_and_release(self):
        values=[('rel','rel-case1-rep1','A1'),('rel','rel-case2-rep1','A1'),
                ('rel','rel-case1-rep2','A1'),('rel','rel-case1-rep1','A2'),
                ('other','rel-case1-rep1','A1')]
        self.assertEqual(len({runner.matched_public_episode_id(*v) for v in values}),len(values))

    def test_exact_versioned_formula_and_unambiguous_field_encoding(self):
        expected='episode-'+hashlib.sha256(protocol.canonical(
            ['candidate-episode-identity-v1','rel','rel-case1-rep1','A1'])).hexdigest()
        self.assertEqual(runner.matched_public_episode_id('rel','rel-case1-rep1','A1'),expected)
        self.assertNotEqual(runner.matched_public_episode_id('a-b','c','A1'),
                            runner.matched_public_episode_id('a','b-c','A1'))

    def test_condition_protected_id_and_all_seed_roles_do_not_participate(self):
        persistent=self.context('/synthetic')
        control=self.context('/synthetic','no-persistence',run_id='private-condition-no-persistence',
            seeds={'world_seed':9,'layout_seed':8,'noise_seed':7,'policy_seed':6})
        self.assertEqual(persistent.public_episode_id,control.public_episode_id)
        self.assertRegex(control.public_episode_id,r'^episode-[0-9a-f]{64}$')
        for forbidden in ('persistent','no-persistence','identity-fixture','A1','world_seed',
                          'layout_seed','policy_seed','noise_seed','112233445566','223344556677'):
            self.assertNotIn(forbidden,persistent.public_episode_id)

    def test_bad_identity_is_rejected(self):
        for args in [('', 'block','A1'),('r',None,'A1'),('r','block','unknown')]:
            with self.subTest(args=args),self.assertRaises(runner.ReleaseError):
                runner.matched_public_episode_id(*args)

    def run_synthetic(self,context=None,development_id=None):
        clock=Clock();cell=fake_cell();worker=MagicMock();worker.alive=True;worker.ready={}
        cell.public_packet.side_effect=lambda order,run_id,incarnation,sequence: {
            'run_id':run_id,'incarnation':incarnation,'sequence':sequence,'sim_time':cell.data.time,
            'order':order,'detections':[]}
        worker.receive.return_value={'type':'step','response':{'type':'wait'},'events':[]}
        executor=ImmediateExecutor(MagicMock(),None)
        kwargs=context.episode_kwargs() if context else {'run_id':development_id,'cap':.3}
        with patch.object(experiment,'ResourceSampler',FakeResourceSampler), \
             patch.object(experiment,'initial_world_report',return_value={'valid':True,'errors':[]}), \
             patch.object(experiment,'Cell',return_value=cell), \
             patch.object(sandbox,'CandidateSandbox',return_value=worker) as sandbox_factory, \
             patch.object(experiment,'ThreadPoolExecutor',return_value=executor), \
             patch.object(experiment.time,'perf_counter',side_effect=clock.now), \
             contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(**kwargs)
        path=context.evidence_dir if context else experiment.EVIDENCE/development_id
        manifest=json.loads((path/'manifest.json').read_text())
        events=[json.loads(line) for line in (path/'events.jsonl').read_text().splitlines()]
        packets=[call.args[0]['packet'] for call in worker.send.call_args_list if call.args[0]['type']=='step']
        self.assertTrue(packets);self.assertIsNone(result['error'])
        return result,manifest,events,packets,sandbox_factory.call_args

    def test_dispatch_public_id_and_protected_ids_paths_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            all_paths=[];all_public=[]
            for condition in ('persistent','no-persistence'):
                context=self.context(directory,condition)
                result,manifest,events,packets,start=self.run_synthetic(context)
                protected=context.manifest['run_id'];public=context.public_episode_id
                self.assertEqual(result['run_id'],protected);self.assertEqual(manifest['run_id'],protected)
                self.assertEqual(manifest['candidate_public_episode_id'],public)
                self.assertTrue(all(e['run_id']==protected for e in events))
                self.assertTrue(all(p['run_id']==public for p in packets))
                exact_inputs=[e['payload']['message']['packet'] for e in events if
                    e['event_type']=='candidate_input' and e['payload']['message']['type']=='step']
                self.assertEqual(exact_inputs,packets)
                for p in packets:
                    self.assertNotIn(protected,json.dumps(p));self.assertNotIn('condition',p)
                    self.assertNotIn('release_id',p);self.assertNotIn('seeds',p)
                expected=Path(directory)/'attempts'/protected/'evidence'
                self.assertEqual(context.evidence_dir,expected)
                self.assertEqual(start.args[1],expected/'candidate_state')
                self.assertEqual(start.kwargs['persistent'],condition=='persistent')
                self.assertTrue((expected/'result.json').exists())
                all_paths.append(start.args[1]);all_public.append(public)
            self.assertNotEqual(*all_paths);self.assertEqual(*all_public)

    def test_development_public_id_stays_verbatim(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(experiment,'EVIDENCE',Path(directory)):
            result,manifest,events,packets,_=self.run_synthetic(development_id='legacy-dev-persistent')
        self.assertEqual(result['run_id'],'legacy-dev-persistent')
        self.assertEqual(manifest['candidate_public_episode_id'],'legacy-dev-persistent')
        self.assertTrue(all(p['run_id']=='legacy-dev-persistent' for p in packets))

    def test_unissued_context_cannot_create_evidence_or_reach_cell(self):
        with tempfile.TemporaryDirectory() as directory:
            issued=self.context(directory)
            forged=runner.VerifiedEvaluationContext(issued.release_dir,issued.manifest_json,'r','m','q','t','{}')
            with patch.object(experiment,'Cell') as factory,self.assertRaises(runner.ReleaseError):
                experiment.run_episode(**forged.episode_kwargs())
            factory.assert_not_called();self.assertFalse(forged.evidence_dir.exists())


if __name__=='__main__':unittest.main()
