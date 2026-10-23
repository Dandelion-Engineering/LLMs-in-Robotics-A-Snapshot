"""Real owned fixture processes, simulated OS trace commands; never elevates."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import run_event_coverage as helper


class SimulatedCommands:
    mode = 'success'

    def __init__(self,out):
        self.out = out
        self.active = False
        self.history = []
        self.status_calls = 0

    def pktmon(self,*args,**kw):
        return self.call(helper.base.PKTMON,list(args),**kw)

    def call(self,exe,args,**kw):
        args = list(map(str,args))
        self.history.append({'exe':str(exe),'args':args,'options':kw})
        (self.out/'simulated-command-history.json').write_text(json.dumps(self.history,indent=2)+'\n',encoding='utf-8')
        if Path(exe) == helper.base.PKTMON:
            if args == ['status']:
                return 'Packet Monitor is not running.\n'
            if args == ['filter','list']:
                return 'Packet Filters:\n    None\n' if self.mode != 'foreign-pktmon-filter' else 'Packet Filters:\n  1 Other TCP 443\n'
            if args[0] == 'etl2txt':
                if '--out' in args:
                    Path(args[args.index('--out')+1]).write_text('Simulated export; no OS coverage.\n',encoding='utf-8')
                return 'Simulated export only\n'
            raise AssertionError('Unexpected Packet Monitor mutation')
        assert Path(exe) == helper.base.NETSH
        if args[:3] == ['trace','show','status']:
            if len(args) == 3:
                return helper.base.NETSH_IDLE_TEXT+'\n'
            assert args == ['trace','show','status','sessionname='+helper.SESSION]
            if self.mode == 'preexisting-named':
                return 'Trace File: C:\\unowned.etl\n'
            if not self.active:
                return helper.base.NETSH_IDLE_TEXT+'\n'
            self.status_calls += 1
            if self.mode == 'foreign-replacement' and self.status_calls > 1:
                return 'Trace File: C:\\unowned.etl\n'
            return 'Status: Running\nTrace File: '+str(self.out/'closure.etl')+'\n'
        if args[:2] == ['trace','start']:
            fixtures=json.loads((self.out/'fixtures.json').read_text(encoding='utf-8'))
            assert args == helper.start_arguments(self.out,fixtures[0]['ready'])
            if self.mode == 'failed-start':
                raise RuntimeError('Simulated refused start')
            self.active = True
            if self.mode != 'missing-etl':
                (self.out/'closure.etl').write_bytes(b'SIMULATED-NO-OS-EVENTS')
            if self.mode == 'uncertain-start':
                raise subprocess.TimeoutExpired(args,5)
            return 'Tracing started\n'
        if args[:2] == ['trace','stop']:
            assert args == ['trace','stop','sessionname='+helper.SESSION]
            assert self.active
            if self.mode == 'stop-failure':
                raise RuntimeError('Simulated stop failure')
            self.active = False
            return 'Trace stopped\n'
        raise AssertionError('Unexpected netsh command')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir()
    sources=args.output/'sources';sources.mkdir()
    bindings=[]
    for name,path in {**helper.source_paths(),'test_event_helper.py':Path(__file__)}.items():
        shutil.copyfile(path,sources/name)
        bindings.append({'name':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    rows=[]
    for mode,interrupt in [('success',None),('ready-interruption','ready'),('capture-interruption','capture'),
                           ('foreign-pktmon-filter',None),('preexisting-named',None),('failed-start',None),
                           ('uncertain-start',None),('foreign-replacement',None),('stop-failure',None),('missing-etl',None)]:
        out=args.output/mode
        SimulatedCommands.mode=mode
        with contextlib.redirect_stdout(io.StringIO()):
            code=helper.run(out,commands_type=SimulatedCommands,require_admin=False,interrupt_at=interrupt)
        receipt=json.loads((out/'receipt.json').read_text(encoding='utf-8'))
        history=json.loads((out/'simulated-command-history.json').read_text(encoding='utf-8'))
        starts=[r for r in history if r['args'][:2]==['trace','start']]
        stops=[r for r in history if r['args'][:2]==['trace','stop']]
        passed=(code==0)==(mode=='success') and all(r and r['qualified'] for r in receipt['fixture_retirements'])
        passed &= len(stops)==int(mode in {'success','capture-interruption','uncertain-start','stop-failure','missing-etl'})
        passed &= len(starts)==int(mode not in {'ready-interruption','foreign-pktmon-filter','preexisting-named'})
        rows.append({'mode':mode,'passed':bool(passed),'exit_code':code,'receipt':str(out/'receipt.json')})
    guards=[]
    for ready in ({'pid':True,'port':1234,'address':'127.0.0.1'}, {'pid':1234,'port':70000,'address':'127.0.0.1'}, {'pid':1234,'port':1234,'address':'0.0.0.0'}):
        try:
            helper.start_arguments(args.output,ready)
            guards.append(False)
        except ValueError:
            guards.append(True)
    guards.append(not helper.owned_status('Trace File: C:\\foreign.etl',args.output/'closure.etl'))
    result={'passed':all(r['passed'] for r in rows) and all(guards),'cases':rows,'guards':guards,
            'sources':bindings,'model_calls':0,'real_fixtures':True,'admin_commands_simulated':True,'os_trace_coverage':False}
    helper.base.save(args.output/'receipt.json',result)
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
