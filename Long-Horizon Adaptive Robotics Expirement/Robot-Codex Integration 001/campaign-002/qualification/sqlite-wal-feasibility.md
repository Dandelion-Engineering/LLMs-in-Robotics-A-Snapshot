# Conditional SQLite WAL feasibility assessment

Recorded 2026-09-27. **Read-only design assessment: no implementation, adoption, benchmark, or qualification.** Consider this option only if the next retained diagnostic localizes the bridge stall to SQLite commit waiting. No source, SQLite setting, durability rule, ordering rule, quota, or timing criterion was changed by this assessment.

WAL with `synchronous=FULL` is a plausible infrastructure option, but it requires explicit finalization and storage safeguards. It is not a one-line timing fix and has no demonstrated timing benefit for this apparatus.

## Current implementation and compatibility obligations

- **Durability and ordering:** [Recorder](../../../Storage%20Retention%20Implementation%20001/future/recorder.py) currently uses `journal_mode=DELETE` and `synchronous=FULL`. Each event commits its referenced objects before updating `last_durable_event`; image availability changes and documents also commit before returning. [FutureEvidence](../../../Storage%20Retention%20Implementation%20001/future/runtime_adapter.py) serializes recorder access with its owner lock. A prospective WAL configuration must retain the single connection, owner lock, transaction boundaries, exact payloads, availability semantics, and commit-before-return behavior. FULL syncs every WAL commit; NORMAL or OFF would weaken the required durability contract and are excluded. FULL still permits commit stalls. [Official synchronous guarantees](https://www.sqlite.org/pragma.html#pragma_synchronous)

- **Final container:** `Recorder.close()` currently flushes pending motion, marks completion, closes SQLite, hashes and compresses the database, verifies the exact restored bytes, durably publishes gzip and manifest, then removes the working database. `Reader` restores gzip bytes into an in-memory database with `deserialize`. SQLite documents that a WAL-mode deserialized database cannot be used. Prospective finalization must complete and verify checkpointing, successfully transition through SQLite to `journal_mode=DELETE`, then retain the existing hash/gzip/publication sequence. Clean close alone does not clear persistent WAL mode. Do not patch reader input headers: retain exact restored-byte authentication. Existing logical evidence can remain exact, while SQLite physical bytes/hashes may differ between journaling implementations. [Official deserialize limitation](https://www.sqlite.org/c3ref/deserialize.html), [persistent WAL mode](https://www.sqlite.org/wal.html#persistence_of_wal_mode)

- **Interrupted recovery:** Preserve the matching main database and WAL after interruption; committed records can reside only in WAL. Use SQLite recovery before any finalization, preserve failed/incomplete recording status, and never publish a gzip of only the main database while committed WAL frames remain. SHM is reconstructible rather than durable content, but it remains part of live storage accounting. Do not manually delete or detach WAL from its database. [Official WAL file lifecycle](https://www.sqlite.org/walformat.html)

- **Checkpoint and storage accounting:** `_physical_guard()` currently compares `page_count * page_size` against the database/container limit; that excludes WAL and SHM. A prospective implementation must bound and account for database, WAL, SHM, gzip temporary output, and publication overlap without increasing the declared evidence quotas or reserve allowances. `journal_size_limit` limits retained size after reset; it does not impose a peak-space ceiling. Checkpoint return codes and frame counts must establish completion; busy, partial, or failed checkpoints cannot authorize publication. Default automatic checkpointing runs on the committing thread and can introduce occasional long commits. Disabling it without a bounded alternative permits WAL growth. [Official journal-size limit](https://www.sqlite.org/pragma.html#pragma_journal_size_limit), [checkpoint semantics](https://www.sqlite.org/c3ref/wal_checkpoint_v2.html), [WAL performance](https://www.sqlite.org/wal.html#performance_considerations)

## Exact local SQLite version evidence

Read-only command executed from `C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics` on 2026-09-27:

```powershell
& .\venv\Scripts\python.exe -X utf8 -B -c 'import sqlite3; print(sqlite3.sqlite_version)'
```

Observed standard output, exit code 0:

```text
3.49.1
```

This reports the SQLite runtime linked to the project Python interpreter; it was not a benchmark or a database configuration change. SQLite's current official documentation describes a WAL-reset corruption bug through 3.51.2, fixed in 3.51.3 and selected backports. Its documented trigger requires separate connections concurrently writing/checkpointing. The current owner-locked single connection lacks that trigger. **Retain the one-connection constraint; a separate-connection background checkpointer is outside this feasibility option.** Any engine upgrade or concurrency expansion would require a separately authorized frozen dependency change and fresh qualification. [Official WAL-reset bug description](https://www.sqlite.org/wal.html#the_wal_reset_bug)

## Existing sensor-worker comparison

[SensorWorker](../../../Runtime%20004/sensor_worker.py) uses one dedicated worker and exactly one outstanding future. Rendering, compression, and optional evidence-file writing finish before a successful result becomes available; a failed write remains a failed job. This bounds work without an accumulating writer queue. These optional file writes do not establish SQLite FULL transaction durability.

The [current host adapter](../../host/run_host.py) requests sensor results with image file paths disabled. After polling, it synchronously invokes `LiveSensorBridge.observe()` before updating the public observation. The bridge encodes PNG/depth and commits the recorder's image/availability state on that path. Moving recorder work to a worker would require preserving completion and failure ordering and is a separate prospective change, not a consequence of WAL configuration.

**Decision remains open pending diagnostic localization.** A compatible prospective implementation would still require recovery, final-format, ordering, quota, and unchanged strict-timing qualification before use. This note provides no campaign admission or scientific result.
