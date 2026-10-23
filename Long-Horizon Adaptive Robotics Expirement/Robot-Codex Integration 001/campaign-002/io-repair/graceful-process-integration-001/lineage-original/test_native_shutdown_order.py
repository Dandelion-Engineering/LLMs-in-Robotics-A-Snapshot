"""Exact reversal of timestamps and the separately declared pre-exit join."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import native_quiescence as native

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARCHIVE = HERE.parents[2]/'Architecture Map/releases/RCI001-C02-dev-091/code.zip'

METHOD = '''    def close_stdin_observed(self):
        # At most the existing graceful close and its existing forced cleanup.
        # Capture inside the worker, immediately around the unchanged operation.
        observation = {'begin_perf_counter_ns': time.perf_counter_ns(),
                       'end_perf_counter_ns': None, 'returned_normally': False}
        self.order_observations['stdin_close'].append(observation)
        try:
            value = self.client.process.stdin.close()
            observation['returned_normally'] = True
            return value
        finally:
            observation['end_perf_counter_ns'] = time.perf_counter_ns()

'''

PRE_EXIT = '''        if not self.failures and getattr(self.client.args, 'native_process_ready', None) is not None:
            try:
                import native_exit_drain
                self.bounded(lambda: native_exit_drain.before_stdin_close(self), self.graceful,
                             'transport_pre_exit_drain_failed')
            except CleanupError as error: self.fail(str(error))
'''

BRIDGE_EXIT = '''    def native_exit_barrier(self, request):
        import native_exit_drain
        return native_exit_drain.bridge_join(self, request)

'''

def strip_instrumentation(candidate):
    if candidate.count(PRE_EXIT) != 1: raise AssertionError('Unexpected pre-exit source change')
    candidate = candidate.replace(PRE_EXIT, '')
    changes = (
        ("        self.order_observations = {'schema': 'campaign002-native-shutdown-order-1',\n"
         "                                  'lifecycle': [], 'stdin_close': []}\n", ''),
        ('        observed_perf_counter_ns = time.perf_counter_ns()\n', ''),
        ("        self.order_observations['lifecycle'].append({'sequence': value['sequence'],\n"
         "            'phase': phase, 'observed_perf_counter_ns': observed_perf_counter_ns})\n", ''),
        ("            with path.with_name('native-shutdown-order.json').open('x',encoding='utf-8') as file:\n"
         "                json.dump(self.order_observations,file,indent=2);file.write('\\n');file.flush();os.fsync(file.fileno())\n", ''),
        ('self.bounded(self.close_stdin_observed, self.graceful,',
         'self.bounded(self.client.process.stdin.close, self.graceful,'),
        ('self.bounded(self.close_stdin_observed,self.hard,',
         'self.bounded(self.client.process.stdin.close,self.hard,'),
        (METHOD, ''),
    )
    for after, before in changes:
        if candidate.count(after) != 1: raise AssertionError('Unexpected timestamp source change')
        candidate = candidate.replace(after, before)
    return candidate

class ShutdownOrderTests(unittest.TestCase):
    def controller(self, operation):
        client = SimpleNamespace(process=SimpleNamespace(stdin=SimpleNamespace(close=operation)))
        return native.Controller(client, 4096)

    def test_interval_surrounds_operation_and_keeps_return(self):
        observed = []
        counter = iter((100, 200))
        result = object()
        controller = self.controller(lambda: observed.append(dict(controller.order_observations['stdin_close'][0])) or result)
        with mock.patch.object(native.time, 'perf_counter_ns', side_effect=lambda: next(counter)):
            self.assertIs(controller.close_stdin_observed(), result)
        self.assertEqual(observed, [{'begin_perf_counter_ns':100,'end_perf_counter_ns':None,'returned_normally':False}])
        self.assertEqual(controller.order_observations['stdin_close'],
                         [{'begin_perf_counter_ns':100,'end_perf_counter_ns':200,'returned_normally':True}])

    def test_exact_exception_survives_with_failed_interval(self):
        original = OSError('do not retain this message')
        def fail(): raise original
        controller = self.controller(fail)
        with self.assertRaises(OSError) as caught: controller.close_stdin_observed()
        self.assertIs(caught.exception, original)
        observation = controller.order_observations['stdin_close'][0]
        self.assertFalse(observation['returned_normally'])
        self.assertGreaterEqual(observation['end_perf_counter_ns'], observation['begin_perf_counter_ns'])
        self.assertNotIn('message', observation)

    def test_only_instrumentation_and_declared_pre_exit_join_differ_from_dev091(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            old = archive.read((HERE/'native_quiescence.py').relative_to(REPO).as_posix()).decode().replace('\r\n','\n')
            candidate = (HERE/'native_quiescence.py').read_text(encoding='utf-8')
            self.assertEqual(strip_instrumentation(candidate), old)
            bridge = (HERE/'codehost_bridge_v3.py').read_text(encoding='utf-8')
            for addition in ('        observed_perf_counter_ns = time.perf_counter_ns()\n',
                             '                observed_perf_counter_ns=observed_perf_counter_ns,\n',
                             BRIDGE_EXIT, '        self.fixture.native_exit_barrier = self.native_exit_barrier\n'):
                self.assertEqual(bridge.count(addition), 1)
                bridge = bridge.replace(addition, '')
            self.assertEqual(bridge, archive.read((HERE/'codehost_bridge_v3.py').relative_to(REPO).as_posix()).decode().replace('\r\n','\n'))

    def test_parity_rejects_changed_deadline_and_missing_timestamp(self):
        candidate = (HERE/'native_quiescence.py').read_text(encoding='utf-8')
        with self.assertRaises(AssertionError): strip_instrumentation(candidate.replace(METHOD, ''))
        self.assertNotEqual(strip_instrumentation(candidate.replace('GRACEFUL_SECONDS = 5', 'GRACEFUL_SECONDS = 6')),
                            strip_instrumentation(candidate))

if __name__ == '__main__': unittest.main()
