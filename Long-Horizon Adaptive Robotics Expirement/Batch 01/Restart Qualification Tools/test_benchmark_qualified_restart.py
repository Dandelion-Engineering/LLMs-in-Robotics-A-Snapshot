"""Small synthetic-only benchmark guards; no queue state/native models/physics."""
import copy
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import benchmark_qualified_restart as benchmark
from test_calibration_loader import write_fixture
from test_qualification import fixture as identity_fixture


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')
    return {'path': str(path.resolve()), 'sha256': benchmark.checksum(path), 'bytes': path.stat().st_size}


def args(root, **values):
    return SimpleNamespace(output=str(root/'output'), provisional_rule=None, development_freeze=None,
        assembly=None, assembly_receipt=None, cut_states=None, events=None, **values)


def rich_fixture(root, current_sources=False):
    loader, state, _ = benchmark.modules()
    import test_restart_state
    freeze, freeze_path, _, bundle_path = write_fixture(root)
    bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
    if current_sources:
        sources = {name: benchmark.checksum(benchmark.RUNTIME/name) for name in
            ('cell.py','actuation.py','evaluator.py','sensor_worker.py','restart_state.py',
             'restart_compatibility.py','restart_qualification.py')}
        sources['descriptor_exporter'] = benchmark.checksum(benchmark.RUNTIME/'restart_physical_class.py')
        bundle['class_spec']['required_source_hashes'] = sources
        write(bundle_path, bundle)
        freeze['restart_qualification'].update(sha256=benchmark.checksum(bundle_path),
            bundle_sha256=benchmark.digest(bundle), class_spec_sha256=benchmark.digest(bundle['class_spec']))
        write(freeze_path, freeze)
    _, observation_scene, _ = identity_fixture()
    snapshot = test_restart_state.snapshot()
    observation = observation_scene['physical_class_observation']
    observation['source_hashes'] = copy.deepcopy(bundle['class_spec']['required_source_hashes'])
    snapshot.update(physical_class_observation=observation,
        source_hashes={k:observation['source_hashes'][k] for k in ('cell.py','actuation.py','evaluator.py','sensor_worker.py')},
        physical_configuration_sha256=observation['physical_configuration_sha256'], scene_xml_sha256=observation['scene_xml_sha256'])
    snapshot['geometry']['zones']['parking2'] = copy.deepcopy(bundle['cells'][0]['route_envelope']['destination_region_m'])
    original = copy.deepcopy(snapshot['geometry']['objects'][0])
    for index, row in enumerate(observation['objects']):
        if row['id'] == 'A1':
            continue
        obj = copy.deepcopy(original); position = [.7, .30 + index*.03, .018]
        obj.update(id=row['id'], kind=row['kind'], family=row['family'], gripper_contact=False,
            position=position, bounds={'min':[position[0]-.02,position[1]-.02,0.],
                                      'max':[position[0]+.02,position[1]+.02,.036]})
        snapshot['geometry']['objects'].append(obj)
        contact = copy.deepcopy(snapshot['contacts']['by_object']['A1'])
        contact.update(hand_contact=False, left_finger_contact=False, right_finger_contact=False,
            bilateral_force_bearing=False, left_normal_force_N=0., right_normal_force_N=0., support_upward_force_N=1.)
        snapshot['contacts']['by_object'][row['id']] = contact
    snapshot['expected_object_ids'] = sorted(o['id'] for o in snapshot['geometry']['objects'])
    snapshot['snapshot_sha256'] = state.digest({k:v for k,v in snapshot.items() if k != 'snapshot_sha256'})
    return loader.load_restart_qualification(freeze, freeze_path).as_dict(), snapshot, bundle, bundle_path


