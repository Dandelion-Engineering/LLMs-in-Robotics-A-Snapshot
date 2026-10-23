"""Factual Maps session/assignment closeout; no Baseline-versus-Maps analysis."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.util
from pathlib import Path

from launch_maps import HERE, CODE, PAIR, OP, queue, succeeded
from common import canonical, read, save, sha
from audit import chain


def main(expect):
    out = OP / ('terminal-' + expect + '-001')
    status = queue('status', read(out / 'audit-queue.json')['id'])
    succeeded(status)
    save(out / 'audit-terminal-queue.json', status)
    audit = read(out / 'output/result.json')
    assert audit['passed'] is True and len(audit['checks']) == 5 and all(v is True for v in audit['checks'].values())
    validation = read(OP / 'reader-validation.json')
    assert validation['passed'] is True and validation['reader_sha256'] == sha(HERE / 'audit_maps_terminal.py')
    lineage = read(PAIR / 'maps-lineage.json')
    assert not lineage['history'], 'Recovery requires explicit lineage-aware accounting of all original and abandoned starts'
    root = Path(lineage['active_root']).resolve()
    assert root == (PAIR / 'maps').resolve()
    checkpoint = Path(read(root / 'latest-checkpoint.json')['path'])
    state = read(checkpoint / 'state.json')
    events = chain(root / 'events.jsonl')
    spec = importlib.util.spec_from_file_location('retained_lifecycle', CODE / 'operations/session-34/summarize_endpoint.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    counted = module.lifecycle(events)
    accounting = audit['evidence']['accounting']
    assert counted['starts'] == counted['normal_closures'] == state['sessions'] == accounting['total_started_sessions']
    assert counted['unclosed_starts'] == accounting['abandoned_started_sessions'] == 0
    advanced = [r for r in counted['assignments'] if r['advancing_session'] is not None]
    assert len(advanced) == state['position'] == accounting['assignments']
    for row, complete in zip(advanced, state['completed']):
        assert (row['position'], row['task'], row['advancing_session'], row['advancement_sim_time']) == (complete['position'], complete['kind'], complete['session'], complete['sim_time'])
    natives = [read(p / 'native/client/result.json') for p in sorted((root / 'sessions').iterdir())]
    assert len(natives) == len({r['thread_id'] for r in natives}) == counted['starts']
    assert all(r['success'] is True and r['turn_status'] == 'completed' for r in natives)
    complete = expect == 'completed'
    assert (state['position'] == 21) is complete
    counts = Counter(r['kind'] for r in events)
    household = sum(r['task'] != 'throwing' for r in advanced)
    throwing = sum(r['task'] == 'throwing' for r in advanced)
    assert household == counts['task_success']
    result = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), passed=True, condition='maps',
                  status=expect, endpoint_complete=complete, endpoint_session_count=counted['starts'] if complete else None,
                  total_started_sessions=counted['starts'], normal_closed_sessions=counted['normal_closures'],
                  abandoned_started_sessions=0, failed_native_turns=0, recovery_branches=0,
                  assignments_completed=state['position'], assignments_total=21, household_successes=household,
                  throwing_windows_completed=throwing, accepted_native_turns=len(natives),
                  checkpoint=str(checkpoint), checkpoint_manifest_sha256=sha(checkpoint / 'manifest.json'),
                  checkpoint_state_sha256=sha(checkpoint / 'state.json'), simulation_time=state['world']['sim_time'],
                  official_queue=read(out / 'official-queue.json'), audit_queue=status,
                  assignment_table=counted['assignments'], physical_event_counts=dict(counts),
                  scientific_comparison_performed=False, secondary_behavioral_analysis_performed=False,
                  limitations=['One dependent Maps history; no independent repetitions.',
                               'Completed throwing windows do not establish throwing mastery.',
                               'Scientific Baseline-versus-Maps comparison is deferred by human instruction.'],
                  evidence={str(p): sha(p) for p in (out / 'output/result.json', OP / 'reader-validation.json', root / 'events.jsonl', OP / 'launch-receipt.json')})
    save(out / 'verified-terminal.json', result)
    save(HERE / ('endpoint.json' if complete else 'hibernation.json'), result)
    print(canonical({k: result[k] for k in ('passed', 'status', 'endpoint_complete', 'endpoint_session_count', 'total_started_sessions', 'assignments_completed', 'household_successes', 'throwing_windows_completed', 'checkpoint_manifest_sha256')}).decode())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--expect', choices=('completed', 'hibernated'), required=True)
    main(parser.parse_args().expect)
