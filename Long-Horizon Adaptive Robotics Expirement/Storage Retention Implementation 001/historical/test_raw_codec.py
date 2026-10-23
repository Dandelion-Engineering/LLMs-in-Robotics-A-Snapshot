import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import raw_codec as codec


class CodecTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def exercise(self, raw):
        source, archive, restored = [self.root / name for name in ("source", "archive", "restored")]
        source.write_bytes(raw)
        before = source.stat()
        manifest = codec.pack(source, archive, chunk_bytes=256)
        self.assertEqual(b"".join(codec.read_chunks(archive, manifest)), raw)
        codec.restore(archive, manifest, restored)
        self.assertEqual(restored.read_bytes(), raw)
        self.assertEqual(manifest["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(source.stat().st_mtime_ns, before.st_mtime_ns)
        return source, archive, restored, manifest

    def test_empty(self):
        self.exercise(b"")

    def test_arbitrary_bytes_and_multiblock_incompressible(self):
        self.exercise(bytes(range(256)) + os.urandom(10000))

    def test_json_spelling_order_duplicate_keys_and_line_endings(self):
        self.exercise(b' {"n":1.000e+00,"n":-0.0,"z":"\\u00e9"} \r\n' * 100 + b'{"unterminated_line":true}')

    def test_large_payload_crosses_many_blocks(self):
        self.exercise(b' {"checkpoint":"' + b'abc\x00\xff' * 10000 + b'"}\n')

    def test_existing_output_and_source_are_never_overwritten(self):
        source, archive, restored, manifest = self.exercise(b"original")
        for path in (source, archive, restored):
            before = path.read_bytes()
            with self.assertRaises((ValueError, FileExistsError)):
                codec.restore(archive, manifest, path)
            self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(FileExistsError):
            codec.pack(source, archive)

    def test_truncation_corruption_trailing_bytes_fail_and_cleanup(self):
        source, archive, restored, manifest = self.exercise(b"lots of repeated text" * 100)
        good = archive.read_bytes()
        for number, bad in enumerate((good[:-1], good + b"trailing", good[:120] + bytes([good[120] ^ 1]) + good[121:])):
            target = self.root / f"bad{number}"
            archive.write_bytes(bad)
            with self.assertRaises((ValueError, codec.lzma.LZMAError)):
                codec.restore(archive, manifest, target)
            self.assertFalse(target.exists())
        self.assertEqual(source.read_bytes(), b"lots of repeated text" * 100)

    def test_wrong_manifest_fails_and_cleanup(self):
        _, archive, _, manifest = self.exercise(b"known")
        for field, value in (("source_sha256", "0" * 64), ("source_bytes", 6), ("archive_sha256", "1" * 64)):
            bad = copy.deepcopy(manifest)
            bad[field] = value
            target = self.root / field
            with self.assertRaises(ValueError):
                codec.restore(archive, bad, target)
            self.assertFalse(target.exists())

    def test_oversized_header_and_block_rejected_before_allocation(self):
        _, archive, _, manifest = self.exercise(b"bounded" * 100)
        good = archive.read_bytes()
        header_offset = len(codec.MAGIC)
        header_size = codec.struct.unpack(">I", good[header_offset:header_offset + 4])[0]
        block_offset = header_offset + 4 + header_size
        variants = [good[:header_offset] + codec.struct.pack(">I", 2 ** 32 - 1) + good[header_offset + 4:],
                    good[:block_offset] + codec.FRAME.pack(2 ** 32 - 1, 1, bytes(32)) + good[block_offset + codec.FRAME.size:]]
        for index, bad in enumerate(variants):
            archive.write_bytes(bad)
            target = self.root / f"oversize{index}"
            with self.assertRaises(ValueError):
                codec.restore(archive, manifest, target)
            self.assertFalse(target.exists())

    def test_pack_refuses_same_source_and_invalid_chunk(self):
        source = self.root / "original"
        source.write_bytes(b"keep")
        with self.assertRaises(ValueError):
            codec.pack(source, source)
        for chunk in (0, codec.MAX_CHUNK + 1):
            with self.assertRaises(ValueError):
                codec.pack(source, self.root / "archive", chunk_bytes=chunk)
        self.assertEqual(source.read_bytes(), b"keep")
        self.assertFalse((self.root / "archive").exists())


if __name__ == "__main__":
    unittest.main()
