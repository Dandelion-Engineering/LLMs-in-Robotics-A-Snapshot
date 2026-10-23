"""One bounded, owned TCPIP ClosePath event trace; no packet capture or models."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
PREPARED = HERE.parent/'admin-coverage-automation-002'
sys.path.insert(0, str(PREPARED))
import run_coverage as base

OUTPUT_ROOT = base.OUTPUT_ROOT
SESSION = 'C02TcpClosureCoverage001'
LIMIT = 16*1024*1024


def clock_pair():
    before = time.perf_counter_ns()
    utc = time.time_ns()
    after = time.perf_counter_ns()
    return {'perf_before_ns':before, 'utc_ns':utc, 'perf_after_ns':after}


def validate_output(out):
    out = Path(out).resolve()
    if out.parent != OUTPUT_ROOT or not re.fullmatch(r'event-coverage-\d{8}-\d{3}', out.name):
        raise ValueError('Unexpected output root or name')
    if out.exists():
        raise FileExistsError('Fresh output required')
    return out


def source_paths():
    return {'run_event_coverage.py':Path(__file__).resolve(), 'run_coverage.py':PREPARED/'run_coverage.py',
            'owned_process.py':PREPARED/'owned_process.py', 'coverage_fixture.py':base.FIXTURE,
            'closepath-schema.json':HERE/'closepath-schema.json', 'DECLARATION.md':HERE/'DECLARATION.md'}


def validate_binding(manifest_path, out):
    binding = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    if binding['output'] != str(out) or binding['session'] != SESSION or set(binding['sources']) != set(source_paths()):
        raise ValueError('Binding scope differs')
    for name, path in source_paths().items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != binding['sources'][name]:
            raise ValueError('Source changed: '+name)
    return binding


def start_arguments(out, ready):
    port, pid = ready.get('port'), ready.get('pid')
    if type(port) is not int or not 1 <= port <= 65535 or type(pid) is not int or pid <= 0 or ready.get('address') != '127.0.0.1':
        raise ValueError('Malformed filter identity')
    return ['trace','start','sessionname='+SESSION,'capture=no','report=disabled','persistent=no',
            'traceFile='+str(out/'closure.etl'),'maxSize=16','fileMode=single','overwrite=no',
            'correlation=disabled','perfMerge=no','bufferSize=64','provider=Microsoft-Windows-TCPIP',
            'providerFilter=Yes','keywords=0x1000000000','level=5','TCP.AnyPort='+str(port),
            'IPv4.SourceAddress=127.0.0.1','IPv4.DestinationAddress=127.0.0.1','ProcessId='+str(pid)]


def owned_status(value, etl):
    for line in value.splitlines():
        if ':' in line:
            label, actual = line.split(':',1)
            if label.strip().casefold() in ('trace file','tracefile','log file'):
                if actual.strip().strip('"').casefold() == str(etl).casefold():
                    return True
    return False


def run(out, *, commands_type=base.Commands, require_admin=True, manifest_path=None, interrupt_at=None):
    out = Path(out).resolve()
    if require_admin:
        validate_output(out)
        if Path(sys.executable).resolve() != base.PYTHON.resolve() or not ctypes.windll.shell32.IsUserAnAdmin():
            raise RuntimeError('Exact project Python through one-shot UAC required')
        validate_binding(manifest_path,out)
    out.mkdir()
    base.save(out/'intent.json', {'session':SESSION,'packet_capture':False,'max_seconds':30,'max_etl_bytes':LIMIT,
                                'model_calls':0,'simulated_commands':commands_type is not base.Commands,
                                'source_sha256':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in source_paths().items()}})
    cmd = commands_type(out)
    children = []
    fixtures = []
    errors, cleanup_errors = [], []
    attempted = started = stopped = False
    begin = end = None
    etl = out/'closure.etl'
    try:
        base.validate_preflight(cmd.pktmon('status'), cmd.pktmon('filter','list'), cmd.call(base.NETSH,['trace','show','status']))
        named = cmd.call(base.NETSH,['trace','show','status','sessionname='+SESSION],required=False)
        if base.normalized(named) != base.NETSH_IDLE_TEXT:
            raise RuntimeError('Named session already present or unknown')
        if hashlib.sha256(base.FIXTURE.read_bytes()).hexdigest() != base.FIXTURE_SHA:
            raise RuntimeError('Original fixture binding changed')
        for label in ('included','excluded'):
            fixture = out/label
            child = base.OwnedProcess([str(base.PYTHON),'-X','utf8','-B',str(base.FIXTURE),'--output',str(fixture)],
                                     base.ROOT,out/(label+'-stdout.txt'),out/(label+'-stderr.txt'))
            children.append(child)
            base.save(out/(label+'-launch.json'),child.launch_identity)
            deadline = time.monotonic()+8
            while True:
                if child.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Fixture readiness failed: '+label)
                try:
                    ready = json.loads((fixture/'ready.json').read_bytes())
                    break
                except (FileNotFoundError,json.JSONDecodeError):
                    time.sleep(.025)
            identity = child.validate_ready(ready,[base.PYTHON,sys._base_executable],fixture)
            base.save(out/(label+'-identity.json'),identity)
            fixtures.append({'label':label,'ready':ready,'output':str(fixture)})
        if fixtures[0]['ready']['port'] == fixtures[1]['ready']['port']:
            raise RuntimeError('Exclusion control port collision')
        base.save(out/'fixtures.json',fixtures)
        if interrupt_at == 'ready':
            raise KeyboardInterrupt('Declared simulated interruption before trace')
        # No unrelated capture is stopped. The named session and exact fresh
        # ETL identity are required again in finally before our stop command.
        if base.normalized(cmd.call(base.NETSH,['trace','show','status'])) != base.NETSH_IDLE_TEXT:
            raise RuntimeError('Default trace became active')
        base.save(out/'clock-before.json',clock_pair())
        begin = time.perf_counter_ns()
        attempted = True
        cmd.call(base.NETSH,start_arguments(out,fixtures[0]['ready']),timeout=5)
        started = True
        status = cmd.call(base.NETSH,['trace','show','status','sessionname='+SESSION],timeout=3)
        if not owned_status(status,etl):
            raise RuntimeError('Started trace ownership not confirmed')
        if interrupt_at == 'capture':
            raise KeyboardInterrupt('Declared simulated interruption after startup')
        for fixture in fixtures:
            base.save(Path(fixture['output'])/'release.json',{'release':True})
        for child in children:
            remaining = 15-(time.perf_counter_ns()-begin)/1e9
            if remaining <= 0 or child.wait(timeout=min(5,remaining)) != 0:
                raise RuntimeError('Socket control failed')
    except BaseException as exc:
        errors.append({'type':type(exc).__name__,'message':str(exc)[:1800]})
    finally:
        if attempted:
            try:
                status = cmd.call(base.NETSH,['trace','show','status','sessionname='+SESSION],required=False,timeout=3)
                if owned_status(status,etl):
                    cmd.call(base.NETSH,['trace','stop','sessionname='+SESSION],timeout=5)
                    end = time.perf_counter_ns()
                    stopped = True
                    status = cmd.call(base.NETSH,['trace','show','status','sessionname='+SESSION],required=False)
                    if base.normalized(status) != base.NETSH_IDLE_TEXT:
                        raise RuntimeError('Named session not confirmed stopped')
                elif base.normalized(status) != base.NETSH_IDLE_TEXT:
                    raise RuntimeError('Foreign/unknown named trace; stop refused')
                elif started:
                    raise RuntimeError('Our confirmed trace disappeared before owned stop')
            except BaseException as exc:
                cleanup_errors.append('TRACE STOP: '+str(exc)[:1500])
        retirements = []
        for child in children:
            try:
                retirements.append(child.retire())
            except BaseException as exc:
                retirements.append(child.retirement)
                cleanup_errors.append('FIXTURE: '+str(exc)[:1000])
            finally:
                child.close()
    elapsed = None if end is None else (end-begin)/1e9
    base.save(out/'clock-after.json',clock_pair())
    if elapsed is not None and elapsed > 30:
        errors.append({'type':'BoundExceeded','message':'Trace exceeded30seconds'})
    if stopped and not etl.is_file():
        errors.append({'type':'MissingETL','message':'Owned stop returned without the declared ETL'})
    if etl.exists() and stopped:
        try:
            if etl.stat().st_size > LIMIT:
                raise RuntimeError('ETL exceeds16MiB')
            cmd.pktmon('etl2txt',str(etl),'--stats',timeout=15)
            cmd.pktmon('etl2txt',str(etl),'--out',str(out/'closure.txt'),'--timestamp','--metadata',timeout=15)
        except BaseException as exc:
            errors.append({'type':type(exc).__name__,'message':str(exc)[:1000]})
    try:
        if not base.idle_status(cmd.pktmon('status')) or not base.empty_filters(cmd.pktmon('filter','list')):
            raise RuntimeError('Packet Monitor state changed; no mutation attempted')
    except BaseException as exc:
        cleanup_errors.append('FINAL PACKET MONITOR STATE: '+str(exc)[:1000])
    receipt = {'collection_completed':not errors and not cleanup_errors,'coverage_qualified':False,
               'model_calls':0,'packet_capture':False,'session':SESSION,'trace_started':started,'trace_stopped':stopped,
               'trace_elapsed_s':elapsed,'errors':errors,'cleanup_errors':cleanup_errors,
               'fixture_retirements':retirements,'simulated_commands':commands_type is not base.Commands}
    base.save(out/'receipt.json',receipt)
    print(json.dumps(receipt,indent=2),flush=True)
    return 0 if receipt['collection_completed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-manifest',type=Path,required=True)
    args = parser.parse_args()
    sys.exit(run(args.output,manifest_path=args.source_manifest))
