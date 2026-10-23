"""Frozen method choice cannot fall back after a new transport failure."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import transport_dispatch as subject


class TransportDispatchTests(unittest.TestCase):
    def test_legacy_snapshot_preserves_legacy_verifier(self):
        frozen={'sources': {}}
        with patch.object(subject,'verify_v2',return_value={'passed':True}) as legacy:
            self.assertEqual(subject.verify_transport_integrity('stage',frozen),{'passed':True})
        legacy.assert_called_once_with('stage',frozen,owner_kind='model_client')

    def test_declared_v3_selects_new_verifier_before_observing_evidence(self):
        frozen={'sources':{subject.V3_METHOD:{'sha256':'a'*64}}}
        candidate=Mock(return_value={'passed':False,'errors':['missing ledger']})
        with patch.dict('sys.modules',{'transport_integrity_v3':SimpleNamespace(verify_transport_integrity=candidate)}), \
             patch.object(subject,'verify_v2') as legacy:
            result=subject.verify_transport_integrity('stage',frozen)
        self.assertFalse(result['passed']);legacy.assert_not_called()
        candidate.assert_called_once_with('stage',frozen,owner_kind='model_client')

    def test_v3_exception_cannot_trigger_legacy_fallback(self):
        frozen={'sources':{subject.V3_METHOD:{}}}
        candidate=Mock(side_effect=ValueError('malformed new evidence'))
        with patch.dict('sys.modules',{'transport_integrity_v3':SimpleNamespace(verify_transport_integrity=candidate)}), \
             patch.object(subject,'verify_v2') as legacy:
            with self.assertRaisesRegex(ValueError,'malformed new evidence'):
                subject.verify_transport_integrity('stage',frozen,owner_kind='transport_probe')
        legacy.assert_not_called()


if __name__=='__main__':unittest.main()
