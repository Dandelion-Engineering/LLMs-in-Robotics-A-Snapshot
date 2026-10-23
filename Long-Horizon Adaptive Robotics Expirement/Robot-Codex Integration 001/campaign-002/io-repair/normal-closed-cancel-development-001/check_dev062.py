"""Fixed synthetic comparison and retained paired fixture; no native launch."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
import zipfile

D=Path(__file__).resolve().parent
C=D.parents[1]
R=C.parents[2]
H=C/'harness'
sys.path.insert(0,str(H))
import codehost_mux_protocol as new
from test_codehost_mux_protocol import h2
from test_codehost_bridge_v3 import BridgeTests

def bind(p):
    raw=p.read_bytes()
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

release=R/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-062'
member=(H/'codehost_mux_protocol.py').relative_to(R).as_posix()
with zipfile.ZipFile(release/'code.zip') as z:raw=z.read(member)
assert hashlib.sha256(raw).hexdigest()=='f3e80e370242254b03b748e4bcc4690242a8229f57aeac08900a723cf814b5c6'
assert json.loads((release/'snapshot.json').read_text())['sources'][member]['sha256']==hashlib.sha256(raw).hexdigest()
old=types.ModuleType('dev062_mux');exec(compile(raw,str(release/'code.zip')+'!'+member,'exec'),old.__dict__)

def projected(w):
    value=copy.deepcopy(w.summary());value.pop('terminal_control_records',None)
    return value

ready=[('upload',new.PREFACE+h2(4)),('download',h2(4))]
opened=[('upload',h2(1,5,1,b'x'))]
closed=opened+[('download',h2(1,5,1,b'y'))]
rst=lambda stream,code=8:h2(3,0,stream,code.to_bytes(4,'big'))
workloads={
    'normal_idle':ready+closed,
    'active_reset':ready+opened+[('download',rst(1))],
    'active_reset_blocks_retirement':ready+opened+[('upload',rst(1)),('retire',None)],
    'previous_reset_duplicate':ready+opened+[('upload',rst(1)),('download',rst(1))],
    'unknown_reset':ready+[('upload',rst(7))],
    'skipped_reset':ready+[('upload',h2(1,4,5,b'x')),('upload',rst(3))],
    'closed_download_cancel':ready+closed+[('download',rst(1))],
    'closed_other_code0':ready+closed+[('upload',rst(1,0))],
    'closed_other_code2':ready+closed+[('upload',rst(1,2))],
    'retirement_active_cancel':ready+opened+[('retire',None),('upload',rst(1))],
    'retirement_closed_cancel':ready+closed+[('retire',None),('upload',rst(1))],
    'reset_crosses_retirement':ready+closed+[('upload',rst(1)[:8]),('retire',None),('upload',rst(1)[8:])],
    'reset_active_crosses_retirement':ready+opened+[('upload',rst(1)[:8]),('retire',None),('upload',rst(1)[8:])],
    'retirement_new_headers':ready+opened+[('retire',None),('upload',h2(1,5,3,b'x')+rst(3))],
    'wrong_flags':ready+closed+[('upload',h2(3,1,1,b'1234'))],
    'wrong_length':ready+closed+[('upload',h2(3,0,1,b'123'))],
    'stream_zero':ready+[('upload',rst(0))],
    'incomplete_upload':ready+[('upload',h2(1,4,1,b'x')),('download',h2(1,5,1,b'y')),('upload',rst(1))],
    'incomplete_headers':ready+[('upload',h2(1,1,1,b'x')),('download',h2(1,5,1,b'y')),('upload',rst(1))],
}
rows=[]
for label,steps in workloads.items():
    for width in (1,3,9,13,65536):
        witnesses=[old.H2Witness(),new.H2Witness()]
        forward=[hashlib.sha256(),hashlib.sha256()]
        calls=0
        for direction,wire in steps:
            chunks=[None] if direction=='retire' else [wire[i:i+width] for i in range(0,len(wire),width)]
            for chunk in chunks:
                outcomes=[]
                for i,w in enumerate(witnesses):
                    try:
                        if direction=='retire':w.begin_retirement()
                        else:
                            w.feed(direction,chunk)
                            forward[i].update(direction.encode()+len(chunk).to_bytes(4,'big')+chunk)
                        outcomes.append(None)
                    except ValueError as error:outcomes.append(str(error))
                calls+=1
                assert outcomes[0]==outcomes[1],(label,width,outcomes)
                assert projected(witnesses[0])==projected(witnesses[1]),(label,width)
        assert forward[0].digest()==forward[1].digest()
        rows.append({'workload':label,'width':width,'calls':calls,'same_outcomes_summary_counters_and_accepted_bytes':True})

changes=[]
for width in (1,3,9,13,65536):
    a,b=old.H2Witness(),new.H2Witness()
    for direction,wire in ready+[('upload',h2(1,5,27,b'synthetic')),('download',h2(1,5,27,b'synthetic'))]:
        a.feed(direction,wire);b.feed(direction,wire)
    assert projected(a)==projected(b)
    wire=rst(27);old_error=None
    for offset in range(0,len(wire),width):
        try:a.feed('upload',wire[offset:offset+width])
        except ValueError as error:old_error=str(error)
        b.feed('upload',wire[offset:offset+width])
    assert old_error=='HTTP/2 reset on unavailable stream'
    summary=b.idle_eof()
    assert summary['reset_streams']==0 and summary['closed_streams']==1 and summary['last_stream_id']==27
    assert len(summary['terminal_control_records'])==1
    changes.append({'width':width,'dev062_error':old_error,'new_terminal_control':summary['terminal_control_records'][0],
                    'scope':'Synthetic structural class only; not a replay of Diagnostic002 bytes or outcome.'})

class PairedFixture(BridgeTests):
    async def test_retain_actual_paired_producer(self):
        await self.test_normal_closed_cancel_is_forwarded_and_proved_at_both_endpoints()
        for name in ['codehost-owner-bridge-v3.json','codehost-transport-v3.jsonl','codehost-owner-stderr-v3.txt']:
            with (D/('paired-'+name)).open('xb') as f:f.write((self.folder/name).read_bytes())

result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([PairedFixture('test_retain_actual_paired_producer')]))
assert result.wasSuccessful()
value={'schema':'campaign002-normal-closed-cancel-dev062-comparison-1',
       'scope':'Fixed synthetic parser comparisons and mocked paired production bridge/namespace; no native/model/OS/queue launch, historical outcome reassessment or qualification claim.',
       'archive':bind(release/'code.zip'),'snapshot':bind(release/'snapshot.json'),'member':member,
       'dev062_member_sha256':hashlib.sha256(raw).hexdigest(),
       'sources':{name:bind(H/name) for name in ['codehost_mux_protocol.py','test_codehost_mux_protocol.py','test_codehost_bridge_v3.py','codehost_bridge_v3.py','codehost_inside_v3.py']},
       'script':bind(Path(__file__)),'unchanged_case_count':len(rows),'unchanged_cases':rows,
       'declared_changed_cases':changes,
       'paired_fixture':{name:bind(D/('paired-'+name)) for name in ['codehost-owner-bridge-v3.json','codehost-transport-v3.jsonl','codehost-owner-stderr-v3.txt']}}
with (D/'dev062-comparison.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2);f.write('\n')
print(json.dumps({'passed':True,'unchanged_cases':len(rows),'changed_cases':len(changes),'receipt':bind(D/'dev062-comparison.json')}))