class BenchmarkTests(unittest.TestCase):
    def test_provisional_is_five_digests_only(self):
        with TemporaryDirectory(dir=benchmark.HERE) as directory:
            root=Path(directory); rule=root/'rule.json'
            write(rule, {'schema_version':'provisional-restart-class-rule-1','status':'provisional_development_rule',
                'cells':[{'cell_id':'synthetic','route_envelope':{'clearance_corridors_m':[
                    {'min':[0,0,0],'max':[1,1,1]}]*3}}]})
            options=args(root); options.provisional_rule=str(rule)
            with patch.object(benchmark, 'modules', side_effect=AssertionError('Provisional mode must not call classifier')):
                report=benchmark.run(options, {'id':'synthetic-not-a-real-job'})
            self.assertEqual(report['status'],'complete',report)
            self.assertEqual(len(report['calls']),5)
            self.assertEqual(report['shape']['total_corridor_boxes'],3)
            self.assertFalse(report['full_qualified_path_measured'])
            self.assertTrue(report['inputs_unchanged'])
            self.assertFalse(report['qualification_granted'])

    def test_changed_input_is_retained_as_failed_even_when_calls_finish(self):
        with TemporaryDirectory(dir=benchmark.HERE) as directory:
            root=Path(directory); path=root/'rule.json'
            value={'schema_version':'provisional-restart-class-rule-1','status':'provisional_development_rule',
                   'cells':[{'route_envelope':{'clearance_corridors_m':[]}}]}
            write(path,value); options=args(root); options.provisional_rule=str(path)
            original=benchmark.digest
            def mutate(value):
                path.write_text('{}\n',encoding='utf-8')
                return original(value)
            with patch.object(benchmark,'digest',side_effect=mutate): report=benchmark.run(options,{})
            self.assertEqual(report['status'],'failed')
            self.assertFalse(report['inputs_unchanged'])
            self.assertEqual(len(report['calls']),5)
            self.assertTrue((root/'output'/'summary.json').is_file())

    def test_actual_loader_selection_classifier_and_source_event_encoder(self):
        with TemporaryDirectory(dir=benchmark.HERE) as directory:
            root=Path(directory); protected,snapshot,_,_=rich_fixture(root)
            loader,state,_=benchmark.modules(); inputs=benchmark.assembly.Inputs()
            encoder=benchmark.event_encoder(inputs)
            with patch.object(state,'qualified_entry_identity',wraps=state.qualified_entry_identity) as identity:
                rows, assessment=benchmark.measure_calls(snapshot,protected,loader,state,encoder)
            self.assertEqual(len(rows),5)
            self.assertEqual(identity.call_count,20)
            self.assertTrue(all(row['full_qualified_route_path_observed'] for row in rows),rows)
            self.assertEqual(assessment['state'],'admissible',assessment)
            self.assertTrue(all(row['encoded_event_utf8_bytes']>0 for row in rows))
            self.assertTrue(all(row['classification_wall_s']>=0 for row in rows))
            encoder.events=io.StringIO()
            encoder.emit('synthetic',{'a':[1,2]},3.,'offline-benchmark')
            event=json.loads(encoder.events.getvalue())
            self.assertEqual(event['payload_sha256'],state.digest(event['payload']))
            self.assertEqual(event['sim_tick'],1500)

    def test_original_cut_line_and_current_source_identity_are_required(self):
        with TemporaryDirectory(dir=benchmark.HERE) as directory:
            root=Path(directory); _,snapshot,bundle,bundle_path=rich_fixture(root,current_sources=True)
            event={'event_id':1,'event_type':'protected_carry_state_before_cut','payload':snapshot,
                   'payload_sha256':benchmark.digest(snapshot)}
            event_path=root/'events.jsonl'; raw=json.dumps(event,sort_keys=True).encode()+b'\n'; event_path.write_bytes(raw)
            stream_ref={'path':str(event_path),'sha256':benchmark.checksum(event_path),'bytes':len(raw)}
            locator={**stream_ref,'line':1,'line_sha256':hashlib.sha256(raw).hexdigest(),
                     **{k:event[k] for k in ('event_id','event_type','payload_sha256')}}
            cut={'status':'recorded',**event,'source_ref':locator}; states=root/'measured-states.json'
            write(states,{'states':{'cut':cut}})
            bundle['artifact_files'].append({'artifact_id':'synthetic-events',**stream_ref})
            options=args(root); options.cut_states=str(states); options.events=str(event_path)
            actual,_=benchmark.retained_cut(options,benchmark.assembly.Inputs(),bundle,bundle_path)
            self.assertEqual(actual,snapshot)
            changed=copy.deepcopy(bundle); changed['class_spec']['required_source_hashes']['cell.py']='f'*64
            with self.assertRaisesRegex(ValueError,'source identities differ'):
                benchmark.retained_cut(options,benchmark.assembly.Inputs(),changed,bundle_path)
            locator['line_sha256']='e'*64; write(states,{'states':{'cut':cut}})
            with self.assertRaisesRegex(ValueError,'Original cut line differs'):
                benchmark.retained_cut(options,benchmark.assembly.Inputs(),bundle,bundle_path)

    def test_official_receipt_exact_job_and_output_binding(self):
        with TemporaryDirectory(dir=benchmark.HERE) as directory:
            root=Path(directory); _,_,real_runner=benchmark.modules(); script=benchmark.HERE/'assemble_qualification.py'
            job={'id':'synthetic','child_pid':1,'worker_pid':2,'resolved_executable':'python',
                 'argv':['python','-B',str(script),'--output',str(root)],'cwd':str(root),
                 'started_at':'2020-01-01T00:00:00Z'}
            receipt={**job,'state':'succeeded','exit_status':0,'ended_at':'2020-01-01T00:02:00Z'}
            path=root/'receipt.json'; write(path,receipt)
            runner=SimpleNamespace(python_entrypoint=real_runner.python_entrypoint,verify_queue_receipt=Mock())
            report={'assembly_queue':job,'completed_at':'2020-01-01T00:01:00Z'}
            benchmark.receipt_binding(benchmark.assembly.Inputs(),path,report,'assembly_queue',script,
                                      root/'assembly.json','assembly.json',runner)
            runner.verify_queue_receipt.assert_called_once_with('synthetic',path)
            receipt['exit_status']=False; write(path,receipt)
            with self.assertRaisesRegex(ValueError,'Successful official receipt'):
                benchmark.receipt_binding(benchmark.assembly.Inputs(),path,report,'assembly_queue',script,
                                          root/'assembly.json','assembly.json',runner)

    def test_draft_assembly_cannot_enter_qualified_mode(self):
        with TemporaryDirectory(dir=benchmark.HERE) as directory:
            root=Path(directory); freeze=root/'development-freeze.json'
            write(freeze,{'schema_version':'development-restart-qualification-freeze-1','stage':'development'})
            write(root/'assembly.json',{'schema_version':'restart-qualification-assembly-1','status':'complete',
                'inputs_unchanged':True,'operator_acceptance_present':False,'loader_validation':'not_run_draft'})
            options=args(root); options.development_freeze=str(freeze)
            with self.assertRaisesRegex(ValueError,'Completed accepted assembly'):
                benchmark.bind_accepted(options,benchmark.assembly.Inputs(),Mock())

    def test_cli_requires_queue_before_reading_any_evidence(self):
        runner=Mock(); runner.queued_job.side_effect=ValueError('not queue owned')
        with patch.object(benchmark.assembly,'runtime_modules',return_value=(None,runner)), patch.object(benchmark,'run') as run:
            with self.assertRaisesRegex(ValueError,'not queue owned'):
                benchmark.main(['--provisional-rule','not-read.json','--output','not-created'])
            run.assert_not_called()


if __name__=='__main__': unittest.main()
