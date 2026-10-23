"""Codex-managed elevated, one-shot synthetic coverage test. No models or campaigns.

Captures the fixed fixture's loopback FIN/RST packets only. Capture is requested
with a 40-byte prefix and 16 MiB ceiling, stopped in finally, and invalidated if
the measured 30-second bound is missed. OS trace coverage is never auto-approved.
"""
import ctypes
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from owned_process import OwnedProcess

ROOT = Path(r'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics')
PYTHON = ROOT / 'venv/Scripts/python.exe'
FIXTURE = ROOT / 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/io-repair/smoke027-os-trace-readiness-001/coverage_fixture.py'
FIXTURE_SHA = '543e71167e24259141c8c1d7c0983184aee3e600974b842c1e2faa6946467c6f'
HERE = Path(__file__).resolve().parent
PKTMON = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/pktmon.exe'
NETSH = PKTMON.with_name('netsh.exe')
NAMES = ('C02CoverageFIN', 'C02CoverageRST')
NETSH_IDLE_TEXT = 'There is no trace session currently in progress.'


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def normalized(value):
    return '\n'.join(line.strip() for line in value.splitlines() if line.strip())


def empty_filters(value):
    return normalized(value) == 'Packet Filters:\nNone'


def idle_status(value):
    return normalized(value) == 'Packet Monitor is not running.'


def recognized_idle_netsh(executable, args, result):
    """This host reports the exact idle trace state with exit 1.

    Do not accept other exit codes, commands, states or additional errors.
    The actual elevated observation is preserved in coverage-20260929T194528Z-
    3fc2e5c2/command-03.json; all ordinary command failures still raise.
    """
    return (Path(executable) == NETSH and list(args) == ['trace', 'show', 'status']
            and result.returncode == 1
            and normalized(result.stdout) == NETSH_IDLE_TEXT
            and not result.stderr.strip())


def filter_names(value):
    """Accept table rows only; unknown formatting fails closed."""
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines or lines[0] != 'Packet Filters:':
        raise ValueError('Unrecognized filter-list format')
    names = []
    for line in lines[1:]:
        if line == 'None':
            raise ValueError('Expected owned filters, got None')
        match = re.match(r'^(\d+)\s+(\S+)(?:\s|$)', line)
        if match:
            names.append(match.group(2))
            continue
        match = re.match(r'^(\S+)\s+(\d+)(?:\s|$)', line)
        if match:
            names.append(match.group(1))
            continue
        if ('Name' in line and ('#' in line or re.search(r'\bId\b', line, re.I))) or set(line) <= set('-= '):
            continue
        raise ValueError('Unrecognized filter-list row; leaving filters intact')
    if not names or len(set(names)) != len(names):
        raise ValueError('Incomplete filter-list identity')
    return set(names)


def capture_arguments(etl):
    return ['start', '--capture', '--comp', 'all', '--pkt-size', '40',
            '--flags', '0x032', '--file-size', '16', '--log-mode', 'circular', '--file-name', str(etl)]


