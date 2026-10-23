"""No admin commands, tracing, sockets, models or project edits in these checks."""
import unittest
import run_coverage as runner

IDLE = 'Packet Monitor is not running.\r\n'
EMPTY = 'Packet Filters:\r\n    None\r\n'
NO_TRACE = 'There is no trace session currently in progress.\r\n'


class GuardTests(unittest.TestCase):
    def test_observed_preflight_accepted(self):
        runner.validate_preflight(IDLE, EMPTY, NO_TRACE)

    def test_existing_capture_rejected(self):
        with self.assertRaises(RuntimeError):
            runner.validate_preflight('Packet Monitor is running.', EMPTY, NO_TRACE)

    def test_existing_filter_rejected(self):
        with self.assertRaises(RuntimeError):
            runner.validate_preflight(IDLE, 'Packet Filters:\n1 ExistingFilter TCP', NO_TRACE)

    def test_existing_etw_trace_rejected(self):
        with self.assertRaises(RuntimeError):
            runner.validate_preflight(IDLE, EMPTY, 'Trace session is running')

    def test_foreign_filter_is_not_hidden_by_our_names(self):
        text = 'Packet Filters:\n# Name IP Address Protocol\n1 C02CoverageFIN 127.0.0.1 TCP FIN\n2 C02CoverageRST 127.0.0.1 TCP RST\n3 AnotherOwner 10.0.0.1 UDP'
        self.assertEqual(runner.filter_names(text), {'C02CoverageFIN','C02CoverageRST','AnotherOwner'})
        self.assertNotEqual(runner.filter_names(text), set(runner.NAMES))

    def test_unknown_filter_format_rejected(self):
        with self.assertRaises(ValueError):
            runner.filter_names('Packet Filters:\nUnknown metadata\n1 C02CoverageFIN TCP FIN')

    def test_duplicate_filter_identity_rejected(self):
        with self.assertRaises(ValueError):
            runner.filter_names('Packet Filters:\n1 C02CoverageFIN TCP FIN\n2 C02CoverageFIN TCP RST')


if __name__ == '__main__':
    unittest.main()
