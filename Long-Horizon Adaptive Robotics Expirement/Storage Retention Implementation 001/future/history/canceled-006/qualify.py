"""Queued read-only r4 replay and bounded native component qualification.

Current computations receive exact decoded objects through the future reader.
Sample-window results are equivalence checks, not whole-run scientific findings.
The native fixture runs real simulated physics/sensing and the frozen evaluator;
it performs no model call, candidate experiment, or scored release attempt.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import hashlib
import gzip
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import unittest
import copy
import math
from collections import deque

HERE=Path(__file__).resolve().parent
EXP=HERE.parents[1]
from recorder import Recorder, Reader, ImagePolicy, pack, GatewayAdapter, container_bytes, VERSION, MAX_CONTAINER_BYTES
from admission import project, project_images, admit
from runtime_adapter import FutureEvidence, LiveSensorBridge

CASES=[('C01','baseline',.1,'nominal'),('C01','A1',.5,'many-model-calls'),
       ('C01','A2',.5,'candidate-input-repetition'),('C01','A3',.5,'model-advisory'),
       ('C14','A1',.5,'restart-continuity'),('C14','A2',.5,'checkpoint-file-activity'),
       ('C14','A3',.9,'delayed-stale-packets'),('C24','baseline',.5,'long-run'),
       ('C24','A3',.9,'high-observation-volume'),('C20','baseline',.9,'large-input-failure')]
RETAINED_SHA256='55569a0375eacc9c71dc39e9e3b006392c657e7619b21f3f196c5a91f67bc09d'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''): h.update(data)
    return h.hexdigest()


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod; spec.loader.exec_module(mod); return mod


def normalized(value):
    if isinstance(value,dict): return {k:normalized(v) for k,v in value.items() if k not in ('created_at',)}
    if isinstance(value,list): return [normalized(v) for v in value]
    return value


def retained_image_inputs():
    """Freeze bounded engineering size samples from authenticated retained pairs only."""
    manifest=HERE.parent/'manifests'/'r4-policy-001-retained.jsonl.gz'
    assert sha(manifest)==RETAINED_SHA256, 'Retained partition changed; explicitly requalify inputs'
    wanted={f'batch01-eval-r4-{case}-rep1-{kind}-persistent' for case,kind,_,_ in CASES}
    rows={}
    with gzip.open(manifest,'rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['run_id'] in wanted: rows[row['path']]=row
    categories=[]
    for case,kind,_,label in CASES:
        rid=f'batch01-eval-r4-{case}-rep1-{kind}-persistent'
        pairs=[]
        for key,row in rows.items():
            if row['run_id']!=rid or row['artifact_type']!='rgb': continue
            path=Path(key); paired=path.with_name(path.stem+'-depth.npz').as_posix()
            if paired in rows: pairs.append((key,paired))
        pairs.sort(); assert pairs, 'No retained paired image input for '+rid
        for fraction in (.1,.5,.9):
            rgb,depth=pairs[min(len(pairs)-1,int(len(pairs)*fraction))]
            item={'label':label,'run_id':rid,'fraction_within_retained_pairs':fraction,
                  'retained_pairs_in_run':len(pairs),'source':str(Path(rgb).relative_to(EXP.name)),
                  'depth_source':str(Path(depth).relative_to(EXP.name))}
            for kind,key in [('rgb',rgb),('depth',depth)]:
                source=EXP.parent/key; row=rows[key]
                assert source.stat().st_size==row['logical_bytes'] and sha(source)==row['sha256']
                item[kind+'_bytes']=row['logical_bytes']; item[kind+'_sha256']=row['sha256']
            item['pair_bytes']=item['rgb_bytes']+item['depth_bytes']; categories.append(item)
    binding={'schema_version':'retained-image-inputs-1','manifest_path':str(manifest.relative_to(EXP)),
        'manifest_sha256':RETAINED_SHA256,'all_sources_authenticated_retained':True,
        'scope':'Deterministic 0.1/0.5/0.9 path quantiles within retained paired images; bounded engineering size samples, not a scientific representative sample',
        'image_pilot_pair_index':0,'frame_categories':categories}
    frozen=HERE/'image-inputs.json'
    if frozen.exists(): assert json.loads(frozen.read_text(encoding='utf-8'))==binding, 'Frozen image inputs changed'
    else: frozen.write_text(json.dumps(binding,indent=2)+'\n',encoding='utf-8')
    return binding,{'path':str(frozen.relative_to(EXP)),'sha256':sha(frozen)}


def sample_events(path,fraction,seconds=30):
    before=path.stat(); rows=[]; source=hashlib.sha256(); nbytes=0
    with path.open('rb') as stream:
        stream.seek(int(before.st_size*fraction))
        if fraction: stream.readline()
        start=stream.tell(); first=None
        while line:=stream.readline():
            row=json.loads(line); stamp=row.get('sim_time_s')
            if isinstance(stamp,(float,int)):
                if first is None: first=stamp
                if stamp-first>seconds and rows: break
            rows.append(row); source.update(line); nbytes+=len(line)
            if nbytes>100_000_000: break
        end=start+nbytes
    after=path.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return rows,{'path':str(path.relative_to(EXP)), 'byte_start':start,'byte_end':end,
                 'sha256':source.hexdigest(),'bytes':nbytes,'source_size':before.st_size,
                 'source_mtime_ns':before.st_mtime_ns,'source_metadata_unchanged':True}


def sample_motion(path,start,end):
    rows=[]; h=hashlib.sha256(); nbytes=0; before=path.stat()
    with path.open('rb') as stream:
        for line in stream:
            row=json.loads(line); t=row['sim_time_s']
            if t>end: break
            if t>=start: rows.append(row); h.update(line); nbytes+=len(line)
    after=path.stat(); assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return rows,{'path':str(path.relative_to(EXP)),'first_sim_s':start,'last_sim_s':end,
                 'sha256':h.hexdigest(),'bytes':nbytes,'source_metadata_unchanged':True}


def run(generation='qualification-002'):
    implementation_before={p.name:sha(p) for p in HERE.glob('*.py')}
    source_paths=(list((EXP/'Runtime 004').glob('*.py'))+
                  list((EXP/'Engineering Investigation 005').glob('*.py'))+
                  [EXP/'Runtime 004'/'vendor'/'panda'/'manifest.json',EXP/'Runtime 004'/'vendor'/'panda'/'panda.xml'])
    source_before={str(p.relative_to(EXP)):sha(p) for p in source_paths}
    image_inputs,image_input_file=retained_image_inputs()
    if not generation.replace('-','').isalnum(): raise ValueError('Safe generation name required')
    output=HERE/'pilots'/generation; output.mkdir(parents=True,exist_ok=False)
    sys.path[:0]=[str(EXP/'Runtime 004'),str(EXP/'Engineering Investigation 005')]
    diagnostics=module('qualified_diagnostics',EXP/'Runtime 004'/'diagnostics.py')
    continuity=module('qualified_continuity',EXP/'Engineering Investigation 005'/'continuity.py')
    tests=unittest.defaultTestLoader.discover(str(HERE),pattern='test_recorder.py')
    test_result=unittest.TextTestRunner(verbosity=2).run(tests)
    assert test_result.wasSuccessful()
    # Exercise the actual Evidence-compatible adapter and frozen protected evaluator
    # on its authored counterexample fixtures. This is not a robot experiment.
    evaluator=module('qualified_evaluator',EXP/'Runtime 004'/'evaluator.py')
    evaluator_fixtures=module('qualified_evaluator_fixtures',EXP/'Runtime 004'/'test_evaluator.py')
    clock=[100.]
    integration=FutureEvidence(output/'integration', 'integration-fixture',clock=lambda:clock[0])
    eval_a=evaluator.IndependentEvaluator(); eval_b=evaluator.IndependentEvaluator()
    snapshot,order=evaluator_fixtures.fixture(); scoring=[]
    for i in range(8):
        clock[0]=100+i*.1; snapshot['sim_time']=10+i*.1
        integration.emit('protected_scoring_snapshot',copy.deepcopy(snapshot),snapshot['sim_time'],source='evaluator')
        scoring.append(eval_a.evaluate_snapshot(copy.deepcopy(snapshot),order,acceptance_open=True,wall_monotonic_s=clock[0]))
        integration.motion.write(json.dumps({'sim_time_s':snapshot['sim_time'],'q':[i*.1]*7,'gap':None})+'\n')
    integration.document('order',order); integration.close(); integration_reader=Reader(output/'integration')
    restored_scoring=[]
    for event in integration_reader.events():
        restored_scoring.append(eval_b.evaluate_snapshot(event['payload'],integration_reader.document('order'),
                                  acceptance_open=True,wall_monotonic_s=100+event['wall_elapsed_s']))
    assert scoring==restored_scoring; assert eval_a.first_success==eval_b.first_success
    integration_reader.close()
    # Same immutable result object and arrays are returned to the live consumer.
    import numpy as np
    from types import SimpleNamespace
    sensor_evidence=FutureEvidence(output/'sensor-bridge','sensor-fixture')
    sensor=SimpleNamespace(camera='overhead',sequence=1,capture_sim_time_s=.1,
        rgb=np.zeros((24,32,3),dtype=np.uint8),depth=np.ones((24,32),dtype=np.float32),
        detections_json='[]',capture_wall_elapsed_s=.3)
    assert LiveSensorBridge(sensor_evidence).observe(sensor) is sensor
    sensor_evidence.close()
    from native_supervisor import qualify as qualify_native
    native_report=qualify_native(output/'native-supervisor')
    (output/'native-supervisor'/'qualification.json').write_text(json.dumps(native_report,indent=2)+'\n',encoding='utf-8')
    print('native supervisor frozen timing gate',native_report['frozen_timing_gate_pass'],flush=True)
    assert native_report['frozen_timing_gate_pass'], 'Native supervisor failed unchanged frozen timing tolerances'
    # Full-cap synthetic duration tests cumulative state and quota behavior.
    # It is explicitly excluded from storage-rate projection: repeated synthetic
    # content and tiny paired blobs would produce misleading compression estimates.
    long_rec=Recorder(output/'long-synthetic-1200s',run_id='long-synthetic-1200s',
                      core_quota_bytes=150_000_000,policy=ImagePolicy(image_quota_bytes=1_000_000))
    history=deque(maxlen=100); event_digest=hashlib.sha256(); motion_digest=hashlib.sha256(); eid=0
    def long_event(kind,payload,stamp,parents=()):
        nonlocal eid
        eid+=1; value={'schema_version':'robot-evidence-1.0','run_id':'long-synthetic-1200s',
            'event_id':eid,'event_type':kind,'source':'supervisor','sim_time_s':stamp,
            'wall_elapsed_s':stamp,'parent_ids':list(parents),'payload':payload}
        long_rec.event(value); event_digest.update(pack(value)); return eid
    for tick in range(120001):
        stamp=tick/100
        q=[math.sin(stamp+j)*.1 for j in range(7)]
        row={'sim_time_s':stamp,'q':q,'dq':[math.cos(stamp+j)*.1 for j in range(7)],
             'effort':[float(j) for j in range(7)],'target':q,'tcp':[.1,.2,.3],
             'contact_peak_N':float(tick%13),'explicit_gap':tick==30001}
        if tick!=30000:  # One deliberate missing sample; no fill or interpolation.
            long_rec.motion(row); motion_digest.update(pack(row))
        history.append({'sequence':tick,'sim_time_s':stamp,'joint_position_rad':q,
                        'joint_velocity_rad_s':row['dq'],'missed_nominal_intervals':1 if tick==30001 else 0})
        if tick%10==0:
            packet={'capture_time_s':stamp,'arm':{'telemetry_history':{'samples':list(history)}}}
            parent=long_event('observation',packet,stamp)
            if tick%50==0: long_event('candidate_input',{'message':{'packet':packet}},stamp,[parent])
            long_rec.image(str(tick),stamp,b'synthetic-rgb',b'synthetic-depth')
        if tick and tick%500==0:
            parent=long_event('model_request',{'messages':[{'role':'user','content':'Repeated exact model context\n'*100}]},stamp)
            long_event('model_response',{'reply':'exact response','stale':tick==60000},stamp,[parent])
        if tick and tick%1000==0:
            long_event('checkpoint',{'path':'candidate-state.json','content':json.dumps({'tick':tick,'history':'state '*1000})},stamp)
        if tick==60000:
            parent=long_event('restart_begin',{'incarnation':1,'ambiguous_action':True},stamp)
            long_event('restart_ready',{'incarnation':2,'retained_checkpoint':True},stamp,[parent])
            long_rec.trigger(stamp,parent,'synthetic restart')
    long_rec.close(); long_reader=Reader(output/'long-synthetic-1200s')
    restored_event_digest=hashlib.sha256(); restored_motion_digest=hashlib.sha256(); nmotion=0
    for event in long_reader.events(): restored_event_digest.update(pack(event))
    for row in long_reader.motion(): restored_motion_digest.update(pack(row)); nmotion+=1
    assert restored_event_digest.digest()==event_digest.digest()
    assert restored_motion_digest.digest()==motion_digest.digest(); assert nmotion==120000
    long_report={'synthetic':True,'duration_s':1200,'motion_samples':nmotion,'events':eid,
        'live_pairs':12001,'exact_events_sha256':event_digest.hexdigest(),'exact_motion_sha256':motion_digest.hexdigest(),
        'database_bytes':container_bytes(output/'long-synthetic-1200s'),
        'features':['100Hz numerical','10Hz public packets and pair metadata','one missing sample',
          'repeated candidate inputs','240 model calls','120 checkpoints','restart and stale response'],
        'excluded_from_projection':True}
    long_reader.close(); print('long synthetic complete',long_report['database_bytes'],flush=True)
    cases=CASES
    reports=[]
    for case,kind,fraction,label in cases:
        rid=f'batch01-eval-r4-{case}-rep1-{kind}-persistent'
        source=EXP/'Evidence'/'releases'/'batch01-eval-r4'/'attempts'/rid/'evidence'
        events,event_identity=sample_events(source/'events.jsonl',fraction)
        times=[e['sim_time_s'] for e in events if isinstance(e.get('sim_time_s'),(float,int))]
        start,end=min(times),max(times); duration=end-start
        assert duration>0
        motion,motion_identity=sample_motion(source/'motion.jsonl',start,end)
        manifest=json.loads((source/'manifest.json').read_text()); result=json.loads((source/'result.json').read_text())
        destination=output/label
        recorder=Recorder(destination,run_id=rid,core_quota_bytes=100_000_000,
                          policy=ImagePolicy(image_quota_bytes=0))
        elapsed=[]
        for event in events:
            before=time.perf_counter(); recorder.event(event); elapsed.append(time.perf_counter()-before)
        for row in motion: recorder.motion(row)
        recorder.document('manifest',manifest); recorder.document('result',result); recorder.close()
        reader=Reader(destination); decoded=list(reader.events()); decoded_motion=list(reader.motion())
        assert pack(events)==pack(decoded); assert pack(motion)==pack(decoded_motion)
        assert pack(reader.document('manifest'))==pack(manifest)
        assert pack(reader.document('result'))==pack(result)
        original_diagnostics=normalized(diagnostics.analyze(events,motion,result,manifest))
        restored_diagnostics=normalized(diagnostics.analyze(decoded,decoded_motion,result,manifest))
        assert original_diagnostics==restored_diagnostics
        counts=dict(reader.db.execute('SELECT "objects",COUNT(*) FROM objects UNION ALL SELECT "telemetry",COUNT(*) FROM telemetry'))
        reader.close(); db_bytes=container_bytes(destination)
        report={'label':label,'run_id':rid,'fraction':fraction,'task_seconds':duration,
          'events':len(events),'motion_rows':len(motion),'event_types':dict(Counter(e['event_type'] for e in events)),
          'event_source':event_identity,'motion_source':motion_identity,
          'database_core_bytes':db_bytes,'source_window_bytes':event_identity['bytes']+motion_identity['bytes'],
          'bytes_per_task_second':db_bytes/duration,'semantic_exact':True,'diagnostics_equivalent':True,
          'continuity_equivalent':None,'continuity_scope':'Continuity requires complete chain; checked separately below',
          'recorded_result_exact':True,'candidate_input_and_public_clocks_exact':True,
          'object_counts':counts,'record_event_latency_ms':{'median':statistics.median(elapsed)*1000,
             'p95':sorted(elapsed)[int(.95*(len(elapsed)-1))]*1000,'max':max(elapsed)*1000},
          'diagnostics_sha256':hashlib.sha256(pack(original_diagnostics)).hexdigest()}
        reports.append(report); print(label,db_bytes,duration,flush=True)

    # Current continuity enforces a complete contiguous event chain beginning at 1.
    # Do not weaken it or rename window IDs. Consume source and decoded chains in
    # sequence to bound memory to one complete source bundle at a time.
    full_continuity=[]
    for suffix in ('C01-rep1-baseline-persistent','C14-rep1-A3-persistent'):
        rid='batch01-eval-r4-'+suffix
        source=EXP/'Evidence'/'releases'/'batch01-eval-r4'/'attempts'/rid/'evidence'
        manifest=json.loads((source/'manifest.json').read_text()); result=json.loads((source/'result.json').read_text())
        recorder=Recorder(output/('complete-'+suffix),run_id=rid,core_quota_bytes=500_000_000)
        source_hash=hashlib.sha256(); before=(source/'events.jsonl').stat(); event_count=[0]
        def originals():
            with (source/'events.jsonl').open('rb') as stream:
                for line in stream:
                    source_hash.update(line); event_count[0]+=1
                    value=json.loads(line); recorder.event(value); yield value
        original_continuity=normalized(continuity.extract(manifest,result,originals()))
        recorder.document('manifest',manifest); recorder.document('result',result); recorder.close()
        reader=Reader(output/('complete-'+suffix))
        restored_continuity=normalized(continuity.extract(manifest,result,reader.events()))
        assert original_continuity==restored_continuity
        # Independently verify every event against the original, not only extracted fields.
        with (source/'events.jsonl').open('rb') as stream:
            for line,decoded in zip(stream,reader.events(),strict=True): assert pack(json.loads(line))==pack(decoded)
        reader.close(); after=(source/'events.jsonl').stat()
        assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
        full_continuity.append({'run_id':rid,'source_event_bytes':before.st_size,'source_event_sha256':source_hash.hexdigest(),
            'source_metadata_unchanged':True,'event_count':event_count[0],'exact_all_events':True,
            'continuity_equivalent':True,'coverage':original_continuity['coverage'],
            'continuity_sha256':hashlib.sha256(pack(original_continuity)).hexdigest(),
            'database_bytes':container_bytes(output/('complete-'+suffix)),
            'scope':'Complete event chain; no qualification context supplied, so original unknown admissibility remains unknown'})
        print('complete continuity',suffix,event_count[0],flush=True)

    # Actual encoded pair bytes from a predeclared viewer-retained trace, no source writes.
    pair=image_inputs['frame_categories'][image_inputs['image_pilot_pair_index']]
    png_path=EXP/pair['source']; depth_path=EXP/pair['depth_source']
    rgb=png_path.read_bytes(); depth=depth_path.read_bytes()
    assert hashlib.sha256(rgb).hexdigest()==pair['rgb_sha256']
    assert hashlib.sha256(depth).hexdigest()==pair['depth_sha256']
    policy=ImagePolicy(sparse_period_s=10,pre_s=2,post_s=3,ring_bytes=24_000_000,
                       ring_frames=64,image_quota_bytes=15_000_000)
    rec=Recorder(output/'image-pilot',run_id='synthetic-policy-real-encoded-pair',policy=policy)
    for i in range(601):
        rec.image(str(i),i/10,rgb,depth)
        if i==200: rec.trigger(20.,'anomaly-1','qualification failure trigger')
    rec.close(); reader=Reader(output/'image-pilot'); inventory=list(reader.images())
    availability=reader.package(output/'selected-package',['0','1','190','220','600'])
    assert reader.image('1')['status']=='unavailable_by_policy'
    assert reader.image('190')['status']=='available'
    assert reader.image('220')['status']=='available'
    image_report={'task_seconds':60,'live_pair_count':601,'retained_pairs':sum(v['status']=='available' for v in inventory),
      'unavailable_by_policy':sum(v['status']!='available' for v in inventory),
      'rgb_source':str(png_path.relative_to(EXP)),'depth_source':str(depth_path.relative_to(EXP)),
      'rgb_sha256':hashlib.sha256(rgb).hexdigest(),'depth_sha256':hashlib.sha256(depth).hexdigest(),
      'rgb_bytes':len(rgb),'depth_bytes':len(depth),'database_bytes':container_bytes(output/'image-pilot'),
      'policy':reader.meta['policy'],'note':'Real encoded pair repeated at synthetic times; policy/storage test, not a new camera acquisition or timing pilot',
      'package_availability':availability}
    reader.close()
    frame_categories=image_inputs['frame_categories']
    image_projection=project_images(measured_pair_bytes=max(p['pair_bytes'] for p in frame_categories))
    image_projection['measured_frame_categories']=frame_categories
    projection=project(reports,image_projection=image_projection)
    qualification={'semantic_exact':True,'diagnostics_equivalent':True,'continuity_equivalent':True,
      'image_policy_qualified':True,'runtime_timing_qualified':False,'frozen_release_bound':False}
    report={'schema_version':'future-recorder-qualification-1','created_at':datetime.now(timezone.utc).isoformat(),
      'generation':generation,'bulk_output':str(output.relative_to(HERE)),
      'scope':'Read-only source replay, synthetic edge tests, and two bounded real simulated workcell component fixtures. No model calls or scored experiments.',
      'tests':{'run':test_result.testsRun,'passed':test_result.wasSuccessful()},'pilots':reports,'image_pilot':image_report,
      'complete_chain_continuity':full_continuity,
      'long_duration_synthetic':long_report,
      'native_supervisor':native_report,
      'integration_fixture':{'scoring_results_exact':True,'first_success_exact':True,'frozen_evaluator_samples':8,
         'future_evidence_api_exercised':True,'live_sensor_result_identity_preserved':True,
         'scope':'Synthetic protected fixtures and immutable array fixture; no simulator or model execution'},
      'projection':projection,'qualification':qualification,
      'container_storage':{'codec':VERSION,'storage':'sqlite-gzip-1',
         'maximum_live_database_bytes':MAX_CONTAINER_BYTES,
         'maximum_finalization_disk_overlap_bytes':2*MAX_CONTAINER_BYTES+1_000_000,
         'reader_disk_restore_bytes':0,'maximum_reader_restore_buffer_bytes':MAX_CONTAINER_BYTES,
         'maximum_reader_sqlite_copy_bytes':MAX_CONTAINER_BYTES,
         'measured_max_uncompressed_database_bytes':max(json.loads(p.read_text(encoding='utf-8'))['uncompressed_bytes']
             for p in output.rglob('container-manifest.json')),
         'measured_max_finalization_disk_overlap_bytes':max(sum(json.loads(p.read_text(encoding='utf-8'))[k]
             for k in ('bytes','uncompressed_bytes')) for p in output.rglob('container-manifest.json')),
         'concurrency_scope':'One queued writer/finalizer; reader memory bound is per open reader. Separate concurrent jobs require additional reservations.'},
      'admission_example':admit(projection,evidence_bytes=160*1_000_000_000,free_bytes=400*1_000_000_000,qualification=qualification),
      'source_hashes':source_before,
      'image_input_binding':image_input_file,'retained_image_inputs':image_inputs,
      'implementation_hashes':implementation_before,
      'container_manifests':{str(p.parent.relative_to(output)):json.loads(p.read_text(encoding='utf-8'))
                             for p in output.rglob('container-manifest.json')},
      'expected_failure_markers':{str(p.parent.relative_to(output)):json.loads(p.read_text(encoding='utf-8'))
                                 for p in output.rglob('RECORDING_FAILED.json')},
      'limitations':['Measured maximum replay-window rate is not a proof for unseen workloads or a full campaign.',
        'Public input objects, stored timing fields and recorded task/scoring records are exact. Historical full tasks and the scored campaign were not rerun; the bounded native fixed-action fixture executes the protected evaluator.',
        'No end-to-end runtime timing qualification or frozen future release integration exists yet; admission correctly rejects scientific use.',
        'Window-local diagnostic equivalence and unchanged whole-chain continuity extraction do not upgrade recovery claims or unknown qualification context.',
        'Image quotas deliberately make some imagery unavailable; ring overflow and quota exhaustion are explicit metadata.']}
    assert implementation_before=={p.name:sha(p) for p in HERE.glob('*.py')}, 'Implementation changed during qualification'
    assert source_before=={str(p.relative_to(EXP)):sha(p) for p in source_paths}, 'Frozen component source changed during qualification'
    assert sha(EXP/image_input_file['path'])==image_input_file['sha256'], 'Frozen image inputs changed during qualification'
    (HERE/'qualification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(projection,indent=2),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--generation',default='qualification-002')
    run(parser.parse_args().generation)
