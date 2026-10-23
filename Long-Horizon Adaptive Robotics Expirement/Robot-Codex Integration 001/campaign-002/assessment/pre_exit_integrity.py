"""Additional pre-exit ordering proof after complete transport qualification.

This reader never replaces native, endpoint-byte, H2, ownership or retirement
assessment. It imports no runtime barrier implementation.
"""
import hashlib
import json
import math
from pathlib import Path
import re

PREFIX='Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/'
METHOD=PREFIX+'io-repair/native-pre-exit-drain-001/DECLARATION.md'
HELPER=PREFIX+'harness/native_exit_drain.py'
SOURCE_NAMES=(METHOD,HELPER)+tuple(PREFIX+p for p in (
    'harness/native_quiescence.py','harness/codehost_bridge_v3.py','harness/runtime.py',
    'assessment/pre_exit_integrity.py','assessment/transport_integrity_v3.py'))

def require(value,message):
    if value is not True:raise ValueError('Pre-exit ordering: '+message)

def digest(raw):return hashlib.sha256(raw).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def finite(v):return type(v) in (int,float) and math.isfinite(v) and v>=0
def ns(v):return type(v) is int and v>0

def object_pairs(pairs):
    value={}
    for key,item in pairs:
        require(key not in value,'duplicate JSON field');value[key]=item
    return value

