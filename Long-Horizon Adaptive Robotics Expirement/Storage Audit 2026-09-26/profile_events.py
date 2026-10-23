"""Queued read-only event byte accounting plus bounded redundancy sampling.

Does not compress, rewrite, or copy source evidence. Full pass inspects event
headers and lengths only. The bounded sample decodes 64 observations after
10/50/90 percent byte offsets in C01/C14/C24 replicate1 persistent runs.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import time

HERE=Path(__file__).resolve().parent
EXP=HERE.parent
ATTEMPTS=EXP/'Evidence/releases/batch01-eval-r4/attempts'
OUTPUT=HERE/'event-profile.json'
if OUTPUT.exists():raise SystemExit('Refusing to overwrite audit output')
kind_re=re.compile(rb'"event_type"\s*:\s*"([^"\\]+)"')
event_totals=collections.defaultdict(lambda:[0,0])
runs=[];samples=[];started=time.time()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

for path in sorted(ATTEMPTS.glob('*/evidence/events.jsonl')):
    before=path.stat();run_id=path.parents[1].name
    totals=collections.defaultdict(lambda:[0,0]);line_count=0
    with path.open('rb',buffering=8*1024*1024) as f:
        for line in f:
            match=kind_re.search(line[:2048])
            kind=match.group(1).decode() if match else '(unclassified)'
            totals[kind][0]+=1;totals[kind][1]+=len(line);line_count+=1
    after=path.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    assert sum(x[1] for x in totals.values())==before.st_size
    for key,(n,s) in totals.items():event_totals[key][0]+=n;event_totals[key][1]+=s
    runs.append(dict(run_id=run_id,bytes=before.st_size,events=line_count,types=dict(totals)))
    if any(f'-{case}-rep1-' in run_id for case in ('C01','C14','C24')) and run_id.endswith('-persistent'):
        for fraction in (.1,.5,.9):
            count=total_line=total_telemetry=unique_bytes=total_rows=0;seen={};other_packet=0
            with path.open('rb') as f:
                f.seek(int(before.st_size*fraction));f.readline()
                while line:=f.readline():
                    match=kind_re.search(line[:2048])
                    if not match or match.group(1)!=b'observation':continue
                    item=json.loads(line)
                    packet=item.get('payload',{}).get('packet',{})
                    rows=packet.get('arm',{}).get('telemetry_history',[])
                    if not isinstance(rows,list):continue
                    count+=1;total_line+=len(line);total_telemetry+=len(canonical(rows));total_rows+=len(rows)
                    for row in rows:
                        b=canonical(row);digest=hashlib.sha256(b).hexdigest()
                        if digest not in seen:seen[digest]=len(b);unique_bytes+=len(b)
                    if count>=64:break
            samples.append(dict(run_id=run_id,byte_fraction=fraction,observations=count,
                                source_line_bytes=total_line,serialized_telemetry_bytes=total_telemetry,
                                telemetry_row_occurrences=total_rows,unique_telemetry_rows=len(seen),
                                unique_telemetry_bytes=unique_bytes,
                                illustrative_reference_bytes=total_rows*80,
                                note='80 bytes per row reference is a conservative illustrative encoding allowance, not an implemented codec. Canonical serialization measures object values, not original file byte recovery.'))
    if len(runs)%25==0:print(f'Profiled {len(runs)} runs',flush=True)

result=dict(started_unix=started,finished_unix=time.time(),runs=len(runs),
            total_event_bytes=sum(r['bytes'] for r in runs),event_types=dict(sorted(event_totals.items(),key=lambda kv:kv[1][1],reverse=True)),
            run_profiles=runs,telemetry_samples=samples,
            limitations='Full byte/type accounting is not content-hash validation. Telemetry samples are fixed byte-offset windows, not random or independent trials; do not treat extrapolation as measured savings. No compression performed and no original evidence modified.')
with OUTPUT.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ('run_profiles','telemetry_samples')},indent=2),flush=True)
