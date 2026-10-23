"""Independent retained GC/memory-policy verification; no host-policy imports."""
import hashlib
import math
from pathlib import Path
import struct

REPO = Path(__file__).resolve().parents[4]
CAMPAIGN = Path(__file__).resolve().parents[1]
HARD = 2 * 1024**3
BASELINE = 1024**3
SOFT = 1536 * 1024**2
GROWTH = 512 * 1024**2
MEMORY_FIELDS = ['wall_read_start_s', 'wall_read_end_s', 'private_commit_bytes', 'working_set_bytes',
                 'peak_private_commit_bytes', 'peak_working_set_bytes', 'kind']
GC_FIELDS = ['wall_start_s', 'wall_end_s', 'thread_cpu_duration_s', 'process_cpu_duration_s',
             'generation', 'collected', 'uncollectable', 'collecting_native_thread_id',
             'on_host_thread', 'host_phase_code', 'sim_start_s', 'sim_end_s']


def require(value, message):
    if value is not True:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def ledger(root, binding, schema, name, fields, count_key, capacity_key, minimum):
    require(isinstance(binding, dict) and binding.get('schema') == schema
            and binding.get('sample_file') == name and binding.get('fields') == fields
            and binding.get('encoding') == 'little-endian float64 rows', 'Resource ledger schema or encoding differs: ' + name)
    count, capacity = binding.get(count_key), binding.get(capacity_key)
    require(integer(count, minimum) and integer(capacity, max(1, minimum)) and count <= capacity,
            'Resource ledger count or capacity differs: ' + name)
    path = Path(root) / name
    require(path.is_file() and not path.is_symlink(), 'Protected resource ledger must be an ordinary file: ' + name)
    require(integer(binding.get('byte_count')) and path.stat().st_size == binding['byte_count'] == count * len(fields) * 8,
            'Resource ledger byte count differs: ' + name)
    raw = path.read_bytes()
    require(digest(raw) == binding.get('sha256'), 'Resource ledger hash differs: ' + name)
    rows = list(struct.iter_unpack('<' + 'd' * len(fields), raw))
    require(all(all(finite(value) for value in row) for row in rows), 'Nonfinite resource ledger sample: ' + name)
    return rows


def source_bindings(frozen):
    paths = [CAMPAIGN / 'harness' / name for name in ('gc_diagnostics.py', 'memory_guard.py', 'timing.py', 'run_host.py')]
    paths.append(Path(__file__).resolve())
    result = {}
    for path in paths:
        raw = path.read_bytes()
        name = path.relative_to(REPO).as_posix()
        expected = {'sha256': digest(raw), 'bytes': len(raw)}
        require(frozen.get('sources', {}).get(name) == expected, 'Resource policy or verifier source differs from freeze: ' + name)
        result[name] = expected
    return result


def config(value):
    require(isinstance(value, dict) and type(value.get('enabled')) is bool
            and isinstance(value.get('thresholds'), list) and len(value['thresholds']) == 3
            and all(integer(item) for item in value['thresholds'])
            and integer(value.get('debug_flags')) and integer(value.get('freeze_count')),
            'GC configuration evidence malformed')
    return {key: value[key] for key in ('enabled', 'thresholds', 'debug_flags', 'freeze_count')}


