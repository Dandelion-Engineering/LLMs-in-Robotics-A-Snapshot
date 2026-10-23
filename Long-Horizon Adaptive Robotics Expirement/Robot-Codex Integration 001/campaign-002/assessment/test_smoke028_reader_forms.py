"""Prospective complete-stream and literal-form adversarial controls; no models."""
import copy
import json
import shlex
import unittest
import completion_chronology as chronology
import initial_read_composition as initial
import retained_reads as retained
import canary_readback_proof as readback
import test_retained_reads as captures
import test_completion_chronology as clocks
import test_initial_read_composition as prefixes
import test_canary_readback_proof as readback_fixtures


class LateExitTests(unittest.TestCase):
    def setUp(self):
        self.f=captures.CapturedReadsTests();self.f.setUp();self.addCleanup(self.f.tearDown)

    def messages(self):
        original=self.f.sequence_case()
        return [original[i] for i in (0,2,3,4,1)]

    def test_complete_late_exit_preserves_arrival_and_bytes(self):
        commands,audit=self.f.read_sequence_case(self.messages(),projection='firstsecondthird')
        self.assertTrue(audit['verified']);self.assertEqual(len(commands),1)
        p=commands[0]['executor_provenance']
        self.assertEqual(p['process_sequence_order'],[1,2,4,5,3])
        self.assertEqual(p['output_sequence_order'],[1,2,4])
        self.assertEqual(p['closed_sequence'],5);self.assertEqual(p['exit_sequence'],3)
        self.assertTrue(p['exit_arrived_after_close'])
        self.assertEqual(commands[0]['aggregatedOutput'],'firstsecondthird')

    def test_late_exit_keeps_all_delivery_and_redaction_requirements(self):
        for method in ('process/output','process/exited','process/closed'):
            with self.subTest(method=method):
                self.assertEqual(self.f.read_sequence_case(self.messages(),omit_delivery=method)[0],[])
        m=self.messages();m[-1]['params']['exitCode']=1
        self.assertEqual(self.f.read_sequence_case(m)[0],[])
        for code in (True,None,'0',0.0):
            m=self.messages();m[-1]['params']['exitCode']=code
            self.assertEqual(self.f.read_sequence_case(m)[0],[])
        m=self.messages();m[-1]['params']['sandboxDenied']=True
        self.assertEqual(self.f.read_sequence_case(m)[0],[])

    def test_only_exit_can_arrive_after_unique_maximum_close(self):
        original=self.messages()
        cases=[]
        m=copy.deepcopy(original);m[2],m[3]=m[3],m[2];cases.append(m)
        m=copy.deepcopy(original);m[0],m[1]=m[1],m[0];cases.append(m)
        m=copy.deepcopy(original);m[3]['params']['seq']=4;m[2]['params']['seq']=5;cases.append(m)
        m=copy.deepcopy(original);m.append(copy.deepcopy(m[-1]));cases.append(m)
        m=copy.deepcopy(original[:-1]);cases.append(m)
        for seq in (True,None,3,6,'2',2.0):
            m=copy.deepcopy(original);m[1]['params']['seq']=seq;cases.append(m)
        for i,m in enumerate(cases):
            with self.subTest(case=i):self.assertEqual(self.f.read_sequence_case(m)[0],[])

    def test_chronology_includes_late_exit_delivery_without_moving_close(self):
        f=clocks.CompletionChronologyTests();f.setUp()
        f.rows[6]['message'],f.rows[8]['message']=f.rows[8]['message'],f.rows[6]['message']
        f.emitted_ms=100650
        p=f.proof()
        self.assertTrue(p['exit_arrived_after_close'])
        self.assertEqual(p['closed_capture_sequence'],7)
        self.assertEqual(p['closed_wall_unix_s'],100.6)
        self.assertEqual(p['evidence_complete_upper_decimal_seconds'],'100.9')
        self.assertFalse(p['evidence_complete_upper_wall_unix_s']<100.9)
        f.delivered.remove(9)
        with self.assertRaisesRegex(ValueError,'required process delivery'):f.proof()

    def test_complete_census_retains_actual_close_row(self):
        f=readback_fixtures.Capture();f.add('open')
        request=f.process('cat /workspace/Robot.md',stdout=b'robot')
        end=[r for r in f.rows if (r.get('message') or {}).get('method') in ('process/exited','process/closed')]
        end[0]['message'],end[1]['message']=end[1]['message'],end[0]['message']
        record=readback.process_record(f.rows,f.delivered,request,f.events)
        self.assertEqual(record['closed_sequence'],end[0]['sequence'])
        self.assertTrue(record['execution']['exit_arrived_after_close'])


