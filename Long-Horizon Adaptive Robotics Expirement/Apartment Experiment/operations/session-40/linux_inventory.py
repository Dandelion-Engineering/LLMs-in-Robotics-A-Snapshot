"""Metadata-only accounting for this project's Linux-owned workspace roots."""
import json
import subprocess
from storage_audit import HERE,now,save
code=r'''import collections,json,os,pathlib
out=[]
for root in ['/var/tmp/robot-codex-session10','/tmp/robot-codex-session9']:
 rows=collections.defaultdict(lambda:{'files':0,'logical_bytes':0,'allocated_bytes':0});errors=[];links=[]
 if not pathlib.Path(root).exists():out.append({'root':root,'exists':False});continue
 for parent,dirs,files in os.walk(root,followlinks=False):
  for name in files:
   p=pathlib.Path(parent)/name
   try:
    st=p.lstat()
    if p.is_symlink():links.append(str(p));continue
    group=p.relative_to(root).parts[0];r=rows[group]
    r['files']+=1;r['logical_bytes']+=st.st_size;r['allocated_bytes']+=st.st_blocks*512
   except OSError as e:errors.append([str(p),str(e)])
 out.append({'root':root,'exists':True,'groups':dict(rows),'errors':errors,'symlinks_not_followed':links,'totals':{k:sum(r[k] for r in rows.values()) for k in ['files','logical_bytes','allocated_bytes']}})
print(json.dumps(out))'''
r=json.loads(subprocess.check_output(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',code],text=True,encoding='utf-8'))
save(HERE/'linux-inventory.json',dict(time=now(),roots=r,disposition='Retain original runtime namespace/journal/fixture evidence. No Linux deletion, trim, shutdown, or shared VHD compaction. Allocated inode blocks are not Windows volume-reclaimable bytes.'))
print(json.dumps([{k:v for k,v in x.items() if k!='groups'} for x in r]))
