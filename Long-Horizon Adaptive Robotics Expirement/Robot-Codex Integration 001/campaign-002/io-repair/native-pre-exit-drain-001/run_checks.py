"""One source-bound full development check; preserve any failure."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
C=HERE.parent.parent
REPO=C.parent.parents[1]

def identity(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def main():
    old=json.loads((HERE.parent/'native-shutdown-order-001/checks-state-002.json').read_text(encoding='utf-8'))
    paths={Path(row['path']) for row in old['sources']}
    paths.update(C.joinpath('harness').glob('*.py'));paths.update(C.joinpath('assessment').glob('*.py'))
    paths.update(HERE.glob('*.py'));paths.update(HERE.glob('*.md'))
    before=[identity(path) for path in sorted(paths)]
    receipt=HERE/'checks-state-001.json'
    if receipt.exists():raise ValueError('Existing check state; never repeat')
    command=[sys.executable,'-X','utf8','-B',str(HERE.parent/'record_checks.py'),'run',
             '--directory',str(HERE.parent/'checks-036')]
    result=subprocess.run(command,cwd=REPO)
    execution=json.loads((HERE.parent/'checks-036/test-execution.json').read_text(encoding='utf-8'))
    after=[identity(path) for path in sorted(paths)]
    passed=result.returncode==0 and execution['passed'] is True and before==after
    with receipt.open('x',encoding='utf-8') as stream:
        json.dump({'schema':'campaign002-pre-exit-checks-1','passed':passed,'sources_unchanged':before==after,
                   'sources':after,'execution':identity(HERE.parent/'checks-036/test-execution.json')},stream,indent=2)
        stream.write('\n')
    print(json.dumps({'passed':passed,'sources':len(after)}))
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
