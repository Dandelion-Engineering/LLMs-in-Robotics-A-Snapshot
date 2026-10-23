"""Authenticate final retained evidence, replay, links and browser captures."""
import json
import struct
from pathlib import Path
import shutil
import sys
from urllib.request import urlopen

HOME = Path(__file__).resolve().parent
sys.path.insert(0, str(HOME.parent))
from common import HERE, REPO, MAP, save, sha
from preservation import verify as preserve


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def run():
    replay = HOME / 'replays/pilot-003-002'
    inputs = read(replay / 'inputs.json')
    build = read(replay / 'build.json')
    checks = {}
    counts = {}
    for name, audit in [('live-002', 'live-audit-004'), ('live-003', 'live-audit-005'),
                        ('pilot-003', 'pilot-audit-003')]:
        episode = HERE / 'live-evidence' / ('RCI001-C03-' + name + '-attempt')
        identities = read(HERE / 'qualification' / audit / 'assessment/input-identities.json')
        assert all(sha(episode / path) == value['sha256']
                   and (episode / path).stat().st_size == value['bytes']
                   for path, value in identities.items())
        counts[name] = len(identities)
    checks['all_three_original_completed_attempt_inventories_unchanged'] = True
    failed = HERE / 'live-evidence/RCI001-C03-pilot-002-attempt'
    identities = read(HERE / 'qualification/pilot-audit-002/assessment/input-identities.json')
    change = read(HERE / 'retirement-revision-001/postmortem-windows-change.json')['changed']
    assert set(change) == {'workspace-block/fuse-server.log'}
    for path, value in identities.items():
        expected = change[path]['after'] if path in change else value
        assert sha(failed / path) == expected['sha256']
    counts['pilot-002-original-files-with-explicit-postmortem-log-exception'] = len(identities)
    checks['invalid_pilot_known_cleanup_delta_only'] = True
    for path, value in build['outputs'].items():
        assert sha(replay / path) == value['sha256'] and (replay / path).stat().st_size == value['bytes']
    checks['derived_replay_bytes_unchanged_after_browser_qa'] = True
    links = {}
    for name in ('verification.json', 'inputs.json', 'build.json'):
        with urlopen('http://127.0.0.1:8920/' + name, timeout=10) as response:
            raw = response.read()
            assert response.status == 200 and raw == (replay / name).read_bytes()
            links[name] = {'status': 200, 'sha256': sha(replay / name)}
    checks['three_actual_browser_link_targets_exact'] = True
    captures = {}
    for name, expected in [('browser-desktop.jpg', (1280, 900)), ('browser-mobile.jpg', (390, 844))]:
        path = replay / name
        raw=path.read_bytes()
        assert raw.startswith(b'\xff\xd8') and raw.endswith(b'\xff\xd9')
        offset=2;size=None
        while offset < len(raw):
            assert raw[offset] == 255
            while raw[offset] == 255:offset += 1
            marker=raw[offset];offset += 1
            if marker in (0xD9,0xDA):break
            length=struct.unpack('>H',raw[offset:offset+2])[0]
            assert length >= 2 and offset+length <= len(raw)
            if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
                precision,height,width=struct.unpack('>BHH',raw[offset+2:offset+7])
                size=(width,height);break
            offset += length
        assert size == expected,(name,size,expected)
        copy = HOME / 'artifacts/pilot-003' / name
        assert sha(copy) == sha(path)
        captures[name] = {'sha256': sha(path), 'bytes': path.stat().st_size, 'size': list(expected)}
    checks['exact_browser_capture_bytes_and_dimensions'] = True
    snapshot = read(MAP / 'releases/RCI001-C03-live/RCI001-C03-pilot-003/snapshot.json')
    for group in ('source', 'inherited'):
        assert all(sha(REPO / name) == value['sha256'] for name, value in snapshot[group].items())
    checks['qualified_experiment_sources_still_exact'] = True
    preserve(HERE / 'preservation-baseline.json', HOME / 'final-historical-preservation.json')
    assert read(HOME / 'final-historical-preservation.json')['passed']
    checks['historical_campaigns_and_original_attempts_unchanged'] = True
    save(HOME / 'final-review-check.json', dict(passed=True, checks=checks, model_calls=0,
         source_sha256=sha(__file__), inventories=counts, links=links, browser_captures=captures,
         free_C_bytes=shutil.disk_usage(HOME).free, free_D_bytes=shutil.disk_usage('D:/').free,
         original_pilot_002_validity='invalid', new_pilot_003_task_outcome='failure',
         scored_model_calls=0, qualification_complete=False))
    print(json.dumps({'passed': True, 'checks': checks, 'inventories': counts}), flush=True)


if __name__ == '__main__':
    run()
