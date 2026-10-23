"""Prepare suites individually, only after the preservation admission gate."""
from attempts import *
import argparse

def source_files():
    frozen=RELEASE/'frozen_repository'
    source=frozen/APP.relative_to(REPO)
    origin=HERE/'source-origin.json'
    if not origin.exists():save(origin,dict(repository=str(frozen)))
    return [(p,'source/'+p.name) for p in source.iterdir() if p.is_file() and p.suffix in ('.py','.html','.md','.json')]+[(origin,'source/source-origin.json')]

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['workspace','offline','recorder','physics','native']);p.add_argument('--name');a=p.parse_args()
    mode=a.mode;name=a.name or mode+'001'
    assert read(ROOT/'preservation002/output/result.json')['passed'] is True
    files=source_files();cases=[dict(mode=mode)]
    s38=APP/'operations/session-38';s37=APP/'operations/session-37'
    if mode=='workspace':
        for n in ('qualify_workspace.py','original_reproductions.py'):
            text=(s38/n).read_text(encoding='utf-8')
            text=text.replace("PROFILE=HERE.parent/'profile001/output'","PROFILE=Path('D:/Dandelion-Apartment-Experiment/engineering/workspace-session38/profile001/output')")
            text=text.replace("ORIGINAL=HERE.parent/'profile001/source'","ORIGINAL=Path('D:/Dandelion-Apartment-Experiment/engineering/workspace-session38/profile001/source')")
            target=HERE/n
            with target.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
            files.append((target,n))
        files.append((s38/'fault_service.py','fault_service.py'))
    if mode in ('recorder','physics'):
        files += [(s37/n,n) for n in ('physics_matrix.py','endpoint_schedule.py')]
        prior=Path('D:/Dandelion-Apartment-Experiment/engineering/physics-recommission-session37')
        cases=read(prior/('recorder001' if mode=='recorder' else 'verification001')/'manifest.json')['cases']
        # Keep the exact case array consumed by the existing suite. Mode is in
        # a separate launcher filename for these unmodified fixed matrices.
        entry='test_recorder.py' if mode=='recorder' else 'verify_candidate.py'
        files += [(s37/entry,entry),(prior/'recorder001/initial.npz','initial.npz')]
        if mode=='recorder':files.append((prior/'recorder001/legacy_matrix.py','legacy_matrix.py'))
        wrapper=HERE/(mode+'_entry.py')
        text=(HERE/'runner.py').read_text(encoding='utf-8').replace("mode=manifest['cases'][0]['mode']","mode="+repr(mode))
        with wrapper.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
        register(name,wrapper.name,'Fresh exact-release '+mode+' qualification with unchanged fixed gates and independent audit still required.',files,cases)
        return
    register(name,'runner.py','Fresh exact-release '+mode+' commissioning; prior evidence preserved and no official condition prepared.',files,cases,model_calls=4 if mode=='native' else 0)

if __name__=='__main__':
    main()
    build()
