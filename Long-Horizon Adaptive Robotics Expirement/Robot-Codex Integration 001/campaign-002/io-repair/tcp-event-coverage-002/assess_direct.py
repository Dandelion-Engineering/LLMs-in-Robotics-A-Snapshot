"""Independent terminal assessment of the prospectively bounded synthetic trace."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import read_etl
import run_direct_coverage as h


def main():
    manifest=json.loads((h.HERE/'launch-source-manifest-001.json').read_text(encoding='utf-8-sig'))
    attempt=json.loads((h.HERE/'elevation-attempt-001.json').read_text(encoding='utf-8-sig'))
    out=Path(manifest['output'])
    assert type(attempt['helperExitCode']) is int and attempt['helperExitCode']==0
    receipt=json.loads((out/'receipt.json').read_text(encoding='utf-8'))
    assert receipt['collection_completed'] and receipt['trace_stopped'] and not receipt['simulated_etw']
    assert manifest['assessmentSha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for name,path in h.source_paths().items():
        assert hashlib.sha256(path.read_bytes()).hexdigest()==manifest['sources'][name]
    decoded=read_etl.read(out/'closure.etl')
    h.base.save(out/'decoded.json',decoded)
    fixtures=json.loads((out/'fixtures.json').read_text(encoding='utf-8'))
    included,excluded=fixtures
    assert included['label']=='included' and excluded['label']=='excluded'
    pid=included['ready']['pid'];excluded_pid=excluded['ready']['pid']
    result=json.loads((out/'included/result.json').read_text(encoding='utf-8'))
    excluded_result=json.loads((out/'excluded/result.json').read_text(encoding='utf-8'))
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
    pairs={tuple(sorted((r['client_port'],r['server_port']))) for r in result['cases']}
    scope_bad=[]
    for i,event in enumerate(events):
        f=event['fields']
        if (f['ProcessId']!=pid or f['LocalAddress']['ip']!='127.0.0.1' or f['RemoteAddress']['ip']!='127.0.0.1'
                or tuple(sorted((f['LocalAddress']['port'],f['RemoteAddress']['port']))) not in pairs):
            scope_bad.append(i)
    controls=[]
    for case in result['cases']:
        selected=[e for e in events if e['fields']['ProcessId']==pid and
            tuple(sorted((e['fields']['LocalAddress']['port'],e['fields']['RemoteAddress']['port'])))==tuple(sorted((case['client_port'],case['server_port'])))]
        timed=all(case['close_requested_perf_counter_ns']<=e.get('perf_counter_ns',-1)<=after['perf_after_ns'] for e in selected)
        if case['case']=='graceful_fin':
            matches=[e for e in selected if e['id']==1043 and e['fields']['Status']==0]
            witnessed={e['fields']['LocalAddress']['port'] for e in matches}=={case['client_port'],case['server_port']}
            fixture_passed=case['genuine_read_eof'] and case['error'] is None
        else:
            matches=[e for e in selected if e['id']==1044 and e['fields']['Status']==0xC000020D and e['fields']['LocalAddress']['port']==case['server_port']]
            witnessed=bool(matches);fixture_passed=not case['genuine_read_eof'] and case['error'] is not None
        controls.append({'case':case['case'],'passed':bool(selected and timed and witnessed and fixture_passed),
            'event_count':len(selected),'matching_events':len(matches),'timing_within_declared_case':timed})
    checks={
        'terminal_collection_and_retirement':receipt['collection_completed'] and all(r['qualified'] for r in receipt['fixture_retirements']),
        'duration_and_size':0<receipt['trace_elapsed_s']<=30 and 0<(out/'closure.etl').stat().st_size<=h.LIMIT,
        'own_stop_and_absence':len(stops)==1 and stops[0]['status']==0 and api[-1]['operation']=='post_stop_query' and api[-1]['status']==4201,
        'no_loss':len(stops)==1 and all(stops[0]['properties'][n]==0 for n in ('EventsLost','LogBuffersLost','RealTimeBuffersLost')) and header['EventsLost']==header['BuffersLost']==0,
        'sequential_and_bounded':header['LogFileMode']==1 and header['MaximumFileSize']==16,
        'no_decode_errors_or_extensions':not decoded['decode_errors'] and not decoded['extended_data_counts'],
        'only_declared_events_and_trace_headers':not unexpected and sum(counts.get(k,0) for k in metadata)<=3 and counts.get('68fdd900-4a3e-11d1-84f4-0000f80464e3/0/2/0')==1,
        'strict_process_and_endpoint_scope':bool(events) and not scope_bad and all(e['fields']['ProcessId']!=excluded_pid for e in events),
        'qpc_clock_correlated':header['ReservedFlags']==1 and header['PerfFreq']==freq.value and drift<=10_000_000 and all(before['perf_before_ns']<=e.get('perf_counter_ns',-1)<=after['perf_after_ns'] for e in events),
        'both_control_expectations':len(controls)==2 and all(c['passed'] for c in controls),
        'excluded_controls_really_ran':excluded_result['passed'] and len(excluded_result['cases'])==2,
    }
    bindings=[]
    for path in sorted(out.rglob('*')):
        if path.is_file():
            bindings.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    assessment={'qualified_for_owned_shutdown_metadata':all(checks.values()),'checks':checks,'controls':controls,
        'packet_fin_rst_coverage':False,'complete_kernel_abort_history':False,'native_diagnostic_admitted':False,
        'model_calls':0,'unexpected_descriptor_counts':unexpected,'scope_bad_event_indices':scope_bad,
        'allowed_event_count':len(events),'descriptor_counts':counts,'trace_header':header,'utc_qpc_drift_ns':drift,
        'original_files':bindings,'raw_trace_copied_to_repository':False}
    if all(checks.values()):
        h.base.save(h.HERE/'owned-control-events.json',events)
    evidence=h.HERE/'evidence';evidence.mkdir()
    for name in ('intent.json','receipt.json','fixtures.json','etw-api.json','filters.json','clock-before.json','clock-after.json'):
        shutil.copyfile(out/name,evidence/name)
    h.base.save(h.HERE/'assessment-001.json',assessment)
    print(json.dumps({k:v for k,v in assessment.items() if k not in ('original_files','descriptor_counts')},indent=2))
    return 0 if all(checks.values()) else 1


if __name__=='__main__':
    raise SystemExit(main())
