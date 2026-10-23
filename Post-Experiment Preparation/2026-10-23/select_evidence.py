"""Select byte-authenticated public evidence for the written shortlist."""
from inspect_history import OUT, ROOTS, SCRATCH, read, raw, sha, save, inputs
import json
import re

def local(name):return json.loads((SCRATCH/name).read_bytes())

def main():
    evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
    receipts=local('file-receipts.json');processes=local('public-process-requests.json')
    reports=local('session-reports.json');catalog=read(OUT/'history-catalog.json')
    selected_reports={'baseline':[1,2,3,6,7,9,19,20,21,22,23], 'maps':[1,5,6,7,8,15,29,34]}
    exports=[]
    def export(path,name):
        b=raw(path);dst=evidence/name;dst.write_bytes(b)
        exports.append({'source':str(path),'export':'evidence/'+name,'sha256':sha(b),'bytes':len(b)})
        return 'evidence/'+name
    for r in reports:
        if r['session'] in selected_reports[r['condition']]:
            assert sha(raw(r['source']))==r['sha256']
            export(r['source'],f"{r['condition']}-session-{r['session']:03}.md")
    specifications=[('baseline',1,6,'/Programs/Learned/throw_orange.py'),
                    ('baseline',6,9,'/Programs/Learned/throw_orange.py'),
                    ('baseline',2,3,'/SummaryOfOnlyNecessaryContext.md'),
                    ('baseline',2,3,'/Maps/bedroom-route.md'),
                    ('maps',1,7,'/Programs/Learned/throw_horizontal.py'),
                    ('maps',5,6,'/SummaryOfOnlyNecessaryContext.md'),
                    ('maps',5,6,'/Maps/Rooms/Kitchen.md'),
                    ('baseline',22,23,'/SummaryOfOnlyNecessaryContext.md'),
                    ('maps',6,9,'/Playbooks/Learned/OpenDrawerB.md')]
    links=[]
    for condition,writer,reader,path in specifications:
        root=ROOTS[condition];cp=root/'checkpoints'/f'session-{writer:05}'
        manifest=read(cp/'manifest.json');rel='filesystem/'+path.lstrip('/')
        b=raw(cp/rel);digest=sha(b);assert manifest['files'][rel]=={'sha256':digest,'bytes':len(b)}
        writes=[r for r in receipts if r['condition']==condition and r['session']==writer and r['path']==path
                and r['content_sha256']==digest and r['operation']=='write']
        reads=[r for r in receipts if r['condition']==condition and r['session']==reader and r['path']==path
               and r['operation']=='read' and r['offset']==0 and r['bytes']==len(b) and r['returned_sha256']==digest]
        assert writes and reads,(condition,writer,reader,path)
        name=f'{condition}-s{writer:03}-'+path.lstrip('/').replace('/','--')+'.txt'
        material=export(cp/rel,name)
        links.append({'condition':condition,'writer_session':writer,'reader_session':reader,'path':path,'sha256':digest,
                      'bytes':len(b),'checkpoint_manifest_sha256':sha(raw(cp/'manifest.json')),
                      'checkpoint_file':str(cp/rel),'export':material,'write':writes[-1],'full_file_read':reads[0],
                      'other_full_reads':reads[1:]})
    selected_processes=[]
    for p in processes:
        cmd=p['argv'][-1]
        if p['condition']=='baseline' and p['session'] in [1,6,9] and 'throw_orange.py' in cmd:
            if p['session']==1 and p['id'] not in [142,153]:continue
            if p['session']!=1 and not cmd.startswith('python3 /workspace/Programs/Learned/'):continue
            selected_processes.append(p)
        if p['condition']=='maps' and p['session'] in [1,7] and cmd.startswith('python3 /workspace/Programs/Learned/throw_horizontal.py'):
            selected_processes.append(p)
    save('reuse-links.json',links)
    save('selected-program-executions.json',selected_processes)
    image_ids={'baseline':[11,34,66,140,147], 'maps':[146,150,165,170,171,210]}
    images=[]
    for condition,ids in image_ids.items():
        root=ROOTS[condition]
        for n in ids:
            row=next(x for x in catalog[condition]['images'] if x['sequence']==n)
            p=root/'sensors'/f'frame-{n:07}.png';assert sha(raw(p))==row['sha256']
            images.append(dict(condition=condition,**row,export=export(p,f'{condition}-observation-{n:04}.png')))
    save('selected-images.json',images)
    for condition, paths in {
        'baseline':['Artifacts/session-001-trials.md','Artifacts/session-001-trial-5.jsonl','Artifacts/session-001-trial-6.jsonl',
                    'Artifacts/session-006-trials.md','Artifacts/session-006-trial-1.jsonl','Artifacts/session-006-trial-6.jsonl',
                    'Artifacts/session-006-trial-7.jsonl','Artifacts/session-006-navigation.md',
                    'Artifacts/session-009-trial-1.jsonl','Artifacts/session-009-trial-7.jsonl'],
        'maps':[]}.items():
        root=ROOTS[condition];final=root/'checkpoints'/('session-00035' if condition=='baseline' else 'session-00034')
        manifest=read(final/'manifest.json')
        for rel in paths:
            b=raw(root/'filesystem'/rel); assert manifest['files']['filesystem/'+rel]=={'sha256':sha(b),'bytes':len(b)}
            export(root/'filesystem'/rel,condition+'-'+PathName(rel))
    save('selected-exports.json',exports)
    save('selection-inputs.json',inputs)
    print(len(links),'cross-session byte-matched write/checkpoint/read links;',len(images),'original RGB exports;',len(selected_processes),'program requests.')

def PathName(x):return x.split('/')[-1]
if __name__=='__main__':main()
