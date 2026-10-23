"""Real owned fixtures and TDH predicates; simulated session APIs, no elevation."""
import argparse
import contextlib
import ctypes as C
import hashlib
import io
import json
from pathlib import Path
import shutil
import uuid
import run_direct_coverage as helper
import etw_session as e
import read_etl


class Commands:
    def __init__(self,out): pass
    def pktmon(self,*args,**kw):
        if args==('status',): return 'Packet Monitor is not running.'
        if args==('filter','list'): return 'Packet Filters:\nNone'
        raise AssertionError('No Packet Monitor mutation allowed')
    def call(self,exe,args,**kw):
        assert Path(exe)==helper.base.NETSH and args==['trace','show','status']
        return helper.base.NETSH_IDLE_TEXT


class API:
    def __init__(self,mode):
        self.mode=mode;self.active=False;self.history=[];self.identity=None
    def start(self,handle,name,prop):
        self.history.append('start')
        if self.mode=='start-failed': return 5
        C.cast(handle,C.POINTER(e.U64))[0]=12345
        self.identity=e.snapshot(C.cast(prop,C.POINTER(e.PROPERTY_BUFFER)).contents)
        self.active=True
        if self.mode!='missing-etl': Path(self.identity['path']).write_bytes(b'SIMULATED-ETL-NOT-COVERAGE')
        return 0
    def enable(self,*args):
        self.history.append('enable')
        return 87 if self.mode=='enable-failed' else 0
    def control(self,handle,name,prop,op):
        self.history.append('stop' if op==1 else 'query')
        if op==1:
            if self.mode=='stop-failed': return 5
            self.active=False;return 0
        if not self.active:
            if self.mode=='preexisting' or (self.identity and self.mode=='post-stop-present'): return 0
            return 4201
        if self.mode=='query-failed': return 5
        b=C.cast(prop,C.POINTER(e.PROPERTY_BUFFER)).contents
        b.p.Wnode.Guid=e.GUID.make(str(uuid.uuid4()) if self.mode=='foreign-guid' else self.identity['guid'])
        b.logger=self.identity['name']
        b.filename=str(Path(self.identity['path']).with_name('foreign.etl')) if self.mode=='foreign-path' else self.identity['path']
        b.p.MaximumFileSize=32 if self.mode=='bounds-changed' else 16
        b.p.LogFileMode=1;b.p.EnableFlags=0
        return 0


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir();sources=args.output/'sources';sources.mkdir()
    bindings=[]
    for name,path in helper.source_paths().items() | {'test_direct.py':Path(__file__)}.items():
        shutil.copyfile(path,sources/name)
        bindings.append({'name':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    cases=[]
    modes=['success','ready-interruption','capture-interruption','preexisting','start-failed','enable-failed',
           'foreign-guid','foreign-path','bounds-changed','query-failed','stop-failed','post-stop-present','missing-etl']
    for mode in modes:
        api=API(mode)
        out=args.output/mode
        interrupt={'ready-interruption':'ready','capture-interruption':'capture'}.get(mode)
        with contextlib.redirect_stdout(io.StringIO()):
            code=helper.run(out,require_admin=False,commands_type=Commands,api=api,interrupt_at=interrupt)
        receipt=json.loads((out/'receipt.json').read_text(encoding='utf-8'))
        must_stop=mode in {'success','capture-interruption','enable-failed','bounds-changed','stop-failed','post-stop-present','missing-etl'}
        passed=((code==0)==(mode=='success') and ('stop' in api.history)==must_stop
                and all(r and r['qualified'] for r in receipt['fixture_retirements']))
        cases.append({'mode':mode,'passed':passed,'exit_code':code,'api_history':api.history,'receipt':str(out/'receipt.json')})
    filters=[]
    for pids in ([10001],[10001,10002]):
        f=e.PayloadFilters(pids)
        filters.append({'pids':pids,'rows':f.rows,'aggregate_bytes':int(f.aggregate.Size)})
        f.close()
    guards=[]
    for pids in ([],[True],[0],[1,1],[1,2,3]):
        try: e.PayloadFilters(pids);guards.append(False)
        except ValueError: guards.append(True)
    fixture=json.loads((helper.HERE/'decoder-probe-001.json').read_text(encoding='utf-8'))
    reader_ok=(not fixture['decode_errors'] and fixture['raw_qpc_mode'] and len(fixture['allowed_events'])==12
               and fixture['decoder_sha256']==hashlib.sha256((helper.HERE/'read_etl.py').read_bytes()).hexdigest())
    reset=[r for r in fixture['allowed_events'] if r['id']==1044 and r['fields']['Status']==0xC000020D]
    reader_ok &= len(reset)==1 and reset[0]['fields']['ProcessId']==49492 and reset[0]['fields']['LocalAddress']['port']==55784
    for raw in (b'',b'\0'*257,b'\0'*16):
        try: read_etl.decode_payload(raw,'<template><data name="x" inType="win:UInt32"/></template>',8);guards.append(False)
        except ValueError: guards.append(True)
    result={'passed':all(r['passed'] for r in cases) and all(guards) and reader_ok,'cases':cases,'guards':guards,
        'reader_terminal_control_passed':bool(reader_ok),'filter_construction':filters,'sources':bindings,
        'model_calls':0,'real_fixtures':True,'real_tdh_filters':True,'etw_apis_simulated':True,'os_trace_coverage':False}
    helper.base.save(args.output/'receipt.json',result)
    print(json.dumps({'passed':result['passed'],'cases':cases,'guards':guards,'reader_passed':bool(reader_ok)},indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
