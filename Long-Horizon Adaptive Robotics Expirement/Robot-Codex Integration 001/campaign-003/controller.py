"""Conventional A/B worker plus C assistance detection; contains no C motion."""
import math
from common import inherited_paths
inherited_paths()
from candidates import Candidate

def public_c_complete(packet):
    if not packet:return False
    age=packet['sim_time']-packet['capture_sim_time_s']
    if not 0<=age<=.35:return False
    matches=[d for d in packet['detections'] if d.get('id')=='C1' and d.get('family')=='C']
    if len(matches)!=1:return False
    d=matches[0];p=d['pos'];u=d.get('uncertainty_m',.004)
    pad=packet['workcell_geometry']['C_pad']
    return (d['zone']=='C_pad' and all(abs(p[i]-pad['center_xy_m'][i])+.021+u<pad['half_extent_xy_m'][i] for i in (0,1))
        and abs(p[2]-.018)<.006 and packet['gripper']['width']>=.065 and not packet['gripper'].get('holding_visible_id')
        and math.dist(packet['tcp_position_m'],p)>.09)

class ConventionalController(Candidate):
    def _complete(self):
        if self._packet['order'].get('kind')=='C-placement':return public_c_complete(self._packet)
        if self._packet['order'].get('kind')=='AB-transfer':
            order=self._packet['order'];item=self._visible.get(order['part_id'])
            return bool(item and item['zone']==order['destination'] and self._packet['gripper']['width']>=.065)
        return super()._complete()

    def _baseline_action(self,*,visibility_fallback=True):
        if self._packet['order'].get('kind')=='C-placement':
            if self._complete():return {'operation':'done','reason':'Current C placement publicly supports job completion'}
            return {'operation':'help','reason':'Family C placement has no installed conventional task skill'}
        if self._packet['order'].get('kind')=='AB-transfer':
            order=self._packet['order']
            if self._complete():return {'operation':'done'}
            return {'operation':'transport','part_id':order['part_id'],'destination':order['destination']}
        return super()._baseline_action(visibility_fallback=visibility_fallback)
