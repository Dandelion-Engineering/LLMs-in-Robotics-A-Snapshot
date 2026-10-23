"""Prospective fixed envelope; no outcome-dependent extensions."""
import json
from common import HERE, sha
ENVELOPE=HERE/'limits.json'
AUTHORITY=ENVELOPE

def apply_limits(manifest, stage):
    limits=dict(json.loads(ENVELOPE.read_text(encoding='utf-8'))['limits'])
    if stage=='live_qualification':limits.update(sim_cap_s=13200,wall_cap_s=14100)
    return {**manifest,**limits,'runtime_envelope_sha256':sha(ENVELOPE)}

def validate_limits(manifest):
    expected=apply_limits({},manifest.get('stage','development'))
    if any(manifest.get(k)!=v or type(manifest.get(k))!=type(v) for k,v in expected.items()):
        raise ValueError('Exact prospectively frozen Campaign 004 envelope required')

def encounter_stop(manifest, invocation, sim_now, wall_now, wall_started):
    if not invocation or invocation['state']!='active':return None
    if sim_now-invocation['started_sim_time_s']>=manifest.get('encounter_sim_cap_s',4200):
        return 'encounter_simulation_cap'
    if wall_started is not None and wall_now-wall_started>=manifest.get('encounter_wall_cap_s',4500):
        return 'encounter_wall_cap'
