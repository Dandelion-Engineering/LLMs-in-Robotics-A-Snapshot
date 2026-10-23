"""One immutable latest-checkpoint/prefix readback, without native-history bulk audit."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
CODE = PAIR / 'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
sys.path.insert(0, str(CODE))
from common import canonical, read, save, sha
from recording import verify_checkpoint, verify_prefix

root = Path(read(PAIR / 'baseline-lineage.json')['active_root']).resolve()
assert root.is_relative_to(PAIR.resolve())
pointer = read(root / 'latest-checkpoint.json')
checkpoint = Path(pointer['path']).resolve()
assert checkpoint.is_relative_to(root)
out = PAIR / 'operator/resume-session34-001/observations'
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
save(path, result)
print(canonical(dict(evidence=str(path), **result)).decode())
raise SystemExit(0 if result['passed'] else 1)
