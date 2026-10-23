"""Focused nonmodel tests. Linux-only cases are short deterministic processes."""
import json
import base64
import hashlib
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock
import gateway_policy as policy
from namespace import command


class GatewayPolicyTests(unittest.TestCase):
    def test_actual_routes_and_finite_body(self):
        for method, path in [('GET', '/status'), ('GET', '/continuity'),
                             ('GET', '/history?after=0&limit=200'),
                             ('GET', '/command/abc:123'), ('GET', '/observation/overhead-12.png'),
                             ('POST', '/command'), ('POST', '/observe'), ('POST', '/handback')]:
            self.assertTrue(policy.allowed_route(method, path), (method, path))
        policy.validate_request({'method': 'POST', 'path': '/continuity', 'capability': 'test',
                                 'body': json.dumps({'content': 'atomic note'})})
        with self.assertRaises(ValueError):
            policy.validate_request({'method': 'POST', 'path': '/command', 'capability': 'test',
                                     'body': '{"duration":NaN}'})

    def test_operator_and_alias_routes_denied(self):
        for path in ('/operator/status', '/operator/start-invocation', '/operator/retire-invocation',
                     '/operator/stop', '/restart-agent', '/run-program', 'http://localhost/status',
                     '//example.com/status', '/%73tatus', '/status?', '/status#fragment',
                     '/command/../status', '/history?after=0&limit=201',
                     '/history?after=0&limit=1&after=2', '/history?limit=1&after=0',
                     '/observation/../../secret.png', '/observation/other.png'):
            for method in ('GET', 'POST'):
                self.assertFalse(policy.allowed_route(method, path), (method, path))
        self.assertFalse(policy.allowed_route('DELETE', '/status'))

    def test_bounds_and_no_destination_fields(self):
        request = {'method': 'GET', 'path': '/status', 'capability': 'test', 'body': ''}
        with self.assertRaises(ValueError):
            policy.validate_request({**request, 'destination': 'http://example.com'})
        with self.assertRaises(ValueError):
            policy.validate_request({**request, 'body': '{}'})
        with self.assertRaises(ValueError):
            policy.validate_request({**request, 'capability': 'test\r\nHeader: value'})
        with self.assertRaises(ValueError):
            policy.validate_request({'method': 'POST', 'path': '/continuity', 'capability': 'test',
                                     'body': json.dumps({'content': 'x' * 32769})})
        with self.assertRaises(ValueError):
            policy.validate_response({'status': 200, 'body': 'x' * (policy.MAX_RESPONSE + 1)})

    def test_namespace_write_split_and_complete_confinement(self):
        args = command('/var/tmp/robot-codex-session10/test/workspace',
                       '/var/tmp/robot-codex-session10/test/gateway.sock', '/trusted', '/codex-bin', '/host-bin')
        binds = [args[n+2] for n, value in enumerate(args) if value == '--bind']
        self.assertEqual(binds, ['/workspace/notes', '/workspace/programs', '/workspace/.continuity'])
        self.assertIn('--unshare-all', args)
        self.assertIn('--disable-userns', args)
        self.assertIn('--clearenv', args)
        self.assertIn('--die-with-parent', args)
        self.assertEqual(args[-5:], ['/', '/usr/bin/python3', '-I', '-B', '/inside.py'])
        self.assertIn('/program_runner.py', args)


@unittest.skipUnless(sys.platform == 'linux', 'Linux layout/runner system calls')
class LinuxLayoutTests(unittest.TestCase):
    def test_continuity_atomic_and_symlink_safety(self):
        import runtime_layout as layout
        with tempfile.TemporaryDirectory(prefix='robot-boundary-test-') as temp:
            with mock.patch.object(layout, 'RUNTIME_ROOT', Path(temp) / 'runs'):
                root = layout.RUNTIME_ROOT / 'case'
                result = layout.prepare_workspace(root, {'RobotAgentPrompt.md': 'read', 'Continuity.md': 'old'})
                workspace = Path(result['workspace'])
                original_link = os.readlink(workspace / 'Continuity.md')
                first = layout.atomic_continuity(workspace, 'new')
                self.assertEqual((workspace / 'Continuity.md').read_text(), 'new')
                self.assertEqual(first['bytes'], 3)
                self.assertEqual(os.readlink(workspace / 'Continuity.md'), original_link)
                unrelated = Path(temp) / 'outside.txt'
                unrelated.write_text('must stay')
                target = workspace / '.continuity/Continuity.md'
                target.unlink()
                target.symlink_to(unrelated)
                layout.atomic_continuity(workspace, 'safe')
                self.assertEqual(unrelated.read_text(), 'must stay')
                self.assertFalse(target.is_symlink())
                self.assertEqual((workspace / 'Continuity.md').read_text(), 'safe')
                with self.assertRaises(FileExistsError):
                    layout.prepare_workspace(root, {})


