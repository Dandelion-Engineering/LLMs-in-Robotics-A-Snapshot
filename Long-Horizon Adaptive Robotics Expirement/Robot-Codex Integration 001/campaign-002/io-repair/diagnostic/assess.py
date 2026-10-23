"""Independent read-only replay of retained IO evidence; never runs benchmark code."""
from __future__ import annotations
import argparse
from array import array
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
INTEGRATION=HERE.parents[2]
REPO=INTEGRATION.parent.parent
sys.path.insert(0,str(INTEGRATION.parent/'Storage Retention Implementation 001/future'))
from recorder import Reader, canonical, pack


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''): h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition: raise ValueError(message)


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def audit_ledger(values, codes):
    require(len(values)%11==0,'Partial timing row')
    rows=[tuple(values[i:i+11]) for i in range(0,len(values),11)]
    require(rows and len(rows)<=250000,'Timing row bound')
    reverse={value:key for key,value in codes.items()}
    require(len(reverse)==len(codes),'Duplicate phase code')
    by_seq={int(row[0]):row for row in rows}
    require(len(by_seq)==len(rows) and sorted(by_seq)==list(range(1,len(rows)+1)),'Missing/duplicate sequence')
    grouped=defaultdict(list); children=defaultdict(list)
    for row in rows:
        seq,parent,code,tick,start,end,cpu,cpu_end,proc,proc_end,failed=row
        require(all(math.isfinite(x) for x in row),'Nonfinite timing')
        require(all(x==int(x) for x in (seq,parent,code,tick,failed)),'Noninteger identity')
        require(code in reverse and end>=start>=0 and cpu_end>=cpu and proc_end>=proc,'Invalid timing interval')
        require(failed==0,'Failed operation retained')
        if parent:
            require(parent<seq and parent in by_seq,'Invalid parent')
            ancestor=by_seq[parent]
            require(ancestor[4]<=start<=end<=ancestor[5],'Child outside parent')
        grouped[reverse[code]].append(row); children[int(parent)].append(row)
    for siblings in children.values():
        siblings.sort(key=lambda row:row[0])
        require(all(a[5]<=b[4] for a,b in zip(siblings,siblings[1:])),'Sibling operations overlap')
    distributions={}
    for name,items in sorted(grouped.items()):
        durations=sorted(row[5]-row[4] for row in items)
        distributions[name]=dict(count=len(items),p50_s=durations[int(.50*(len(items)-1))],
            p95_s=durations[int(.95*(len(items)-1))],p99_s=durations[int(.99*(len(items)-1))],
            maximum_s=durations[-1],above_10ms=sum(x>.01 for x in durations),
            above_25ms=sum(x>.025 for x in durations),above_50ms=sum(x>.05 for x in durations),
            total_inclusive_wall_s=sum(durations),total_thread_cpu_s=sum(row[7]-row[6] for row in items),
            total_process_cpu_s=sum(row[9]-row[8] for row in items),quantile_method='lower order statistic')
    return rows,grouped,distributions


