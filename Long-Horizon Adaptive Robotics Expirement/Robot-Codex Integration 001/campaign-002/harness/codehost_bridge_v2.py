"""Single-client private codehost byte bridge with fail-closed lifecycle receipts.

No payload or endpoint is added to metadata. A clean EOF is successful only
after the trusted owner has declared finishing, with an independently retained
namespace child-status receipt and completed namespace retirement.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
NAMESPACE_PREFIX = 'RCI_CODEHOST_V2 '
MAX_LEDGER_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 1024 * 1024
MAX_CONNECTIONS = 16


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_identities():
    paths = [HERE / name for name in ('codehost_bridge_v2.py', 'codehost_entry_v2.py', 'codehost_inside_v2.py')]
    paths += [HERE.parents[1] / 'readiness-session-10/boundary' / name for name in ('linux_entry.py', 'namespace.py')]
    return {p.relative_to(REPO).as_posix(): {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size} for p in paths}


def save(path, value):
    raw = json.dumps(value, indent=2).encode() + b'\n'
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return {'path': Path(path).name, 'sha256': sha(raw), 'bytes': len(raw)}


class Ledger:
    def __init__(self, fixture):
        self.fixture = fixture
        self.path = Path(fixture.evidence) / 'codehost-transport-v2.jsonl'
        self.path.touch(exist_ok=False)
        self.sequence, self.previous, self.bytes = 0, None, 0
    def emit(self, kind, **fields):
        value = {'schema': 'campaign002-codehost-transport-2', 'sequence': self.sequence + 1,
                 'previous_sha256': self.previous, 'wall_unix_s': time.time(),
                 'monotonic_s': time.monotonic(), 'kind': kind, **fields}
        value['record_sha256'] = sha(canonical(value))
        raw = canonical(value) + b'\n'
        try:
            if self.bytes + len(raw) > MAX_LEDGER_BYTES:
                raise RuntimeError('Codehost metadata bound exceeded')
            with self.path.open('ab') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        except BaseException:
            self.fixture.abort_event.set()
            raise
        self.sequence += 1
        self.previous = value['record_sha256']
        self.bytes += len(raw)
        return value


def namespace_records(raw):
    records = []
    if not raw.endswith(b'\n'):
        raise ValueError('Codehost stderr has incomplete tail')
    for line in raw.decode('utf-8', errors='strict').splitlines():
        if line.startswith(NAMESPACE_PREFIX):
            value = json.loads(line[len(NAMESPACE_PREFIX):])
            if (value.get('schema') != 'campaign002-codehost-namespace-2'
                    or type(value.get('sequence')) is not int or value['sequence'] != len(records) + 1):
                raise ValueError('Namespace metadata sequence/schema differs')
            records.append(value)
    if (not records or records[0].get('kind') != 'open' or records[-1].get('kind') != 'closed'
            or sum(row.get('kind') == 'closed' for row in records) != 1):
        raise ValueError('Missing complete namespace metadata')
    end = records[-1]
    if (end.get('qualified') is not True or end.get('reason') != 'owner_input_eof'
            or end.get('stdin_eof') is not True or end.get('error_type') is not None
            or end.get('diagnostic_streams_complete') is not True
            or end.get('kill_sent') is not False
            or end.get('child_exit_before_cleanup') not in (None, 0)
            or type(end.get('child_exit_code')) is not int
            or not (end['child_exit_code'] == 0 or end.get('terminate_sent') is True and end['child_exit_code'] == -15)):
        raise ValueError('Namespace child/relay failed')
    diagnostics = [row for row in records if row.get('kind') == 'child_diagnostic']
    if (len(diagnostics) != 2 or {row.get('stream') for row in diagnostics} != {'stdout', 'stderr'}
            or any(type(row.get('bytes')) is not int or row['bytes'] < 0
                   or row.get('truncated') is not False for row in diagnostics)
            or sum(row['bytes'] for row in diagnostics) > MAX_STDERR_BYTES):
        raise ValueError('Namespace child diagnostic streams incomplete')
    return records


async def run(fixture, callback):
    from retirement import retire
    ledger = Ledger(fixture)
    sources = source_identities()
    ledger.emit('open', sources=sources, max_connections=MAX_CONNECTIONS,
                max_ledger_bytes=MAX_LEDGER_BYTES, max_stderr_bytes=MAX_STDERR_BYTES)
    active = False
    tasks, failures = set(), []
    accepted = denied = connections = 0

    def fail(reason):
        failures.append(reason)
        fixture.abort_event.set()

    async def handle(reader, writer):
        nonlocal active, accepted, denied, connections
        current = asyncio.current_task()
        tasks.add(current)
        connections += 1
        connection_id = connections
        if active or connections > MAX_CONNECTIONS:
            denied += 1
            reason = 'single_active_client' if active else 'connection_bound'
            ledger.emit('connection_denied', connection_id=connection_id, reason=reason)
            if reason == 'connection_bound': fail(reason)
            writer.close()
            await writer.wait_closed()
            tasks.discard(current)
            return
        active = True
        accepted += 1
        prefix = 'codehost-' + str(connection_id)
        identity = fixture.run + '/codehost-' + uuid.uuid4().hex + '.json'
        ledger.emit('connection_accepted', connection_id=connection_id)
        process = None
        errors_task = None
        pumps = []
        first = None
        receipt = {'schema': 'campaign002-codehost-bridge-2', 'connection_id': connection_id,
                   'to_host': 0, 'from_host': 0, 'pump_errors': [], 'expected_client_shutdown_resets': 0,
                   'qualified': False, 'sources': sources, 'namespace_records': [], 'namespace_record_count': 0}
        try:
            process = await asyncio.create_subprocess_exec(*fixture.argv('codehost'), '--identity-file', identity,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            ledger.emit('child_started', connection_id=connection_id)
            async def pump(name):
                exception_type = None
                reason = 'eof'
                try:
                    if name == 'upload':
                        while data := await reader.read(65536):
                            process.stdin.write(data)
                            await process.stdin.drain()
                            receipt['to_host'] += len(data)
                    else:
                        while data := await process.stdout.read(65536):
                            writer.write(data)
                            await writer.drain()
                            receipt['from_host'] += len(data)
                except asyncio.CancelledError:
                    reason = 'cancelled'
                    raise
                except Exception as error:
                    exception_type, reason = type(error).__name__, 'error'
                finally:
                    row = ledger.emit('pump_end', connection_id=connection_id, pump=name, reason=reason,
                                      client_finishing=fixture.client_finishing.is_set(), exception_type=exception_type)
                    if reason != 'cancelled':
                        receipt.setdefault('first_pump_end', row)
                    if reason == 'error':
                        if exception_type == 'ConnectionResetError' and row['client_finishing']:
                            receipt['expected_client_shutdown_resets'] += 1
                        else:
                            receipt['pump_errors'].append(exception_type)
                            fail('unexpected_' + name + '_' + exception_type)
                    elif reason == 'eof' and not row['client_finishing']:
                        fail('unexpected_' + name + '_eof')
            async def errors():
                raw = bytearray()
                total = 0
                digest = hashlib.sha256()
                while data := await process.stderr.read(65536):
                    total += len(data); digest.update(data)
                    raw.extend(data[:max(0, MAX_STDERR_BYTES - len(raw))])
                    if total > MAX_STDERR_BYTES: fail('codehost_stderr_bound')
                return bytes(raw), total, digest.hexdigest()
            errors_task = asyncio.create_task(errors())
            pumps = [asyncio.create_task(pump(name), name=name) for name in ('upload', 'download')]
            await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
            first = receipt.get('first_pump_end')
        except Exception as error:
            fail('bridge_' + type(error).__name__)
            receipt['pump_errors'].append(type(error).__name__)
        finally:
            for task in pumps: task.cancel()
            if pumps: await asyncio.gather(*pumps, return_exceptions=True)
            receipt['first_pump_end'] = first or receipt.get('first_pump_end')
            receipt['client_finishing_at_first_end'] = bool(receipt['first_pump_end']
                                                          and receipt['first_pump_end']['client_finishing'])
            if process is not None:
                ledger.emit('retirement_started', connection_id=connection_id,
                            client_finishing=fixture.client_finishing.is_set(), exit_code_before=process.returncode)
                process.stdin.close()
                retirement_path = Path(fixture.evidence) / (prefix + '-retirement.json')
                try:
                    await retire(process, identity, retirement_path)
                    retirement_raw = retirement_path.read_bytes()
                    retired = json.loads(retirement_raw)
                    if retired.get('qualified') is not True: raise ValueError('Unverified namespace retirement')
                    receipt['retirement'] = {'path': retirement_path.name, 'sha256': sha(retirement_raw), 'bytes': len(retirement_raw)}
                except Exception as error:
                    fail('retirement_' + type(error).__name__)
                receipt['exit_code'] = process.returncode
                if type(process.returncode) is not int or process.returncode != 0:
                    fail('codehost_wrapper_nonzero_or_missing_exit')
            try:
                if errors_task is None: raise ValueError('No stderr drain')
                raw, total, raw_sha = await asyncio.wait_for(errors_task, 3)
                safe = fixture.redact(raw.decode('utf-8', errors='strict')).encode()
                stderr_path = Path(fixture.evidence) / (prefix + '-stderr.txt')
                with stderr_path.open('xb') as stream:
                    stream.write(safe); stream.flush(); os.fsync(stream.fileno())
                receipt['stderr'] = {'path': stderr_path.name, 'bytes': len(safe), 'sha256': sha(safe),
                                     'raw_bytes': total, 'raw_sha256': raw_sha,
                                     'truncated': total != len(raw), 'redacted': safe != raw}
                if total != len(raw) or safe != raw: raise ValueError('Incomplete namespace metadata stream')
                receipt['namespace_records'] = namespace_records(safe)
                receipt['namespace_record_count'] = len(receipt['namespace_records'])
            except Exception as error:
                if errors_task and not errors_task.done(): errors_task.cancel()
                fail('namespace_receipt_' + type(error).__name__)
            receipt['qualified'] = (receipt['client_finishing_at_first_end'] and not receipt['pump_errors']
                                    and bool(receipt['namespace_records']) and receipt.get('exit_code') == 0
                                    and 'retirement' in receipt)
            if not receipt['qualified']: fail('connection_unqualified')
            binding = save(Path(fixture.evidence) / (prefix + '-bridge.json'), receipt)
            ledger.emit('connection_closed', connection_id=connection_id, qualified=receipt['qualified'], receipt=binding)
            writer.close()
            try: await writer.wait_closed()
            except (ConnectionResetError, BrokenPipeError):
                if not fixture.client_finishing.is_set(): fail('client_close_error')
            active = False

    outcome = None
    try:
        async with await asyncio.start_server(handle, '127.0.0.1', 0) as server:
            ledger.emit('listening')
            try:
                outcome = await callback('http://127.0.0.1:' + str(server.sockets[0].getsockname()[1]))
            finally:
                server.close()
                await server.wait_closed()
                if tasks:
                    _, pending = await asyncio.wait(tasks, timeout=25)
                    for task in pending: task.cancel()
                    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 25)
                    for value in results:
                        if isinstance(value, BaseException): fail('handler_' + type(value).__name__)
    except BaseException as error:
        fail('callback_or_server_' + type(error).__name__)
        raise
    finally:
        ledger.emit('closed', failures=list(failures), accepted=accepted, denied=denied)
    if failures: raise RuntimeError('Codehost v2 failed: ' + '; '.join(failures))
    return outcome
