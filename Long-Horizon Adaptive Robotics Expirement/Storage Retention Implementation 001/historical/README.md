# Historical r4 exact-byte codec prototype

This is a bounded qualification, not a migration. Original r4 event/motion files remain in place. The historical format preserves bytes directly: JSON key order, number spelling, duplicate keys, whitespace, line endings, Unicode spelling and non-JSON bytes do not change. No downsampling, event selection or numerical conversion occurs.

The [measured result](Results.md) passed: eight exact roundtrips, 95.842% smaller combined storage and matching diagnostic/continuity output on the bounded semantic case. The official successful queue receipt and detailed records are linked there.

The implementation uses Python's standard-library LZMA2/XZ compression in independent blocks of at most 8 MiB. Repeated nearby telemetry/model/checkpoint byte strings compress without interpreting their scientific meaning. This is a simpler historical compatibility option than normalizing and then attempting to recreate an original JSON serialization. It does not implement a shared cross-run object store.

## Files and use

- `raw_codec.py`: pack, authenticated streaming byte reader and exclusive-output restore.
- `test_raw_codec.py`: arbitrary-byte and failure-path tests.
- `qualify.py`: fixed representative read-only qualification; heavy execution must use the shared compute queue.
- `manifests/`: small source/archive size, SHA-256, chunk and timing records, suitable for Git.
- `archives/`: ignored bulk prototype containers; originals are still authoritative.
- `scratch/`: ignored, required empty before and after qualification; holds at most one temporary restored file.
- `qualification.json`: detailed measured coverage, sizes, exact comparisons, timings and equivalence.
- `equivalence-original.json` / `equivalence-restored.json`: complete deterministic diagnostic/continuity output pair for the bounded timeout/restart case.
- `queue-receipt.json`: official terminal state; outputs are evidence only when this is `succeeded` with `exit_status=0`.
- `check_after_retirement.py` and `pre-retirement-input-identities.json`: separately queued original-input numerical/continuity replay after root-owned image retirement, with immutable pre-retirement source/expectation hashes. Its new report and receipt must be authenticated separately; the original codec qualification is never rewritten.
- `post-image-retirement-equivalence.json` and `post-image-retirement-queue-receipt.json`: passed replay after the completed retirement continuation, authenticating unchanged original inputs/methods and equal complete diagnostic/qualified-continuity outputs on A2 C14. The replay's official job is `20260927T030240284878Z-ac1558a0`, succeeded with exit status 0.

From the project root, with output paths that do not exist:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Storage Retention Implementation 001/historical/raw_codec.py" pack "PATH/TO/ORIGINAL/events.jsonl" "NEW/LOCATION/events.r4raw"
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Storage Retention Implementation 001/historical/raw_codec.py" restore "NEW/LOCATION/events.r4raw" "NEW/LOCATION/events.r4raw.json" "NEW/RESTORE/events.jsonl"
```

The pack CLI creates an adjacent `.json` manifest. Qualification instead stores manifests in its versioned `manifests/` directory. Keep the manifest independently with provenance; it contains the original and compressed SHA-256 digests. An archive alone has internal checks but is not an independently authenticated record. A restore refuses existing outputs and the manifest's original source path. It removes its newly-created incomplete output if validation fails. An interrupted pack can leave a partial archive; it is unqualified until full manifest-backed restore succeeds.

The Python `read_chunks(archive, manifest)` API emits original byte blocks. Its caller must exhaust the iterator to verify the terminal full-file and archive digests. `restore` always exhausts it, verifies before returning, and fsyncs the completed file. Frozen path-based tools need a restored ordinary file with their expected filename in a separate directory; they do not natively read `.r4raw`. This prototype deliberately does not intercept or change old tools.

## Format and bounds

The container starts with magic `R4RAW001` plus a newline, a four-byte big-endian JSON header length, and a small version/chunk/preset header. Each frame has uncompressed length, compressed length, SHA-256 of uncompressed bytes, and one independent XZ stream. A zero-length terminator precedes the total uncompressed length and complete original SHA-256. The sidecar authenticates the entire container and original byte count/digest. Trailing bytes, truncation, malformed sizes, mismatched blocks, excess decompression output and wrong manifests fail closed.

No source-sized memory buffer is needed for packing/restoration. Blocks are at most 8 MiB; compressed input is capped at raw size plus 1 MiB; the decoder has a 64 MiB memory limit and an output cap of the declared raw size plus one byte. Full diagnostic comparison intentionally materializes one bounded case's parsed events/motion, separately from codec memory requirements.

Disk use during qualification is cumulative retained prototype archives plus **one** full-size restored source at a time, plus small reports/manifests. There is no second campaign copy. Source and restored files are compared block by block as bytes, then matched by SHA-256; source size and modification time must also remain unchanged. The temporary restored file is removed after the comparison. The report distinguishes the maximum single restored file from the measured cumulative archive-plus-restore peak, both logical byte counts rather than filesystem allocation measurements.

## Coverage and interpretation

Four predetermined cases cover baseline/A1/A2/A3, the longest audited baseline event stream, long A1/A3 streams, model calls, restarts, late replies, partial/failure outcomes and the A2 C14 30-second model timeout. All eight complete event/motion files are packed and restored. Per-type maximum record sizes and exact checkpoint/file content maxima are recorded from these runs, including full input payloads; these maxima are not global census claims.

For A2 C14, the unchanged Runtime 004 `diagnostics.analyze` and Investigation 005 `continuity.extract` run once using original events/motion and again using reconstructed events/motion. Event payload/parent/clock validation also runs on each version, and continuity uses independently loaded frozen qualification context. Both reconstructed arrays are read from restored files, with the event scratch file removed before the motion scratch file is created. Only the diagnostics generation timestamp is excluded from equality. Result/manifest inputs and aggregate-analysis inputs remain unchanged; this job does not rerun whole-campaign aggregate analysis. Exact byte equality for every representative means the original serialized data is retained, not that the science or sensors have been independently validated.

Full historical migration would still require an explicit decision, a complete per-file conversion/restore/hash manifest, tested operational availability for all frozen readers, interruption/recovery handling and planned temporary space. This bounded ratio must not be presented as a measured all-r4 saving. Until migration is separately authorized and qualified, originals remain authoritative and no event/motion deletion is permitted by this prototype.
