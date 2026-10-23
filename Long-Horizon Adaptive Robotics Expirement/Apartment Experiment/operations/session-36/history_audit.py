"""Authenticate protected evidence and derive cup history without advancing physics."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import mujoco
import numpy as np
from scene import xml

HERE=Path(__file__).resolve().parent
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
ROOT=PAIR/'maps'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def read(p):return json.loads(p.read_bytes())
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

def main():
 out=HERE/'output';out.mkdir(exist_ok=False)
 manifest=read(HERE/'manifest.json')
 for n,v in manifest['files'].items():assert sha(HERE/n)==v['sha256']
 # Full byte inventory of both v2 histories, including native sessions, all learning,
 # checkpoints, original sensors and replay. It is checked again at closeout.
 identities=[]
 for condition in ('baseline','maps'):
  for p in sorted((PAIR/condition).rglob('*')):
   if p.is_file():
    st=p.stat();identities.append(dict(path=str(p),bytes=st.st_size,mtime_ns=st.st_mtime_ns,sha256=sha(p)))
  print('hashed',condition,len(identities),flush=True)
 save(out/'protected-v2-files.json',identities)
 anchors={}
 for n in ['frozen-source-manifest.json','COMMISSIONED.json','baseline-lineage.json','maps-lineage.json']:
  p=PAIR/n
  if p.exists():anchors[n]=dict(bytes=p.stat().st_size,sha256=sha(p))
 save(out/'pair-anchors.json',anchors)
 events=[json.loads(x) for x in (ROOT/'events.jsonl').read_bytes().splitlines()]
 prev='0'*64
 for i,r in enumerate(events,1):
  assert r['sequence']==i and r['previous']==prev and hashlib.sha256(canonical({k:v for k,v in r.items() if k!='sha256'})).hexdigest()==r['sha256']
  prev=r['sha256']
 starts=[r for r in events if r['kind']=='session_started']
 commands=[r for r in events if r['kind'] in ['command_requested','command_admitted','command_terminal','session_started','session_closed']]
 save(out/'commands.json',commands)
 m=mujoco.MjModel.from_xml_string(xml());d=mujoco.MjData(m)
 qa=int(m.joint('cup_free').qposadr[0]);va=int(m.joint('cup_free').dofadr[0]);g=m.geom('cup_geom').id
 baseqa=[int(m.joint(n).qposadr[0]) for n in ['base_x','base_y','base_yaw']]
 rows=[];contacts=[];next_contact=3429.8;sources=[]
 for row in read(ROOT/'replay/index.json'):
  p=ROOT/'replay'/row['file'];assert sha(p)==row['sha256'];sources.append(row)
  with np.load(p) as z:
   for i,t in enumerate(z['t']):
    q=z['qpos'][i];v=z['qvel'][i]
    session=int(np.searchsorted([s['sim_time'] for s in starts],t,side='right'))
    rows.append([float(t),session,*q[qa:qa+7],*v[va:va+6],*q[baseqa]])
    if t>=next_contact and session>=5:
     next_contact=float(t)+.24
     d.qpos[:]=q;d.qvel[:]=v;mujoco.mj_forward(m,d)
     cupcontacts=[]
     for c in d.contact:
      if g in (c.geom1,c.geom2):
       other=int(c.geom2 if c.geom1==g else c.geom1)
       cupcontacts.append(dict(geom=m.geom(other).name,body=m.body(int(m.geom_bodyid[other])).name,distance=float(c.dist)))
     contacts.append(dict(t=float(t),session=session,contacts=cupcontacts))
 a=np.array(rows);np.savez_compressed(out/'cup-history.npz',samples=a)
 save(out/'reconstructed-contact-history.json',contacts)
 bysession=[]
 for s in starts:
  sn=s['payload']['session'];z=a[a[:,1]==sn]
  if not len(z):continue
  bysession.append(dict(session=sn,task=s['payload']['task'],first_t=float(z[0,0]),last_t=float(z[-1,0]),
   cup_first=z[0,2:5].tolist(),cup_last=z[-1,2:5].tolist(),cup_min=z[:,2:5].min(axis=0).tolist(),cup_max=z[:,2:5].max(axis=0).tolist(),
   max_speed=float(np.linalg.norm(z[:,9:12],axis=1).max()),path_m=float(np.linalg.norm(np.diff(z[:,2:4],axis=0),axis=1).sum())))
 save(out/'per-session.json',bysession)
 milestones=[]
 for label,mask in [('first_kitchen_floor',(a[:,1]>=5)&(a[:,4]<.1)),('first_bathroom',(a[:,1]>=5)&(a[:,2]>6)&(a[:,3]>5.15)),('post_drop_fastest',(a[:,1]>=5)&(a[:,4]<.2))]:
  ix=np.flatnonzero(mask)
  if len(ix):
   k=ix[np.argmax(np.linalg.norm(a[ix,9:12],axis=1))] if label.endswith('fastest') else ix[0]
   t=float(a[k,0]);near=[r for r in commands if abs(r['sim_time']-t)<25]
   milestones.append(dict(label=label,t=t,sample=a[k].tolist(),nearby_events=near))
 save(out/'milestones.json',milestones)
 transcripts=[];memory=[]
 for session in sorted((ROOT/'sessions').glob('session-*')):
  sn=int(session.name.split('-')[-1]);p=session/'native/client/events.jsonl'
  if p.exists():
   for line_no,line in enumerate(p.read_bytes().splitlines(),1):
    r=json.loads(line)
    if r.get('method')!='item/completed':continue
    item=r.get('params',{}).get('item',{})
    if item.get('type') not in ['agentMessage','commandExecution']:continue
    transcripts.append(dict(session=sn,path=str(p),line=line_no,monotonic_ns=r.get('capture_windows_perf_ns'),item=item))
  fp=session/'workspace/final-filesystem'
  for p in fp.rglob('*'):
   if p.is_file() and p.suffix.lower() in ['.md','.txt','.json','.py'] and p.stat().st_size<150000:
    try:text=p.read_text(encoding='utf-8')
    except UnicodeError:continue
    if any(k in text.lower() for k in ['cup','bathroom','rolling','oscillat']):
     memory.append(dict(session=sn,path=str(p),sha256=sha(p),text=text))
 save(out/'observable-transcripts.json',transcripts);save(out/'cup-related-files.json',memory)
 # Byte identities bind the extracted records; all contacts are reconstructed,
 # messages and file text are recorded outputs, never inferred private reasoning.
 save(out/'result.json',dict(passed=True,protected_files=len(identities),protected_bytes=sum(x['bytes'] for x in identities),
  replay_chunks=len(sources),samples=len(a),event_records=len(events),event_chain=prev,
  derived_contact_samples=len(contacts),transcript_items=len(transcripts),cup_related_files=len(memory),
  new_physics_steps=0,original_writes=0,method='Replay samples and observable native outputs; contacts reconstructed with mj_forward without original warmstart/control history',
  artifacts={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in out.iterdir() if p.is_file()}))
 print(json.dumps(read(out/'result.json')),flush=True)

if __name__=='__main__':main()
