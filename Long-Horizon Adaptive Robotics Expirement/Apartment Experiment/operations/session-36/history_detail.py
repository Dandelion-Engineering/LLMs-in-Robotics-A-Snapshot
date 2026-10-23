"""Full recorded-sample contact/energy readback of selected handling transitions."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import mujoco
import numpy as np
from scene import xml
HERE=Path(__file__).resolve().parent
ROOT=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2/maps')
WINDOWS=[('counter_exit',6548,6555),('first_carry_loss',7119,7126),('bathroom_transfer',9660,9744),('return_carry_loss',13390,13402),('second_bathroom_transfer',13902,13997)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
 manifest=json.loads((HERE/'manifest.json').read_bytes())
 for n,v in manifest['files'].items():assert sha(HERE/n)==v['sha256']
 out=HERE/'output';out.mkdir(exist_ok=False)
 m=mujoco.MjModel.from_xml_string(xml());d=mujoco.MjData(m)
 qa=int(m.joint('cup_free').qposadr[0]);va=int(m.joint('cup_free').dofadr[0]);g=m.geom('cup_geom').id;b=m.body('cup').id
 index=json.loads((ROOT/'replay/index.json').read_bytes());events=[json.loads(s) for s in (ROOT/'events.jsonl').read_bytes().splitlines()]
 summaries=[]
 for label,begin,end in WINDOWS:
  rows=[];sources=[];previous_names=None;groups=[];vec=np.zeros(m.nv);mv=np.zeros(m.nv)
  for chunk in index:
   if chunk['last']<begin or chunk['first']>end:continue
   p=ROOT/'replay'/chunk['file'];assert sha(p)==chunk['sha256'];sources.append(chunk)
   with np.load(p) as z:
    for t,q,v in zip(z['t'],z['qpos'],z['qvel']):
     if not begin<=t<=end:continue
     d.qpos[:]=q;d.qvel[:]=v;mujoco.mj_forward(m,d)
     contacts=[]
     for c in d.contact:
      if g in (c.geom1,c.geom2):contacts.append(m.geom(int(c.geom2 if c.geom1==g else c.geom1)).name)
     names=sorted(set(contacts))
     if names!=previous_names:groups.append(dict(first=float(t),last=float(t),contacts=names));previous_names=names
     else:groups[-1]['last']=float(t)
     vec[:]=0;vec[va:va+6]=v[va:va+6];mujoco.mj_mulM(m,d,mv,vec)
     rows.append(dict(t=float(t),position=q[qa:qa+3].tolist(),velocity=v[va:va+6].tolist(),kinetic_J=float(.5*np.dot(vec,mv)),potential_J=float(-m.body_mass[b]*np.dot(m.opt.gravity,d.xipos[b])),contacts=names))
  save(out/(label+'.json'),dict(samples=rows,sources=sources,contact_intervals=groups,
   commands=[e for e in events if begin-10<=e['sim_time']<=end+10 and e['kind']=='command_requested']))
  summaries.append(dict(window=label,begin=begin,end=end,samples=len(rows),contact_intervals=groups,
   first=rows[0],last=rows[-1],source_sha256=sha(out/(label+'.json'))))
 save(out/'result.json',dict(passed=True,windows=summaries,physics_steps=0,original_writes=0,
  limitation='Contact existence is reconstructed at every original sample (nominal ~32 ms), not continuously logged contact/force telemetry; sub-sample contacts remain unobserved. No inference about unlogged reasoning.'))
 print('Completed five full-sample transition windows',flush=True)
if __name__=='__main__':main()
