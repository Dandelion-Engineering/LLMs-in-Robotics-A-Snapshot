"""Read one newly published checkpoint for an explicitly selected pair."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid

parser=argparse.ArgumentParser();parser.add_argument('--pair',type=Path,required=True);args=parser.parse_args()
PAIR = args.pair.resolve()
CODE = PAIR / 'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
sys.path.insert(0, str(CODE))
from common import canonical, read, save, sha
from recording import verify_checkpoint, verify_prefix

root = Path(read(PAIR / 'baseline-lineage.json')['active_root']).resolve()
assert root == (PAIR / 'baseline').resolve(), 'No recovery branch is authorized'
out = PAIR / 'operator/observations'
out.mkdir(parents=True, exist_ok=True)
if not (root / 'latest-checkpoint.json').exists():
    print(canonical(dict(status='not_yet_published', root=str(root), observational_only=True)).decode())
    raise SystemExit(0)
pointer = read(root / 'latest-checkpoint.json')
checkpoint = Path(pointer['path']).resolve()
assert checkpoint.is_relative_to(root)
for prior in sorted(out.glob('checkpoint-*.json')):
    recorded = read(prior)
    if recorded.get('pointer') == pointer:
        print(canonical(dict(status='previously_observed', evidence=str(prior), **recorded)).decode())
        raise SystemExit(0 if recorded['passed'] else 1)
started = time.monotonic()
result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), root=str(root), checkpoint=str(checkpoint),
              pointer=pointer, observational_only=True, passed=False)
try:
    assert sha(checkpoint / 'manifest.json') == pointer['manifest_sha256']
    result['checkpoint_readback'] = verify_checkpoint(checkpoint)
    result['prefix_readback'] = verify_prefix(root, checkpoint)
    state = read(checkpoint / 'state.json')
    result.update(normal_closed_sessions=state['sessions'], assignments_completed=state['position'],
                  simulation_time=state['world']['sim_time'], passed=True)
except Exception as error:
    result['error'] = repr(error)
result['elapsed_seconds'] = time.monotonic() - started
path = out / ('checkpoint-' + str(pointer['session']).zfill(5) + '-' + uuid.uuid4().hex + '.json')
assert not path.exists()
save(path, result)
print(canonical(dict(status='new_observation', evidence=str(path), **result)).decode())
raise SystemExit(0 if result['passed'] else 1)
