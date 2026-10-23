"""Check the fixed guest protocol against the real synthetic protected gateway.

No WSL, model, or simulation. This validates the qualification probe itself;
the queued boundary suite separately validates actual namespace containment.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import boundary_suite as suite
from run_host import HttpGateway
from supervisor import Supervisor,Journal
from test_supervisor import FakeAdapter,Candidate,packet


class UnitSuiteDeclarations(unittest.TestCase):
    def test_both_parity_suites_are_discovered_and_receipted(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            def completed(argv, **kwargs):
                return subprocess.CompletedProcess(argv, 0, 'mocked unit test output', '')
            with patch.object(suite.subprocess, 'run', side_effect=completed) as execute:
                rows = suite.unit_suites(output)
            self.assertEqual(len(rows), 11)
            self.assertEqual(execute.call_count, 11)
            for name, pattern in [('journal-instrumentation', 'test_instrumented_journal.py'),
                                  ('recorder-instrumentation', 'test_instrumented_recorder.py')]:
                row = next(row for row in rows if row['name'] == name)
                self.assertEqual(row['argv'][row['argv'].index('-s') + 1], str(suite.HARNESS))
                self.assertEqual(row['argv'][row['argv'].index('-p') + 1], pattern)
                receipt = json.loads((output / name / 'execution.json').read_text())
                self.assertEqual(receipt['argv'], row['argv'])
                self.assertEqual(receipt['exit_code'], 0)

    def test_either_parity_failure_blocks_boundary_progress(self):
        for pattern in ('test_instrumented_journal.py', 'test_instrumented_recorder.py'):
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)
                def completed(argv, **kwargs):
                    return subprocess.CompletedProcess(argv, 1 if pattern in argv else 0, '', 'mocked failure')
                with patch.object(suite.subprocess, 'run', side_effect=completed):
                    with self.assertRaisesRegex(RuntimeError, 'bounded unit suite failed'):
                        suite.unit_suites(output)
                name = 'journal-instrumentation' if 'journal' in pattern else 'recorder-instrumentation'
                receipt = json.loads((output / name / 'execution.json').read_text())
                self.assertEqual(receipt['exit_code'], 1)


class FixedGuestProtocol(unittest.TestCase):
    def test_original_supervisor_supports_declared_guest_probe_and_stale_note_denial(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            journal=Journal(root/'protected',root/'workspace','synthetic-boundary-test')
            (journal.workspace/'notes').mkdir(exist_ok=True)
            adapter=FakeAdapter()
            host=Supervisor(adapter,Candidate('baseline',root/'baseline',True),journal)
            host.update_observation(packet());host.activate('Synthetic qualification probe test')
            gateway=HttpGateway(journal.workspace)
            gateway.rotate(host.epoch);gateway.start()
            stop=threading.Event()
            def owner():
                while not stop.wait(.005):gateway.process(host)
            thread=threading.Thread(target=owner,daemon=True);thread.start()
            # Only substitute the test workspace location. The HTTP routes,
            # expected receipts, bounds, and fixed source control flow are exact.
            source=suite.GUEST_SOURCE.replace('/workspace',journal.workspace.as_posix())
            try:
                first=subprocess.run([sys.executable,'-X','utf8','-B','-c',source,'control'],
                                     capture_output=True,text=True,encoding='utf-8',timeout=20)
                self.assertEqual(first.returncode,0,first.stdout+'\n'+first.stderr)
                self.assertTrue(all(json.loads(first.stdout)['checks'].values()))
                self.assertEqual(len(adapter.submissions),1)
                note=journal.read_continuity()
                adapter.active=False
                host.native_feedback({'request_id':'boundary-valid','status':'completed'})
                adapter.now=1.2;host.update_observation(packet('parking1',sequence=2,sim=1.2))
                second=subprocess.run([sys.executable,'-X','utf8','-B','-c',source,'handback'],
                                      capture_output=True,text=True,encoding='utf-8',timeout=20)
                self.assertEqual(second.returncode,0,second.stdout+'\n'+second.stderr)
                self.assertTrue(all(json.loads(second.stdout)['checks'].values()))
                self.assertEqual(journal.read_continuity(),note)
                self.assertEqual(len(adapter.submissions),1)
                self.assertEqual(host.owner,'conventional')
            finally:
                stop.set();thread.join(timeout=2);gateway.close()


if __name__=='__main__':unittest.main()
