"""Assess terminal trace scope without copying unrelated metadata into the repo."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
OUT=Path(r'C:\Users\cresp\Documents\Campaign002 TCP Trace\event-coverage-20260930-001')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    launch=read(HERE/'elevation-attempt-001.json')
    assert type(launch['helperExitCode']) is int and launch['helperExitCode']==0 and launch['exitedWithin60Seconds']
    receipt=read(OUT/'receipt.json')
    included=read(OUT/'included/result.json')
    excluded=read(OUT/'excluded/result.json')
    port=included['cases'][0]['server_port']
    excluded_ports={c[k] for c in excluded['cases'] for k in ('client_port','server_port')}
    text=(OUT/'closure.txt').read_text(encoding='utf-16')
    # Discard all out-of-scope field values from the repository projection.
    selected=[]
    counts=Counter()
    scope_failures=Counter()
    closure_ids={1038,1039,1040,1043,1044,1045,1046,1047,1048,1200,1201,1468}
    pair_re=re.compile(r'local=(127\.0\.0\.1):(\d+) remote=(127\.0\.0\.1):(\d+)')
    for line in text.splitlines():
        match=re.search(r'Event: ([^,]+)',line)
        if not match:
            continue
        event=match.group(1)
        counts[event]+=1
        pair=pair_re.search(line)
        if event.isdigit() and int(event) in closure_ids and pair and port in (int(pair[2]),int(pair[4])):
            selected.append(line)
        elif event not in {'Header','PartitionInfoExtensionV2'}:
            scope_failures[event]+=1
    exact_excluded_pairs=[]
    for line in text.splitlines():
        pair=pair_re.search(line)
        if pair and {int(pair[2]),int(pair[4])} <= excluded_ports:
            exact_excluded_pairs.append(line)
    controls=[]
    for case in included['cases']:
        pair={case['server_port'],case['client_port']}
        rows=[line for line in selected if {int(pair_re.search(line)[2]),int(pair_re.search(line)[4])}==pair]
        ids=sorted({int(re.search(r'Event: (\d+)',line)[1]) for line in rows})
        controls.append({'case':case['case'],'endpoint_ports':sorted(pair),'event_ids':ids,'selected_event_count':len(rows),
                         'observed_expected_event_kind':(1043 in ids and 1039 not in ids) if case['case']=='graceful_fin' else (1039 in ids and 1040 in ids)})
    commands=[read(p) for p in sorted(OUT.glob('command-*.json'))]
    stats=next(c for c in commands if '--stats' in c['argv'])
    export=next(c for c in commands if '--out' in c['argv'])
    binding=[]
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            binding.append({'path':str(path),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                            'retention':'external local original; not copied into repository'})
    result={
        'kind':'bounded no-model coverage diagnostic; not scientific qualification',
        'collection_completed':receipt['collection_completed'],'coverage_adequate':False,
        'reason':'Strict collection scope failed: netsh retained unrelated endpoint, zero-keyword and system process rundown metadata despite explicit provider filters and report/correlation/perfMerge disabled.',
        'trace_elapsed_s':receipt['trace_elapsed_s'],'etl_bytes':(OUT/'closure.etl').stat().st_size,
        'controls':controls,'excluded_exact_connection_event_count':len(exact_excluded_pairs),
        'excluded_endpoint_close_rows':sum(1 for line in text.splitlines() if 'Event: 1009,' in line and any(':'+str(p)+')' in line for p in excluded_ports)),
        'event_counts':dict(counts),'out_of_scope_event_counts':dict(scope_failures),
        'manifest_based_events':int(re.search(r'Manifest-based events\s+(\d+)',stats['stdout'])[1]),
        'reported_formatting_errors':int(re.search(r'Formatting errors:\s+(\d+)',export['stdout'])[1]),
        'trace_header_reports_zero_loss':'EventsLost: 0' in text and 'BuffersLost: 0' in text,
        'noncircular_size_and_duration_within_bounds':receipt['trace_elapsed_s']<30 and (OUT/'closure.etl').stat().st_size<16*1024*1024 and 'LogFileMode: 0x1,' in text,
        'owned_trace_stopped_and_fixtures_retired':receipt['trace_stopped'] and not receipt['cleanup_errors'] and all(r['qualified'] for r in receipt['fixture_retirements']),
        'clock_correlation':'Host clock pairs retained, but exact raw-QPC event correlation is not established. Scope already failed; no qualification inferred.',
        'interpretation':'Included FIN and deliberate-RST controls have distinct endpoint-linked closure records. This does not diagnose Smoke027 or qualify the collector.',
        'raw_trace_policy':'Keep original ETL/text only at their external local path. Do not publish or copy unrelated process command lines to the repository.',
        'source_bindings':binding,'model_calls':0,'scored_starts':0,
        'next_step':'Do not repeat this netsh collector. Investigate a direct ETW collector with explicit event IDs and fail-closed filters; any broader scope needs an explicit new decision.'
    }
    assert all(c['observed_expected_event_kind'] for c in controls)
    assert scope_failures and result['owned_trace_stopped_and_fixtures_retired']
    with (HERE/'assessment-001.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    with (HERE/'included-control-projection.txt').open('x',encoding='utf-8') as stream:
        stream.write('Selected exact included-control endpoints only; raw trace remains local.\n')
        stream.write('\n'.join(selected)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_bindings','event_counts','out_of_scope_event_counts')},indent=2))


if __name__=='__main__':
    main()
