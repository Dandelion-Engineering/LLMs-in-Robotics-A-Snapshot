"""Authenticate a registered no-model command before deterministic execution."""
import argparse
import json
from pathlib import Path
import subprocess
import os
from common import REPO, sha

def run(path):
    path=Path(path);manifest=json.loads(path.read_text(encoding='utf-8'));snapshot=path.with_name('snapshot.json')
    if sha(snapshot)!=manifest['source_snapshot_sha256']:raise ValueError('Snapshot mismatch')
    sources=json.loads(snapshot.read_text(encoding='utf-8'))
    for area in ('source','inherited'):
        for name,value in sources[area].items():
            if sha(REPO/name)!=value['sha256']:raise ValueError('Source changed before attempt: '+name)
    argv=manifest['command']
    if argv and argv[0]=='--':argv=argv[1:]
    # This wrapper has no launch mode. Only declared deterministic qualifiers.
    if not any(Path(arg).name in ('qualify_fs.py','qualify_scene.py','qualify_stack.py','qualify_image.py','qualify_system.py','qualify_audit.py','duration_check.py') for arg in argv):
        raise ValueError('Not a deterministic qualification command')
    env={**os.environ,'C003_REVISION_ID':manifest['revision_id'],'C003_SOURCE_SNAPSHOT_SHA256':manifest['source_snapshot_sha256']}
    return subprocess.run(argv,cwd=REPO,env=env).returncode
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);a=p.parse_args();raise SystemExit(run(a.manifest))
