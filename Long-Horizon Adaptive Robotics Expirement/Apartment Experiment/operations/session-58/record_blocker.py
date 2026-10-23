"""Record failed storage admission and bounded preservation readback; never launch."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tomllib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'
sys.path.insert(0, str(HERE.parent / 'session-41'))
from admission_checks import storage


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def inventory(root):
    return {p.relative_to(root).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in sorted(root.rglob('*')) if p.is_file()}


def queue(*args):
    return json.loads(subprocess.check_output(
        [sys.executable, '-X', 'utf8', '-B', str(QUEUE), *args],
        text=True, encoding='utf-8'))


def main():
    transcript = REPO / 'chats/Codex-Human/Apartment v4 Maps Launch and Monitoring/Apartment v4 Maps Launch and Monitoring - Active.md'
    authority = transcript.read_bytes()
    assert authority.count(b'**Randy (2026-10-10 08:48 PDT):**') == 1
    with (HERE / 'authority-original.md').open('xb') as stream:
        stream.write(authority)
    capacity = storage()
    requirement = capacity['minimum_bytes'] + capacity['expected_run_and_preparation_envelope_bytes']
    result = {
        'schema': 'apartment-maps-prelaunch-storage-blocker-1',
        'observed_utc': datetime.now(timezone.utc).isoformat(),
        'development_session': 58, 'condition': 'maps', 'run_id': 'APARTMENT-v4-maps',
        'root': str(PAIR / 'maps'), 'passed': False,
        'status': 'blocked_before_launch', 'scientific_submission_attempted': False,
        'scientific_queue_id': None, 'viewer_started': False, 'monitor_created': False,
        'authority': {'path': str(HERE / 'authority-original.md'), 'sha256': sha(HERE / 'authority-original.md')},
        'capacity': capacity,
        'required_free_bytes_under_inherited_headroom_gate': requirement,
        'shortfall_bytes': max(0, requirement - capacity['free_bytes']),
        'reader_sha256': sha(Path(__file__)),
        'admission_reader_sha256': sha(HERE.parent / 'session-41/admission_checks.py'),
        'disposition': 'Stop at failed capacity gate. No cleanup, lower gate, source change, submission, viewer or monitor.',
        'not_run': [
            'Fresh complete source inventory and installed environment qualification',
            'New full Baseline history/replay/filesystem audit and complete runtime retirement census',
            'Full Maps prelaunch isolation and official verify_run admission',
            'Official queue submission, native startup, sensor/journal checks and rendered live viewer',
            'Maps monitoring and checkpoint/endpoint audits',
            'Baseline-versus-Maps scientific comparison',
        ],
    }
    assert capacity['minimum_gate'] and not capacity['headroom_gate'], 'Record only this observed blocker; never infer launch permission.'
    save(HERE / 'admission-blocker.json', result)

    # These bounded checks preserve the stopped state; they do not reopen admission.
    retained = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'observational_only': True,
                'scope': 'Current identity anchors and retained audit receipts, not a fresh full history audit.', 'checks': {}}
    endpoint_path = HERE.parent / 'session-57/endpoint.json'
    endpoint = read(endpoint_path)
    retained['endpoint_sha256'] = sha(endpoint_path)
    assert retained['endpoint_sha256'] == sha(PAIR / 'operator/endpoint-audit-session57-001/verified-endpoint.json')
    retained['endpoint_evidence_hashes'] = {}
    for name, ref in endpoint['evidence'].items():
        actual = sha(ref['uri'])
        assert actual == ref['sha256'], f'Retained endpoint evidence changed: {name}'
        retained['endpoint_evidence_hashes'][name] = actual
    retained['checks']['all_31_endpoint_references_match'] = len(retained['endpoint_evidence_hashes']) == 31
    retained['queues'] = {}
    for name in ('official_queue', 'full_audit_queue', 'supplement_queue'):
        prior = read(endpoint['evidence'][name]['uri'])
        current = queue('status', prior['id'])
        assert current == prior and current['state'] == 'succeeded' and type(current['exit_status']) is int and current['exit_status'] == 0
        retained['queues'][name] = current
    for name in ('full_audit', 'supplement'):
        audit = read(endpoint['evidence'][name]['uri'])
        assert audit['passed'] is True and len(audit['checks']) == 5 and all(v is True for v in audit['checks'].values())
    retained['checks']['accepted_baseline_and_two_successful_audit_receipts'] = True
    baseline = PAIR / 'baseline'
    checkpoint = read(baseline / 'latest-checkpoint.json')
    cp = Path(checkpoint['path'])
    assert checkpoint['session'] == 35 and checkpoint['reason'] == 'completed'
    assert sha(cp / 'manifest.json') == checkpoint['manifest_sha256'] == '84ef12f0d1e39e05cc4cc3325451374f12afe104efdb21f91487dde65856fd97'
    assert sha(cp / 'state.json') == checkpoint['state_sha256'] == '405262ee52202745424b14e55c5232751702b4d73c1077143ec2c0298f7d0c79'
    completed = read(baseline / 'completed.json')
    assert completed['sessions'] == 35 and completed['assignments'] == 21 and completed['checkpoint'] == checkpoint
    retained['baseline_checkpoint'] = checkpoint
    retained['baseline_anchors'] = {n: sha(baseline / n) for n in (
        'run.json', 'completed.json', 'latest-checkpoint.json', 'latest-execution.json',
        'events.jsonl', 'filesystem-namespace.json', 'replay/index.json')}
    retained['checks']['completed_baseline_checkpoint_anchors'] = True
    maps = PAIR / 'maps'
    run = read(maps / 'run.json')
    prepared = read(PAIR / 'prepared.json')
    lineage = read(PAIR / 'maps-lineage.json')
    assert Path(lineage['active_root']).resolve() == maps.resolve() and lineage['history'] == []
    assert run['launched'] is False and run['run_id'] == 'APARTMENT-v4-maps' and run['condition'] == 'maps'
    assert set(p.name for p in maps.iterdir()) == {'filesystem', 'run.json', 'config.json', 'schedule.json', 'initial-filesystem.json'}
    initial = inventory(maps / 'filesystem')
    assert initial == read(maps / 'initial-filesystem.json') == run['template'] == prepared['initial']['maps']
    retained['maps_initial_files'] = len(initial)
    retained['maps_initial_inventory_sha256'] = sha(maps / 'initial-filesystem.json')
    retained['maps_full_root_inventory'] = inventory(maps)
    retained['checks']['maps_pristine_original_19_file_start'] = len(initial) == 19
    base_run = read(baseline / 'run.json')
    assert all(run[k] == base_run[k] for k in ('source_identity', 'config_sha256', 'schedule_sha256'))
    assert sha(maps / 'schedule.json') == sha(baseline / 'schedule.json') == sha(PAIR / 'hidden-schedule.json') == prepared['schedule_sha256']
    assert read(maps / 'config.json') == read(baseline / 'config.json') == prepared['config']
    retained['checks']['pair_schedule_configuration_identity_records'] = True
    retained['source_manifest_sha256'] = prepared['source_manifest_sha256']
    retained['certificate_sha256'] = prepared['certificate_sha256']
    retained['prepared_sha256'] = sha(PAIR / 'prepared.json')
    retained['active_jobs'] = sum((queue('list', '--state', state) for state in ('running', 'queued', 'cancel_requested')), [])
    retained['checks']['no_active_queue_jobs'] = not retained['active_jobs']
    retained['running_locks'] = [str(PAIR / c / 'running.lock') for c in ('baseline', 'maps') if (PAIR / c / 'running.lock').exists()]
    retained['checks']['v4_running_locks_absent'] = not retained['running_locks']
    with socket.socket() as sock:
        sock.settimeout(1)
        retained['old_baseline_viewer_listening'] = sock.connect_ex(('127.0.0.1', 49645)) == 0
    retained['checks']['old_baseline_viewer_port_closed'] = not retained['old_baseline_viewer_listening']
    retained['monitors'] = []
    for path in sorted(Path('C:/Users/cresp/.codex/automations').glob('*/automation.toml')):
        row = tomllib.loads(path.read_text(encoding='utf-8'))
        if 'apartment' in json.dumps(row).lower():
            retained['monitors'].append({'id': row.get('id', path.parent.name), 'status': row.get('status'), 'sha256': sha(path)})
    retained['checks']['all_four_apartment_monitors_paused'] = len(retained['monitors']) == 4 and all(m['status'] == 'PAUSED' for m in retained['monitors'])
    retained['passed_bounded_readback'] = all(retained['checks'].values())
    save(HERE / 'preservation-readback.json', retained)
    assert retained['passed_bounded_readback'], 'Preserve discrepancy; no launch.'
    print(json.dumps({'status': result['status'], 'free_gib': capacity['free_gib'],
        'required_gib': requirement / 1024**3, 'shortfall_gib': result['shortfall_bytes'] / 1024**3,
        'preservation_checks': retained['checks'], 'official_submission': False}, indent=2))


if __name__ == '__main__':
    main()
