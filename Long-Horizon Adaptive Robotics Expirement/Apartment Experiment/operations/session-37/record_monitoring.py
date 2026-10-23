"""Save authenticated startup and scheduler receipts, outside experimental inputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tomllib

HERE = Path(__file__).resolve().parent
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3')
STARTUP = PAIR / 'operator/startup/observation-5b3915ab2bb14e35bbb9fc84b8078308.json'
AUTO = Path('C:/Users/cresp/.codex/automations/apartment-v3-baseline-observations/automation.toml')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')

startup = json.loads(STARTUP.read_bytes())
assert startup['passed'] and all(startup['checks'].values())
assert not (HERE / 'startup-verification.json').exists()
(HERE / 'startup-verification.json').write_bytes(STARTUP.read_bytes())
config = tomllib.loads(AUTO.read_text(encoding='utf-8'))
assert config['kind'] == 'heartbeat' and config['status'] == 'ACTIVE'
assert config['rrule'] == 'FREQ=MINUTELY;INTERVAL=30'
assert config['target_thread_id'] == '01a11e14-5a71-7e40-857b-f4dd9dbea394'
save(HERE / 'monitoring.json', dict(
    recorded_utc=datetime.now(timezone.utc).isoformat(),
    automation_id=config['id'], status=config['status'], kind=config['kind'],
    target_thread=config['target_thread_id'], interval_minutes=30,
    queue_job='20261009T010627656726Z-71e4ed51', pair=str(PAIR),
    startup_evidence=str(STARTUP), startup_sha256=sha(STARTUP),
    scheduler_config_path=str(AUTO), scheduler_config_sha256=sha(AUTO),
    scheduler_created_at=config['created_at'], prompt=config['prompt'],
    viewer=dict(url='http://127.0.0.1:50062', browser='Codex in-app browser', tab_id='1',
                visible=True, screenshot_verified=True, retained_as_deliverable=True),
    session_closeout='Session 37 remains open until verified endpoint or genuine blocker; no final Git closeout yet',
    local_scheduler_requirement='Computer and Codex app must remain running',
    official_endpoint_status='running; no completed result inferred',
    maps_status='pristine and unlaunched',
    creation_note='First request rejected before creation for missing destination; one successful creation with destination=thread. No duplicate automation.'
))
print(json.dumps(dict(startup_checks=len(startup['checks']), automation=config['id'], status=config['status'])))
