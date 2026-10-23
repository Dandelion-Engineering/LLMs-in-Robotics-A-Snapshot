"""Queued, read-only integration check after explicit administrative adoption."""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import shutil
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
ROOT = EXPERIMENT.parent
sys.path.insert(0, str(EXPERIMENT / 'Runtime Recovery 001'))
import recovery_runner as runner
import recovery_contract as contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annex', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    job = runner.queued_job(Path(__file__).resolve())
    output = args.output.resolve()
    contract.require(not output.exists(), 'Readiness output must be fresh')
    output.mkdir(parents=True)
    source = contract.ref(Path(__file__))
    verified = runner.verify_recovery(args.annex)
    checked = verified['recovery']
    for disposition in checked['dispositions'].values():
        contract.verify_partial_inventory(disposition)
    runner.require_supervisor_hook()
    selected = runner.select_runs(verified, limit=4)
    untouched = [row for row in checked['annex']['remaining_originals']
                 if not (checked['root'] / 'attempts' / row['run_id']).exists()]
    contract.require(len(untouched) == 131, 'Adoption check requires the untouched initial partition')
    cap_seconds = sum(300 if int(row['run_id'].split('-C')[1][:2]) <= 8 else
                      600 if int(row['run_id'].split('-C')[1][:2]) <= 16 else 900
                      for row in untouched)
    required = math.ceil(cap_seconds * 3.189121856241325 * 1048576) + 53687091200
    free = shutil.disk_usage(ROOT).free
    contract.require(free >= required, 'Insufficient remaining capacity')
    module_path = EXPERIMENT / 'Batch 01' / 'Release Analysis 005' / 'collect_results.py'
    spec = importlib.util.spec_from_file_location('_adoption_collect005', module_path)
    collector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(collector)
    def rows(kind):
        return [json.loads(line) for line in (EXPERIMENT / 'Architecture Map' / (kind + 's.jsonl'))
                .read_text(encoding='utf-8').splitlines() if line.strip()]
    report = collector.collect(checked['root'], rows('result'), notes=rows('note'), annex_path=args.annex)
    counts = report['counts']
    contract.require(counts['original_finalized'] == 132 and counts['annex_finalized'] == 0
                     and counts['administrative_interruption'] == 1 and counts['missing_disposition'] == 131,
                     'Integrated administrative accounting differs')
    contract.require(contract.ref(Path(__file__)) == source, 'Readiness source changed')
    runner.original.write_once(output / 'readiness.json', {
        'schema_version': 'administrative-adoption-readiness-1',
        'recorded_at': runner.original.utc(), 'queue_job_id': job['id'], 'queued_argv': job['argv'],
        'source': source, 'annex': checked['annex_ref'], 'passed': True,
        'checks': {'adopted_authority': True, 'canonical_administrative_note': True,
                   'original_release_verified': True, 'partial_inventory_verified': True,
                   'actual_supervisor_hook': True, 'original_order_selection': True,
                   'analysis_projection': True, 'remaining_capacity': True},
        'counts': counts, 'next_run_ids': [row['run_id'] for row in selected],
        'remaining_cap_seconds': cap_seconds, 'required_bytes': required, 'free_bytes': free,
        'policy_episode_launched': False})
    print(json.dumps({'passed': True, 'counts': counts, 'next_run_ids': [row['run_id'] for row in selected]}))


if __name__ == '__main__':
    main()
