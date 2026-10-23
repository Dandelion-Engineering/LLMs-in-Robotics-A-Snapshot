"""Bounded synthetic parity against exact dev061; no OS/native/model launch."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
import zipfile

D = Path(__file__).resolve().parent
C = D.parents[1]
R = C.parents[2]
H = C / 'harness'
sys.path.insert(0, str(H))
import codehost_mux_protocol as current
from test_codehost_mux_protocol import h2
from test_codehost_bridge_v3 import BridgeTests


def binding(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


archive = R / 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-061/code.zip'
snapshot = archive.with_name('snapshot.json')
member = (H / 'codehost_mux_protocol.py').relative_to(R).as_posix()
with zipfile.ZipFile(archive) as bundle:
    original = bundle.read(member)
assert hashlib.sha256(original).hexdigest() == 'b9d61b200e3bb698d06eed3a5a16bf047278be5f7cba2109659e9b261f0ec7cd'
assert json.loads(snapshot.read_text())['sources'][member]['sha256'] == hashlib.sha256(original).hexdigest()
old = types.ModuleType('dev061_mux')
exec(compile(original, str(archive) + '!' + member, 'exec'), old.__dict__)

# Reversing exactly the three declared additive blocks restores every byte.
raw = (H / 'codehost_mux_protocol.py').read_bytes()
init = b'        # Diagnostic-only tombstones never participate in protocol decisions.\r\n        self._diagnostic_closed_streams = {}\r\n        self._diagnostic_closed_evicted = False\r\n'
close = b'            self._diagnostic_closed_streams[stream] = None\r\n            if len(self._diagnostic_closed_streams) > MAX_H2_STREAMS:\r\n                del self._diagnostic_closed_streams[next(iter(self._diagnostic_closed_streams))]\r\n                self._diagnostic_closed_evicted = True\r\n'
start = raw.index(b'                if self.first_rejection is None:', raw.index(b'        elif kind == 3:'))
end = raw.index(b"                raise ValueError('HTTP/2 reset on unavailable stream')", start)
reset_block = raw[start:end]
restored = raw
for block in (init, close, reset_block):
    assert restored.count(block) == 1
    restored = restored.replace(block, b'')
assert restored == original


def nondiagnostic(witness):
    value = copy.deepcopy(vars(witness))
    value.pop('_diagnostic_closed_streams', None)
    value.pop('_diagnostic_closed_evicted', None)
    if (value.get('first_rejection') or {}).get('schema') == 'campaign002-h2-reset-rejection-1':
        value['first_rejection'] = None
    return value


ready = [('upload', current.PREFACE + h2(4)), ('download', h2(4))]
opened = [('upload', h2(1, 5, 1, b'synthetic-header'))]
closed = opened + [('download', h2(1, 5, 1, b'synthetic-response'))]
rst = lambda stream, code=8: h2(3, 0, stream, code.to_bytes(4, 'big'))
workloads = {
    'normal_close': ready + closed,
    'normal_close_late_reset': ready + closed + [('upload', rst(1))],
    'normal_close_late_other_reset': ready + closed + [('download', rst(1, 0xffffffff))],
    'unknown_reset': ready + [('upload', rst(7))],
    'active_reset_then_duplicate': ready + opened + [('download', rst(1)), ('upload', rst(1, 2))],
    'active_retirement_cancel': ready + opened + [('retire', None), ('download', rst(1))],
    'retirement_duplicate_cancel': ready + opened + [('retire', None), ('download', rst(1)), ('upload', rst(1))],
    'retirement_new_headers': ready + opened + [('retire', None), ('upload', h2(1, 5, 3, b'synthetic'))],
    'retirement_reset_reuse_headers': ready + opened + [('retire', None), ('upload', rst(1) + h2(1, 5, 1, b'synthetic'))],
    'new_open_close_same_read': ready + [('retire', None), ('upload', h2(1, 5, 1, b'synthetic') + rst(1))],
    'coalesced_after_bad_reset': ready + closed + [('upload', rst(1) + h2(1, 5, 3, b'never-forwarded'))],
    'invalid_reset_flags': ready + [('upload', h2(3, 1, 1, b'1234'))],
    'invalid_reset_length': ready + [('upload', h2(3, 0, 1, b'123'))],
    'invalid_reset_scope': ready + [('upload', rst(0))],
    'preexisting_reset_blocks_retirement': ready + opened + [('upload', rst(1)), ('retire', None)],
    'partial_reset_before_retirement': ready + opened + [('upload', rst(1)[:3]), ('retire', None), ('upload', rst(1)[3:])],
    'reset_outside_retirement_rule': ready + opened + [('retire', None), ('download', rst(1, 2))],
}
many = list(ready)
for stream in range(1, 2050, 2):
    many.extend([('upload', h2(1, 5, stream, b'x')), ('download', h2(1, 5, stream, b'y'))])
workloads['evicted_normal_close_still_rejected'] = many + [('upload', rst(1))]
proofs = []
for name, steps in workloads.items():
    for width in (1, 3, 9, 13, 64, 65536):
        before, after = old.H2Witness(), current.H2Witness()
        forwarded = [hashlib.sha256(), hashlib.sha256()]
        accepted_counts = [0, 0]
        calls = 0
        for direction, wire in steps:
            chunks = [None] if direction == 'retire' else [wire[i:i+width] for i in range(0, len(wire), width)]
            for chunk in chunks:
                outcomes = []
                for i, witness in enumerate((before, after)):
                    try:
                        if direction == 'retire':
                            answer = witness.begin_retirement()
                            if (answer.get('first_rejection') or {}).get('schema') == 'campaign002-h2-reset-rejection-1':
                                del answer['first_rejection']
                        else:
                            witness.feed(direction, chunk)
                            forwarded[i].update(direction.encode() + len(chunk).to_bytes(4, 'big') + chunk)
                            accepted_counts[i] += len(chunk)
                            answer = None
                        outcomes.append(('accepted', answer))
                    except ValueError as error:
                        outcomes.append(('ValueError', str(error)))
                calls += 1
                assert outcomes[0] == outcomes[1], (name, width, outcomes)
                assert nondiagnostic(before) == nondiagnostic(after), (name, width)
        assert accepted_counts[0] == accepted_counts[1]
        assert forwarded[0].digest() == forwarded[1].digest()
        proofs.append({'workload': name, 'chunk_width': width, 'calls': calls,
                       'accepted_bytes': accepted_counts[0], 'accepted_transcript_sha256': forwarded[0].hexdigest()})


class ResetReceipt(BridgeTests):
    async def test_unavailable_reset_serializes_without_forwarding(self):
        wire = rst(1)
        before = []
        async def body():
            reader, writer, task = self.client()
            await writer.received.wait()
            self.assertEqual(self.bridge.channels[1].h2.summary()['closed_streams'], 1)
            before.append(self.bridge.channels[1].meters['upload'].summary())
            reader.feed_data(wire)
            reader.feed_eof()
            await task
        receipt = await self.run_bridge(body, fail=True)
        channel = receipt['channels'][0]
        self.assertFalse(receipt['qualified'])
        self.assertFalse(receipt['drain']['seal_qualified'])
        self.assertEqual(channel['h2']['error'], 'HTTP/2 reset on unavailable stream')
        self.assertEqual(channel['meters']['upload'], before[0])
        self.assertEqual(channel['meters']['client_read']['bytes'], before[0]['bytes'] + 13)
        self.assertEqual(channel['h2']['first_rejection']['observed_normal_close'], True)
        self.assertEqual(channel['h2']['first_rejection']['error_code'], 8)
        self.assertEqual(channel['h2']['first_rejection'], channel['seal_frontier']['first_rejection'])
        self.assertNotIn('first_rejection', channel['namespace_closed']['h2'])
        self.assertEqual(len(self.process.hosts[0][1].data), before[0]['bytes'])
        self.assertIsNotNone(receipt['retirement'])
        (D / 'synthetic-failed-bridge-receipt.json').write_bytes((self.folder / 'codehost-owner-bridge-v3.json').read_bytes())


result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([ResetReceipt('test_unavailable_reset_serializes_without_forwarding')]))
assert result.wasSuccessful()
output = {'schema': 'campaign002-reset-rejection-parity-1', 'scope': 'Fixed synthetic workloads and mocked in-memory bridge; no historical replay, native/OS/model/namespace launch or qualification claim',
          'archive': binding(archive), 'snapshot': binding(snapshot), 'archive_member': member,
          'original_member_sha256': hashlib.sha256(original).hexdigest(),
          'instrumented_source': binding(H / 'codehost_mux_protocol.py'),
          'test_source': binding(H / 'test_codehost_mux_protocol.py'), 'check_script': binding(Path(__file__)),
          'exact_byte_reversal_passed': True, 'additive_blocks_removed': 3,
          'acceptance_errors_counters_internal_nondiagnostic_state_equal_after_each_call': True,
          'parse_before_forward_transcripts_equal': True,
          'workload_count': len(workloads), 'case_count': len(proofs), 'cases': proofs,
          'mocked_bridge_failure_receipt': binding(D / 'synthetic-failed-bridge-receipt.json')}
with (D / 'parity.json').open('x', encoding='utf-8', newline='\n') as f:
    json.dump(output, f, indent=2);f.write('\n')
print(json.dumps({'passed': True, 'cases': len(proofs), 'parity': binding(D / 'parity.json')}))
