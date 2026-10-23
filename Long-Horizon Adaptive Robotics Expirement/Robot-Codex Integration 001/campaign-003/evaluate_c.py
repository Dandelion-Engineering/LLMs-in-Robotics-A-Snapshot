"""Independent protected C acceptance; no observations or controls exposed."""
import math

class CAcceptance:
    def __init__(self):self.since=None;self.accepted_at=None
    def update(self,truth):
        p,b=truth['position_m'],truth['bounds_m']
        valid=(all(math.isfinite(v) for v in p+b) and
            all(abs(p[i]-(.52,-.13)[i])+b[i]<.053 for i in (0,1)) and
            abs(p[2]-b[2])<.006 and truth['speed_m_s']<.02 and
            truth['jaw_width_m']>=.065 and math.dist(p,truth['tcp_m'])>.09)
        now=truth['sim_time_s']
        if not valid:self.since=None
        elif self.since is None:self.since=now
        if valid and now-self.since>=1 and self.accepted_at is None:self.accepted_at=now
        return {'success':self.accepted_at is not None,'current_conditions':valid,
                'accepted_at_sim_s':self.accepted_at,'stable_since_sim_s':self.since,
                'scope':'protected C placement only; accepted handback and conventional resumption separately required'}

