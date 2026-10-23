"""Bounded no-model original restore profile and byte-preservation baseline."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import traceback
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))
from common import read,save,sha,inventory
from native_runtime import linux,wsl,DISTRO,REPO

OFFICIAL=Path('D:/Dandelion-Apartment-Experiment/official')
CHECKPOINT=OFFICIAL/'apartment-v3/baseline/checkpoints/session-00014'

def fixture(root,kind):
    root.mkdir();(root/'filesystem').mkdir();(root/'filesystem-objects').mkdir()
    state=read(CHECKPOINT/'filesystem-namespace.json')
    if kind=='small':
        files=[p for p,i in sorted(state['paths'].items()) if stat.S_ISREG(state['nodes'][str(i)]['mode'])][:90]
        keep={'/'}
        for p in files:
            keep.add(p);keep.update(str(x) for x in Path(p).parents if str(x)!='.')
        # Windows Path cannot supply POSIX parent spelling.
        from pathlib import PurePosixPath
        keep={'/'}|set(files)
        for p in files:keep.update(str(x) for x in PurePosixPath(p).parents)
        state['paths']={p:i for p,i in state['paths'].items() if p in keep}
        state['nodes']={k:v for k,v in state['nodes'].items() if int(k) in state['paths'].values()}
    for node in state['nodes'].values():
        if node.get('sha256'):
            source=CHECKPOINT/'filesystem-objects'/node['sha256'];destination=root/'filesystem-objects'/node['sha256']
            if not destination.exists():shutil.copyfile(source,destination)
    if kind=='large':
        maximum=max(map(int,state['nodes']));extra_paths={};extra_nodes={}
        for p,i in state['paths'].items():
            ni=i+maximum;node=copy.deepcopy(state['nodes'][str(i)])
            if node.get('sha256'):
                raw=(root/'filesystem-objects'/node['sha256']).read_bytes()+b'\nengineering scaling replica\n'
                node['sha256']=hashlib.sha256(raw).hexdigest();node['size']=len(raw)
                (root/'filesystem-objects'/node['sha256']).write_bytes(raw)
            extra_paths['/engineering-growth'+('' if p=='/' else p)]=ni;extra_nodes[str(ni)]=node
        state['paths'].update(extra_paths);state['nodes'].update(extra_nodes)
    save(root/'filesystem-namespace.json',state)
    return dict(paths=len(state['paths']),nodes=len(state['nodes']),files=sum('sha256' in n for n in state['nodes'].values()),bytes=sum(n['size'] for n in state['nodes'].values()))

def measure(out,root,cache):
    out.mkdir();run_id='apartment-s38-profile-'+uuid.uuid4().hex
    run='/var/tmp/robot-codex-session10/'+run_id;mount=run+'/workspace'
    payload={'initial.json':{},'identity.json':dict(run_id=run_id,session_id=out.name,source_revision='s38-profile-original',phase='engineering'),
             'restore.json':dict(state=read(root/'filesystem-namespace.json'),objects=wsl(root/'filesystem-objects'))}
    begin=time.perf_counter_ns()
    linux("import pathlib,json,sys;r=pathlib.Path(sys.argv[1]);r.mkdir();(r/'workspace').mkdir();[(r/k).write_text(json.dumps(v)) for k,v in json.load(sys.stdin).items()]",run,payload=payload)
    result=dict(run_id=run_id,run=run,mount=mount,cache=cache,preparation_s=(time.perf_counter_ns()-begin)/1e9)
    # DONTNEED requests only eviction of these throwaway inputs; Windows caches
    # are not flushed, so this is explicitly not a proven device-cold start.
    result['cache_advice']=json.loads(linux("import os,pathlib,json,sys;n=0\nfor p in pathlib.Path(sys.argv[1]).iterdir():\n with p.open('rb') as f:\n  if sys.argv[2]=='advised-cold':os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)\n  else:f.read()\n n+=1\nprint(json.dumps({'files':n,'mode':sys.argv[2],'device_cold_proven':False}))",wsl(root/'filesystem-objects'),cache,timeout=90))
    with (out/'console.log').open('wb') as log:
        launched=time.perf_counter_ns()
        process=subprocess.Popen(['wsl.exe','-d',DISTRO,'--','python3','-B',wsl(HERE/'profile_service.py'),wsl(HERE/'source'),wsl(out/'profile.json'),
            '--mount',mount,'--evidence',wsl(out/'journal'),'--initial',run+'/initial.json','--identity',run+'/identity.json','--repo',wsl(REPO),'--socket',run+'/control.sock','--restore',run+'/restore.json'],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        save(out/'location.json',dict(run=run,workspace=mount,run_id=run_id))
        try:
            ready=json.loads(linux("import os,time,json,sys;start=time.monotonic();end=start+120\nwhile not os.path.ismount(sys.argv[1]):\n if time.monotonic()>end:raise RuntimeError('diagnostic 120s cap')\n time.sleep(.05)\nprint(json.dumps({'poll_s':time.monotonic()-start}))",mount,timeout=130))
            result.update(ready=ready,launch_to_ready_s=(time.perf_counter_ns()-launched)/1e9)
        finally:
            result['cleanup']=json.loads(linux("import os,subprocess,json,sys;mounted=os.path.ismount(sys.argv[1]);r=subprocess.run(['fusermount3','-u',sys.argv[1]],capture_output=True,text=True,timeout=10) if mounted else None;print(json.dumps({'was_mounted':mounted,'unmount_exit':None if r is None else r.returncode,'mounted':os.path.ismount(sys.argv[1])}))",mount))
            try:result['exit_status']=process.wait(15)
            except subprocess.TimeoutExpired:
                identity=read(out/'journal/service-identity.json')
                linux("import os,pathlib,signal,json,sys;x=json.load(sys.stdin);p=pathlib.Path('/proc')/str(x['pid']);assert p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==x['start_ticks'];os.kill(x['pid'],signal.SIGTERM)",payload=identity)
                result['forced_cleanup']=True;result['exit_status']=process.wait(15)
        assert result['exit_status']==0 and result['cleanup']['mounted'] is False,result
    import journal_reader
    proof=journal_reader.verify(out/'journal',run_id)
    assert proof['passed'] and proof['state']==read(root/'filesystem-namespace.json')
    result['profile']=read(out/'profile.json');result['journal_verified']=True
    save(out/'measurement.json',result);return result

def main():
    out=HERE/'output';out.mkdir();result=dict(passed=False,model_calls=0,cases=[])
    try:
        preservation={}
        for pair in ('apartment-v2','apartment-v3'):
            print('Inventory '+pair,flush=True);rows=inventory(OFFICIAL/pair);save(out/(pair+'-before.json'),rows)
            preservation[pair]=dict(files=len(rows),bytes=sum(r['bytes'] for r in rows.values()),inventory_sha256=sha(out/(pair+'-before.json')))
        result['preservation_before']=preservation
        result['environment']=dict(windows=sys.version,linux=linux("import sys,platform,json;print(json.dumps({'python':sys.version,'platform':platform.platform()}))"),disk_free=shutil.disk_usage(HERE).free)
        for kind in ('small','checkpoint14','large'):
            root=out/('fixture-'+kind);size=fixture(root,kind)
            for cache in ('advised-cold','warm'):
                print(kind+' '+cache,flush=True)
                case=measure(out/(kind+'-'+cache),root,cache)
                result['cases'].append(dict(size=kind,shape=size,**case))
        result['passed']=True
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='cases'}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