def assess(manifest_path, output):
    manifest=read_json(manifest_path); output=Path(output).resolve(); result=read_json(output/'result.json')
    require(result['manifest_sha256']==sha(manifest_path),'Manifest hash mismatch')
    require(result['run_id']==manifest['run_id'] and result['framework_revision']==manifest['framework_revision'],'Identity mismatch')
    require(result['completed'] is True and result['completed_ticks']==12000 and result['failure'] is None,'Incomplete workload')
    require(result['total_wall_s']<=180,'Total cooperative wall bound')
    require(result['sources_before']==result['sources_after'],'Sources changed during workload')
    for binding in result['sources_before']+manifest['input_bindings']:
        source=REPO/binding['path']
        require(source.stat().st_size==binding['bytes'] and sha(source)==binding['sha256'],'Source binding differs: '+binding['path'])
    actual={p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p.name!='result.json'}
    require(actual==set(result['files']),'Retained inventory differs')
    for relative,binding in result['files'].items():
        path=output/relative
        require(path.stat().st_size==binding['bytes'] and sha(path)==binding['sha256'],'Output binding differs: '+relative)
    observed_bytes=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    require(observed_bytes<134217728,'Observed output bound')
    require(result['pragmas']==[dict(at=when,journal_mode='delete',synchronous=2) for when in ('before','after')],
        'DELETE/FULL readback differs')
    ledger=result['timing']; require(ledger['rows']*88==ledger['bytes'],'Timing dimensions')
    require(ledger['fields']==['sequence','parent','phase','tick','wall_start_s','wall_end_s',
        'thread_cpu_start_s','thread_cpu_end_s','process_cpu_start_s','process_cpu_end_s','failed'],'Timing fields differ')
    require(sha(output/ledger['path'])==ledger['sha256'],'Timing hash differs')
    values=array('d'); values.frombytes((output/ledger['path']).read_bytes())
    if ledger['byteorder']!=sys.byteorder: values.byteswap()
    rows,grouped,distributions=audit_ledger(values,ledger['phase_codes'])
    require(len(rows)==ledger['rows'],'Timing rows differ')
    counts={'workload.tick':12000,'workload.motion':12000,'workload.image':1200,
        'workload.event':1200,'workload.registry':1200,'workload.state':240,'finalize.recorder':1,
        'recorder.sqlite.commit':1213,'journal.event.protected.fsync':1200,
        'journal.event.public.fsync':1200,'journal.state.protected.fsync':240,
        'journal.state.public.fsync':240,'journal.registry.fsync':1200}
    for name,count in counts.items(): require(len(grouped[name])==count,'Operation count differs: '+name)
    children=defaultdict(list)
    names={value:key for key,value in ledger['phase_codes'].items()}
    for row in rows: children[int(row[1])].append(row)
    def sequence_under(row):
        result=[]
        def walk(sequence):
            for child in sorted(children[int(sequence)],key=lambda x:x[0]):
                result.append(names[child[2]]); walk(child[0])
        walk(row[0]); return result
    order_checks={'workload.event':['journal.event.protected.write_flush','journal.event.protected.fsync',
        'journal.event.protected.close','journal.event.public.write_flush','journal.event.public.fsync','journal.event.public.close'],
        'workload.state':['journal.state.protected.fsync','journal.state.protected.close','journal.state.protected.replace',
        'journal.state.public.fsync','journal.state.public.close','journal.state.public.replace'],
        'workload.registry':['journal.registry.fsync','journal.registry.close','journal.registry.replace'],
        'workload.image':['recorder.image','recorder.sqlite.commit','recorder.physical_guard']}
    for name,expected in order_checks.items():
        for row in grouped[name]:
            seq=sequence_under(row); filtered=[x for x in seq if x in expected]
            require(filtered==expected,'Durability order differs: '+name)
    require([int(row[3]) for row in sorted(grouped['workload.motion'],key=lambda x:x[0])]==list(range(12000)),
        'Motion ordering differs')
    schedule=read_json(output/'schedule.json')['rows']
    require(len(schedule)==12000 and [row[0] for row in schedule]==list(range(12000)),'Schedule incomplete')
    require(all(row[1]>=row[0]/100-.001 and row[2]>=row[1] for row in schedule),'Invalid paced schedule')
    require(result['measured_end_s']-result['measured_start_s']>=120,'Measured interval shortened')
    host=REPO/manifest['input_host']
    originals=[json.loads(line) for line in (host/'public-history.jsonl').read_text().splitlines()]
    observations=[row for row in originals if row['type']=='observation']
    protected=(output/'protected/public-history.jsonl').read_bytes()
    require(protected==(output/'public-workspace/live/events.jsonl').read_bytes(),'Protected/public byte parity')
    events=[json.loads(line) for line in protected.splitlines()]
    require(len(events)==1200,'Journal event count')
    for index,event in enumerate(events):
        original=observations[index%len(observations)]
        for key in ('payload','type','source','authority_epoch','owner'):
            require(event[key]==original[key],'Journal exact payload mismatch')
        require(event['event_id']==index+1 and event['run_id']==manifest['run_id'] and event['sim_time_s']==index/10,'Journal identity/time')
    for out,source in [('protected/public-state.json','public-state.json'),('public-workspace/live/state.json','public-state.json'),
                       ('protected/command-registry.json','command-registry.json')]:
        require((output/out).read_bytes()==canonical(read_json(host/source))+b'\n','Atomic snapshot parity')
    require(not list(output.rglob('*.next')),'Unpublished atomic stage remains')
    source_reader=Reader(host/'native-recording'); reader=Reader(output/'native-recording')
    try:
        source_motion=list(source_reader.motion()); motion=list(reader.motion())
        require(len(motion)==12000,'SQLite motion count')
        for index,row in enumerate(motion):
            expected=dict(source_motion[index%len(source_motion)]); expected['sim_time_s']=index/100
            require(pack(row)==pack(expected),'Exact decoded motion payload differs')
        require(list(reader.events())==[],'Unexpected SQLite event rows')
        require(reader.db.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'SQLite integrity failure')
        require(reader.db.execute('SELECT count(*) FROM motion').fetchone()[0]==12,'Motion chunking changed')
        pairs=[source_reader.image(row['id']) for row in source_reader.images() if row['status']=='available']
        images=list(reader.images()); require(len(images)==1200,'SQLite image count')
        available=0; bytes_used=0
        for index,row in enumerate(images):
            require(row['id']=='overhead:'+str(index+1) and row['capture_time_s']==index/10,'Image order/time')
            pair=pairs[(index//20)%len(pairs)]; selected=index%20==0
            expected_available=selected and bytes_used+len(pair['rgb'])+len(pair['depth'])<=12000000
            image=reader.image(row['id'])
            require((image['status']=='available')==expected_available,'Image availability policy differs')
            if expected_available:
                require(image['rgb']==pair['rgb'] and image['depth']==pair['depth'],'Image exact byte mismatch')
                available+=1; bytes_used+=len(pair['rgb'])+len(pair['depth'])
        require(reader.meta['state']=='complete','Recorder not complete')
    finally: source_reader.close(); reader.close()
    return dict(schema='rci-c02-protected-io-assessment-1',run_id=manifest['run_id'],
        framework_revision=manifest['framework_revision'],passed=True,parity=True,durability_order_preserved=True,
        full_operation_rows=len(rows),distributions=distributions,retained_image_pairs=available,
        retained_image_bytes=bytes_used,observed_output_bytes=observed_bytes,
        maximum_scheduled_start_delay_s=max(row[1]-row[0]/100 for row in schedule),
        duration_s=result['measured_end_s']-result['measured_start_s'],
        result_sha256=sha(output/'result.json'),manifest_sha256=sha(manifest_path),
        qualification_passed=False,scorable=False,task_outcome='unknown',
        interpretation='Complete diagnostic only. Latency and CPU intervals do not identify device/filter/scheduler causes. '
        'No qualification threshold, repair adoption, model performance, physics equivalence, or power-loss claim.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--assessment',type=Path,required=True)
    args=parser.parse_args()
    try: value=assess(args.manifest,args.output)
    except Exception as error:
        value=dict(passed=False,error=dict(type=type(error).__name__,message=str(error)),qualification_passed=False,
                   scorable=False,task_outcome='unknown')
    args.assessment.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'assessment':str(args.assessment),'passed':value['passed']}))
    sys.exit(0 if value['passed'] else 1)
