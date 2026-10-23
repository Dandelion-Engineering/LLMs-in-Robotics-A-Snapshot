"""Compact, hash-bound diagnostic synthesis from completed queue evidence."""
from attempts import *
import numpy as np
summary={}
for attempt in ['matrix001','matrix002']:
 q=read(HERE/(attempt+'-terminal.json'))
 assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
 for row in read(ROOT/attempt/'output/result.json')['results']:
  n=row['case']['id'];p=ROOT/attempt/'output'/(n+'.npz');a=np.load(p)['samples']
  summary[n]=dict(attempt=attempt,source=ref('Original engineering samples',p),
   peak_speed_m_s=row['max_speed_m_s'],peak_energy_gain_J=row['energy_gain_max_J'],
   late_30s_displacement_range_m=float(np.linalg.norm(row['late_xy_range_m'])),
   peak_abs_normal_roll_torque_Nm=float(np.max(np.abs(a[:,18]))),
   kinetic_max_J=float(a[:,14].max()),potential_span_J=float(np.ptp(a[:,15])),
   final_energy_change_J=row['final_energy_change_J'],midpoint_contact_work_J=row['contact_work_J'][1],
   hidden_force_max=row['force_max_applied_passive_actuator_xfrc'],warnings=row['warnings'])
save(HERE/'diagnostic-summary.json',dict(cases=summary,
 reproduction=read(HERE/'reproduction-readback.json'),
 ineffective_controls=['matrix001 condim6_no_rolling retained floor rolling friction','matrix001 frictionless retained floor condim 3'],
 limitations=['Two old ineffective controls are retained, with corrected prospective matrix002 controls.','Legacy CCD and single-contact cases leave finite support; their falling speeds are not a bounded floor stability result.','Exact implementation-level collision bug unproven; controlled intervention establishes sensitivity to contact generation precision.']))
print('Saved diagnostic-summary.json')
