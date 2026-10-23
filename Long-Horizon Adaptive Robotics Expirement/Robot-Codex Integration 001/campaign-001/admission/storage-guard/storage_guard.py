"""External Campaign001 metadata accounting; never launches or changes a queued run."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

SCHEMA = 'campaign001-storage-guard-1'
TERMINAL = {'succeeded', 'failed', 'canceled', 'interrupted', 'worker_start_failed'}


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.pending-' + uuid.uuid4().hex)
    with tmp.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def scan(roots, free_paths):
    """Only lstat/scandir/disk_usage: no watched file contents or symlink targets."""
    identities = {}
    path_count = 0
    path_bytes = 0
    link_count = 0
    special_count = 0
    vanished_count = 0
    seen_paths = set()
    missing_roots = []
    for item in roots:
        root = Path(item['path'])
        if not root.is_absolute():
            raise ValueError('Accounting root must be absolute')
        stack = [root]
        while stack:
            path = stack.pop()
            key = os.path.normcase(os.path.abspath(path))
            if key in seen_paths:
                continue
            seen_paths.add(key)
            try:
                info = path.lstat()
            except FileNotFoundError:
                if path == root:
                    if item.get('required', False):
                        raise ValueError('Required accounting root absent: ' + str(root))
                    missing_roots.append(str(root))
                else:
                    vanished_count += 1  # atomic mirror replacement can race enumeration
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                if path == root:
                    raise ValueError('Accounting root is an alias: ' + str(root))
                link_count += 1
                continue
            if stat.S_ISDIR(info.st_mode):
                with os.scandir(path) as entries:
                    for entry in entries:
                        if item.get('top_files_only') and entry.is_dir(follow_symlinks=False):
                            continue
                        if path == root and item.get('name_prefixes') and not any(entry.name.startswith(p) for p in item['name_prefixes']):
                            continue
                        stack.append(Path(entry.path))
            elif stat.S_ISREG(info.st_mode):
                identity = str(info.st_dev) + ':' + str(info.st_ino)
                if not info.st_ino:
                    raise ValueError('File identity unavailable')
                # A changing hardlink can be seen at different sizes: use the maximum.
                identities[identity] = max(identities.get(identity, 0), info.st_size)
                path_bytes += info.st_size
                path_count += 1
            else:
                special_count += 1
    return {'identities': identities, 'distinct_bytes': sum(identities.values()),
            'pathname_bytes': path_bytes, 'pathname_count': path_count,
            'identity_count': len(identities), 'skipped_links': link_count,
            'special_files': special_count, 'vanished_during_scan': vanished_count,
            'missing_optional_roots': missing_roots,
            'free_bytes': {str(p): shutil.disk_usage(p).free for p in free_paths}}


def growth(current, baseline):
    # Deletion/shrinkage elsewhere never subsidizes new evidence growth.
    return sum(max(0, size - baseline.get(key, 0)) for key, size in current.items())


def wsl_path(path):
    path = Path(path).resolve()
    if len(path.drive) != 2 or path.drive[1] != ':':
        raise ValueError('Expected a Windows drive path')
    return '/mnt/' + path.drive[0].lower() + path.as_posix()[2:]


def collect(config):
    started = utc()
    native = scan(config['native_roots'], config['native_free_paths'])
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    process = subprocess.run(['wsl.exe', '-d', config['wsl_distro'], '--', 'python3', '-B',
                              wsl_path(__file__), 'scan'],
                             input=json.dumps({'roots': config['wsl_roots'],
                                               'free_paths': config['wsl_free_paths']}),
                             capture_output=True, text=True, encoding='utf-8',
                             timeout=config['scan_timeout_s'], creationflags=flags)
    if process.returncode:
        # Never echo subprocess stderr; it might include an unexpected file value.
        raise RuntimeError('WSL metadata scan failed; exit=' + str(process.returncode))
    wsl = json.loads(process.stdout)
    return {'started_utc': started, 'finished_utc': utc(), 'native': native, 'wsl': wsl}


def summarize(sample, baseline):
    out = {k: v for k, v in sample.items() if k not in ('native', 'wsl')}
    total = 0
    for scope in ('native', 'wsl'):
        current = sample[scope]
        additional = growth(current['identities'], baseline[scope]['identities'])
        total += additional
        out[scope] = {k: v for k, v in current.items() if k != 'identities'}
        out[scope]['additional_bytes'] = additional
    out['aggregate_additional_bytes'] = total
    return out


def decisions(sample, config):
    stops = []
    notices = []
    for scope in ('native', 'wsl'):
        if min(sample[scope]['free_bytes'].values()) < config['reserve_bytes'] + config['retirement_headroom_bytes']:
            stops.append(scope + '_free_reserve_threat')
    size = sample['aggregate_additional_bytes']
    if size > config['planning_allowance_bytes']:
        notices.append('planning_allowance_exceeded_not_a_hard_cutoff')
    if size > config['large_growth_notice_bytes']:
        notices.append('unexpectedly_large_growth_notify_Randy')
    return stops, notices


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def protected_stop(endpoint_path):
    """Use only the attempt's ephemeral host capability; never retain its bytes."""
    if not Path(endpoint_path).exists():
        return {'attempted_utc': utc(), 'status': 'endpoint_not_yet_available'}
    try:
        endpoint = read_json(endpoint_path)
        url = urllib.parse.urlsplit(endpoint['url'])
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or
                url.path or url.query or url.fragment or url.username or url.password):
            raise ValueError('Invalid protected origin')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

        def request(method, path, body=None):
            req = urllib.request.Request(endpoint['url'] + '/operator/' + path,
                data=None if body is None else json.dumps(body).encode(), method=method,
                headers={'X-Robot-Operator-Capability': endpoint['capability'],
                         'Content-Type': 'application/json'})
            with opener.open(req, timeout=8) as response:
                data = response.read(1048577)
                if len(data) > 1048576:
                    raise ValueError('Oversized protected response')
                return json.loads(data)

        status = request('GET', 'status')
        result = request('POST', 'stop', {'request_id': 'storage-stop-' + uuid.uuid4().hex,
            'authority_epoch': status['authority_epoch'],
            'reason': 'Campaign001 external capacity guard stop; retain all evidence'})
        return {'attempted_utc': utc(), 'status': 'accepted' if result.get('ok') and
                result.get('command', {}).get('status') == 'completed' else 'not_accepted'}
    except Exception as error:
        # No exception text: URLs/headers/response contents must never enter receipts.
        return {'attempted_utc': utc(), 'status': 'failed', 'error_type': type(error).__name__}


