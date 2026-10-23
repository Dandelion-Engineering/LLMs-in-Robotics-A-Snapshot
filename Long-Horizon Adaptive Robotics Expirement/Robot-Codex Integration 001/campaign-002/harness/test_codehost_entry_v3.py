"""A fixed extra read-only source does not change namespace permissions."""
import unittest

import codehost_entry_v3 as entry


class CleanupMountTests(unittest.TestCase):
    def test_fixed_helper_precedes_original_root_remount(self):
        original = ['bwrap', '--unshare-net', '--ro-bind', 'old', '/inside.py',
                    '--remount-ro', '/', '/usr/bin/python3', '-I', '-B', '/inside.py']
        expected = ['bwrap', '--unshare-net', '--ro-bind', 'new', '/inside.py',
                    '--ro-bind', 'mux', '/codehost_mux_protocol.py',
                    '--ro-bind', 'cleanup', '/native_cleanup_protocol.py',
                    '--remount-ro', '/', '/usr/bin/python3', '-I', '-B', '/inside.py']
        self.assertEqual(entry.replace_inside(original, 'old', 'new', 'mux', 'cleanup'), expected)
        self.assertEqual(original[3], 'old')

    def test_duplicate_destination_or_changed_terminal_remount_fails(self):
        original = ['bwrap', '--ro-bind', 'old', '/inside.py', '--remount-ro', '/',
                    '/usr/bin/python3', '-I', '-B', '/inside.py']
        for duplicate in ('/native_cleanup_protocol.py', '/codehost_mux_protocol.py'):
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError):
                entry.replace_inside([duplicate]+original, 'old', 'new', 'mux', 'cleanup')
        with self.assertRaises(ValueError):
            entry.replace_inside(original+['extra'], 'old', 'new', 'mux', 'cleanup')


if __name__ == '__main__': unittest.main()
