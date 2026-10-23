"""Independent, terminal-only assessment of the one authorized pktmon attempt."""
import hashlib
import json
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent
SOURCE = Path(r'C:\Users\cresp\Documents\Campaign002 TCP Trace\coverage-managed-20260929-001')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    attempt = read(HERE / 'elevation-attempt-002.json')
    assert type(attempt['helperExitCode']) is int and attempt['helperExitCode'] == 0
    assert attempt['processExitedWithinFirst60Seconds'] is True
    receipt = read(SOURCE / 'receipt.json')
    fixture = read(SOURCE / 'fixture/result.json')
    commands = [read(p) for p in sorted(SOURCE.glob('command-*.json'))]
    text = (SOURCE / 'coverage.txt').read_text(encoding='utf-16')
    assert len(commands) == 18
    rows = [line for line in text.splitlines() if line.strip()]
    manifest_events = int(re.search(r'Manifest-based events\s+(\d+)', commands[15]['stdout']).group(1))
    checks = {
        'helper_terminal_integer_zero': True,
        'real_collection_completed': receipt['collection_completed'] and not receipt['simulated_commands'],
        'two_controls_passed': fixture['passed'] and [c['case'] for c in fixture['cases']] == ['graceful_fin', 'deliberate_rst'],
        'exact_port_both_filters': all(str(fixture['cases'][0]['server_port']) == commands[i]['argv'][-1] for i in (3,5)),
        'both_controls_within_capture_command_bracket': all(commands[8]['ended_perf_counter_ns'] < c['close_requested_perf_counter_ns'] <= c['server_observed_perf_counter_ns'] < commands[10]['started_perf_counter_ns'] for c in fixture['cases']),
        'prefix_40_bytes': commands[8]['argv'][commands[8]['argv'].index('--pkt-size') + 1] == '40',
        'file_limit_16_MiB': commands[8]['argv'][commands[8]['argv'].index('--file-size') + 1] == '16' and (SOURCE/'coverage.etl').stat().st_size <= 16*1024*1024,
        'capture_under_30_seconds': 0 < receipt['capture_elapsed_s_including_command_startup'] < 30,
        'reported_no_event_or_buffer_loss': 'No events lost' in commands[10]['stdout'] and 'EventsLost: 0' in text and 'BuffersLost: 0' in text,
        'fixture_retired': receipt['fixture_retirement']['qualified'] and receipt['fixture_retirement']['after_pids'] == [] and receipt['fixture_retirement']['retained_handles_signaled'],
        'owned_capture_stopped': receipt['capture_stopped'] and 'Packet Monitor is not running.' in commands[-1]['stdout'],
        'owned_filters_removed': commands[14]['stdout'].strip() == 'Packet Filters:\n    None',
        'os_fin_and_rst_coverage': False,
        'os_endpoint_and_clock_correlation': False,
    }
    assert manifest_events == 0 and len(rows) == 3
    assert all(checks[k] for k in checks if not k.startswith('os_'))
    copies = HERE/'evidence'
    copies.mkdir()
    bindings = []
    for path in sorted(SOURCE.rglob('*')):
        if path.is_file():
            relative = path.relative_to(SOURCE)
            target = copies/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(path.read_bytes())
            original = hashlib.sha256(path.read_bytes()).hexdigest()
            assert hashlib.sha256(target.read_bytes()).hexdigest() == original
            bindings.append({'source': str(path), 'copy': str(target.relative_to(HERE)), 'bytes': path.stat().st_size, 'sha256': original})
    result = {
        'kind': 'no-model infrastructure coverage; not scientific qualification',
        'collection_completed': True, 'coverage_adequate': False,
        'coverage_failure': 'No packet/provider events: only Header and two PartitionInfoExtensionV2 metadata rows. Neither control is observable in the OS trace.',
        'checks': checks, 'fixture': fixture, 'capture_elapsed_s': receipt['capture_elapsed_s_including_command_startup'],
        'etl_bytes': (SOURCE/'coverage.etl').stat().st_size, 'trace_rows': len(rows), 'manifest_based_events': manifest_events,
        'wrap_assessment': 'No wrap indication in this small metadata-only ETL; absence of packet events prevents complete measurement validation.',
        'source_bindings': bindings, 'model_calls': 0, 'scored_starts': 0,
        'next_step': 'Separate prospective event-trace scope; no unchanged pktmon repetition and no native/scored launch from this result.'
    }
    with (HERE/'assessment-001.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_bindings','fixture')},indent=2))


if __name__ == '__main__':
    main()
