"""Single-use preparation/freeze/launch journals for the declared diagnostic."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
MAP = RCI.parent / 'Architecture Map'
RUN = 'RCI001-C02-shutdown-diagnostic-002'
REV = 'RCI001-C02-dev-062'
MANIFEST = HERE / 'shutdown-diagnostic-002/manifest.json'
SNAPSHOT = MAP / 'releases' / REV / 'snapshot.json'
JOURNAL = HERE / 'shutdown-diagnostic-control-002'
spec = importlib.util.spec_from_file_location('shutdown_diagnostic_journal', CAMPAIGN / 'qualification/run_final_qualification_v21.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'freeze', 'launch'])
    args = parser.parse_args()
    JOURNAL.mkdir(exist_ok=True)
    if args.action == 'prepare':
        receipt = c.command_once(JOURNAL, 'prepare', c.python(HERE / 'prepare_reset_diagnostic.py'),
            inputs=[HERE / 'RESET_REJECTION_DIAGNOSTIC_V1.md'],
            outputs=[MANIFEST, MANIFEST.with_name('preparation-receipt.json')], absent=[MANIFEST.parent])
    elif args.action == 'freeze':
        receipt = c.command_once(JOURNAL, 'freeze', c.python(CAMPAIGN / 'registry.py', 'freeze',
            '--manifest', MANIFEST, '--revision', REV), inputs=[MANIFEST],
            outputs=[SNAPSHOT, SNAPSHOT.with_name('code.zip')], absent=[SNAPSHOT.parent])
        previous = c.read(MAP / 'releases/RCI001-C02-dev-061/snapshot.json')['sources']
        current = c.read(SNAPSHOT)['sources']
        changed = sorted(name for name in previous if current.get(name, {}).get('sha256') != previous[name]['sha256'])
        allowed = {str((CAMPAIGN / 'harness' / name).relative_to(c.REPO)).replace('\\', '/') for name in (
            'codehost_mux_protocol.py', 'test_codehost_mux_protocol.py')}
        if not set(changed) <= allowed or not changed:
            raise ValueError('Unexpected diagnostic source changes: ' + repr(changed))
        c.save_exact(JOURNAL / 'source-change-inventory.json', {
            'schema': 'campaign002-shutdown-diagnostic-source-inventory-1',
            'before': c.identity(MAP / 'releases/RCI001-C02-dev-061/snapshot.json'),
            'after': c.identity(SNAPSHOT), 'changed_existing_sources': changed,
            'added_sources': sorted(set(current) - set(previous)),
            'removed_sources': sorted(set(previous) - set(current)),
            'diagnostic_only': True,
        })
    else:
        inventory = c.read(JOURNAL / 'source-change-inventory.json')
        c.admission.artifact(inventory['after'])
        tests = c.read(HERE / 'checks-022/repair-test-receipt.json')
        if tests.get('passed') is not True or tests.get('source_snapshot') != c.identity(SNAPSHOT):
            raise ValueError('Bound diagnostic checks missing')
        receipt = c.command_once(JOURNAL, 'launch', c.python(HERE / 'single-interrupt-diagnostic-v2/launch.py',
            '--manifest', MANIFEST, '--snapshot', SNAPSHOT), inputs=[MANIFEST, SNAPSHOT,
                HERE / 'checks-022/repair-test-receipt.json', JOURNAL / 'source-change-inventory.json'],
            outputs=[MANIFEST.parent / 'records/queue-submit.json'],
            absent=[MANIFEST.parent / 'records', RCI / 'local-evidence/campaign002/io-repair' / RUN])
    print(json.dumps({'action': args.action, 'exit_code': receipt['exit_code'], 'stdout': receipt['stdout']}))


if __name__ == '__main__':
    main()
