"""Real fixture processes with simulated admin commands; never starts OS capture."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import run_coverage as runner

OUTPUT = None


class SimulatedCommands:
    fault = None

    def __init__(self, output):
        self.output, self.filters, self.active = output, [], None
        self.calls = []

    def call(self, executable, args, **kwargs):
        assert executable == runner.NETSH and args == ['trace', 'show', 'status']
        self.calls.append(['netsh', *args])
        return runner.NETSH_IDLE_TEXT

    def pktmon(self, *args, **kwargs):
        self.calls.append(list(args))
        if args == ('status',):
            if self.fault == 'existing_capture' and not self.filters:
                return 'Packet Monitor is running.\nLog file: C:\\foreign.etl\n'
            return ('Packet Monitor is not running.\n' if self.active is None else
                    'Packet Monitor is running.\nLog file: '+str(self.active)+'\n')
        if args == ('filter', 'list'):
            return 'Packet Filters:\n' + ('None\n' if not self.filters else
                '# Name IP Address Protocol Port\n'+'\n'.join(
                    f'{i+1} {name} 127.0.0.1 TCP {flag} {port}'
                    for i,(name,flag,port) in enumerate(self.filters)))
        if args[:2] == ('filter', 'add'):
            if self.fault == 'second_add' and self.filters:
                raise RuntimeError('Declared failure of second filter add')
            self.filters.append((args[2], args[6], args[8]))
            return 'Added'
        if args[0] == 'start':
            assert list(args) == runner.capture_arguments(self.output/'coverage.etl')
            self.active = self.output/'coverage.etl'
            if self.fault == 'start_timeout':
                raise subprocess.TimeoutExpired(args, 5)
            if self.fault == 'foreign_capture':
                self.active = Path('C:/foreign.etl')
            if self.fault == 'foreign_filter':
                self.filters.append(('ForeignOwner', 'SYN', 9999))
            if self.fault == 'changed_filter':
                name,flag,port = self.filters[0]
                self.filters[0] = (name,flag,int(port)+1)
            return 'Started'
        if args == ('stop',):
            if self.fault == 'stop_failure':
                raise RuntimeError('Declared stop failure')
            assert self.active == self.output/'coverage.etl', 'Stopped foreign capture'
            self.active = None
            return 'Stopped'
        if args == ('filter', 'remove'):
            assert self.active is None, 'Removed filters during active capture'
            assert all(x[0] in runner.NAMES for x in self.filters), 'Removed foreign filter'
            self.filters = []
            return 'Removed'
        raise AssertionError(args)


class CompletePath(unittest.TestCase):
    def exercise(self, name, fault=None, interruption=None):
        directory = OUTPUT/name
        self.command = None
        def factory(output):
            self.command = SimulatedCommands(output)
            self.command.fault = fault
            return self.command
        with contextlib.redirect_stdout(io.StringIO()):
            code = runner.run(directory, commands_type=factory, require_admin=False, interrupt_at=interruption)
        value = json.loads((directory/'receipt.json').read_text(encoding='utf-8'))
        runner.save(directory/'simulated-command-history.json', self.command.calls)
        self.assertTrue(value['simulated_commands'])
        self.assertFalse(value['trace_coverage_qualified'])
        self.assertEqual(value['model_calls'], 0)
        if value['fixture_retirement'] is not None:
            self.assertTrue(value['fixture_retirement']['qualified'])
        return code, value

    def test_full_success(self):
        code,r = self.exercise('success')
        self.assertEqual(code, 0)
        self.assertTrue(r['collection_completed'])
        self.assertTrue(r['fixture_identity_verified'])
        self.assertIsNone(self.command.active)
        self.assertEqual(self.command.filters, [])

    def test_ready_interruption(self):
        code,r = self.exercise('ready-interruption', interruption='ready')
        self.assertEqual(code, 1)
        self.assertFalse(r['capture_started'])
        self.assertEqual(self.command.filters, [])

    def test_capture_interruption(self):
        code,r = self.exercise('capture-interruption', interruption='capture')
        self.assertEqual(code, 1)
        self.assertTrue(r['capture_stopped'])
        self.assertEqual(self.command.filters, [])

    def test_partial_filter_setup(self):
        code,r = self.exercise('second-add', 'second_add')
        self.assertEqual(code, 1)
        self.assertFalse(r['capture_started'])
        self.assertEqual(self.command.filters, [])

    def test_uncertain_start_with_exact_owned_path(self):
        code,r = self.exercise('start-timeout', 'start_timeout')
        self.assertEqual(code, 1)
        self.assertFalse(r['capture_started'])
        self.assertTrue(r['capture_stopped'])
        self.assertIsNone(self.command.active)

    def test_foreign_capture_is_never_stopped(self):
        code,r = self.exercise('foreign-capture', 'foreign_capture')
        self.assertEqual(code, 1)
        self.assertFalse(r['capture_stopped'])
        self.assertNotIn(['stop'], self.command.calls)
        self.assertNotIn(['filter','remove'], self.command.calls)

    def test_foreign_filters_are_never_removed(self):
        code,r = self.exercise('foreign-filter', 'foreign_filter')
        self.assertEqual(code, 1)
        self.assertTrue(r['capture_stopped'])
        self.assertNotIn(['filter','remove'], self.command.calls)

    def test_changed_filter_description_is_not_removed(self):
        code,r = self.exercise('changed-filter', 'changed_filter')
        self.assertEqual(code, 1)
        self.assertNotIn(['filter','remove'], self.command.calls)

    def test_stop_failure_is_retained_and_filters_left(self):
        code,r = self.exercise('stop-failure', 'stop_failure')
        self.assertEqual(code, 1)
        self.assertFalse(r['capture_stopped'])
        self.assertTrue(r['cleanup_errors'])
        self.assertNotIn(['filter','remove'], self.command.calls)

    def test_existing_capture_makes_no_mutation(self):
        code,r = self.exercise('existing-capture', 'existing_capture')
        self.assertEqual(code, 1)
        self.assertFalse(r['fixture_identity_verified'])
        self.assertEqual(self.command.filters, [])
        self.assertNotIn(['stop'], self.command.calls)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    OUTPUT = args.output.resolve()
    OUTPUT.mkdir()
    (OUTPUT/'sources').mkdir()
    sources = list(runner.HERE.glob('*.py')) + [runner.FIXTURE]
    for source in sources:
        shutil.copy2(source, OUTPUT/'sources'/source.name)
    with (OUTPUT/'tests.txt').open('x', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompletePath))
    receipt = {'passed':result.wasSuccessful(), 'tests':result.testsRun,
               'failures':len(result.failures), 'errors':len(result.errors),
               'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
               'scope':'Real private-job fixture launches with simulated administrator commands. No OS capture or elevation.'}
    runner.save(OUTPUT/'receipt.json', receipt)
    print(json.dumps(receipt, indent=2))
    sys.exit(0 if result.wasSuccessful() else 1)
