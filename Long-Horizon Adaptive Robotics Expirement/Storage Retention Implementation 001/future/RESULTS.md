# Sustainable recorder qualification result

Generation **qualification-007**, format **sustainable-evidence-3**, completed in official queue job `20260927T025222061809Z-29ab4d01` with `state=succeeded`, `exit_status=0`. The report, receipt, code/source hashes, retained image inputs and admission seal are in this directory.

## Measured campaign projection

The projection covers 156,600 task-seconds and 264 runs at the maximum measured real pilot core rate. Decimal GB are used. It is a projection for r4-shaped traffic, not a completed campaign or a guarantee for an unseen raw-image-heavy workload.

| Category | Bytes | GB |
|---|---:|---:|
| Core plus run overhead | 14,334,881,438 | 14.335 |
| Imagery and metadata | 6,630,105,216 | 6.630 |
| Compact provenance | 1,000,000,000 | 1.000 |
| Selected packages | 4,000,000,000 | 4.000 |
| Development | 2,000,000,000 | 2.000 |
| Permanent total | 27,964,986,654 | 27.965 |
| Peak including 25% uncertainty and 2 GB temporary space | 36,956,233,318 | 36.956 |

Both the 30 GB permanent target and 40 GB peak ceiling passed. The largest measured live database was 57,683,968 bytes; largest measured finalization overlap was 103,028,031 bytes. Hard bounds are 512 MB live database and 1.025 GB overlap for one queued writer. Readers restore in memory, with a 512 MB buffer plus SQLite copy and a separate 64 MB encoded cache, and create no temporary disk file.

## Qualification coverage

All **20 tests** passed. Every sampled event and numeric row reconstructed exactly, including timing, gaps, signed zero, arbitrary fields, exact model/file strings and ordered telemetry references. Frozen diagnostics matched on all ten windows; two complete event chains matched the current continuity reader without upgrading unknown qualification context. The 1,200-second synthetic stream covered 120,000 numeric samples, 12,001 pair metadata records, restart, missing sample, stale response, repeated candidate input, 240 model-call fixtures and 120 checkpoint fixtures. Synthetic bytes were excluded from the projection.

| Real replay window | Seconds | Finalized core bytes | Bytes/task-second |
|---|---:|---:|---:|
| nominal | 29.950 | 2,697,464 | 90,066 |
| many-model-calls | 29.896 | 2,723,414 | 91,096 |
| candidate-input-repetition | 29.904 | 2,705,582 | 90,476 |
| model-advisory | 30.000 | 2,501,519 | 83,384 |
| restart-continuity | 29.960 | 2,348,407 | 78,385 |
| checkpoint-file-activity | 30.000 | 1,666,083 | 55,536 |
| delayed-stale-packets | 29.936 | 2,110,724 | 70,508 |
| long-run | 29.988 | 2,550,925 | 85,065 |
| high-observation-volume | 29.984 | 2,471,961 | 82,443 |
| large-input-failure | 29.972 | 2,388,341 | 79,686 |

All 30 image input pairs are explicit hash-checked members of the retained manifest. Their within-retained path quantiles are engineering size samples, not a scientific representative sample.

## Native component boundary

Two real ten-second workcell passes executed the same two fixed joint commands, one without recording and one with the new backend. Each delivered 99 live pairs with zero misses; physical state, action admission/feedback and protected scoring matched exactly. One matched frozen/native raw request preserved exact candidate wire bytes and capture/delivery metadata. Core-quota failure reached the supervisor. No full-stream image files were created by the new backend.

Both passes met the unchanged frozen host-timing tolerance. Maximum lag was 2.0 ms in the reference and 33.7 ms with recording; no complete one-second window was outside RTF tolerance. This measures a bounded component fixture, not full task/restart/inference timing. Finalization happens after the timed fixture.

Whole-task/inference/restart timing and a legitimate new scientific release remain unqualified: `runtime_timing_qualified=false`, `frozen_release_bound=false`. Historical full tasks and the scored campaign were not rerun. No model calls or new scored attempts were made.

## Capacity and admission

The actual sealed admission CLI **rejected a large batch with exit status 2** at 2026-09-27 03:40:02 UTC. [admission-check.json](admission-check.json) records the subprocess command, observed return code and result hash; [admission-result.json](admission-result.json) contains the decision. Its three reasons are the 150 GB project evidence ceiling, missing whole-task/inference/restart timing qualification, and missing frozen scientific-release binding.

[capacity-census.json](capacity-census.json) derives **219,064,795,788 bytes (219.065 GB)** across 480,296 whole-experiment paths from the completed postflight census, whose official queue job `20260927T031016337738Z-487a1eaf` succeeded with exit 0. Both source census and receipt hashes are bound. This intentionally conservative scope includes code, models and repeated hardlink pathname sizes as well as scientific artifacts; the source Evidence subtree alone is 175,841,527,628 bytes (175.842 GB). Adding the qualified permanent campaign projection gives 247,029,782,442 bytes (247.030 GB), above the 150 GB ceiling.

The CLI measured 424,143,765,504 free bytes on the actual output volume, leaving 387,187,532,186 bytes after the projected campaign peak. The 100 GB free reserve and the 40 GB campaign peak gate pass. Those passing checks do not override the project ceiling or either missing scientific gate. [admission-input.json](admission-input.json) fixes the counted output scope, authenticated census and zero outstanding reservations. These records document this admission attempt; new admission requires a census no more than one hour old and a new live volume observation.

## Preserved unsuccessful iterations

Generation 003 passed semantics but failed the budget (79.57 GB permanent / 101.46 GB peak). Optimization generations 004 and 005 are bounded development comparisons. Generations 002 and 006 were canceled for retained-input and durability corrections. Their reports, receipts, logs and relevant source snapshots remain visible under `history/` and the named canceled/failed files; none is substituted for the final qualification.
