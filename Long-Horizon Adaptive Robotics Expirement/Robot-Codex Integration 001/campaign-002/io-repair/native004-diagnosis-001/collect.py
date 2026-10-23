"""Bounded terminal infrastructure metadata only. Never assess or retry."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
C = HERE.parent.parent
REPO = C.parent.parents[1]
QUEUE = REPO.parent/'tools/compute_queue/compute_queue.py'
RUN = 'RCI001-C02-shutdown-diagnostic-004'
JOB = '20260929T172359627310Z-e9b8409e'
RAW = C.parent/'local-evidence/campaign002/io-repair'/RUN/'orchestrator'
ROOT = RAW/'interrupt'
bindings = []

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()
def save(name, value):
    with (HERE/name).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def read(path, maximum):
    if not path.exists(): return None
    if not path.is_file() or path.is_symlink() or path.stat().st_size>maximum: raise ValueError('Input bounds')
    data=path.read_bytes();bindings.append({'path':str(path),'bytes':len(data),'sha256':sha(data)})
    return json.loads(data)

def main():
    status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',JOB],cwd=REPO,text=True,encoding='utf-8'))
    assert status['id']==JOB and type(status['exit_status']) is int
    assert (status['state'],status['exit_status']) in (('succeeded',0),('failed',1))
    save('official-status.json',status)
    save('scope.json',{'run_id':RUN,'job_id':JOB,'diagnostic_only':True,'task_outcome':'unknown',
        'qualification_assessed':False,'bounds':{'sequence':1048576,'client':1048576,'native':262144,
        'ordering':65536,'ledger':1048576,'transport':8388608,'retirement_each':262144,'retirements_max':8},
        'purpose':'Finite shutdown order, error metadata, trigger presence and owned cleanup. No model output or task outcome.'})
    seq=read(RAW/'sequence-result.json',1048576) or {}
    client=read(ROOT/'client/result.json',1048576) or {}
    native=read(ROOT/'client/native-quiescence.json',262144) or {}
    order=read(ROOT/'client/native-shutdown-order.json',65536)
    transport=read(ROOT/'codehost-owner-bridge-v3.json',8388608) or {}
    ledger=ROOT/'codehost-transport-v3.jsonl'
    rows=[]
    if ledger.exists():
        assert ledger.is_file() and not ledger.is_symlink() and ledger.stat().st_size<=1048576
        raw=ledger.read_bytes();assert raw.endswith(b'\n')
        bindings.append({'path':str(ledger),'bytes':len(raw),'sha256':sha(raw)})
        previous=None
        for line in raw.splitlines():
            row=json.loads(line);expected=row.pop('record_sha256')
            assert row['sequence']==len(rows)+1 and row['previous_sha256']==previous and sha(canonical(row))==expected
            row['record_sha256']=expected;previous=expected;rows.append(row)
        assert len(rows)<=16384
    faults=[]
    fields=('sequence','kind','channel_id','observed_perf_counter_ns','operation','exception_class','errno','winerror',
            'cleanup_active','client_finishing','owner_draining','owner_sealed','byte_counters','monotonic_s','wall_unix_s')
    for row in rows:
        if row['kind']=='socket_failure':faults.append({k:row.get(k) for k in fields})
    assert len(faults)<=64
    selected=[]
    for row in rows:
        if row['kind'] in ('client_eof','owner_drain_begin','owner_finishing','failure','channel_closed'):
            selected.append({k:row.get(k) for k in ('sequence','kind','channel_id','monotonic_s','wall_unix_s','code','client_finishing')})
    retirements=[]
    paths=sorted(ROOT.glob('*retirement*.json'));assert len(paths)<=8
    for path in paths:
        value=read(path,262144)
        retirements.append({'filename':path.name,'qualified':value.get('qualified'),
                            'retired':value.get('retired'),'namespace_members':value.get('namespace_members')})
    stage=(seq.get('stages') or [{}])[0]
    result={'schema':'campaign002-native004-order-observations-1','run_id':RUN,'job_id':JOB,
        'queue_state':status['state'],'queue_exit':status['exit_status'],'diagnostic_only':True,'task_outcome':'unknown',
        'orchestrator_completed':seq.get('orchestrator_completed'),'resume_attempted':seq.get('resume_attempted'),
        'host_exit_code':seq.get('host_exit_code'),
        'stage':{k:stage.get(k) for k in ('injected_interruption','all_namespaces_retired','cleanup_clean','durable_retention_verified','old_token_denied_after_retirement')},
        'trigger_present':'command_at_interruption' in stage,
        'client':{k:client.get(k) for k in ('model_started','success','turn_status')},
        'native':{k:native.get(k) for k in ('qualified','failures','handshake_qualified','stdin_closed','forced_job_close','native_exit_code')},
        'order':order,'ledger_rows_verified':len(rows),'socket_failures':faults,'transport_timeline':selected,
        'transport':{k:transport.get(k) for k in ('qualified','failures','attempts','accepted','denied','queued_bytes_at_close')},
        'retirements':retirements,'inputs':bindings}
    for row in bindings:
        raw=Path(row['path']).read_bytes();assert len(raw)==row['bytes'] and sha(raw)==row['sha256']
    result['original_inputs_unchanged']=True
    save('observations.json',result)
    print(json.dumps({k:result[k] for k in ('queue_state','queue_exit','trigger_present','stage','native','socket_failures','order','retirements')},indent=2))

if __name__=='__main__':main()