class FilteredPrefixTests(unittest.TestCase):
    def setUp(self):
        self.f=prefixes.InitialReadCompositionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.command='cat /workspace/Continuity.md && '+initial.FILTERED_FIND_SCRIPT

    def test_complete_initial_bytes_covered_with_three_root_exclusion(self):
        self.f.prefix(command=self.command,tail=b'/workspace/live/observations/a\n')
        p=self.f.accepted()
        self.assertEqual(p['excluded_find_initial_prefixes'],[x.decode() for x in initial.FILTERED_ROOT_PREFIXES])
        self.assertFalse(p['whole_current_file_identity_claimed'])
        self.assertFalse(p['remainder_listing_snapshot_claimed'])
        self.assertEqual(p['segment']['bytes'],len(self.f.note))

    def test_live_root_occurrence_and_every_boundary_straddle_are_rejected(self):
        root=b'/workspace/live'
        self.f.prefix(note=b'prefix\n'+root+b'/a\n',command=self.command)
        self.f.rejected()
        for n in range(1,len(root)):
            with self.subTest(n=n),self.assertRaisesRegex(ValueError,'straddle'):
                initial.prefix_attribution(b'note\n'+root[:n],b'note\n'+root+b'/a\n',initial.FILTERED_ROOT_PREFIXES)

    def test_no_find_byte_can_enter_initial_prefix_for_any_split(self):
        accepted=0
        for cat in (b'',b'plain\n',b'/work',b'changed note\n'):
            for root in initial.FILTERED_ROOT_PREFIXES:
                for name in (b'/a\n',b'/name\nforged note\n',b'/x\n/workspace/live/z\n'):
                    raw=cat+root+name
                    for n in range(1,len(raw)+1):
                        try:initial.prefix_attribution(raw[:n],raw,initial.FILTERED_ROOT_PREFIXES)
                        except ValueError:continue
                        accepted+=1;self.assertLessEqual(n,len(cat),(cat,root,name,n))
        self.assertGreater(accepted,0)

    def test_mutated_shell_or_find_grammar_is_not_interpreted(self):
        attacks=[self.command+'; true',self.command+' && cat Robot.md',self.command+'\n',
            self.command.replace('&&','||'),self.command.replace('&&',';'),
            self.command.replace('find ','find -L '),self.command.replace('-print','-print0'),
            self.command.replace('-print','-exec echo {} \\;'),self.command.replace('-maxdepth 3','-maxdepth 4'),
            self.command.replace('/workspace/live','/workspace/.continuity'),self.command+' > notes/out',
            self.command.replace('! -name endpoint.json ','')]
        for body in attacks:
            with self.subTest(body=body):self.assertFalse(initial.find_prefix_recipe(['/usr/bin/bash','-lc',body]))

    def test_shortened_projection_or_missing_initial_byte_is_not_admitted(self):
        self.f.prefix(command=self.command,projection='tail');self.f.rejected()
        self.f.prefix(command=self.command)
        self.f.f.make_capture(self.command,output=(self.f.note[:-1]+b'/workspace/live/x\n').decode())
        self.f.rejected()


class ConditionalCanaryTests(unittest.TestCase):
    BODY='python3 /canary.py > notes/resume-boundary-observation.json && cat notes/resume-boundary-observation.json'

    def recipe(self,body):return retained.canary_recipe({'command':shlex.join(['/usr/bin/bash','-lc',body])})

    def test_exact_literal_recipe_joins_full_capture_and_named_note(self):
        f=captures.CapturedReadsTests();f.setUp();self.addCleanup(f.tearDown)
        doc={'qualified':True,'checks':dict.fromkeys([str(i) for i in range(45)],True),'details':{}}
        raw=json.dumps(doc).encode();_,events=f.make((raw,),projection=raw.decode(),command=self.BODY)
        commands,audit=retained.authenticated_commands(f.root,events)
        self.assertTrue(audit['verified'])
        matches=retained.canary_matches(commands,{'notes/resume-boundary-observation.json':raw},doc)
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['recipe']['form'],'conditional_redirect_then_read')
        self.assertEqual(retained.canary_matches(commands,{'notes/boundary-observation.json':raw},doc),[])
        doc['checks']['0']=False
        self.assertEqual(retained.canary_matches(commands,{'notes/resume-boundary-observation.json':json.dumps(doc).encode()},doc),[])

    def test_unknown_operators_paths_commands_redirection_and_newline_rejected(self):
        attacks=[self.BODY.replace('&&',';'),self.BODY.replace('&&','||'),self.BODY+'; true',
            self.BODY+' && echo done',self.BODY+'\n',self.BODY.replace(' > ',' >> '),
            self.BODY.replace(' && ',' 2> notes/err && '),self.BODY.replace('/canary.py','notes/canary.py'),
            self.BODY.replace('notes/','notes/../'),self.BODY.replace('notes/','notes/./'),
            self.BODY.replace('cat notes/resume','cat notes/different'),self.BODY+' #comment',
            self.BODY.replace('cat ','cat -n '),self.BODY.replace('python3 ','env python3 ')]
        for body in attacks:
            with self.subTest(body=body):self.assertIsNone(self.recipe(body))

    def test_older_direct_newline_and_status_preserving_forms_remain(self):
        self.assertEqual(self.recipe('python3 /canary.py')['form'],'direct')
        self.assertEqual(self.recipe(self.BODY.replace(' && ','\n'))['form'],'redirect_then_read')


if __name__=='__main__':unittest.main()
