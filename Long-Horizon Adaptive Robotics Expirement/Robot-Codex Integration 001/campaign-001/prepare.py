"""Seal a pre-outcome attempt schedule. This tool cannot launch a model or admit a campaign."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parent
EXPERIMENT = INTEGRATION.parent
REPO = EXPERIMENT.parent
SNAPSHOT = EXPERIMENT / 'Architecture Map/releases/RCI001-wsl-010d/snapshot.json'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    mismatches = [name for name, entry in source['sources'].items()
                  if not (REPO / name).is_file() or sha(REPO / name) != entry['sha256']]
    if mismatches:
        raise SystemExit('Frozen framework changed: ' + repr(mismatches))
    spec = importlib.util.spec_from_file_location('campaign_challenges', INTEGRATION / 'host/challenges.py')
    challenges = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(challenges)
    args.output.mkdir(parents=True, exist_ok=False)
    slots = []
    for pair in range(1, 13):
        families = ['misplaced-stock', 'blocked-insert-home']
        if pair % 2 == 0:
            families.reverse()
        for family in families:
            ordinal = len(slots) + 1
            code = 'stock' if family == 'misplaced-stock' else 'home'
            run_id = f'RCI001-C01-{code}-{pair:02d}'
            manifest = challenges.make_manifest(family, 'serve', run_id)
            manifest.update(seed=173, noise_seed=22000 + ordinal, sim_cap_s=900,
                            wall_cap_s=1100, storage_cap_bytes=512 * 1024 * 1024)
            manifest.update(model='gpt-6-astra', effort='max',
                            bootstrap='Follow the instructions in RobotAgentPrompt.md.',
                            model_turns_max=1, invocation_wall_cap_s=600,
                            action_request_budget=20, observation_request_budget=50,
                            interruption_trigger=None, prior_attempt=None,
                            outer_campaign_protocol='RCI001-Campaign001-plan-v1',
                            scoring_scope='Prospective repeated fixed development fixtures; no held-out family or layout claim',
                            host_stage_label_preserved=True)
            manifest['runtime_workspace'] = str(Path(os.environ['LOCALAPPDATA']) / 'RobotCodex' / 'Campaign001' / run_id)
            challenges.validate_manifest(manifest)
            path = args.output / (run_id + '.json')
            write_new(path, manifest)
            slots.append({'ordinal': ordinal, 'run_id': run_id, 'family': family,
                          'within_family_replicate': pair, 'world_seed': 173,
                          'noise_seed': manifest['noise_seed'], 'manifest': path.name,
                          'runtime_workspace': manifest['runtime_workspace'],
                          'sha256': sha(path), 'maximum_model_invocations': 1})
    protocol = {
        'schema': 'robot-codex-campaign-plan-1',
        'id': 'RCI001-Campaign001-plan-v1',
        'prepared_at': datetime.now(timezone.utc).isoformat(),
        'source_revision': 'RCI001-wsl-010d',
        'source_snapshot_sha256': sha(SNAPSHOT),
        'frozen_sources_verified': len(source['sources']),
        'plan_sha256': sha(HERE / 'PLAN.md'),
        'prepare_source_sha256': sha(Path(__file__)),
        'attempt_count': 24,
        'replacements_allowed': 0,
        'model_calls_started': 0,
        'admission_granted': False,
        'admission_reason': 'Preparation only; capacity, complete timing and campaign release/accounting gates remain separate.',
        'seeds_access': 'operator_only; never mounted inside Robot-Codex',
        'runtime_manifest_stage': 'development-only (unchanged required host schema)',
        'estimand': 'Repeatability on two fixed development-qualified fixtures, with fresh sensor seeds and model invocations',
        'per_attempt_reservation_bytes': 1073741824,
        'permanent_reservation_bytes': 24 * 1073741824 + 3000000000,
        'peak_projection_bytes': int((24 * 1073741824 + 3000000000) * 1.25) + 2000000000,
        'slots': slots,
    }
    write_new(args.output / 'schedule.json', protocol)
    print(json.dumps({'prepared': len(slots), 'sources_verified': len(source['sources']),
                      'schedule_sha256': sha(args.output / 'schedule.json'), 'admission_granted': False}))

if __name__ == '__main__':
    main()
