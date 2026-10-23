"""Freeze the time-only decision without declaring or launching a live attempt."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from measure import ROOT, REPO, MAP, read, identity, digest


def save(name, value):
    with (ROOT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


measurement = read(ROOT / 'measurement.json')
assert measurement['passed'] and measurement['model_calls'] == measurement['plant_runs'] == 0
job = json.loads(subprocess.check_output([
    sys.executable, '-X', 'utf8', '-B', str(REPO.parent / 'tools/compute_queue/compute_queue.py'),
    'status', '20261004T020348222170Z-b2c231fe'], text=True, encoding='utf-8'))
assert job['state'] == 'succeeded' and type(job['exit_status']) is int and job['exit_status'] == 0
assert Path(job['cwd']).resolve() == REPO.resolve()
assert (REPO / job['argv'][-2]).resolve() == ROOT / 'measure.py'
assert measurement['measurement_script']['sha256'] == digest(ROOT / 'measure.py')
save('measurement-official-status.json', job)
chat = REPO / 'chats/Codex-Human/Robot-Codex Campaign 003/Robot-Codex Campaign 003 - Active.md'
raw = chat.read_bytes()
assert b'2026-10-03 18:52 PDT' in raw and b'per-session runtime envelope only' in raw
authority = {'path': chat.relative_to(REPO).as_posix(), 'bytes': len(raw),
             'sha256': hashlib.sha256(raw).hexdigest(), 'message': 'Randy, 2026-10-03 18:52 PDT'}
envelope = {
    'schema': 'campaign003-prospective-runtime-envelope-1',
    'id': 'C03-runtime-envelope-001', 'created_at': datetime.now(timezone.utc).isoformat(),
    'authority': authority, 'limits_s': measurement['envelope_choice'],
    'previous_limits_s': {'model_invocation_s': 600, 'encounter_sim_s': 900, 'encounter_wall_s': 1100},
    'clock_semantics': {
        'model_invocation_s': 'Existing app-server invocation deadline, starting at its current invocation boundary.',
        'encounter_sim_s': 'Elapsed continuously running simulation time from accepted start-invocation.',
        'encounter_wall_s': 'Elapsed monotonic host wall time from accepted start-invocation; never reset by commands.',
    },
    'reason': 'Sixfold model allowance, with 600 simulation seconds and 900 wall seconds beyond the model allowance for setup, RTF tolerance, handback and retirement. Chosen only from retained original failures.',
    'aggregate_time_only_limits_s': {
        'live_qualification': {'sim_cap_s': 4500, 'wall_cap_s': 4800},
        'three_encounter_block': {'sim_cap_s': 13200, 'wall_cap_s': 14100},
        'derivation': 'One-encounter totals add 300 seconds; three-encounter totals add 600 seconds to the sums of encounter limits for initialization and intervening A/B work. Existing per-job waits stay unchanged.',
    },
    'measurement': identity(ROOT / 'measurement.json'),
    'measurement_official_status': identity(ROOT / 'measurement-official-status.json'),
    'unchanged_task_source_snapshot': identity(MAP / 'releases/RCI001-C03-live/RCI001-C03-pilot-001/snapshot.json'),
    'unchanged': ['GPT-6 Astra/max/ChatGPT', 'sole bootstrap', 'C task/geometry/physics',
                  'placement and handback tolerances', 'memory/prompt strategy', 'vision interface',
                  'action and observation limits', 'all evidence quotas', 'workspace/file quotas',
                  'timing, isolation, authority, evaluator, durability, retirement, free-space and memory criteria'],
    'after_failure': 'Retain valid failure; do not extend this envelope again to obtain success.',
    'prospective_only': True, 'no_new_attempt_declared': True,
}
save('runtime-envelope.json', envelope)
save('freeze-receipt.json', {
    'schema': 'campaign003-runtime-envelope-freeze-1', 'created_at': datetime.now(timezone.utc).isoformat(),
    'envelope': identity(ROOT / 'runtime-envelope.json'), 'generator': identity(ROOT / 'freeze.py'),
    'selection_frozen': True, 'installed_in_executable_lineage': False,
    'model_invocations_since_selection': 0, 'launch_admitted': False,
    'reason': 'Separate non-time budget decision required; no attempt or runnable revised lineage is registered.',
})
print(json.dumps({'frozen': identity(ROOT / 'runtime-envelope.json'), 'launch_admitted': False}))
