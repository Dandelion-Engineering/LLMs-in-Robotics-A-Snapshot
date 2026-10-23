"""Prevent unrelated host endpoints or earlier socket reuse entering the report."""
import copy
import hashlib
import json
from pathlib import Path
import collect_assess as a


def main():
    endpoint = {'channel_id': 1, 'client': ['127.0.0.1', 40000],
                'server': ['127.0.0.1', 50000], 'owner_pid': 77, 'monotonic_s': 2.0}
    event = {'id': 1040, 'perf_counter_ns': 3_000_000_000, 'fields': {
        'ProcessId': 0, 'LocalAddress': {'ip': '127.0.0.1', 'port': 40000},
        'RemoteAddress': {'ip': '127.0.0.1', 'port': 50000}}}
    native = copy.deepcopy(event)
    reversed_pair = copy.deepcopy(event)
    reversed_pair['fields']['LocalAddress'], reversed_pair['fields']['RemoteAddress'] = (
        reversed_pair['fields']['RemoteAddress'], reversed_pair['fields']['LocalAddress'])
    same_port_other_ip = copy.deepcopy(event)
    same_port_other_ip['fields']['RemoteAddress']['ip'] = '192.0.2.1'
    neighbor_port = copy.deepcopy(event)
    neighbor_port['fields']['LocalAddress']['port'] += 1
    stale = copy.deepcopy(event)
    stale['perf_counter_ns'] = 1_999_999_999
    cases = {'native_pid0': (native, True), 'reverse_pair': (reversed_pair, True),
             'nonloopback_same_ports': (same_port_other_ip, False),
             'neighbor_socket': (neighbor_port, False), 'prior_port_reuse': (stale, False)}
    checks = {}
    for name, (value, expected) in cases.items():
        before = copy.deepcopy(value)
        selected = a.select_native_events([value], [endpoint])
        checks[name] = bool(selected) is expected and value == before
        if selected:
            checks[name] &= selected[0]['matched_channels'] == [1]
    assert all(checks.values()), checks
    a.save(a.HERE / 'projection-tests.json', {
        'synthetic_only': True, 'checks': checks,
        'sources': [a.binding(Path(__file__)), a.binding(a.HERE / 'collect_assess.py')],
        'empirical_reads': 0})
    print(json.dumps(checks))


if __name__ == '__main__':
    main()
