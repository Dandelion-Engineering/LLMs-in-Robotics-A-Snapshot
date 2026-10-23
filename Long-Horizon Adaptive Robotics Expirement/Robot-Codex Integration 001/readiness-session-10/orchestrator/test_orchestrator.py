"""Lightweight failure-path checks; no model, Linux process or simulator."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from runtime import Runtime, run_bootstrap

class BrokenInput:
    def close(self):raise BrokenPipeError('injected broker already exited')
class Broker:
    stdin=BrokenInput()
    returncode=7
    def wait(self,timeout):return self.returncode
class Gateway:
    closed=False
    def close(self):self.closed=True

class FailurePaths(unittest.TestCase):
    def test_cleanup_continues_after_broker_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            value=Runtime.__new__(Runtime)
            value.evidence=Path(temp);value.stop=threading.Event();value.broker=Broker()
            value.mirror_thread=value.broker_thread=value.owner=None
            value.gateway=Gateway();value.broker_calls=[]
            value.personal_canary=Path(temp)/'owned.txt';value.personal_canary.write_text('owned')
            self.assertFalse(value.close())
            self.assertTrue(value.gateway.closed)
            self.assertFalse(value.personal_canary.exists())
            result=json.loads((Path(temp)/'cleanup.json').read_text())
            self.assertFalse(result['clean']);self.assertEqual(len(result['errors']),2)
            self.assertTrue((Path(temp)/'gateway-calls.json').is_file())

    def test_existing_attempt_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            marker=Path(temp)/'orchestration-result.json';marker.write_text('historical')
            with self.assertRaises(ValueError):run_bootstrap(temp)
            self.assertEqual(marker.read_text(),'historical')

if __name__=='__main__':unittest.main()
