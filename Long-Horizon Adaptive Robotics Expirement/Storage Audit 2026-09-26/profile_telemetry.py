"""Queued bounded read-only telemetry sample; correct nested history schema.

No compression or source changes. Supersedes the empty optional sample in
event-profile.json; its full event byte accounting remains valid.
"""
import hashlib
import json
from pathlib import Path
import re
import time

HERE=Path(__file__).resolve().parent
ATTEMPTS=HERE.parent/'Evidence/releases/batch01-eval-r4/attempts'
OUT=HERE/'telemetry-profile.json'
if OUT.exists():raise SystemExit('Refusing to replace output')
pattern=re.compile(rb'"event_type"\s*:\s*"([^"\\]+)"')
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
samples=[];started=time.time()
for path in sorted(ATTEMPTS.glob('*/evidence/events.jsonl')):
    run=path.parents[1].name
    if not(any(f'-{c}-rep1-' in run for c in ('C01','C14','C24')) and run.endswith('-persistent')):continue
    st=path.stat()
    for fraction in (.1,.5,.9):
        count=raw=telemetry=occurrences=unique=0;seen=set()
        with path.open('rb') as f:
            f.seek(int(st.st_size*fraction));f.readline()
            while line:=f.readline():
                m=pattern.search(line[:2048])
                if not m or m.group(1)!=b'observation':continue
                x=json.loads(line);history=x['payload']['packet']['arm']['telemetry_history'];rows=history['samples']
                assert isinstance(rows,list)
                count+=1;raw+=len(line);telemetry+=len(canonical(rows));occurrences+=len(rows)
                for row in rows:
                    b=canonical(row);h=hashlib.sha256(b).digest()
                    if h not in seen:seen.add(h);unique+=len(b)
                if count>=64:break
        samples.append(dict(run_id=run,byte_fraction=fraction,observations=count,source_line_bytes=raw,
                            serialized_telemetry_bytes=telemetry,telemetry_row_occurrences=occurrences,
                            unique_telemetry_rows=len(seen),unique_telemetry_bytes=unique,
                            illustrative_per_row_references_bytes=occurrences*80,
                            illustrative_range_references_bytes=count*100))
    after=path.stat();assert(st.st_size,st.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    print(run,flush=True)
keys=('observations','source_line_bytes','serialized_telemetry_bytes','telemetry_row_occurrences',
      'unique_telemetry_rows','unique_telemetry_bytes','illustrative_per_row_references_bytes','illustrative_range_references_bytes')
totals={key:sum(s[key] for s in samples) for key in keys}
assert len(samples)==36 and totals['observations']>0
out=dict(started_unix=started,finished_unix=time.time(),selection='C01/C14/C24 replicate1, all four persistent entrants, 64 observations after10/50/90 percent byte offsets',
         samples=samples,totals=totals,
         limitations='Fixed byte-offset windows, not independent random samples. Exact equality is for canonical serialized telemetry rows within each window. Range encoding100 bytes/window and per-row80 bytes are illustrative overhead assumptions; no codec/compression implemented, no demonstrated original-byte restoration. Extrapolation is a scenario, not measured whole-batch savings.',
         correction='Initial full-event profile looked for telemetry_history as a list; actual schema is telemetry_history.samples. Its optional samples were empty; full event type/byte counts remain valid.')
with OUT.open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
print(json.dumps(totals,indent=2),flush=True)