class Commands:
    def __init__(self, output):
        self.output = output
        self.sequence = 0

    def call(self, executable, args, timeout=5, required=True):
        self.sequence += 1
        started = time.perf_counter_ns()
        record = {'argv':[str(executable), *map(str,args)], 'started_perf_counter_ns':started}
        try:
            result = subprocess.run(record['argv'], capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=timeout,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            record.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
            record['recognized_idle_netsh_exit'] = recognized_idle_netsh(executable, args, result)
        except BaseException as exc:
            record.update(error=type(exc).__name__, message=str(exc)[:1000])
            raise
        finally:
            record['ended_perf_counter_ns'] = time.perf_counter_ns()
            save(self.output / ('command-%02d.json' % self.sequence), record)
        if required and result.returncode != 0 and not record['recognized_idle_netsh_exit']:
            raise RuntimeError('Command failed: ' + ' '.join(record['argv']) + '\n' + result.stdout + result.stderr)
        return result.stdout

    def pktmon(self, *args, **kwargs):
        return self.call(PKTMON, list(args), **kwargs)


def validate_preflight(status, filters, netsh):
    if not idle_status(status):
        raise RuntimeError('Packet Monitor is already running or its state is unknown; no changes made')
    if not empty_filters(filters):
        raise RuntimeError('Existing or unrecognized packet filters; no changes made')
    if normalized(netsh) != NETSH_IDLE_TEXT:
        raise RuntimeError('Existing or unrecognized netsh trace state; no changes made')


def capture_is_owned(status, etl):
    # Retain and require the exact unique ETL path from the live status. An
    # unrelated replacement capture must never be stopped by this helper.
    lines = [x.strip() for x in status.splitlines() if x.strip()]
    path = str(etl).casefold()
    return (not idle_status(status) and any(
        line.split(':', 1)[-1].strip().strip('"').casefold() == path for line in lines))


def run(out, *, commands_type=Commands, require_admin=True, source_manifest=None, interrupt_at=None):
    out = Path(out).resolve()
    out.mkdir()
    save(out / 'intent.json', {'model_calls':0, 'fixture':str(FIXTURE), 'fixture_sha256':FIXTURE_SHA,
                              'capture_limit_s':30,'packet_prefix_bytes':40,'etl_ceiling_MiB':16,
                              'automatic_coverage_qualification':False,'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                              'owned_process_sha256':hashlib.sha256((HERE/'owned_process.py').read_bytes()).hexdigest(),
                              'simulated_commands':commands_type is not Commands})
    cmd = commands_type(out)
    child = None
    owned = set()
    filter_snapshot = None
    capture_started = False
    capture_attempted = False
    capture_begin = None
    capture_end = None
    errors = []
    cleanup_errors = []
    retirement = None
    identity = None
    etl = out / 'coverage.etl'
    try:
        if os.name != 'nt' or (require_admin and not ctypes.windll.shell32.IsUserAnAdmin()):
            raise RuntimeError('A one-shot Windows UAC launch is required')
        if Path(sys.executable).resolve() != PYTHON.resolve():
            raise RuntimeError('Exact project venv Python required')
        if hashlib.sha256(FIXTURE.read_bytes()).hexdigest() != FIXTURE_SHA:
            raise RuntimeError('Prepared fixture changed; refusing to run')
        if source_manifest is not None:
            binding = json.loads(Path(source_manifest).read_text(encoding='utf-8'))
            if binding['output'] != str(out) or set(binding['sources']) != {'run_coverage.py', 'owned_process.py', 'coverage_fixture.py'}:
                raise RuntimeError('Source manifest scope differs')
            for name, digest in binding['sources'].items():
                path = FIXTURE if name == 'coverage_fixture.py' else HERE/name
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise RuntimeError('Source binding changed: '+name)
        status = cmd.pktmon('status')
        filters = cmd.pktmon('filter', 'list')
        netsh = cmd.call(NETSH, ['trace','show','status'])
        validate_preflight(status, filters, netsh)
        fixture_out = out / 'fixture'
        child = OwnedProcess([str(PYTHON),'-X','utf8','-B',str(FIXTURE),'--output',str(fixture_out)],
                             ROOT, out/'fixture-stdout.txt', out/'fixture-stderr.txt')
        save(out/'launch.json', child.launch_identity)
        wait_until = time.monotonic() + 8
        ready = None
        while ready is None:
            if child.poll() is not None or time.monotonic() >= wait_until:
                raise RuntimeError('Synthetic fixture did not become ready')
            try:
                ready = json.loads((fixture_out / 'ready.json').read_text(encoding='utf-8'))
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            if ready is not None:
                break
            time.sleep(.025)
        port = ready['port']
        identity = child.validate_ready(ready, [PYTHON, sys._base_executable], fixture_out)
        save(out/'identity.json', identity)
        if interrupt_at == 'ready':
            raise KeyboardInterrupt('Declared simulated interruption after ready')
        for name, flag in zip(NAMES, ('FIN','RST')):
            cmd.pktmon('filter','add',name,'-i','127.0.0.1','-t','TCP',flag,'-p',str(port))
            owned.add(name)
            view = cmd.pktmon('filter','list')
            if filter_names(view) != owned:
                raise RuntimeError('Unexpected filter appeared; refusing capture or blanket cleanup')
            filter_snapshot = normalized(view)
        # Repeat the idle check immediately before the scoped capture.
        if not idle_status(cmd.pktmon('status')):
            raise RuntimeError('Packet Monitor became active before our capture')
        capture_begin = time.perf_counter_ns()
        capture_attempted = True
        cmd.pktmon(*capture_arguments(etl), timeout=5)
        capture_started = True
        if interrupt_at == 'capture':
            raise KeyboardInterrupt('Declared simulated interruption after capture startup')
        # Release the two known controls only after successful capture startup.
        save(fixture_out / 'release.json', {'release':True})
        child.wait(timeout=8)
        if child.returncode != 0:
            raise RuntimeError('Synthetic fixture failed; inspect its retained output')
    except BaseException as exc:
        errors.append({'type':type(exc).__name__,'message':str(exc)[:1800]})
    finally:
        if capture_attempted:
            try:
                current_status = cmd.pktmon('status')
                if capture_is_owned(current_status, etl):
                    cmd.pktmon('stop', timeout=5)
                    capture_end = time.perf_counter_ns()
                elif not idle_status(current_status):
                    raise RuntimeError('Current capture identity is not the exact owned ETL; stop refused')
                elif capture_started:
                    raise RuntimeError('Confirmed owned capture disappeared before stop; coverage invalid')
            except BaseException as exc:
                cleanup_errors.append('STOP FAILED: ' + str(exc)[:1000])
        if child is not None:
            try:
                retirement = child.retire()
            except BaseException as exc:
                retirement = child.retirement
                cleanup_errors.append('FIXTURE RETIREMENT: '+str(exc)[:1000])
            finally:
                child.close()
        if owned:
            try:
                view = cmd.pktmon('filter','list')
                # Full filter list must contain exactly our successful additions;
                # if available, require the exact previous full description too.
                if filter_names(view) != owned or (filter_snapshot is not None and normalized(view) != filter_snapshot):
                    raise RuntimeError('Filter list changed; filters were left intact')
                if not idle_status(cmd.pktmon('status')):
                    raise RuntimeError('Capture is still active; filters were left intact')
                cmd.pktmon('filter','remove')
                if not empty_filters(cmd.pktmon('filter','list')):
                    raise RuntimeError('Filters remain after owned cleanup')
            except BaseException as exc:
                cleanup_errors.append('FILTER CLEANUP: ' + str(exc)[:1000])
    capture_seconds = None if capture_end is None else (capture_end - capture_begin)/1e9
    if capture_seconds is not None and capture_seconds > 30:
        errors.append({'type':'CaptureBoundExceeded','message':'The measured capture exceeded 30 seconds; invalid coverage'})
    if etl.exists() and capture_end is not None:
        try:
            if etl.stat().st_size > 16 * 1024 * 1024:
                raise RuntimeError('ETL exceeds declared 16 MiB ceiling')
            # Statistics and text export are retained for later independent
            # loss/wrap/FIN/RST/endpoint inspection. No pass is inferred here.
            cmd.pktmon('etl2txt',str(etl),'--stats',timeout=15)
            text_path = out/'coverage.txt'
            if text_path.exists():
                raise RuntimeError('Refusing to overwrite an export')
            cmd.pktmon('etl2txt',str(etl),'--out',str(text_path),'--timestamp','--metadata',timeout=15)
        except BaseException as exc:
            errors.append({'type':type(exc).__name__,'message':str(exc)[:1000]})
    if not errors and not cleanup_errors:
        try:
            if not idle_status(cmd.pktmon('status')):
                raise RuntimeError('Packet Monitor is not confirmed idle')
        except BaseException as exc:
            cleanup_errors.append('FINAL STATUS: '+str(exc)[:1000])
    receipt = {'collection_completed':not errors and not cleanup_errors,'model_calls':0,
               'trace_coverage_qualified':False,'coverage_review':'Required: both controls, endpoint/clock correlation and no loss/wrap.',
               'capture_started':capture_started,'capture_stopped':capture_end is not None,
               'capture_elapsed_s_including_command_startup':capture_seconds,
               'errors':errors,'cleanup_errors':cleanup_errors,'results':str(out),
               'fixture_retirement':retirement, 'fixture_identity_verified':identity is not None,
               'simulated_commands':commands_type is not Commands}
    save(out/'receipt.json',receipt)
    print(json.dumps(receipt,indent=2),flush=True)
    return 0 if receipt['collection_completed'] else 1


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--output', required=True, type=Path)
        parser.add_argument('--source-manifest', required=True, type=Path)
        args = parser.parse_args()
        output = args.output.resolve()
        if output.parent != HERE or not re.fullmatch(r'elevated-coverage-\d{3}', output.name):
            raise ValueError('Output must be a fresh declared elevated-coverage-NNN directory beside this helper')
        sys.exit(run(output, source_manifest=args.source_manifest))
    except Exception as exc:
        print('STOPPED: ' + str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
