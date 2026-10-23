"""One prospectively frozen envelope; no outcome-dependent time extensions."""
from functools import lru_cache
import json
from common import HERE, sha

ENVELOPE = HERE / 'runtime-revision-001/runtime-envelope.json'
AUTHORITY = HERE / 'runtime-revision-001/additional-authorization.json'
ENVELOPE_SHA = 'bbe75c5fb188a4fc8ce1e7698352fcd96f812723bdcf66779c784ad5e356586b'


@lru_cache(maxsize=1)
def configuration():
    if sha(ENVELOPE) != ENVELOPE_SHA:
        raise ValueError('Frozen time selection changed')
    envelope = json.loads(ENVELOPE.read_text(encoding='utf-8'))
    approval = json.loads(AUTHORITY.read_text(encoding='utf-8'))
    expected = {'actions_per_activation': 120, 'native_core_bytes_per_block': 256 * 1024**2,
                'host_evidence_bytes_per_block': 2 * 1024**3}
    if approval['approved'] != expected or not approval['verbatim_reply'].startswith('I approve all three proposed limits'):
        raise ValueError('Separate budget authorization missing')
    return envelope, approval


def apply_limits(manifest, stage):
    envelope, approval = configuration()
    limits = envelope['limits_s']; budgets = approval['approved']
    total = envelope['aggregate_time_only_limits_s']['live_qualification' if stage == 'live_qualification' else 'three_encounter_block']
    return {**manifest, **total, 'model_timeout_s': limits['model_invocation_s'],
            'encounter_sim_cap_s': limits['encounter_sim_s'], 'encounter_wall_cap_s': limits['encounter_wall_s'],
            'robot_action_limit': budgets['actions_per_activation'], 'native_core_cap_bytes': budgets['native_core_bytes_per_block'],
            'storage_cap_bytes': budgets['host_evidence_bytes_per_block'],
            'runtime_envelope_sha256': ENVELOPE_SHA, 'additional_budget_authority_sha256': sha(AUTHORITY)}


def validate_limits(manifest):
    stage = manifest.get('stage', 'development')
    expected = apply_limits({}, stage)
    if any(manifest.get(key) != value or type(manifest.get(key)) != type(value) for key, value in expected.items()):
        raise ValueError('Manifest does not use the exact authorized frozen envelope')


def encounter_stop(manifest, invocation, sim_now, wall_now, wall_started):
    if not invocation or invocation['state'] != 'active':
        return None
    if sim_now - invocation['started_sim_time_s'] >= manifest.get('encounter_sim_cap_s', 900):
        return 'encounter_simulation_cap'
    if wall_started is not None and wall_now - wall_started >= manifest.get('encounter_wall_cap_s', 1100):
        return 'encounter_wall_cap'
    return None
