"""Independent full-system reader, plus explicit native retirement receipts."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]))
import build_viewer
import qualify_audit
from common import save,sha,HERE
build_viewer.HERE=ROOT
code=qualify_audit.run(ROOT/'system-002','20261004T041522847742Z-052bd089',ROOT/'independent-audit')
assert code==0,'Original full-system gates failed'
native=json.loads((ROOT/'independent-audit/raw/journal/native-exit.json').read_text())
rows=[json.loads(x) for x in (ROOT/'independent-audit/raw/journal/mutations.jsonl').read_text().splitlines()]
lifetime=json.loads((ROOT/'system-002/workspace-block/close-lifetime.json').read_text())
assert lifetime['completed'] and lifetime['error'] is None
assert rows[-1]['type']=='final' and sum(r['type']=='final' for r in rows)==1
assert native['final_sequence']==rows[-1]['sequence'] and native['final_state_sha256']==rows[-1]['state_sha256']
requests=[r for r in rows if r.get('label')=='retirement-requested']
if native['requested_sigterm']:
    assert native['libfuse_main_return'] in (0,8) and len(requests)==1
    assert requests[0]['sequence']+1==rows[-1]['sequence'] and requests[0]['state_sha256']==rows[-1]['state_sha256']
    assert lifetime['retirement_request']['sequence']==requests[0]['sequence']
else:assert native['libfuse_main_return']==0 and not requests
save(ROOT/'retirement-reader-receipt.json',dict(passed=True,model_calls=0,native_exit=native,
    full_system_reader_receipt_sha256=sha(ROOT/'independent-audit/receipt.json'),
    source_hashes={p.name:sha(p) for p in [HERE/'qualify_audit.py',HERE/'verify_journal.py',Path(__file__)]}))
print(json.dumps({'passed':True,'native_exit':native}),flush=True)
