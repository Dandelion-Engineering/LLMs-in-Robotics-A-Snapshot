"""Create immutable external admission certificate from verified local evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CAMP = HERE.parent
RCI = CAMP.parent
EXP = RCI.parent
REPO = EXP.parent
sys.path.insert(0, str(CAMP / 'assessment'))
import admitted

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def item(path):
    path = path.resolve()
    return {'path': str(path), 'sha256': digest(path)}

def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')

def main():
    output = HERE / 'sealed-v3'
    if output.exists():
        raise FileExistsError('Preserve existing seal; use a separately authorized pre-outcome generation')
    release = EXP / 'Architecture Map/releases/RCI001-wsl-010d'
    paths = {
        'protocol': HERE / 'PROTOCOL-v2.md', 'original_plan': CAMP / 'PLAN.md',
        'schedule': CAMP / 'predeclared-v1/schedule.json', 'snapshot': release / 'snapshot.json',
        'archive': release / 'code.zip', 'assessor': CAMP / 'assessment/assess.py',
        'admitted_assessor': CAMP / 'assessment/admitted.py',
        'timing_source': EXP / 'Runtime 004/experiment.py',
        'approval': HERE / 'storage-approval-session12.md',
        'storage_monitor': HERE / 'storage-guard/storage_guard.py',
        'storage_policy': HERE / 'storage-guard/policy.json',
        'storage_tests': HERE / 'storage-guard/qualification.json',
        'preflight_capacity': HERE / 'storage-guard/baseline-001.json',
        'retained_timing': HERE / 'census-002/retained-timing.json',
        'retained_timing_queue': HERE / 'census-002/queue-receipt.json',
        'existing_capacity': HERE / 'census-002/capacity.json',
        'asset_refresh': HERE / 'asset-refresh-session12.json', 'asset_verifier': HERE / 'verify_assets.py',
        'operator_source': CAMP / 'operate.py', 'registration_source': CAMP / 'registration/register.py',
        'execution_plan': CAMP / 'execution-plan.json', 'seal_source': Path(__file__),
    }
    cert = {'schema': 'rci-campaign-scientific-admission-1', 'campaign_id': 'RCI001-Campaign001',
            'created_at': datetime.now(timezone.utc).isoformat(), 'framework_revision': 'RCI001-wsl-010d',
            'release_revision': 'RCI001-C01-frozen-001', 'source_count': 624,
            'artifacts': {key: item(path) for key, path in paths.items()},
            'timing': dict(admitted.TIMING),
            'storage': {'free_reserve_bytes': 100_000_000_000, 'planning_peak_bytes': 37_962_254_720,
                        'planning_allowance_is_hard_limit': False},
            'conditions': {'maximum_attempts': 24, 'no_replacements': True, 'no_injected_restart': True, 'no_tuning': True},
            'attempts': json.loads((CAMP / 'execution-plan.json').read_text())['attempts']}
    cert['supersedes_pre_outcome_certificate'] = item(HERE / 'sealed-v2/certificate.json')
    cert['supersession_reason'] = 'Final registration-helper hardening overlapped the first seal; registration correctly refused before any canonical map change or model launch. This seal binds the completed helper and unchanged protocol, allocation and framework. The earlier seal is retained.'
    with tempfile.TemporaryDirectory(prefix='rci-campaign-seal-check-') as directory:
        temporary = Path(directory) / 'certificate.json'
        write(temporary, cert)
        admitted.verify_certificate(temporary, digest(temporary))
    output.mkdir()
    certificate_path = output / 'certificate.json'
    write(certificate_path, cert)
    certificate_sha256 = digest(certificate_path)
    admitted.verify_certificate(certificate_path, certificate_sha256)
    write(output / 'seal.json', {'schema': 'rci-campaign-seal-1', 'certificate_sha256': certificate_sha256,
          'verified_at': datetime.now(timezone.utc).isoformat(), 'attempt_count': len(cert['attempts']),
          'source_count': cert['source_count'], 'model_calls_before_seal': 0,
          'verification': 'Independent admitted consumer reproduced retained timing, verified identities, storage qualification, fresh preflight and fixed allocation. Canonical map registration must follow before launch.'})
    print(json.dumps({'certificate': str(certificate_path), 'sha256': certificate_sha256, 'attempts': 24}))

if __name__ == '__main__':
    main()