def queue_status(config, job_id):
    proc = subprocess.run([sys.executable, '-X', 'utf8', '-B', config['queue_tool'], 'status', job_id],
                          capture_output=True, text=True, encoding='utf-8', timeout=10,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if proc.returncode:
        raise RuntimeError('Official queue status unavailable')
    return json.loads(proc.stdout)


def validate_config(config):
    if config['schema'] != SCHEMA or config['reserve_bytes'] < 100_000_000_000:
        raise ValueError('Invalid policy schema/reserve')
    if not 1 <= config['interval_s'] <= 10 or config['max_sample_gap_s'] > 30:
        raise ValueError('Unbounded monitor interval')
    if not config['native_roots'] or not config['wsl_roots']:
        raise ValueError('Both native and WSL scopes required')


def monitor(args, config):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    baseline_doc = read_json(args.baseline)
    if baseline_doc['config_sha256'] != digest(args.config):
        raise ValueError('Baseline policy mismatch')
    baseline = baseline_doc['sample']
    paths = {name: str(getattr(args, name).resolve()) for name in ('manifest', 'evidence', 'host_evidence', 'workspace')}
    receipt = {'schema': SCHEMA, 'run_id': args.run_id, 'job_id': None,
        'monitor_source_sha256': digest(__file__), 'config_sha256': digest(args.config),
        'baseline': {'path': str(args.baseline.resolve()), 'sha256': digest(args.baseline)},
        'paths': paths, 'state': 'monitoring', 'sample_count': 0,
        'reserve_bytes': config['reserve_bytes'], 'admission_stop_latched': False,
        'alerts': [], 'safe_stop_attempts': [], 'coverage_complete': False,
        'first_sample_utc': None, 'last_sample_utc': None, 'max_sample_gap_s': 0.0,
        'peak_aggregate_additional_bytes': 0, 'minimum_free_bytes': {},
        'accounting_scope': config['accounting_scope']}
    previous = None
    deadline = time.monotonic() + args.max_wait_s
    queue = None
    sample_path = output / 'samples.jsonl'

    def latch(reason):
        receipt['admission_stop_latched'] = True
        if reason not in receipt['alerts']:
            receipt['alerts'].append(reason)
        write_json(output / 'admission-stop.json', {'schema': SCHEMA, 'utc': utc(),
                   'run_id': args.run_id, 'job_id': receipt['job_id'], 'reason': reason})

    with sample_path.open('x', encoding='utf-8') as stream:
        while True:
            cycle = time.monotonic()
            if previous is not None:
                gap = cycle - previous
                receipt['max_sample_gap_s'] = max(receipt['max_sample_gap_s'], gap)
                if gap > config['max_sample_gap_s']:
                    latch('monitor_sample_gap_exceeded')
            previous = cycle
            try:
                sample = summarize(collect(config), baseline)
                receipt['first_sample_utc'] = receipt['first_sample_utc'] or sample['started_utc']
                receipt['last_sample_utc'] = sample['finished_utc']
                receipt['sample_count'] += 1
                receipt['peak_aggregate_additional_bytes'] = max(receipt['peak_aggregate_additional_bytes'], sample['aggregate_additional_bytes'])
                for scope in ('native', 'wsl'):
                    free = min(sample[scope]['free_bytes'].values())
                    receipt['minimum_free_bytes'][scope] = min(receipt['minimum_free_bytes'].get(scope, free), free)
                stops, notices = decisions(sample, config)
                receipt['alerts'] = list(dict.fromkeys(receipt['alerts'] + notices))
                for reason in stops:
                    latch(reason)
                stream.write(json.dumps(sample, allow_nan=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            except Exception as error:
                latch('monitor_scan_failure_' + type(error).__name__)
            if receipt['admission_stop_latched'] and config['safe_stop']:
                accepted = any(x['status'] == 'accepted' for x in receipt['safe_stop_attempts'])
                if not accepted:
                    receipt['safe_stop_attempts'].append(protected_stop(args.host_evidence / 'operator-endpoint.json'))
            write_json(output / 'live-status.json', receipt)
            if receipt['sample_count'] == 1 and not receipt['admission_stop_latched'] and not (output / 'ready.json').exists():
                write_json(output / 'ready.json', {'schema': SCHEMA, 'ready_utc': utc(),
                    'source_sha256': receipt['monitor_source_sha256'], 'config_sha256': receipt['config_sha256']})
            if args.job_file.exists():
                try:
                    submitted = read_json(args.job_file)
                    job_id = submitted.get('job_id', submitted.get('id'))
                    if not job_id or (receipt['job_id'] and receipt['job_id'] != job_id):
                        raise ValueError('Invalid or changed queue identity')
                    receipt['job_id'] = job_id
                    queue = queue_status(config, job_id)
                    if queue['state'] == 'running':
                        receipt.setdefault('queue_running_first_observed_utc', utc())
                    if queue['state'] in TERMINAL:
                        receipt['queue_terminal_observed_utc'] = utc()
                        # One complete post-terminal scan covers finalization bytes.
                        final_sample = summarize(collect(config), baseline)
                        stream.write(json.dumps(final_sample, allow_nan=False) + '\n')
                        stream.flush()
                        os.fsync(stream.fileno())
                        receipt['sample_count'] += 1
                        receipt['last_sample_utc'] = final_sample['finished_utc']
                        receipt['peak_aggregate_additional_bytes'] = max(receipt['peak_aggregate_additional_bytes'], final_sample['aggregate_additional_bytes'])
                        for scope in ('native', 'wsl'):
                            receipt['minimum_free_bytes'][scope] = min(receipt['minimum_free_bytes'][scope], min(final_sample[scope]['free_bytes'].values()))
                        stops, notices = decisions(final_sample, config)
                        receipt['alerts'] = list(dict.fromkeys(receipt['alerts'] + notices))
                        for reason in stops:
                            latch(reason)
                        queue_path = output / 'queue-receipt.json'
                        write_json(queue_path, queue)
                        receipt['official_queue_receipt'] = {'path': str(queue_path), 'sha256': digest(queue_path)}
                        receipt['official_queue_state'] = queue['state']
                        receipt['official_queue_exit_status'] = queue.get('exit_status')
                        started, ended = queue.get('started_at'), queue.get('ended_at')
                        def instant(value):
                            return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
                        receipt['coverage_complete'] = bool(started and ended and not receipt['admission_stop_latched'] and
                            instant(receipt['first_sample_utc']) <= instant(started) and instant(receipt['last_sample_utc']) >= instant(ended))
                        receipt['state'] = 'completed'
                        break
                except Exception as error:
                    latch('queue_or_final_scan_failure_' + type(error).__name__)
            if time.monotonic() > deadline:
                latch('monitor_deadline_exceeded')
                receipt['state'] = 'deadline_failed'
                break
            time.sleep(max(0.05, config['interval_s'] - (time.monotonic() - cycle)))
    receipt['samples'] = {'path': str(sample_path), 'sha256': digest(sample_path)}
    write_json(output / 'receipt.json', receipt)
    write_json(output / 'live-status.json', receipt)
    print(json.dumps({'state': receipt['state'], 'coverage_complete': receipt['coverage_complete'],
                      'admission_stop_latched': receipt['admission_stop_latched'], 'receipt': str(output / 'receipt.json')}))
    return 0 if receipt['coverage_complete'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('scan')
    baseline = sub.add_parser('baseline')
    baseline.add_argument('--config', type=Path, required=True)
    baseline.add_argument('--output', type=Path, required=True)
    run = sub.add_parser('monitor')
    for name in ('config', 'baseline', 'output', 'job-file', 'manifest', 'evidence', 'host-evidence', 'workspace'):
        run.add_argument('--' + name, type=Path, required=True)
    run.add_argument('--run-id', required=True)
    run.add_argument('--max-wait-s', type=float, default=43200)
    args = parser.parse_args()
    if args.command == 'scan':
        spec = json.load(sys.stdin)
        print(json.dumps(scan(spec['roots'], spec['free_paths'])))
        return 0
    config = read_json(args.config)
    validate_config(config)
    if args.command == 'baseline':
        if args.output.exists():
            raise ValueError('Baseline is immutable; select a fresh path')
        sample = collect(config)
        summary = summarize(sample, sample)
        stops, notices = decisions(summary, config)
        write_json(args.output, {'schema': SCHEMA, 'created_utc': utc(),
            'monitor_source_sha256': digest(__file__), 'config_sha256': digest(args.config),
            'sample': sample, 'preflight_passed': not stops, 'alerts': stops + notices,
            'accounting_scope': config['accounting_scope']})
        print(json.dumps({'preflight_passed': not stops, 'native_bytes': sample['native']['distinct_bytes'],
            'wsl_bytes': sample['wsl']['distinct_bytes'], 'minimum_free_bytes': {
                scope: min(sample[scope]['free_bytes'].values()) for scope in ('native', 'wsl')}}))
        return int(bool(stops))
    return monitor(args, config)


if __name__ == '__main__':
    raise SystemExit(main())
