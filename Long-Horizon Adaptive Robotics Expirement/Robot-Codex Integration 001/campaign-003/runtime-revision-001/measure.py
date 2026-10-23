"""Read-only runtime-envelope planning from retained attempts; no plant/model.

Reconstruct the recorder's charged core bytes from authenticated SQLite tables.
Projections are capacity planning, never predictions of task success or a replay.
"""
import argparse
import collections
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import struct
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
C3 = ROOT.parent
REPO = C3.parents[2]
MAP = REPO / 'Long-Horizon Adaptive Robotics Expirement/Architecture Map'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def identity(path):
    return {'path': path.relative_to(REPO).as_posix(),
            'bytes': path.stat().st_size, 'sha256': digest(path)}


def inspect(run_id):
    root = C3 / 'live-evidence' / (run_id + '-attempt')
    release = MAP / 'releases/RCI001-C03-live' / run_id
    all_inputs = sorted(p for p in root.rglob('*') if p.is_file())
    inputs_before = {p.relative_to(root).as_posix(): identity(p) for p in all_inputs}
    receipt = read(root / 'receipt.json')
    manifest = read(release / 'manifest.json')
    assert receipt['manifest_sha256'] == digest(release / 'manifest.json')
    assert read(root / 'host/manifest.json') == manifest['apparatus_manifest']
    host = read(root / 'host/result.json')
    timing = read(root / 'host/timing-v2.json')
    status = read(root / 'host/public-state.json')
    registry = read(root / 'host/command-registry.json')
    assert host['execution_completed'] and host['error'] is None
    sim_s = host['sim_elapsed_s']
    container = root / 'host/native-recording'
    binding = read(container / 'container-manifest.json')
    compressed = (container / binding['database']).read_bytes()
    assert len(compressed) == binding['bytes']
    assert hashlib.sha256(compressed).hexdigest() == binding['sha256']
    raw = gzip.decompress(compressed)
    assert len(raw) == binding['uncompressed_bytes']
    assert hashlib.sha256(raw).hexdigest() == binding['uncompressed_sha256']
    db = sqlite3.connect(':memory:')
    db.deserialize(raw)
    assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    meta = dict(db.execute('SELECT key,value FROM meta'))
    assert meta['run_id'] == manifest['run_id'] and int(meta['core_quota_bytes']) == 50_000_000
    charged = {}
    # These are the exact _guard charges in the frozen recorder. No charge is
    # inferred from gzip size; image payload has a separate allowance.
    for table, overhead in [('objects', 128), ('telemetry', 160), ('events', 64), ('motion', 96)]:
        amount, count = db.execute(
            f'SELECT COALESCE(SUM(length(payload)+{overhead}),0),COUNT(*) FROM {table}'
        ).fetchone()
        charged[table] = {'bytes': amount, 'rows': count}
    amount, count = db.execute('SELECT COALESCE(SUM(160+length(CAST(id AS BLOB))),0),COUNT(*) FROM images').fetchone()
    charged['images'] = {'bytes': amount, 'rows': count}
    amount, count = db.execute('SELECT COALESCE(SUM(length(payload)+length(CAST(name AS BLOB))+64),0),COUNT(*) FROM documents').fetchone()
    charged['documents'] = {'bytes': amount, 'rows': count}
    core = sum(v['bytes'] for v in charged.values())
    images = [dict(zip(('status', 'reason', 'count', 'first_sim_s', 'last_sim_s'), row))
              for row in db.execute('SELECT status,reason,COUNT(*),MIN(time),MAX(time) FROM images GROUP BY status,reason')]
    image_bytes = db.execute('SELECT COALESCE(SUM(COALESCE(length(rgb),0)+COALESCE(length(depth),0)),0) FROM images').fetchone()[0]
    db.close()
    fs_bytes = collections.Counter()
    with tarfile.open(root / 'workspace-block/evidence.tar.gz', 'r:gz') as tar:
        for member in tar:
            assert not member.issym() and not member.islnk()
            if member.isfile() and member.name.startswith('journal/'):
                key = 'content_objects' if '/objects/' in member.name else member.name
                fs_bytes[key] += member.size
    memory = timing['host_memory']
    sample_path = root / 'host' / memory['sample_file']
    assert digest(sample_path) == memory['sha256']
    rows = list(struct.iter_unpack('<7d', sample_path.read_bytes()))
    assert len(rows) == memory['sample_count']
    public_bytes = (root / 'host/public-history.jsonl').stat().st_size
    actions = [r for r in registry.values() if r['actor'] == 'robot' and r['kind'] == 'command']
    observes = [r for r in registry.values() if r['actor'] == 'robot' and r['kind'] == 'observe']
    official = read(release / 'official-status.json')
    outputs = {
        'run_id': manifest['run_id'],
        'original_queue': {k: official[k] for k in ('state', 'exit_status')},
        'original_coordinator_infrastructure_valid': receipt['infrastructure_valid'],
        'original_and_corrected_dispositions_unchanged': True,
        'host_sim_elapsed_s': sim_s,
        'coordinator_wall_elapsed_s': receipt['wall_elapsed_s'],
        'actions_used': status['robot_action_budget']['used'],
        'action_limit': status['robot_action_budget']['limit'],
        'physical_request_count': len(actions),
        'physical_status_counts': dict(collections.Counter(r['status'] for r in actions)),
        'explicit_observations': len(observes),
        'accepted_handbacks': sum(r['kind'] == 'handback' and r['status'] == 'completed' for r in registry.values()),
        'core_charged_bytes': core, 'core_charge_tables': charged,
        'core_limit_bytes': int(meta['core_quota_bytes']),
        'native_image_payload_bytes': image_bytes, 'native_image_availability': images,
        'public_history_bytes': public_bytes,
        'host_final_bytes': sum(p.stat().st_size for p in (root / 'host').rglob('*') if p.is_file()),
        'journal_uncompressed_bytes': sum(fs_bytes.values()), 'journal_components': dict(fs_bytes),
        'windows_retained_bytes_at_measurement': sum(p.stat().st_size for p in all_inputs),
        'native_memory': {
            'baseline_private_commit_bytes': memory['baseline']['private_commit_bytes'],
            'baseline_limit_bytes': memory['baseline_private_commit_limit_bytes'],
            'peak_measured_private_commit_bytes': int(max(r[2] for r in rows)),
            'last_measured_private_commit_bytes': int(rows[-1][2]),
            'soft_limit_bytes': memory['soft_limit_bytes'],
            'hard_limit_bytes': memory['native_job']['hard_process_commit_limit_bytes'],
            'longer_duration_qualification': 'not_run; do not extrapolate a qualified memory pass',
        },
        'rates': {
            'core_bytes_per_sim_s': core / sim_s,
            'public_history_bytes_per_sim_s': public_bytes / sim_s,
            'journal_bytes_per_sim_s': sum(fs_bytes.values()) / sim_s,
            'physical_actions_per_model_second': status['robot_action_budget']['used'] / 600,
        },
        'source_manifest': identity(release / 'manifest.json'),
        'original_official_status': identity(release / 'official-status.json'),
        'inputs': inputs_before,
    }
    assert inputs_before == {p.relative_to(root).as_posix(): identity(p) for p in all_inputs}
    assert set(all_inputs) == {p for p in root.rglob('*') if p.is_file()}
    return outputs