def verify_gc(root, binding, terminal):
    rows = ledger(root, binding, 'rci-gc-diagnostics-2', 'gc-collections.bin', GC_FIELDS,
                  'collection_count', 'maximum_collection_capacity', 0)
    policy = binding.get('policy', {})
    require(binding.get('passed') is True and binding.get('error') is None
            and binding.get('overflow') == 0 and type(binding.get('overflow')) is int
            and binding.get('policy_unchanged') is False
            and binding.get('measured_terminal_wall_elapsed_s') == terminal
            and binding.get('measured_interval_collection_count') == 0
            and type(binding.get('measured_interval_collection_count')) is int
            and policy.get('name') == 'bounded-automatic-cyclic-gc-deferral-1'
            and policy.get('restoration_attempted') is True and policy.get('configuration_restored') is True
            and policy.get('error') is None and policy.get('restore_errors') == []
            and integer(policy.get('verification_count'), 1)
            and integer(policy.get('full_configuration_verification_count'), 1)
            and policy['full_configuration_verification_count'] <= policy['verification_count']
            and type(policy.get('unexpected_collection_count')) is int and policy['unexpected_collection_count'] == 0,
            'GC deferral or restoration failed or was not verified')
    initial, final = binding.get('initial', {}), binding.get('final', {})
    require(config(initial) == config(final) == config(policy.get('restored_configuration')),
            'Original GC configuration was not restored exactly')
    require(integer(initial.get('callback_count')) and final.get('callback_count') == initial['callback_count'],
            'GC observer callback retirement differs')
    for value in (initial, final):
        require(isinstance(value.get('counts'), list) and len(value['counts']) == 3
                and all(integer(item) for item in value['counts'])
                and isinstance(value.get('statistics'), list) and len(value['statistics']) == 3
                and all(all(integer(row.get(key)) for key in ('collections', 'collected', 'uncollectable'))
                        for row in value['statistics']), 'GC count/statistic evidence malformed')
    require(all(after[key] >= before[key] for before, after in zip(initial['statistics'], final['statistics'])
                for key in ('collections', 'collected', 'uncollectable')), 'GC lifetime statistics moved backwards')
    bounds = [binding.get('attached_wall_elapsed_s'), policy.get('disable_start_wall_elapsed_s'),
              policy.get('disable_end_wall_elapsed_s'), 0., terminal,
              policy.get('restore_start_wall_elapsed_s'), policy.get('restore_end_wall_elapsed_s'),
              binding.get('detached_wall_elapsed_s')]
    require(all(finite(value) for value in bounds) and all(a <= b for a, b in zip(bounds, bounds[1:])),
            'GC policy/observer boundaries do not enclose the measured interval')
    mutations = binding.get('collector_policy_mutations', [])
    operations = ['disable_automatic_gc', 'restore_thresholds', 'restore_debug_flags', 'restore_enabled_state']
    require(isinstance(mutations, list) and [row.get('operation') for row in mutations] == operations
            and all(finite(row.get('wall_elapsed_s')) for row in mutations), 'GC policy mutation sequence differs')
    times = [row['wall_elapsed_s'] for row in mutations]
    require(bounds[1] <= times[0] <= bounds[2] and all(bounds[5] <= value <= bounds[6] for value in times[1:])
            and all(a <= b for a, b in zip(times, times[1:])), 'GC policy mutation clocks differ from boundaries')
    names = binding.get('phase_names', {})
    require(isinstance(names, dict) and 1 <= len(names) <= 129 and names.get('0', False) is None
            and integer(binding.get('host_native_thread_id'), 1), 'GC phase/thread identity malformed')
    previous = None
    for row in rows:
        start, end = row[:2]
        require(bounds[0] <= start <= end <= bounds[-1] and (previous is None or start >= previous),
                'GC callback intervals exceed observer bounds or overlap')
        require(not (start < terminal and end > 0), 'GC collection overlaps the measured physics interval')
        require(all(value >= 0 for value in row[2:10]) and all(value == int(value) for value in row[4:10])
                and row[4] in (0., 1., 2.) and row[7] > 0 and row[8] in (0., 1.)
                and row[8] == int(row[7] == binding['host_native_thread_id'])
                and str(int(row[9])) in names and row[11] >= row[10], 'GC callback counters or thread attribution differ')
        previous = end
    return {'passed': True, 'schema': 'rci-independent-gc-policy-1',
            'sample_sha256': binding['sha256'], 'collection_count': len(rows),
            'measured_interval_collection_count': 0, 'configuration_restored': True,
            'policy': policy, 'observer_bounds_s': [bounds[0], bounds[-1]],
            'outside_loop_collection_wall_s': sum(row[1] - row[0] for row in rows)}


def memory_counters(value):
    keys = MEMORY_FIELDS[2:6]
    require(all(integer(value.get(key)) for key in keys)
            and value['private_commit_bytes'] <= value['peak_private_commit_bytes'] <= HARD
            and value['working_set_bytes'] <= value['peak_working_set_bytes'], 'Native memory counters malformed or exceed hard ceiling')


