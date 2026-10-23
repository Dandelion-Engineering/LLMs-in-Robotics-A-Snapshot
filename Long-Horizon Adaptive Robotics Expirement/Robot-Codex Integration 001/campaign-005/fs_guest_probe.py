"""Deterministic filesystem-only guest; never contains a robot solution."""
import json
import mmap
import os
from pathlib import Path
import socket
import sys

session=int(sys.argv[1]);root=Path('/workspace');checks={}
checks['fresh_scratch']=not Path('/tmp/prior-session').exists()
checks['fresh_environment']='PRIOR_SESSION_SECRET' not in os.environ
Path('/tmp/prior-session').write_text('scratch disappears')
for name in ('/mnt/c','/home/dandelion','/protected','/var/tmp'):
    checks['denied_'+name]=not Path(name).exists()
try:(root/'Tasks.md').write_text('forbidden');checks['trusted_read_only']=False
except OSError:checks['trusted_read_only']=True
try:
    s=socket.create_connection(('1.1.1.1',443),.2);s.close();checks['network_denied']=False
except OSError:checks['network_denied']=True
path=root/'notes/probe.bin'
if session==1:
    inventory=json.loads((root/'ArtifactInventory.json').read_text())
    entries={e['path']:e for e in inventory['entries']}
    import hashlib
    checks['updated_artifact_inventory']=entries['programs/format_label.py']['snapshot_version']==2 and entries['programs/format_label.py']['identity']['sha256']==hashlib.sha256((root/'programs/format_label.py').read_bytes()).hexdigest()
    checks['removed_artifact_accounted']='notes/removed-between-sessions.txt' in inventory['removed_since_previous_snapshot']
    checks['updated_semantic_handoff']='casefold Unicode' in (root/'Continuity.md').read_text()
    fd=os.open(path,os.O_CREAT|os.O_RDWR,0o600)
    os.write(fd,b'alpha');os.pwrite(fd,b'BETA',1);os.fsync(fd)
    assert os.pread(fd,5,0)==b'aBETA'
    try:mmap.mmap(fd,5,access=mmap.ACCESS_WRITE);checks['mmap_denied']=False
    except OSError:checks['mmap_denied']=True
    os.close(fd)
    os.link(path,root/'notes/alias.bin')
    os.rename(path,root/'notes/renamed.bin')
    path=root/'notes/renamed.bin'
    os.symlink('renamed.bin',root/'notes/link.bin')
    assert (root/'notes/link.bin').read_bytes()==b'aBETA'
    fd=os.open(path,os.O_RDWR);os.unlink(path);os.pwrite(fd,b'!',5);os.close(fd)
    assert (root/'notes/alias.bin').read_bytes()==b'aBETA!'
    (root/'notes/link.bin').unlink()
    (root/'notes/transient').write_bytes(b'exact short-lived bytes');(root/'notes/transient').unlink()
    (root/'.continuity/Continuity.md').write_text('Agent-authored test continuity.\n')
    (root/'programs/retained.txt').write_text('Neutral persistent test artifact.\n')
else:
    checks['persisted_bytes']=(root/'notes/alias.bin').read_bytes()==b'aBETA!'
    checks['persisted_continuity']='Agent-authored' in (root/'Continuity.md').read_text()
    checks['persisted_program']=(root/'programs/retained.txt').read_text()=='Neutral persistent test artifact.\n'
    (root/'notes'/f'session-{session}').write_text(f'fresh process {os.getpid()}\n')
print(json.dumps({'session':session,'pid':os.getpid(),'checks':checks}),flush=True)
assert all(checks.values()),checks
