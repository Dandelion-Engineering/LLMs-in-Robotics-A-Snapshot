# Recorder feasibility 002: retain DELETE/FULL

**Mechanical feasibility passed; PERSIST is not adopted for this campaign.** All 14 independent checks, eight fixed counterbalanced rounds and four process-crash recovery checks passed. The campaign will proceed to final qualification using the unchanged dev009 production lineage. This decision is engineering judgment, not a failed mechanical gate or a new performance threshold.

Official job `20260927T235540596512Z-eea4849f` succeeded with integer exit status 0 at `2026-09-27T23:56:02.536998Z`. The 658-source dev011 archive, manifest, result and source bindings were authenticated; the independent assessment and all binary latency summaries were recomputed identically. See the [assessment](recorder-feasibility-002-assessment.json), [official receipt](RCI001-C02-recorder-feasibility-002/official-status.json), and [hash-bound analysis JSON](recorder-feasibility-002-analysis.json).

## All eight rounds

Order was fixed before launch: DELETE, PERSIST, PERSIST, DELETE, DELETE, PERSIST, PERSIST, DELETE. Every round used the same seed 173, 600 synthetic 64×48 RGB/depth frames and 6,000 motion records. Each retained ledger contains 600 image/API calls, 614 native commits and 1,924 native execute calls. Nothing was discarded. Times below are milliseconds; the JSON retains minimum, median, p95, p99, maximum and total for every round.

### Image/API

| Round | Mode | Median | p95 | p99 | Maximum |
|---:|---|---:|---:|---:|---:|
| 1 | DELETE | 3.673 | 4.388 | 5.078 | 9.746 |
| 2 | PERSIST | 3.300 | 4.085 | 4.590 | 5.224 |
| 3 | PERSIST | 3.168 | 3.879 | 4.247 | 8.469 |
| 4 | DELETE | 3.755 | 4.486 | 4.876 | 5.627 |
| 5 | DELETE | 3.764 | 4.818 | 6.447 | 83.317 |
| 6 | PERSIST | 3.362 | 4.068 | 4.568 | 8.530 |
| 7 | PERSIST | 3.590 | 4.410 | 5.034 | 42.982 |
| 8 | DELETE | 3.353 | 4.183 | 4.743 | 6.863 |

### Native commit

| Round | Mode | Median | p95 | p99 | Maximum |
|---:|---|---:|---:|---:|---:|
| 1 | DELETE | 1.736 | 2.174 | 2.613 | 3.134 |
| 2 | PERSIST | 1.842 | 2.268 | 2.702 | 3.482 |
| 3 | PERSIST | 1.760 | 2.138 | 2.497 | 6.868 |
| 4 | DELETE | 1.685 | 2.068 | 2.311 | 2.768 |
| 5 | DELETE | 1.733 | 2.172 | 2.650 | 78.411 |
| 6 | PERSIST | 1.829 | 2.268 | 2.677 | 6.754 |
| 7 | PERSIST | 1.820 | 2.280 | 2.621 | 41.051 |
| 8 | DELETE | 1.542 | 2.068 | 2.433 | 5.147 |

### Native execute

| Round | Mode | Median | p95 | p99 | Maximum |
|---:|---|---:|---:|---:|---:|
| 1 | DELETE | 0.056 | 0.570 | 0.762 | 2.378 |
| 2 | PERSIST | 0.042 | 0.086 | 0.108 | 0.452 |
| 3 | PERSIST | 0.040 | 0.081 | 0.105 | 0.574 |
| 4 | DELETE | 0.054 | 0.583 | 0.707 | 1.394 |
| 5 | DELETE | 0.058 | 0.606 | 0.762 | 11.484 |
| 6 | PERSIST | 0.042 | 0.088 | 0.108 | 0.577 |
| 7 | PERSIST | 0.051 | 0.095 | 0.126 | 0.560 |
| 8 | DELETE | 0.050 | 0.450 | 0.574 | 1.359 |

Image/API durations include encoding, hashing, nested SQL and accounting overhead. Native SQL timings exclude their pre/post file census. These inclusive categories must not be summed.

## Interpretation

Pooled image/API median decreased from **3.656 to 3.350 ms**, and execute median from **0.0542 to 0.0428 ms**. Commit median increased from **1.681 to 1.811 ms**, with p99 **2.613 versus 2.677 ms**. The observed commit maxima remained **78.411 ms for DELETE and 41.051 ms for PERSIST**. Pooled operation summaries are descriptive, not independent experimental replications.

This approximately 21.5-second, 416 KiB database fixture supports a modest API/execute overhead benefit. It does not establish better tail behavior in the long-running physics/model host or explain its separate journal fsync waits. Adopting a new mode would also require production space and finalization qualification. The retained production policy therefore remains DELETE/FULL.

## All four process-crash checks

| Mode | Interruption | Child exit | Recovered committed documents | Exact payloads verified |
|---|---|---:|---|---|
| DELETE | before commit | 23 | stable | Yes |
| DELETE | after commit | 23 | pending, stable | Yes |
| PERSIST | before commit | 23 | stable | Yes |
| PERSIST | after commit | 23 | pending, stable | Yes |

Each original interrupted database/journal set was retained unchanged; SQLite recovery and original hash-checking payload decoding used a copy. The post-commit pending payload was independently verified, including referenced object hashes. The pre-commit fixture used a declared small cache to force the journal. These checks do not certify power-loss behavior.

## Content, space and remaining limits

Original Reader fingerprints matched in every round: 600 image availability records, 12 retained image pairs, 6,000 motion rows, six events and two documents. Source-bound full-input/all-encoded-pair digests also matched; discarded image bytes cannot be independently replayed. FULL readbacks, single-connection operation, SQLite-managed DELETE finalization, authenticated containers and Reader compatibility passed.

Each round observed a 425,984-byte database and 25,136-byte rollback-journal maximum. Maximum observed combined native footprint was 434,736 bytes for DELETE and 451,120 bytes for PERSIST. Observed boundaries and declared allowances do not establish continuous transient peaks or production quota coverage. The fixture excludes physics, model load and simultaneous host journal publication.

Probe 004 remains valid/unknown; probe 003 and the earlier non-CPU smoke stall remain retained failures. Nothing in this comparison proves those historical stalls fixed. No performance-win threshold was predeclared. Final qualification must still establish the unchanged production lineage under its required actual workloads.

JSON SHA256: `fa2bee5a3cf5118c27bf2034636995aa00c391bb9571b6040444004d34a6ab5c`. The JSON binds the official receipt, assessment, manifest, frozen archive, every round result/timing ledger, all recovery inventories and the unchanged production source lineage.