def read(root,name,maximum,bindings):
    path=Path(root)/name
    require(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=maximum,
            'missing or unbounded '+name)
    raw=path.read_bytes();require(raw.endswith(b'\n') and len(raw)<=maximum,'incomplete '+name)
    value=json.loads(raw,object_pairs_hook=object_pairs,
                     parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    bindings[name]={'bytes':len(raw),'sha256':digest(raw)}
    return value

def enabled(frozen):
    sources=frozen.get('sources',{})
    require((METHOD in sources)==(HELPER in sources),'incomplete declared source lineage')
    return METHOD in sources

def verify(root,frozen,rows,channels,quiescence,*,repo):
    """The caller has already verified these complete rows/channels/quiescence."""
    try:return _verify(root,frozen,rows,channels,quiescence,repo=repo)
    except (KeyError,IndexError,TypeError,AttributeError,UnicodeError) as error:
        raise ValueError('Pre-exit ordering: malformed evidence') from error

def _verify(root,frozen,rows,channels,quiescence,*,repo):
    require(enabled(frozen),'method not declared')
    sources={}
    for name in SOURCE_NAMES:
        path=Path(repo)/name
        require(path.is_file() and not path.is_symlink(),'source unavailable')
        raw=path.read_bytes();identity={'sha256':digest(raw),'bytes':len(raw)}
        require(frozen['sources'].get(name)==identity,'source differs from freeze: '+name)
        sources[name]=identity
    require(isinstance(quiescence,dict) and quiescence.get('passed') is True,'native proof absent')
    bindings={}
    native=read(root,'client/native-pre-exit-drain.json',16384,bindings)
    bridge=read(root,'codehost-pre-exit-drain.json',16384,bindings)
    order=read(root,'client/native-shutdown-order.json',65536,bindings)
    receipt=read(root,'client/native-quiescence.json',262144,bindings)
    require(quiescence['input_bindings'].get('client/native-quiescence.json')
            ==bindings['client/native-quiescence.json'],'native receipt changed')
    require(receipt.get('qualified') is True and receipt.get('forced_job_close') is False,
            'native completion not graceful')
    cleanup=quiescence['cleanup_barrier']
    expected={'schema':'campaign002-native-pre-exit-request-1',
        'cleanup_request_sha256':digest(canonical(cleanup['request'])),
        'owner_receipt_sha256':cleanup['request']['owner_receipt_sha256'],
        'start_monotonic_s':quiescence['start_monotonic_s'],
        'graceful_deadline_monotonic_s':quiescence['graceful_deadline_monotonic_s']}
    require(cleanup['request_sha256']==expected['cleanup_request_sha256']
            and expected['graceful_deadline_monotonic_s']==expected['start_monotonic_s']+5,
            'cleanup identity or original deadline')
    require(isinstance(native,dict) and set(native)=={'schema','request','bridge',
        'begin_perf_counter_ns','received_perf_counter_ns'}
        and native['schema']=='campaign002-native-pre-exit-client-1'
        and native['request']==expected and native['bridge']==bridge,'native join identity')
    require(isinstance(bridge,dict) and set(bridge)=={'schema','request','qualified','channels',
        'ledger_prefix','completed_monotonic_s','completed_perf_counter_ns'}
        and bridge['schema']=='campaign002-native-pre-exit-bridge-1'
        and bridge['request']==expected and bridge['qualified'] is True,'bridge join identity')
    require(isinstance(bridge['channels'],list) and all(type(v) is int for v in bridge['channels'])
            and bridge['channels']==list(channels),'channel set differs')
    prefix=bridge['ledger_prefix']
    require(isinstance(prefix,dict) and set(prefix)=={'sequence','sha256'}
            and type(prefix['sequence']) is int and 1<=prefix['sequence']<=len(rows)
            and rows[prefix['sequence']-1]['record_sha256']==prefix['sha256'],'ledger prefix differs')
    witnessed=rows[:prefix['sequence']]
    require(not any(r['kind'] in ('failure','socket_failure','channel_denied') for r in witnessed),
            'failed ledger prefix')
    for kind in ('owner_finishing','namespace_finished'):
        require(sum(r['kind']==kind for r in witnessed)==1,'prefix lacks '+kind)
    for cid in channels:
        for kind in ('client_eof','upload_drained','channel_closed'):
            require(sum(r['kind']==kind and r.get('channel_id')==cid for r in witnessed)==1,
                    'prefix lacks channel '+kind)
    completed=bridge['completed_monotonic_s']
    require(finite(completed) and expected['start_monotonic_s']<=completed
            <expected['graceful_deadline_monotonic_s']
            and rows[prefix['sequence']-1]['monotonic_s']<=completed,'late or stale ledger prefix')
    require(isinstance(order,dict) and set(order)=={'schema','lifecycle','stdin_close'}
            and order['schema']=='campaign002-native-shutdown-order-1','ordering sidecar shape')
    events=receipt['events'];lifecycle=order['lifecycle']
    require(isinstance(lifecycle,list) and len(lifecycle)==len(events)<=24,'lifecycle count')
    for observed,event in zip(lifecycle,events):
        require(isinstance(observed,dict) and set(observed)=={'sequence','phase','observed_perf_counter_ns'}
                and type(observed['sequence']) is int and observed['sequence']==event['sequence']
                and observed['phase']==event['phase'] and ns(observed['observed_perf_counter_ns']),
                'lifecycle event mismatch')
    require(all(a['observed_perf_counter_ns']<=b['observed_perf_counter_ns']
                for a,b in zip(lifecycle,lifecycle[1:])),'nonmonotonic observations')
    intervals=order['stdin_close']
    require(isinstance(intervals,list) and len(intervals)==1,'stdin close count')
    close=intervals[0]
    require(isinstance(close,dict) and set(close)=={'begin_perf_counter_ns','end_perf_counter_ns','returned_normally'}
            and close['returned_normally'] is True,'stdin close shape')
    def event_ns(phase):
        values=[r['observed_perf_counter_ns'] for r in lifecycle if r['phase']==phase]
        require(len(values)==1,'lifecycle phase count');return values[0]
    ordered=[event_ns('finishing'),native['begin_perf_counter_ns'],bridge['completed_perf_counter_ns'],
             native['received_perf_counter_ns'],close['begin_perf_counter_ns'],close['end_perf_counter_ns'],
             event_ns('stdin_closed'),event_ns('native_exit')]
    require(all(ns(v) for v in ordered) and all(a<=b for a,b in zip(ordered,ordered[1:])),
            'stdin close preceded complete transport drain')
    # Recheck every newly consumed protected file after the join.
    for name,identity in bindings.items():
        raw=(Path(root)/name).read_bytes()
        require(identity=={'bytes':len(raw),'sha256':digest(raw)},'input changed during verification')
    return {'schema':'campaign002-native-pre-exit-proof-1','passed':True,
        'channels':list(channels),'ledger_prefix':prefix,'source_bindings':sources,'input_bindings':bindings,
        'scope':'Additional pre-exit ordering only; complete native and transport proofs remain required.'}
