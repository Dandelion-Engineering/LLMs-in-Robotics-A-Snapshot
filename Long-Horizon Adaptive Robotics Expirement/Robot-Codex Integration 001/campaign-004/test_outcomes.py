"""Contract checks for clean bounded failure versus unqualified infrastructure."""
import copy
import json
from pathlib import Path
import unittest
from coordinator import model_completion
from common import HERE

class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.timeout=json.loads((HERE/'live-evidence/RCI001-C04-live-001-attempt/robot-session-1/client/result.json').read_text())
    def test_retained_clean_timeout_is_bounded_failure(self):
        self.assertEqual(model_completion(self.timeout),'bounded_deadline')
    def test_failed_retirement_is_invalid(self):
        value=copy.deepcopy(self.timeout);value['native_quiescence']['qualified']=False
        self.assertEqual(model_completion(value),'invalid')
    def test_unconfirmed_interrupt_is_invalid(self):
        value=copy.deepcopy(self.timeout);value['native_quiescence']['terminal_turn']['status']='unknown'
        self.assertEqual(model_completion(value),'invalid')
    def test_other_provider_failure_is_invalid(self):
        value=copy.deepcopy(self.timeout);value['error']='usageLimitExceeded'
        self.assertEqual(model_completion(value),'invalid')
    def test_wrong_model_effort_or_auth_is_invalid(self):
        for field,bad in [('model_effective','other'),('effort_effective','high'),('auth_type','apikey')]:
            with self.subTest(field=field):
                value=copy.deepcopy(self.timeout);value[field]=bad
                self.assertEqual(model_completion(value),'invalid')
    def test_normal_completion_is_separate(self):
        value=copy.deepcopy(self.timeout);value.update(success=True,turn_status='completed');value.pop('error')
        self.assertEqual(model_completion(value),'completed')

if __name__=='__main__':unittest.main()
