from attempts import *
import math
import numpy as np
import mujoco
app=HERE.parents[1]
cases=[dict(id='recorded_reversal'),dict(id='recorded_zero',zero_velocity=True),dict(id='recorded_long',seconds=7200)]
def mult(a,b):
 q=np.zeros(4);mujoco.mju_mulQuat(q,np.array(a,dtype=float),np.array(b,dtype=float));return q.tolist()
for i,yaw in enumerate([0.,.4,1.2,2.1]):
 q=mult([math.cos(yaw/2),0,0,math.sin(yaw/2)],[math.sqrt(.5),math.sqrt(.5),0,0])
 for speed in [0.,.1,.4]:
  cases.append(dict(id=f'side_{i}_speed_{speed}',initial_qpos=[6,5,.032,*q],initial_qvel=[speed*math.cos(yaw),speed*math.sin(yaw),0,0,0,-speed/.032]))
 for height in [.25,1.0]:
  cases.append(dict(id=f'drop_{i}_{height}',drop=True,initial_qpos=[6,5,height,*q],initial_qvel=[.1,-.1,0,1.1,-.7,.3]))
for i,q in enumerate([[1,0,0,0],[math.cos(.1),math.sin(.1),0,0],[math.cos(.4),0,math.sin(.4),0]]):
 cases.append(dict(id=f'upright_{i}',drop=True,initial_qpos=[6,5,.15,*q],initial_qvel=[.05,0,0,0,0,0]))
sources=[(p,p.name) for p in app.glob('*.py')]
sources += [(HERE/'physics_matrix.py','physics_matrix.py'),(ROOT/'matrix001/initial.npz','initial.npz')]
register('verification001','verify_candidate.py','Fixed candidate verification of collision tolerance 1e-10 and cup condim6. Twenty-six unattended states include rolling, drops and 7200-second stability; then existing integrated real-control fixtures cover both drawers/docks, toy handling, sensors/continuation, ball throwing. All failures retained; no official launch unless every required gate passes.',cases,sources)
build()
