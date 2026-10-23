"""Retain bounded repair checks and bind their exact inputs before a freeze."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
REPO=CAMPAIGN.parent.parents[1]

def identity(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','bind']);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--snapshot',type=Path);a=p.parse_args();root=a.directory.resolve()
    if a.action=='run':
        root.mkdir(parents=True,exist_ok=False)
        commands=[]
        targets=[('harness',CAMPAIGN/'harness','test_*.py'),('assessment',CAMPAIGN/'assessment','test_*.py')]
        for label,directory,pattern in targets:
            files=sorted(directory.glob(pattern));before=[identity(x) for x in files]
            argv=[sys.executable,'-X','utf8','-B','-m','unittest','discover','-s',str(directory),'-p',pattern,'-v']
            with (root/(label+'.stdout')).open('x',encoding='utf-8') as out,(root/(label+'.stderr')).open('x',encoding='utf-8') as err:
                result=subprocess.run(argv,cwd=REPO,stdout=out,stderr=err)
            after=[identity(x) for x in files]
            commands.append({'argv':argv,'exit_code':result.returncode,'test_inputs':before,
                'stdout':identity(root/(label+'.stdout')),'stderr':identity(root/(label+'.stderr')),
                'test_sources_unchanged':before==after})
            print(json.dumps({'suite':label,'exit_code':result.returncode,'sources_unchanged':before==after}),flush=True)
        save(root/'test-execution.json',{'commands':commands,'passed':all(x['exit_code']==0 and x['test_sources_unchanged'] for x in commands)})
    else:
        snapshot=json.loads(a.snapshot.read_text(encoding='utf-8'))
        tests=json.loads((root/'test-execution.json').read_text(encoding='utf-8'))
        if not tests['passed']:raise ValueError('Tests did not pass')
        for command in tests['commands']:
            for item in command['test_inputs']:
                path=Path(item['path']);relative=path.relative_to(REPO).as_posix()
                if snapshot['sources'].get(relative,{}).get('sha256')!=item['sha256'] or identity(path)!=item:
                    raise ValueError('Test input not frozen unchanged: '+str(path))
        value={'schema':'campaign002-repair-test-receipt-1','source_snapshot':identity(a.snapshot),
               'passed':True,'commands':tests['commands']}
        save(root/'repair-test-receipt.json',value)
        print(json.dumps({'receipt':identity(root/'repair-test-receipt.json'),'commands':len(tests['commands'])}))

if __name__=='__main__':main()
