"""Retain one full development check with exact source state and wrapper gates."""
import json
import subprocess
import sys
import prepare as p

def main():
    paths = {row['path'] for row in p.common.read(p.IO/'checks-033-source-state.json')['sources']}
    paths.update(str(path.resolve()) for path in p.HERE.glob('*.py'))
    paths.update(str(path.resolve()) for path in p.WRAPPER.glob('*.py'))
    paths.add(str((p.CAMPAIGN/'harness/test_native_shutdown_order.py').resolve()))
    before = [p.identity(path) for path in sorted(paths)]
    p.common.require(not (p.HERE/'checks-state.json').exists(), 'Existing checks; never overwrite')
    argv = [sys.executable,'-X','utf8','-B',str(p.IO/'record_checks.py'),'run','--directory',str(p.IO/'checks-034')]
    result = subprocess.run(argv,cwd=p.REPO)
    execution = p.common.read(p.IO/'checks-034/test-execution.json')
    output = p.HERE/'wrapper-checks';output.mkdir(exist_ok=False)
    wrapper_argv = [sys.executable,'-X','utf8','-B','-m','unittest','discover','-s',str(p.WRAPPER),'-p','test_*.py','-v']
    with (output/'stdout').open('x',encoding='utf-8') as out,(output/'stderr').open('x',encoding='utf-8') as err:
        wrapper = subprocess.run(wrapper_argv,cwd=p.REPO,stdout=out,stderr=err)
    p.common.save(output/'receipt.json',{'argv':wrapper_argv,'exit_code':wrapper.returncode,'passed':wrapper.returncode==0})
    after = [p.identity(path) for path in sorted(paths)]
    outputs = [p.IO/'checks-034'/n for n in ('test-execution.json','harness.stdout','harness.stderr','assessment.stdout','assessment.stderr')]
    outputs += [output/n for n in ('stdout','stderr','receipt.json')]
    passed = result.returncode == 0 and execution['passed'] is True and wrapper.returncode == 0 and before == after
    p.common.save(p.HERE/'checks-state.json',{'schema':'campaign002-ordered-diagnostic-checks-1',
        'passed':passed,'sources_unchanged':before==after,'sources':after,'outputs':[p.identity(path) for path in outputs]})
    print(json.dumps({'passed':passed,'sources':len(after),'wrapper_exit':wrapper.returncode}))
    raise SystemExit(0 if passed else 1)

if __name__ == '__main__': main()
