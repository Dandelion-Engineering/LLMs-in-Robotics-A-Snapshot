"""Append startup observation without assigning an official terminal result."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common import read
from register import append, base, ref

startup = read(HERE / 'startup-verification.json')
monitor = read(HERE / 'monitoring.json')
assert startup['passed'] and all(startup['checks'].values())
assert monitor['status'] == 'ACTIVE' and monitor['interval_minutes'] == 30
append('note', {
    **base('APARTMENT-v3-baseline-startup-s37'),
    'tags': ['apartment', 'official', 'baseline', 'startup-observation'],
    'target_ids': ['APARTMENT-v3-baseline', 'APARTMENT-v3-cup-physics-frozen'],
    'claim_type': 'observation', 'supersedes_note_id': None,
    'body': 'Following separate original-filesystem publication and complete new independent commissioning, the fresh matched v3 Baseline was launched once as queue job 20261009T010627656726Z-71e4ed51. All 12 startup checks passed, including actual native/tool/sensor-image activity, namespace canaries, advancing physics, replay capture, protected filesystem journal, and pristine Maps. The live viewer was visually verified. Read-only heartbeat observations are active every 30 minutes. This records verified startup only; the all-21-assignment endpoint, complete history and terminal retirement audit remain pending. No Maps launch or final condition comparison is authorized.',
    'evidence': [ref('Authenticated startup observation', HERE / 'startup-verification.json'),
                 ref('Retained scheduler and viewer configuration', HERE / 'monitoring.json'),
                 ref('Once-only launch queue receipt', HERE / 'official-queue-submission.json')]
}, HERE)
print('Registered APARTMENT-v3-baseline-startup-s37; no terminal result added.')