def main(output):
    cases = [inspect('RCI001-C03-live-001'), inspect('RCI001-C03-pilot-001')]
    # One choice based solely on prior evidence; never read a new model result.
    envelope = {'model_invocation_s': 3600, 'encounter_sim_s': 4200, 'encounter_wall_s': 4500}
    projection = []
    for case in cases:
        rates = case['rates']
        projection.append({
            'based_on': case['run_id'], 'classification': 'linear capacity planning, not observed future behavior',
            'one_full_model_session_core_bytes_at_rtf_1': rates['core_bytes_per_sim_s'] * 3600,
            'three_full_model_sessions_core_bytes_at_rtf_1': rates['core_bytes_per_sim_s'] * 10800,
            'core_limit_crossing_sim_s_at_observed_rate': 50_000_000 / rates['core_bytes_per_sim_s'],
            'one_full_model_session_actions_at_observed_rate': rates['physical_actions_per_model_second'] * 3600,
            'action_limit_crossing_model_s_at_observed_rate': 20 / rates['physical_actions_per_model_second'],
            'full_three_encounter_sim_envelope_public_history_bytes': rates['public_history_bytes_per_sim_s'] * 12600,
            'full_three_encounter_sim_envelope_core_bytes': rates['core_bytes_per_sim_s'] * 12600,
            'full_three_encounter_sim_envelope_journal_bytes': rates['journal_bytes_per_sim_s'] * 12600,
        })
    dependencies = [
        'campaign-003/coordinator.py', 'campaign-003/apparatus.py', 'campaign-003/gateway_c.py',
        'campaign-003/CONTRACT.md', 'campaign-003/PHASE2.md', 'host/supervisor.py',
        'campaign-002/harness/continuous_adapter.py', 'campaign-002/harness/memory_guard.py',
    ]
    source = [identity(C3.parent / p) for p in dependencies]
    source.append(identity(REPO / 'Long-Horizon Adaptive Robotics Expirement/Storage Retention Implementation 001/future/recorder.py'))
    result = {
        'schema': 'campaign003-runtime-capacity-planning-1', 'passed': True,
        'created_at': datetime.now(timezone.utc).isoformat(), 'model_calls': 0, 'plant_runs': 0,
        'method': 'Authenticate retained bytes and reconstruct exact recorder charges; extrapolations explicitly conditional.',
        'envelope_choice': envelope, 'cases': cases, 'projections': projection,
        'native_free_bytes_at_measurement': shutil.disk_usage(REPO).free,
        'native_free_reserve_bytes': 100 * 1024**3, 'retirement_headroom_bytes': 2 * 1024**3,
        'sources': source, 'measurement_script': identity(Path(__file__).resolve()),
        'admission': 'blocked_on_separate_non_time_budget_decision; no runtime or scientific limit changed by this reader',
        'limits': [
            'Two ten-minute failures do not predict how long a successful new session will take.',
            'Neither prior run exhausted the action or core-storage quota.',
            'The action-rate projection is behavioral and may change; it does not prove that 20 actions cannot succeed.',
            'Core/public-history/journal rates depend on future motion and data; projections are not qualified maxima.',
            'Sparse-camera exhaustion is prior policy, not evidence of failed explicit image availability.',
            'Queue success for this reader is not live qualification, task success, or a scored campaign result.',
        ],
    }
    output = Path(output)
    with output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({'passed': True, 'model_calls': 0, 'output': str(output),
                      'core_bytes': [c['core_charged_bytes'] for c in cases], 'envelope': envelope}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    main(parser.parse_args().output)
