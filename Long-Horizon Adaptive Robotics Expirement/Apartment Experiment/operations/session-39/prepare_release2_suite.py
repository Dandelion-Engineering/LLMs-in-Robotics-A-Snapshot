"""Fresh full commissioning suites for exact frozen release002; once-only."""
import argparse
from release2 import *

parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['workspace','offline','recorder','physics','core','native']);args=parser.parse_args()
assert read(ROOT/'retirement001/output/result.json')['passed'] is True
mode=args.mode;files=source_files();entry='runner.py';name=mode+'002'
cases=[dict(mode=mode)]
if mode=='workspace':
    files += [(HERE/n,n) for n in ('qualify_workspace.py','original_reproductions.py')]
    files.append((APP/'operations/session-38/fault_service.py','fault_service.py'))
if mode in ('recorder','physics'):
    entry=mode+'_entry.py'
    old=ROOT/(mode+'001')
    cases=read(old/'manifest.json')['cases']
    names=['physics_matrix.py','endpoint_schedule.py','initial.npz','test_recorder.py' if mode=='recorder' else 'verify_candidate.py']
    if mode=='recorder':names.append('legacy_matrix.py')
    files += [(old/n,n) for n in names]
if mode=='core':
    name='core005';entry='core_complete002.py'
    text=(HERE/'core_suite.py').read_text(encoding='utf-8').replace('native_stream_engineering','current_native_stream_fixture')
    with (HERE/entry).open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
    files += [(HERE/'current_toy_fixture.py','current_toy_fixture.py'),(HERE/'current_navigation_fixture003.py','current_navigation_fixture.py'),(HERE/'current_native_stream_fixture.py','current_native_stream_fixture.py')]
    cases=['All five core groups, unchanged fixed gates and already justified integration fixtures; fresh release002 execution']
if mode=='native':
    for prerequisite in ('workspace002','offline002','recorder002','physics002','core005'):
        assert read(ROOT/prerequisite/'output/result.json')['passed'] is True,prerequisite
        terminal=read(HERE/(prerequisite+'-terminal.json'))
        assert terminal['state']=='succeeded' and type(terminal['exit_status']) is int and terminal['exit_status']==0
register(name,entry,'Fresh complete '+mode+' commissioning against exact release002. All release001 outcomes remain immutable; identical fixed gates and scientific parameters.',files,cases,model_calls=4 if mode=='native' else 0)
build()
