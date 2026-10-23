"""Compact accounting, hardlink correction and retained candidate categories."""
import collections
import gzip
import json
import os
from pathlib import Path
from storage_audit import HERE,save,sha
counts=collections.defaultdict(lambda:dict(files=0,bytes=0,allocated=0))
links=collections.defaultdict(list);special=[];large=[]
with gzip.open(HERE/'census001/files.jsonl.gz','rt',encoding='utf-8') as f:
    for line in f:
        r=json.loads(line);p=Path(r['root'])/r['path'];root=r['root']
        key=(root,p.suffix.lower() or '(none)');v=counts[key]
        v['files']+=1;v['bytes']+=r['bytes'];v['allocated']+=r['allocated']
        if r['links']>1:
            s=p.stat();links[str((s.st_dev,s.st_ino))].append(dict(path=str(p),bytes=r['bytes'],allocated=r['allocated'],links=r['links']))
        if r['bytes']>=100*1024**2:large.append(dict(path=str(p),bytes=r['bytes'],allocated=r['allocated'],links=r['links']))
        if p.suffix.lower() in ('.tmp','.temp','.pyc') and not r['path'].startswith('venv/'):
            special.append(dict(path=str(p),bytes=r['bytes'],allocated=r['allocated']))
save(HERE/'census001/hardlinks.json',dict(groups=dict(links),repeated_logical_bytes=sum(sum(x['bytes'] for x in a[1:]) for a in links.values()),repeated_allocated_bytes=sum(sum(x['allocated'] for x in a[1:]) for a in links.values()),method='Identity from current st_dev/st_ino for every censused path whose FILE_STANDARD_INFO reported multiple links. No hardlink was removed.'))
save(HERE/'census001/extensions.json',[dict(root=k[0],extension=k[1],**v) for k,v in counts.items()])
save(HERE/'census001/large-files.json',sorted(large,key=lambda r:r['allocated'],reverse=True))
save(HERE/'census001/special-files-retained.json',special)
print(json.dumps(dict(hardlink_groups=len(links),special_files=len(special),large_files=len(large))))
