"""No admin commands, tracing, sockets, models or project edits in these checks."""
import unittest
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
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


class NetshIdleExitTests(unittest.TestCase):
    def test_actual_elevated_idle_record_through_command_runner(self):
        record = json.loads(Path(r'C:\Users\cresp\Documents\Campaign002 TCP Trace\coverage-20260929T194528Z-3fc2e5c2\command-03.json').read_text(encoding='utf-8'))
        completed = subprocess.CompletedProcess(record['argv'],record['exit_code'],record['stdout'],record['stderr'])
        with tempfile.TemporaryDirectory() as directory, patch.object(runner.subprocess,'run',return_value=completed) as call:
            cmd = runner.Commands(Path(directory))
            output = cmd.call(runner.NETSH,['trace','show','status'])
            runner.validate_preflight(IDLE,EMPTY,output)
            saved = json.loads((Path(directory)/'command-01.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['exit_code'],1)
            self.assertTrue(saved['recognized_idle_netsh_exit'])
            self.assertEqual(call.call_args.args[0],record['argv'])

    def test_other_codes_errors_commands_and_trace_states_remain_fatal(self):
        cases = [
            (runner.NETSH,['trace','show','status'],5,NO_TRACE,''),
            (runner.NETSH,['trace','show','status'],1,NO_TRACE,'Access is denied'),
            (runner.NETSH,['trace','show','status'],1,'Trace session is running',''),
            (runner.NETSH,['trace','show','status'],1,NO_TRACE+'Unexpected state',''),
            (runner.NETSH,['trace','stop'],1,NO_TRACE,''),
            (runner.PKTMON,['status'],1,NO_TRACE,''),
        ]
        for executable,args,code,stdout,stderr in cases:
            with self.subTest(executable=executable,args=args,code=code,stdout=stdout,stderr=stderr):
                completed = subprocess.CompletedProcess([str(executable),*args],code,stdout,stderr)
                with tempfile.TemporaryDirectory() as directory, patch.object(runner.subprocess,'run',return_value=completed):
                    with self.assertRaises(RuntimeError):
                        runner.Commands(Path(directory)).call(executable,args)


if __name__ == '__main__':
    unittest.main()
