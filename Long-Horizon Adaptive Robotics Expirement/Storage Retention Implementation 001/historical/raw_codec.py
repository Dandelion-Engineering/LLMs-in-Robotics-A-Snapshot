"""Versioned, bounded, exact-byte historical archive. Never mutates its source.

Each <=8 MiB byte block is an independent XZ/LZMA2 stream; envelopes authenticate
uncompressed blocks and the complete original. A small sidecar also authenticates
the container. This is byte compression, not JSON normalization or lossy sampling.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import struct
import time

MAGIC = b"R4RAW001\n"
FORMAT = "r4-raw-chunk-lzma2-1"
MAX_CHUNK = 8 * 1024 * 1024
FRAME = struct.Struct(">II32s")
FOOTER = struct.Struct(">Q32s")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(MAX_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def pack(source, archive, chunk_bytes=MAX_CHUNK):
    source, archive = Path(source).resolve(), Path(archive).resolve()
    if source == archive or not 256 <= chunk_bytes <= MAX_CHUNK:
        raise ValueError("Invalid source/output or chunk size")
    before = source.stat()
    header = {"format": FORMAT, "chunk_bytes": chunk_bytes, "preset": 1}
    header_raw = canonical(header)
    h, count, chunks = hashlib.sha256(), 0, 0
    started = time.perf_counter()
    with source.open("rb") as src, archive.open("xb") as dst:
        dst.write(MAGIC + struct.pack(">I", len(header_raw)) + header_raw)
        for raw in iter(lambda: src.read(chunk_bytes), b""):
            compressed = lzma.compress(raw, format=lzma.FORMAT_XZ, preset=1)
            dst.write(FRAME.pack(len(raw), len(compressed), hashlib.sha256(raw).digest()))
            dst.write(compressed)
            h.update(raw)
            count += len(raw)
            chunks += 1
        dst.write(FRAME.pack(0, 0, bytes(32)))
        dst.write(FOOTER.pack(count, h.digest()))
        dst.flush()
        os.fsync(dst.fileno())
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or count != before.st_size:
        raise ValueError("Source changed during packing; archive is not qualified")
    return {"format": FORMAT, "source_path": str(source), "source_bytes": count,
            "source_sha256": h.hexdigest(), "source_mtime_ns": before.st_mtime_ns,
            "archive_name": archive.name, "archive_bytes": archive.stat().st_size,
            "archive_sha256": digest(archive), "chunk_bytes": chunk_bytes,
            "chunks": chunks, "pack_seconds": time.perf_counter() - started}


def read_chunks(archive, manifest):
    """Yield original bytes; caller MUST exhaust generator to authenticate totals.

    Decompression output is bounded to one declared block plus one byte. No JSON
    parsing, float conversion, Unicode transcoding, or newline handling occurs.
    """
    ah, rh, total, chunks = hashlib.sha256(), hashlib.sha256(), 0, 0
    if manifest.get("format") != FORMAT:
        raise ValueError("Unsupported sidecar format")
    with Path(archive).open("rb") as src:
        def take(n):
            raw = src.read(n)
            if len(raw) != n:
                raise ValueError("Truncated archive")
            ah.update(raw)
            return raw
        if take(len(MAGIC)) != MAGIC:
            raise ValueError("Unsupported archive magic")
        length = struct.unpack(">I", take(4))[0]
        if not 1 <= length <= 16384:
            raise ValueError("Oversize header")
        header = json.loads(take(length))
        if (set(header) != {"format", "chunk_bytes", "preset"} or header["format"] != FORMAT
                or header["preset"] != 1 or type(header["chunk_bytes"]) is not int
                or not 256 <= header["chunk_bytes"] <= MAX_CHUNK):
            raise ValueError("Invalid archive header")
        while True:
            raw_size, compressed_size, expected = FRAME.unpack(take(FRAME.size))
            if raw_size == 0:
                if compressed_size or expected != bytes(32):
                    raise ValueError("Malformed terminator")
                break
            if not 1 <= raw_size <= header["chunk_bytes"] or not 1 <= compressed_size <= raw_size + 1024 * 1024:
                raise ValueError("Invalid block size")
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=64 * 1024 * 1024)
            raw = decoder.decompress(take(compressed_size), max_length=raw_size + 1)
            if len(raw) != raw_size or not decoder.eof or decoder.unused_data:
                raise ValueError("Invalid bounded compressed block")
            if hashlib.sha256(raw).digest() != expected:
                raise ValueError("Block SHA-256 mismatch")
            rh.update(raw)
            total += len(raw)
            chunks += 1
            yield raw
        expected_total, expected_hash = FOOTER.unpack(take(FOOTER.size))
        if src.read(1):
            raise ValueError("Trailing archive bytes")
    if (total != expected_total or rh.digest() != expected_hash or total != manifest["source_bytes"]
            or rh.hexdigest() != manifest["source_sha256"] or ah.hexdigest() != manifest["archive_sha256"]
            or chunks != manifest["chunks"] or header["chunk_bytes"] != manifest["chunk_bytes"]
            or Path(archive).stat().st_size != manifest["archive_bytes"]):
        raise ValueError("Archive/original manifest authentication failed")


def restore(archive, manifest, output):
    archive, output = Path(archive).resolve(), Path(output).resolve()
    if output in (archive, Path(manifest["source_path"]).resolve()):
        raise ValueError("Refusing to restore onto archive or historical source")
    started, created = time.perf_counter(), False
    try:
        with output.open("xb") as dst:
            created = True
            for raw in read_chunks(archive, manifest):
                dst.write(raw)
            dst.flush()
            os.fsync(dst.fileno())
    except BaseException:
        if created:
            output.unlink()
        raise
    return {"restored_bytes": output.stat().st_size, "restore_seconds": time.perf_counter() - started,
            "restored_sha256": digest(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pack")
    p.add_argument("source")
    p.add_argument("archive")
    p = sub.add_parser("restore")
    p.add_argument("archive")
    p.add_argument("manifest")
    p.add_argument("output")
    args = parser.parse_args()
    if args.command == "pack":
        sidecar = Path(args.archive + ".json")
        if sidecar.exists():
            raise FileExistsError(sidecar)
        result = pack(args.source, args.archive)
        with sidecar.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    else:
        result = restore(args.archive, json.loads(Path(args.manifest).read_text(encoding="utf-8")), args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
