"""Assess only a terminal, explicitly authorized six-event synthetic trace."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import read_etl
import run_direct_coverage as h


def controls(fixtures,events,after):
    rows=[];projection=[]
    for fixture in fixtures:
        pid=fixture['ready']['pid']
        result=json.loads((Path(fixture['output'])/'result.json').read_text(encoding='utf-8'))
        for case in result['cases']:
            pair=tuple(sorted((case['client_port'],case['server_port'])))
            selected=[e for e in events if e['fields']['ProcessId'] in (0,pid) and
                e['fields']['LocalAddress']['ip']==e['fields']['RemoteAddress']['ip']=='127.0.0.1' and
                tuple(sorted((e['fields']['LocalAddress']['port'],e['fields']['RemoteAddress']['port'])))==pair]
            timed=bool(selected) and all(case['close_requested_perf_counter_ns']<=e.get('perf_counter_ns',-1)<=after['perf_after_ns'] for e in selected)
            if case['case']=='graceful_fin':
                matches=[e for e in selected if e['id']==1043 and e['fields']['Status']==0 and e['fields']['ProcessId']==pid]
                witnessed={e['fields']['LocalAddress']['port'] for e in matches}==set(pair)
                valid_fixture=case['genuine_read_eof'] and case['error'] is None
            else:
                matches=[e for e in selected if e['id']==1044 and e['fields']['Status']==0xC000020D
                         and e['fields']['ProcessId']==pid and e['fields']['LocalAddress']['port']==case['server_port']]
                witnessed=bool(matches) and {1039,1040}.issubset({e['id'] for e in selected})
                valid_fixture=not case['genuine_read_eof'] and case['error'] is not None
            rows.append({'fixture':fixture['label'],'case':case['case'],'passed':bool(result['passed'] and timed and witnessed and valid_fixture),
                         'event_count':len(selected),'timing_passed':timed})
            projection.extend(selected)
    return rows,projection


def main():
    manifest=json.loads((h.HERE/'launch-source-manifest-001.json').read_text(encoding='utf-8-sig'))
    attempt=json.loads((h.HERE/'elevation-attempt-001.json').read_text(encoding='utf-8-sig'))
    assert type(attempt['helperExitCode']) is int and attempt['helperExitCode']==0
    out=Path(manifest['output']);receipt=json.loads((out/'receipt.json').read_text(encoding='utf-8'))
    assert receipt['collection_completed'] and receipt['trace_stopped'] and not receipt['simulated_etw']
    assert manifest['assessmentSha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for name,path in h.source_paths().items():
        assert hashlib.sha256(path.read_bytes()).hexdigest()==manifest['sources'][name]
    decoded=read_etl.read(out/'closure.etl');h.base.save(out/'decoded.json',decoded)
    fixtures=json.loads((out/'fixtures.json').read_text(encoding='utf-8'))
    before=json.loads((out/'clock-before.json').read_text(encoding='utf-8'))
    after=json.loads((out/'clock-after.json').read_text(encoding='utf-8'))
    api=json.loads((out/'etw-api.json').read_text(encoding='utf-8'))
    stops=[r for r in api if r['operation']=='owned_stop']
    counts=decoded['descriptor_counts'];header=decoded['trace_header'];events=decoded['allowed_events']
    metadata={'68fdd900-4a3e-11d1-84f4-0000f80464e3/0/2/0','68fdd900-4a3e-11d1-84f4-0000f80464e3/0/2/80'}
    schema=json.loads((h.HERE/'schema.json').read_text(encoding='utf-8-sig'))
    allowed={f"{read_etl.PROVIDER}/{e['id']}/{e['version']}/0" for e in schema['events']}
    unexpected={key:n for key,n in counts.items() if key not in metadata|allowed}
    freq=C.c_longlong();assert C.windll.kernel32.QueryPerformanceFrequency(C.byref(freq))
    drift=abs((after['utc_ns']-before['utc_ns'])-((after['perf_before_ns']+after['perf_after_ns']-before['perf_before_ns']-before['perf_after_ns'])//2))
    control_rows,projection=controls(fixtures,events,after)
    checks={
        'complete_owned_cleanup':all(r['qualified'] for r in receipt['fixture_retirements']) and not receipt['cleanup_errors'],
        'duration_and_size':0<receipt['trace_elapsed_s']<=30 and 0<(out/'closure.etl').stat().st_size<=h.LIMIT,
        'own_stop_and_absence':len(stops)==1 and stops[0]['status']==0 and api[-1]['operation']=='post_stop_query' and api[-1]['status']==4201,
        'no_loss':len(stops)==1 and all(stops[0]['properties'][n]==0 for n in ('EventsLost','LogBuffersLost','RealTimeBuffersLost')) and header['EventsLost']==header['BuffersLost']==0,
        'sequential_and_bounded':header['LogFileMode']==1 and header['MaximumFileSize']==16 and len(stops)==1 and stops[0]['properties']['LogFileMode']==0x400001,
        'no_decode_errors_or_extensions':not decoded['decode_errors'] and not decoded['extended_data_counts'],
        'only_six_types_and_required_trace_headers':not unexpected and sum(counts.get(k,0) for k in metadata)<=3 and counts.get('68fdd900-4a3e-11d1-84f4-0000f80464e3/0/2/0')==1,
        'qpc_clock_correlated':header['ReservedFlags']==1 and header['PerfFreq']==freq.value and drift<=10_000_000 and all(before['perf_before_ns']<=e.get('perf_counter_ns',-1)<=after['perf_after_ns'] for e in events),
        'both_fixtures_and_four_controls':len(fixtures)==2 and len(control_rows)==4 and all(c['passed'] for c in control_rows),
    }
    bindings=[]
    for path in sorted(out.rglob('*')):
        if path.is_file():
            bindings.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    assessment={'qualified_for_six_type_closure_metadata':all(checks.values()),'checks':checks,'controls':control_rows,
        'packet_capture':False,'complete_kernel_abort_history':False,'native_diagnostic_admitted':False,'model_calls':0,
        'collection_scope':'all-processes','unexpected_descriptor_counts':unexpected,'allowed_event_count':len(events),
        'synthetic_event_count':len(projection),'other_event_count':len(events)-len(projection),'descriptor_counts':counts,
        'trace_header':header,'utc_qpc_drift_ns':drift,'original_files':bindings,'raw_trace_copied_to_repository':False}
    if all(checks.values()):
        h.base.save(h.HERE/'synthetic-control-events.json',projection)
    evidence=h.HERE/'evidence';evidence.mkdir()
    for name in ('intent.json','receipt.json','fixtures.json','etw-api.json','filters.json','clock-before.json','clock-after.json'):
        shutil.copyfile(out/name,evidence/name)
    h.base.save(h.HERE/'assessment-001.json',assessment)
    print(json.dumps({k:v for k,v in assessment.items() if k not in ('original_files','descriptor_counts')},indent=2))
    return 0 if all(checks.values()) else 1


if __name__=='__main__':
    raise SystemExit(main())
