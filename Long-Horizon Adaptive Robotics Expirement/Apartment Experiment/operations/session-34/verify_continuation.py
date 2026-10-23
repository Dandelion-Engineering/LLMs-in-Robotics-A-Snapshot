"""Bounded read-only verification of the first events and inode state after resume."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
CODE = PAIR / 'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
sys.path.insert(0, str(CODE))
from common import canonical, read, save, sha

root = Path(read(PAIR / 'baseline-lineage.json')['active_root'])
checkpoint = root / 'checkpoints/session-00023'
state = read(checkpoint / 'state.json')
with (root / 'events.jsonl').open('rb') as stream:
    prefix = stream.read(state['log_bytes'])
    resumed = json.loads(stream.readline())
    started = json.loads(stream.readline())
with (root / 'sessions/session-00024/workspace/journal/mutations.jsonl').open('rb') as stream:
    initial = json.loads(stream.readline())
native = read(root / 'sessions/session-00024/native/client/preflight.json')
op = PAIR / 'operator/resume-session34-001'
old_execution = read(op / 'preresume-idle.json')['old_queue']
receipt = dict(observed_utc=datetime.now(timezone.utc).isoformat(), root=str(root),
               checkpoint=str(checkpoint), checkpoint_sha256=sha(checkpoint / 'manifest.json'),
               prior_session=23, first_resumed_session=24, preserved_assignments=state['position'],
               preserved_sim_time=state['world']['sim_time'], resumed_event=resumed, started_event=started,
               old_execution_queue=old_execution['id'], new_execution_queue=read(op / 'resume-queue.json')['id'],
               native_identity={k:native[k] for k in ('model_effective','effort_effective','auth_type','preflight_passed','thread_id')}, checks={})
checks = receipt['checks']
checks['checkpoint_identity'] = receipt['checkpoint_sha256'] == '09d4e72c95198337567e567bf3431293ea9ab64087bb4dfcef90306e79d53b9c'
checks['original_event_prefix_preserved'] = hashlib.sha256(prefix).hexdigest() == state['event_prefix_sha256']
checks['exact_resume_boundary'] = (resumed['kind'] == 'resumed' and resumed['sequence'] == state['event_sequence'] + 1
    and resumed['previous'] == state['event_chain'] and resumed['sim_time'] == state['world']['sim_time']
    and resumed['payload']['session'] == 23 and resumed['payload']['position'] == 15
    and Path(resumed['payload']['checkpoint']).resolve() == checkpoint.resolve())
checks['fresh_clock_epoch'] = resumed['clock_epoch'] != state['clock_epoch']
checks['first_session_is_24'] = started['kind'] == 'session_started' and started['payload']['session'] == 24
checks['persistent_inode_state_preserved'] = initial['state'] == read(checkpoint / 'filesystem-namespace.json')
checks['original_model_identity'] = (native['preflight_passed'] is True and native['model_effective'] == 'gpt-6-astra'
    and native['effort_effective'] == 'max' and native['auth_type'] == 'chatgpt')
checks['old_hibernation_processed_by_frozen_runtime'] = not (root / 'hibernate-requested.json').exists() and len(list(root.glob('hibernate-processed-*.json'))) == 1
receipt['passed'] = all(checks.values())
save(op / 'continuation-verification.json', receipt)
save(Path(__file__).with_name('continuation-verification.json'), receipt)
print(canonical(receipt).decode())
raise SystemExit(0 if receipt['passed'] else 1)