@unittest.skipUnless(sys.platform == 'linux', 'Linux sealed snapshots and pidfds')
class LinuxProgramTests(unittest.TestCase):
    def run_program(self, source, timeout=2):
        import program_runner
        with tempfile.TemporaryDirectory(prefix='robot-program-test-') as temp:
            workspace = Path(temp)
            (workspace / 'programs').mkdir()
            (workspace / 'notes').mkdir()
            (workspace / 'programs/case.py').write_text(source)
            result = program_runner.execute('programs/case.py', timeout, workspace)
            saved = json.loads(Path(result['evidence_path']).read_text())
            self.assertEqual(saved['source_sha256'], result['source_sha256'])
            admitted_bytes = Path(result['admission_path']).read_bytes()
            admitted = json.loads(admitted_bytes)
            self.assertEqual(hashlib.sha256(admitted_bytes).hexdigest(), saved['admission_sha256'])
            self.assertEqual(base64.b64decode(admitted['source_base64']), source.encode())
            self.assertEqual(admitted['disposition'], 'admitted_execution_unknown_until_final_record')
            self.assertFalse(admitted['completed'])
            self.assertTrue(result['retirement']['qualified'], result)
            return result

    def test_sigkill_before_popen_preserves_admission_without_false_final(self):
        import program_runner
        with tempfile.TemporaryDirectory(prefix='robot-program-kill-test-') as temp:
            workspace = Path(temp)
            (workspace / 'programs').mkdir()
            (workspace / 'notes').mkdir()
            source = b'print("must not launch")\n'
            (workspace / 'programs/case.py').write_bytes(source)
            helper = ('import os,signal,sys\nfrom pathlib import Path\n'
                      'sys.path.insert(0,sys.argv[1])\nimport program_runner\n'
                      'def killed_before_launch(*args,**kwargs):\n'
                      ' os.kill(os.getpid(),signal.SIGKILL)\n'
                      'program_runner.subprocess.Popen=killed_before_launch\n'
                      'program_runner.execute("programs/case.py",1,Path(sys.argv[2]))\n')
            result = subprocess.run(['/usr/bin/python3', '-I', '-B', '-c', helper,
                                     str(Path(program_runner.__file__).parent), str(workspace)],
                                    stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, -9, result.stderr)
            admissions = list((workspace / 'notes/program-runs').glob('*.admitted.json'))
            self.assertEqual(len(admissions), 1)
            admitted = json.loads(admissions[0].read_text())
            self.assertEqual(base64.b64decode(admitted['source_base64']), source)
            self.assertEqual(admitted['source_sha256'], hashlib.sha256(source).hexdigest())
            self.assertFalse(admitted['completed'])
            self.assertEqual(admitted['disposition'], 'admitted_execution_unknown_until_final_record')
            self.assertFalse((admissions[0].parent / admitted['final_record']).exists())

    def test_success_sealed_snapshot_and_complete_output(self):
        result = self.run_program('import os,sys\nprint("x"*200000)\n')
        self.assertTrue(result['completed'], result)
        self.assertEqual(len(result['output']['stdout']), 200001)
        self.assertTrue(result['sealed_snapshot'])

    def test_timeout_detached_descendant_retired(self):
        result = self.run_program('import subprocess,time\nsubprocess.Popen(["/usr/bin/python3","-c","import time;time.sleep(20)"],start_new_session=True)\ntime.sleep(20)\n', .2)
        self.assertFalse(result['completed'])
        self.assertTrue(result['timed_out'])
        self.assertGreaterEqual(len(result['retirement']['term_pids']), 2)

    def test_output_bound(self):
        result = self.run_program('import sys\nsys.stdout.write("x"*1100000)\nsys.stdout.flush()\n')
        self.assertFalse(result['completed'])
        self.assertTrue(result['output_limit'])
        self.assertEqual(len(result['output']['stdout']), 1048576)


if __name__ == '__main__':
    unittest.main()