def verify_memory(root, binding, origin, terminal, native_job):
    rows = ledger(root, binding, 'rci-host-memory-1', 'memory-samples.bin', MEMORY_FIELDS,
                  'sample_count', 'maximum_sample_capacity', 2)
    require(binding.get('kind_codes') == {'periodic': 0, 'origin': 1, 'terminal': 2}
            and binding.get('sampling_interval_s') == .1 and binding.get('maximum_permitted_sample_gap_s') == .2
            and binding.get('baseline_private_commit_limit_bytes') == BASELINE
            and binding.get('soft_absolute_limit_bytes') == SOFT and binding.get('soft_growth_limit_bytes') == GROWTH
            and binding.get('loop_origin_qpc_s') == origin and binding.get('terminal_wall_elapsed_s') == terminal
            and binding.get('complete') is True and binding.get('passed') is True and binding.get('error') is None,
            'Host memory policy, common origin or complete evidence differs')
    baseline = binding.get('baseline', {})
    memory_counters(baseline)
    require(finite(baseline.get('read_start_qpc_s')) and finite(baseline.get('read_end_qpc_s'))
            and baseline['read_start_qpc_s'] <= baseline['read_end_qpc_s'] <= origin
            and baseline['private_commit_bytes'] < BASELINE
            and binding.get('soft_limit_bytes') == min(SOFT, baseline['private_commit_bytes'] + GROWTH),
            'Host memory baseline or derived soft ceiling differs')
    job = binding.get('native_job', {})
    require(job == native_job and job.get('schema') == 'rci-host-memory-1' and job.get('platform') == 'win32'
            and integer(job.get('pid'), 1) and job.get('hard_process_commit_limit_bytes') == HARD
            and job.get('applied') is True and job.get('final_readback_verified') is True
            and job.get('handle_closed') is True and job.get('membership_detached') is False,
            'Native host JobObject application/readback/closure receipt differs')
    for record in (job.get('initial_readback', {}), job.get('final_readback', {})):
        require(record.get('process_is_member') is True and record.get('limit_flags') == 0x100
                and record.get('process_memory_limit_bytes') == HARD
                and record.get('assigned_process_count') == record.get('listed_process_count') == 1
                and record.get('process_ids') == [job['pid']]
                and record.get('returned_structure_bytes') == record.get('expected_structure_bytes') == 144
                and all(integer(record.get(key)) and record[key] <= HARD for key in
                        ('peak_process_memory_used_bytes', 'peak_job_memory_used_bytes')),
                'Native host JobObject hard limit or membership readback differs')
    require(all(job['final_readback'][key] >= job['initial_readback'][key] for key in
                ('peak_process_memory_used_bytes', 'peak_job_memory_used_bytes')), 'Native JobObject peaks moved backwards')
    cleanup = job.get('post_cleanup_memory', {})
    memory_counters(cleanup)
    require(finite(cleanup.get('read_start_qpc_s')) and finite(cleanup.get('read_end_qpc_s'))
            and origin + terminal <= cleanup['read_start_qpc_s'] <= cleanup['read_end_qpc_s'],
            'Native memory cleanup read predates terminal boundary')
    previous, maximum_gap = None, 0.
    for index, row in enumerate(rows):
        start, end, private, working, peak_private, peak_working, kind = row
        expected_kind = 1. if index == 0 else 2. if index == len(rows) - 1 else 0.
        require(0 <= start <= end <= terminal and kind == expected_kind,
                'Memory ledger read or origin/terminal marker lies outside measured interval')
        require(all(value >= 0 and value == int(value) for value in row[2:6])
                and private < binding['soft_limit_bytes'] and private <= peak_private <= HARD
                and working <= peak_working, 'Memory ledger reached a ceiling or contains malformed counters')
        if previous is not None:
            require(start >= previous[1] and peak_private >= previous[4] and peak_working >= previous[5],
                    'Memory read chronology or lifetime peak moved backwards')
            maximum_gap = max(maximum_gap, end - previous[1])
        else:
            maximum_gap = max(maximum_gap, end)
        previous = row
    maximum_gap = max(maximum_gap, terminal - rows[-1][1])
    require(maximum_gap <= .2, 'Memory sampling coverage exceeds declared maximum gap')
    return {'passed': True, 'schema': 'rci-independent-host-memory-1', 'sample_sha256': binding['sha256'],
            'sample_count': len(rows), 'maximum_sample_gap_s': maximum_gap,
            'baseline_private_commit_bytes': baseline['private_commit_bytes'], 'soft_limit_bytes': binding['soft_limit_bytes'],
            'maximum_observed_private_commit_bytes': max(row[2] for row in rows),
            'hard_process_commit_limit_bytes': HARD, 'native_job': job}


def verify_resources(root, metadata, host_result, frozen):
    sources = source_bindings(frozen)
    terminal = metadata['terminal']['wall_elapsed_s']
    origin = metadata['loop_origin']['monotonic_s']
    gc = verify_gc(root, metadata.get('garbage_collection'), terminal)
    memory = verify_memory(root, metadata.get('host_memory'), origin, terminal, host_result.get('native_memory_job'))
    return {'resource_integrity_pass': True, 'garbage_collection_pass': True, 'host_memory_pass': True,
            'garbage_collection': gc, 'host_memory': memory, 'resource_source_bindings': sources}
