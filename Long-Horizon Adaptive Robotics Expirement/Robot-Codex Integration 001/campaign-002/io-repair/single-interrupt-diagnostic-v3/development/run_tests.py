"""Exclusive local mocked-test receipts; no empirical runner is invoked."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent.parent
target = HERE / 'development' / sys.argv[1]
target.mkdir()
def binding(path):
    data = path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def save(name, value):
    with (target/name).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')
sources = {p.name:binding(p) for p in HERE.glob('*.py')}
for name in sources:
    (target/name).write_bytes((HERE/name).read_bytes())
argv = [sys.executable,'-X','utf8','-B','-m','unittest',*sys.argv[2:],'-v']
save('intent.json', {'argv':argv,'cwd':str(HERE),'sources':sources,
                    'scope':'Mocked wrapper tests and read-only physical import only'})
with (target/'stdout.txt').open('xb') as out, (target/'stderr.txt').open('xb') as err:
    result = subprocess.run(argv,cwd=HERE,stdout=out,stderr=err,timeout=120)
save('receipt.json', {'argv':argv,'cwd':str(HERE),'exit_code':result.returncode,
    'source_bindings':sources,'sources_unchanged':all(binding(HERE/name)==item for name,item in sources.items()),
    'stdout':binding(target/'stdout.txt'),'stderr':binding(target/'stderr.txt')})
print(json.dumps({'path':str(target),'exit_code':result.returncode,
                  'stderr_tail':(target/'stderr.txt').read_text(encoding='utf-8')[-2500:]}))
