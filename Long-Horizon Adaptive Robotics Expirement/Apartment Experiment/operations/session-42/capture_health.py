"""Bounded read-only heartbeat evidence; writes only a new operator snapshot."""
from collections import Counter
import ctypes
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import tomllib
import uuid

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
ROOT = PAIR / 'baseline'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ref(path, label):
    data = path.read_bytes()
    return dict(label=label, uri=str(path), sha256=digest(data), state='available',
                access='operator', locator=None)


def receipt(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=digest(data), value=json.loads(data))


def prefix(path, include_last=True):
    data = path.read_bytes()
    complete = data[:data.rfind(b'\n') + 1]
    rows = [json.loads(line) for line in complete.splitlines()]
    result = dict(path=str(path), bytes=len(data), complete_bytes=len(complete),
                  prefix_sha256=digest(complete), records=len(rows),
                  incomplete_tail_bytes=len(data) - len(complete))
    if include_last:
        result['last'] = rows[-1] if rows else None
    return result, rows


def windows_identity(owner):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = (W.DWORD, W.BOOL, W.DWORD)
    k.OpenProcess.restype = W.HANDLE
    k.GetProcessTimes.argtypes = (W.HANDLE, *([ctypes.POINTER(W.FILETIME)] * 4))
    k.GetProcessTimes.restype = W.BOOL
    k.GetExitCodeProcess.argtypes = (W.HANDLE, ctypes.POINTER(W.DWORD))
    k.GetExitCodeProcess.restype = W.BOOL
    k.CloseHandle.argtypes = (W.HANDLE,)
    k.CloseHandle.restype = W.BOOL
    result = dict(pid=owner['pid'], expected_creation_filetime=owner['process_creation_filetime'])
    handle = k.OpenProcess(0x1000, False, owner['pid'])
    if not handle:
        error = ctypes.get_last_error()
        return dict(**result, state='absent' if error == 87 else 'unknown', winerror=error)
    try:
        times = [W.FILETIME() for _ in range(4)]
        code = W.DWORD()
        if not (k.GetProcessTimes(handle, *[ctypes.byref(t) for t in times])
                and k.GetExitCodeProcess(handle, ctypes.byref(code))):
            return dict(**result, state='unknown', winerror=ctypes.get_last_error())
        actual = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        state = ('pid_reused' if actual != owner['process_creation_filetime']
                 else 'alive' if code.value == 259 else 'exited')
        return dict(**result, actual_creation_filetime=actual, state=state, exit_code=code.value)
    finally:
        k.CloseHandle(handle)


def main():
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                  observed_monotonic_ns=time.monotonic_ns(), observational_only=True,
                  scope='Bounded live recording, native receipt and scheduler inspection; not an endpoint audit.')
    result['events'], events = prefix(ROOT / 'events.jsonl')
    result['event_counts'] = dict(Counter(row['kind'] for row in events))
    result['lifecycle'] = [row for row in events if row['kind'] in
                           ('session_started', 'session_closed', 'boundary_checkpoint', 'task_success', 'resumed')]
    session_number = max(row['payload']['session'] for row in events if row['kind'] == 'session_started')
    result['latest_started_session'] = session_number
    result['sessions'] = []
    for number in (session_number - 1, session_number):
        if number < 1:
            continue
        session = ROOT / 'sessions' / f'session-{number:05}'
        item = dict(session=number, receipts={})
        for relative in ('native/client/preflight.json', 'native/client/result.json',
                         'native/canary.json', 'native/codehost-canary.json',
                         'native/codehost-native-owner-v3.json', 'native/executor-1-exit.json',
                         'native/codehost-owner-retirement-v3.json', 'workspace/cleanup-001.json',
                         'workspace/journal/native-exit.json'):
            path = session / relative
            if path.exists():
                item['receipts'][relative] = receipt(path)
        owner = item['receipts'].get('native/codehost-native-owner-v3.json')
        if owner:
            item['windows_owner'] = windows_identity(owner['value'])
        path = session / 'closeout.json'
        if path.exists():
            value = receipt(path)
            item['closeout'] = {k: v for k, v in value.items() if k != 'value'}
            item['closeout'].update(passed=value['value']['passed'], report=value['value']['report'])
        item['recording_prefixes'] = {}
        for relative in ('native/executor-1-capture.jsonl', 'native/broker-events.jsonl',
                         'workspace/journal/mutations.jsonl'):
            path = session / relative
            if path.exists():
                item['recording_prefixes'][relative] = prefix(path, include_last=False)[0]
        result['sessions'].append(item)
    index = receipt(ROOT / 'replay/index.json')
    last_chunk = index['value'][-1]
    result['replay'] = dict(index_path=index['path'], index_bytes=index['bytes'],
                            index_sha256=index['sha256'], chunks=len(index['value']), last=last_chunk,
                            last_chunk_sha256=digest((ROOT / 'replay' / last_chunk['file']).read_bytes()))
    result['replay']['last_chunk_matches'] = result['replay']['last_chunk_sha256'] == last_chunk['sha256']
    delivered = [row for row in events if row['kind'] == 'image_delivered']
    if delivered:
        last = delivered[-1]
        path = ROOT / 'sensors' / f"frame-{last['payload']['sequence']:07}.png"
        sensor = ref(path, 'Latest delivered sensor frame')
        result['sensor'] = dict(delivered_event=last, reference=sensor,
                                hash_matches=sensor['sha256'] == last['payload']['sha256'])
    result['monitoring'] = []
    for aid in ('apartment-v4-baseline-observations', 'apartment-v2-baseline-observations',
                'apartment-v2-maps-observations', 'apartment-v3-baseline-observations'):
        path = Path('C:/Users/cresp/.codex/automations') / aid / 'automation.toml'
        data = path.read_bytes()
        value = tomllib.loads(data.decode('utf-8'))
        result['monitoring'].append(dict(path=str(path), sha256=digest(data),
            **{k: value.get(k) for k in ('id', 'kind', 'status', 'rrule', 'target_thread_id', 'updated_at')}))
    result['source_references'] = [ref(PAIR / relative, label) for relative, label in (
        ('frozen_repository/source-manifest.json', 'Frozen source manifest'),
        ('frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json',
         'Release certification'))]
    result['latest_checkpoint_at_end'] = receipt(ROOT / 'latest-checkpoint.json')
    result['reader_sha256'] = digest(Path(__file__).read_bytes())
    result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    out = PAIR / 'operator/observations' / ('session42-health-' + uuid.uuid4().hex + '.json')
    with out.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(evidence=str(out), sha256=digest(out.read_bytes()),
        session=session_number, event_counts=result['event_counts'], replay=result['replay'],
        sensor_hash_matches=result.get('sensor', {}).get('hash_matches'),
        windows=[s.get('windows_owner') for s in result['sessions']],
        checkpoint=result['latest_checkpoint_at_end']['value'])))


if __name__ == '__main__':
    main()
