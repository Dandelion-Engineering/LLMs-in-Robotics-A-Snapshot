"""Read-only Maps observations and immutable checkpoint readback, outside robot roots."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

from launch_maps import PAIR, FROZEN_CODE, OP, queue
from common import canonical, read, save, sha


def prefix(path):
    raw = path.read_bytes()
    raw = raw[:raw.rfind(b'\n') + 1]
    return [json.loads(line) for line in raw.splitlines()], dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def observe(label, startup=False):
    root = Path(read(PAIR / 'maps-lineage.json')['active_root']).resolve()
    assert root.is_relative_to(PAIR.resolve())
    job = read(OP / 'maps-launch-queue.json')['id']
    result = dict(label=label, observed_utc=datetime.now(timezone.utc).isoformat(),
                  observed_monotonic_ns=time.monotonic_ns(), observational_only=True,
                  active_root=str(root), queue_job=job, checks={}, anomalies=[])
    result['queue'] = queue('status', job)
    result['running_lock'] = (root / 'running.lock').exists()
    result['free_disk_gib'] = {d: shutil.disk_usage(d + ':/').free / 1024**3 for d in ('C', 'D')}
    expected = read(OP / 'prelaunch.json')['baseline_identity']
    result['baseline_unchanged'] = all(sha(PAIR / 'baseline' / name) == digest for name, digest in expected.items())
    if not result['baseline_unchanged']:
        result['anomalies'].append('Baseline identity changed')
    events, result['physical_prefix'] = prefix(root / 'events.jsonl')
    counts = Counter(r['kind'] for r in events)
    result['event_counts'] = dict(counts)
    started = [r for r in events if r['kind'] == 'session_started']
    closed = [r for r in events if r['kind'] == 'session_closed']
    result['last_closed'] = closed[-1] if closed else None
    for name in ('latest-checkpoint.json', 'completed.json', 'controller-failure.json', 'hibernate-requested.json'):
        if (root / name).exists():
            result[name] = read(root / name)
    if 'controller-failure.json' in result:
        result['anomalies'].append('Controller failure evidence present')
    if (root / 'latest-execution.json').exists():
        pointer = read(root / 'latest-execution.json')
        assert Path(pointer['path']).parent.resolve() == root and sha(pointer['path']) == pointer['sha256']
        execution = read(pointer['path'])
        result['execution'] = {k: execution.get(k) for k in ('passed', 'error', 'failure_phase', 'structured_failure', 'retirement')}
        if execution['passed'] is False:
            result['anomalies'].append('Authenticated failed execution')
    try:
        url = read(root / 'viewer.json')['url']
        assert url.startswith('http://127.0.0.1:')
        result['viewer_url'] = url
        frames = []
        for i in range(2 if startup else 1):
            with urllib.request.urlopen(url + '/frame', timeout=12) as response:
                frames.append(json.load(response))
            if startup and i == 0:
                time.sleep(.2)
        result['viewer_responding'] = True
        result['frame'] = {k: v for k, v in frames[-1].items() if k not in ('geoms', 'activity')}
        result['frame']['geometry_count'] = len(frames[-1]['geoms'])
        if startup:
            result['checks']['advancing_simulator'] = frames[1]['sim_time'] > frames[0]['sim_time'] and len(frames[1]['geoms']) > 0
    except Exception as error:
        result.update(viewer_responding=False, viewer_error=repr(error))
        if result['queue']['state'] == 'running':
            result['anomalies'].append('Viewer observation unavailable; inspect lifecycle before intervention')
    if started:
        session_number = len(started)
        native = root / 'sessions' / ('session-' + str(session_number).zfill(5)) / 'native'
        result['session'] = session_number
        if (native / 'client/preflight.json').exists():
            native_identity = read(native / 'client/preflight.json')
            result['native_identity'] = {k: native_identity.get(k) for k in ('model_effective', 'effort_effective', 'auth_type', 'preflight_passed', 'thread_id')}
        if (native / 'client/events.jsonl').exists():
            native_rows, result['native_prefix'] = prefix(native / 'client/events.jsonl')
            result['native_event_counts'] = dict(Counter(r.get('method', r.get('kind', 'unknown')) for r in native_rows))
            result['native_error_events'] = [r for r in native_rows if r.get('method', r.get('kind')) in ('error', 'turn/failed')]
            if result['native_error_events']:
                result['anomalies'].append('Native error event present')
        transport = native / 'codehost-transport-v3.jsonl'
        if transport.exists():
            records, receipt = prefix(transport)
            result['transport'] = dict(prefix=receipt, records=len(records), last_kind=records[-1]['kind'] if records else None,
                                       failures=[r for r in records if r['kind'] in ('bridge_failure', 'channel_error', 'queue_overflow', 'failed')],
                                       live_queue_occupancy=None,
                                       live_queue_occupancy_reason='No live queue occupancy receipt is published; terminal bridge receipt provides qualified headroom.')
            if result['transport']['failures']:
                result['anomalies'].append('Transport failure event present')
        if startup:
            checks = result['checks']
            checks['queue_running'] = result['queue']['state'] == 'running' and result['queue']['exit_status'] is None
            checks['run_launched_once'] = read(root / 'run.json')['launched'] is True and result['running_lock']
            identity = result.get('native_identity', {})
            checks['native_model_identity'] = identity.get('preflight_passed') is True and identity.get('model_effective') == 'gpt-6-astra' and identity.get('effort_effective') == 'max' and identity.get('auth_type') == 'chatgpt'
            checks['namespace_canaries'] = all((native / name).exists() and read(native / name)['exit_status'] == 0 and json.loads(read(native / name)['stdout'])['qualified'] is True for name in ('canary.json', 'codehost-canary.json'))
            native_counts = result.get('native_event_counts', {})
            checks['native_turn_started'] = native_counts.get('turn/started', 0) > 0
            checks['observable_tool_activity'] = native_counts.get('item/tool/call', 0) > 0 or native_counts.get('public_tool_call', 0) > 0
            checks['sensors_and_images'] = counts['sensor_capture'] > 0 and counts['image_delivered'] > 0
            journal = native.parent / 'workspace/journal/mutations.jsonl'
            if journal.exists():
                journal_rows, result['journal_prefix'] = prefix(journal)
                checks['protected_filesystem_active'] = len(journal_rows) > 1
            else:
                checks['protected_filesystem_active'] = False
            index = read(root / 'replay/index.json')
            checks['original_replay_recording'] = bool(index) and sha(root / 'replay' / index[-1]['file']) == index[-1]['sha256']
            checks['baseline_unchanged'] = result['baseline_unchanged']
            result['startup_passed'] = all(checks.values())
    path = OP / 'observations' / (label + '-' + uuid.uuid4().hex + '.json')
    save(path, result)
    summary = {k: result.get(k) for k in ('observed_utc', 'session', 'event_counts', 'frame', 'viewer_url', 'viewer_responding', 'baseline_unchanged', 'free_disk_gib', 'anomalies', 'checks', 'startup_passed', 'execution')}
    summary.update(evidence=str(path), queue_state=result['queue']['state'], exit_status=result['queue']['exit_status'])
    print(canonical(summary).decode())
    return result


def checkpoint():
    from recording import verify_checkpoint, verify_prefix
    root = Path(read(PAIR / 'maps-lineage.json')['active_root']).resolve()
    assert root.is_relative_to(PAIR.resolve())
    pointer = read(root / 'latest-checkpoint.json')
    path = Path(pointer['path']).resolve()
    assert path.is_relative_to(root)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), pointer=pointer, root=str(root), passed=False)
    try:
        assert sha(path / 'manifest.json') == pointer['manifest_sha256']
        result['checkpoint_readback'] = verify_checkpoint(path)
        result['prefix_readback'] = verify_prefix(root, path)
        state = read(path / 'state.json')
        result.update(normal_closed_sessions=state['sessions'], assignments_completed=state['position'], simulation_time=state['world']['sim_time'], passed=True)
        native = root / 'sessions' / ('session-' + str(pointer['session']).zfill(5)) / 'native'
        bridge = native / 'codehost-owner-bridge-v3.json'
        if bridge.exists():
            receipt = read(bridge)
            result['transport_terminal'] = {k: v for k, v in receipt.items() if k not in ('namespace_records', 'channels', 'owner')}
            assert receipt['qualified'] is True and not receipt['failures'] and receipt['queued_bytes_at_close'] == 0 and receipt['drain']['seal_qualified'] is True
    except Exception as error:
        result.update(passed=False, error=repr(error))
    out = OP / 'observations' / ('checkpoint-' + str(pointer['session']).zfill(5) + '-' + uuid.uuid4().hex + '.json')
    save(out, result)
    print(canonical(dict(evidence=str(out), **result)).decode())
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='periodic')
    parser.add_argument('--startup', action='store_true')
    parser.add_argument('--checkpoint', action='store_true')
    args = parser.parse_args()
    if args.checkpoint:
        raise SystemExit(0 if checkpoint() else 1)
    result = observe(args.label, args.startup)
    raise SystemExit(1 if args.startup and not result.get('startup_passed') else 0)
