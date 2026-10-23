"""Test-only injected service behavior, outside production and guest inputs."""
import json
import os
from pathlib import Path
import sys
import time

source=Path(os.environ['S38_SOURCE']);fault=os.environ['S38_FAULT']
sys.path.insert(0,str(source))
identity_path=Path(sys.argv[sys.argv.index('--identity')+1]);identity=json.loads(identity_path.read_text())
mount=sys.argv[sys.argv.index('--mount')+1]
(identity_path.parent/'injected-owner.json').write_text(json.dumps(dict(run_id=identity['run_id'],mount=mount,pid=os.getpid(),start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])))
if fault=='early_exit':raise SystemExit(23)
if fault=='original_timeout':time.sleep(60)
import content_store
put=content_store.Store.put
get=content_store.Store.get
calls=0
def inject():
    global calls
    calls+=1
    if fault=='partial_failure' and calls==4:raise RuntimeError('Injected fourth-content failure')
    if fault=='hang' and calls==4:time.sleep(60)
    if fault=='slow':time.sleep(.25)
    if fault=='absolute':time.sleep(.12)
def injected_put(self,*args,**kwargs):
    inject();return put(self,*args,**kwargs)
def injected_get(self,*args,**kwargs):
    inject();return get(self,*args,**kwargs)
content_store.Store.put=injected_put
content_store.Store.get=injected_get
if fault=='seed_flush':
    fsync=os.fsync
    def failed_directory_flush(fd):
        if os.readlink('/proc/self/fd/'+str(fd)).endswith('/journal/chunks'):
            raise OSError('Injected adopted-directory flush failure')
        return fsync(fd)
    os.fsync=failed_directory_flush
if fault=='heartbeat':
    import workspace_lifecycle as life
    advance=life.Progress.advance
    def fake_heartbeat(self,phase,*args,**kwargs):
        result=advance(self,phase,*args,**kwargs)
        if phase=='restoring' and self.files==3:
            for _ in range(600):
                row=json.loads(self.path.read_text());row['sequence']+=1;row['monotonic_ns']=time.monotonic_ns()
                life.atomic(self.path,row);time.sleep(.1)
        return result
    life.Progress.advance=fake_heartbeat
if fault=='race':
    repo=Path(sys.argv[sys.argv.index('--repo')+1])
    sys.path.insert(0,str(repo/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-005'))
    import journal_fs
    fuse=journal_fs.FUSE
    def delayed_exit(*args,**kwargs):
        result=fuse(*args,**kwargs)
        (identity_path.parent/'destroy-complete').write_text('closed')
        time.sleep(3)
        return result
    journal_fs.FUSE=delayed_exit
import journal_service
journal_service.main()
