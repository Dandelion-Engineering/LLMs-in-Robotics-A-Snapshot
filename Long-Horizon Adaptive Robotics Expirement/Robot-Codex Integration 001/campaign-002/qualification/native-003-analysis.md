# Native 003 — strict timing failure retained

The six-run native qualification **failed**. Stock-1 exceeded both unchanged timing gates: maximum lag **100.1493 ms** (strictly below 100 ms required) and **2/59 bad one-second RTF windows (3.3898%)** (strictly below 1% required). Its independent reference task succeeded, as did the other five tasks. That does not change the suite’s **invalid / unknown** disposition. Final qualification and scoring remain blocked; no unchanged retry is recommended.

The [official queue receipt](native-003-queue.json) records `20260928T000132806431Z-9dde72d5`, `succeeded` with an actual integer exit 0, from 00:01:33.046023 to 00:09:38.985302 UTC on September 28, 2026. A fresh read-only replay of the full independent assessor exactly matched the [retained assessment](native-003-assessment.json), including all 657 frozen source identities, archive, per-host source receipts, task outcomes, timing ledgers and resource gates. All nine production harness modules still match dev009. The [analysis JSON](native-003-analysis.json) binds receipt, manifest, dev013 snapshot/archive, assessor sources, every host result, journal and binary ledger by SHA-256.

## All six references

| Run | Reference task | Strict timing | Max lag (ms) | Bad / full windows | Max sample gap (ms) | Memory peak (MiB) |
|---|---|---|---:|---:|---:|---:|
| stock-1 | success | **fail** | 100.1493 | 2/59 | 99.7698 | 1068.6758 |
| home-1 | success | pass | 43.2500 | 0/99 | 41.9787 | 1079.6484 |
| stock-2 | success | pass | 66.0185 | 0/59 | 67.5979 | 1044.1562 |
| home-2 | success | pass | 48.1848 | 0/99 | 40.4853 | 1076.7891 |
| stock-3 | success | pass | 48.4368 | 0/59 | 40.1248 | 1075.4336 |
| home-3 | success | pass | 51.8218 | 0/99 | 45.7844 | 1074.5977 |

All six resource, collector and scheduling gates pass. No cyclic collection occurred during any measured loop; every run restored the prior collector configuration and records one later collection. Stock-1’s generation0 collection began at 59.1342506s, after terminal 59.1342316s and restoration, and lasted 5.8644ms. Stock-1 memory baseline was 1007.4844MiB, observed peak 1068.6758MiB, and soft limit 1519.4844MiB under the 2048MiB native hard limit. Its largest memory sampling gap was 153.6501ms, below 200ms. The native lifetime commit peak was 1076.5898 MiB. Memory and GC do not explain the failed boundaries.

## The failed intervals

Times below share the retained QPC physics origin. Its Unix anchor estimates 00:01:34.046733 UTC; cross-clock correlation is descriptive, with a 1.3 microsecond QPC bracket at origin, not a later clock-drift guarantee.

| Interval | Wall time | Recorded host thread / process CPU | Evidence |
|---|---:|---:|---|
| Housekeeping 19.543442–19.561059s |17.6171ms|0 /0ms|Includes protected-state `fsync` 13.6827ms.|
| Adapter 19.561491–19.645751s |84.2609ms|15.625 /15.625ms|Includes observation update 55.3924ms and protected-event `fsync` 48.4492ms, with zero CPU in those two nested intervals.|
| Maximum-lag sample 19.6461493s |100.1493ms lag|—|Only 2 ms simulation advanced during the adapter step; existing 17.4852 ms lag plus this step reaches the strict breach.|
| Adapter 23.9327335–24.0181328s |85.3993ms|31.25 /31.25ms|Observation update 57.6852ms contains protected-event `fsync` 23.9608955–24.0127466s:51.8511ms, zero CPU.|

The latter protected-event `fsync` crosses wall 24s. Fresh samples bracket that boundary at `(23.9327265,23.9320)` and `(24.0184960,23.9340)` wall/sim seconds. The unchanged monitor interpolates sim 23.9335687045 at wall 24 and 25.0 at wall 25: RTF 0.9335687045, then catch-up 1.0664312955. Both windows fail. The journal events at the two failed intervals are observation events 226 and 269; no recovery/ownership transition is needed to explain their protected-event writes.

The phase probes wrap the actual synchronous `os.fsync` calls in [instrumented_journal.py](../harness/instrumented_journal.py). [Supervisor observation handling](../../host/supervisor.py) emits that durable event before publishing the latest observation. The source hashes and line references are retained in the JSON. This directly localizes the delayed operations; it does not identify the storage device, driver, filter or scheduler cause.

## Other tails and causal limits

Stock-1 also records SQLite commit 58.5050ms and execute 42.3278ms, public-event `fsync` 54.6762ms, registry `fsync` 51.4562ms, and public-state `fsync` 49.1314ms. Its longest adapter step, 99.3452 ms, contains a 54.4674 ms SQLite commit followed by 14.1669 ms protected-event `fsync`. The failures therefore involve several synchronous durability paths. A SQLite-only PERSIST change would leave the protected-journal calls at both failed boundaries unchanged.

Recorder lock acquisition peaked at 0.0397 ms and evaluator work at 1.4560 ms in stock-1; neither explains its failed intervals. All six runs recorded zero atomic-replace retries. Of stock-1’s 33 full timing-sample gaps above 40 ms, 30 ended before 25 s; the remaining three occurred in 25–30, 30–35 and 50–55 s. The other five references have smaller journal tails. This concentration does **not** establish startup/cache warmup or prove an external process was responsible.

Zero recorded host CPU indicates no credited CPU at the available accounting granularity. An API interval can include I/O waiting and descheduling. There is no retained kernel I/O or context-switch trace to separate them. Nested phase durations overlap, and bounded retained top rows are selected diagnostics; they cannot be summed or treated as a complete operation latency distribution.

## Proportionate next direction

Keep this failure and stop qualification. Do not repeat the unchanged suite to seek a pass. The evidence supports investigating the shared synchronous storage path before another material repair: a fixed, bounded, source-bound non-physics reproduction of the protected/public event, atomic-state `fsync`, and FULL SQLite sequence on the intended storage path, with OS I/O/scheduling attribution if available. Any such workload requires prospective declaration and root authorization; none was launched here.

A storage-path/device or interfering-workload correction is justified only after measurement identifies its contribution. Preserve durability ordering, commit-before-visible evidence, quotas and strict timing thresholds. Off-thread writers or batching would change synchronization and failure behavior and need separate design/parity/failure qualification; these measurements do not validate them. The [PERSIST feasibility decision](recorder-feasibility-002-analysis.md) remains **no adoption**: its mechanical pass did not establish host-tail benefit, and both failed boundaries here are outside SQLite.

After a supported material repair, freeze a new revision and repeat the complete prospective qualification gates. This analysis performs only authenticated read-only replay and adds these two artifacts. It makes no production changes, model calls, scored runs, retry or retroclassification.
