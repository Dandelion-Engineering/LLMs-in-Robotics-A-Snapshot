"""Require independent success, add navigation, copy to Git and audit staged blobs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
BUILD=Path('D:/Dandelion-Apartment-Experiment/engineering/filesystem-publication-session37/publication001')
DEST=HERE.parents[1]/'evidence/original-v2-filesystems'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
def call(*a):return subprocess.check_output(list(a),cwd=REPO,text=True,encoding='utf-8')
def main():
    q=json.loads((HERE/'publication-audit001-queue.json').read_bytes())
    terminal=json.loads(call(sys.executable,'-X','utf8','-B',str(QUEUE),'status',q['id']))
    assert terminal['state']=='succeeded' and type(terminal['exit_status']) is int and terminal['exit_status']==0
    (HERE/'publication-audit001-terminal.json').write_text(json.dumps(terminal,indent=2)+'\n',encoding='utf-8')
    assert json.loads((BUILD/'corpus/verification.json').read_bytes())['passed'] is True
    assert not call('git','diff','--cached','--name-only').strip(),'Unexpected preexisting staged changes'
    subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'publication_navigation.py'),str(BUILD/'corpus')],check=True)
    assert not DEST.exists()
    shutil.copytree(BUILD/'corpus',DEST)
    originals={p.relative_to(BUILD/'corpus').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (BUILD/'corpus').rglob('*') if p.is_file()}
    copied={p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.rglob('*') if p.is_file()}
    assert copied==originals
    call('git','add','-f','--',DEST.relative_to(REPO).as_posix())
    tree=call('git','write-tree').strip()
    subprocess.run([sys.executable,'-X','utf8','-B',str(BUILD/'audit_publication.py'),str(DEST),'--git-ref',tree,'--output',str(HERE/'publication-git-readback001.json')],cwd=REPO,check=True)
    (HERE/'publication-staging.json').write_text(json.dumps({'passed':True,'tree':tree,'corpus_files':len(copied),'corpus_bytes':sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file()),'destination':str(DEST)},indent=2)+'\n',encoding='utf-8')
    print('Publication staged; exact Git blob and original-source readback passed',flush=True)
if __name__=='__main__':main()
