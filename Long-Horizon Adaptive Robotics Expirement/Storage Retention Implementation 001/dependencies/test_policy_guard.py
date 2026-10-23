"""Boundary tests for the process-local staged image availability guard."""
import builtins
import os
from pathlib import Path
import tempfile
import unittest
import validate_policy as policy

class GuardTests(unittest.TestCase):
    def test_denies_only_nonretained_affected_images_and_restores_io(self):
        with tempfile.TemporaryDirectory() as directory:
            attempts=Path(directory)/'attempts'
            frames=attempts/'run/evidence/frames';frames.mkdir(parents=True)
            keep=frames/'000001.png';drop=frames/'000002-depth.npz'
            raw=frames.parent/'events.jsonl'
            for p in (keep,drop,raw):p.write_bytes(b'original')
            original=policy.ATTEMPTS;policy.ATTEMPTS=attempts
            try:
                allowed={os.path.normcase(os.path.abspath(keep))}
                with policy.retained_only(allowed) as denied:
                    self.assertEqual(keep.read_bytes(),b'original')
                    self.assertEqual(raw.read_bytes(),b'original')
                    self.assertFalse(drop.exists());self.assertFalse(drop.is_file())
                    with self.assertRaises(FileNotFoundError):drop.stat()
                    with self.assertRaises(FileNotFoundError):drop.read_bytes()
                    with self.assertRaises(FileNotFoundError):builtins.open(str(drop),'rb')
                    self.assertEqual(len(denied),5)
                self.assertEqual(drop.read_bytes(),b'original')
            finally:policy.ATTEMPTS=original

if __name__=='__main__':unittest.main()
