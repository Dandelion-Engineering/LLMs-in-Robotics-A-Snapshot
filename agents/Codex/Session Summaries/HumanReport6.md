# Session 6 — storage audit and retention recommendations

September 26, 2026. Randy's new Audit Storage chat requested a recursive storage audit and recommendations only, with no modification, deletion, movement or compression of existing project data. The audit is complete; cleanup and a new simulation batch remain unapproved.

Start with [Sustainable Retention](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Storage%20Audit%202026-09-26/Sustainable%20Retention.md), then the [detailed audit](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Storage%20Audit%202026-09-26/README.md). Randy rejected the initial archive-first recommendation because external capacity is finite. The final recommendation reduces retained imagery and repeated event storage, with explicit information tradeoffs and a bounded future budget. Compact metadata tables retain directory totals, all files at least 1 MB, file categories, physical identity checks, verified asset hashes, viewer dependencies, estimates and source pointers.

## Findings

- Logical file sizes total433.084 GB (403.340 GiB) across2,782,462 files. Known repeated hardlinks account for 25.536 GB; adjusted logical content is407.548 GB. This is not a full NTFS physical-allocation census.
- The final r4 release occupies363.997 GB. Across the project, depth/RGB frames account for 250.187 GB and event/motion streams136.350 GB. Full10 Hz camera/depth persistence,100 Hz motion and repeated uncompressed event payloads explain the growth.
- Large model copies already share hardlinks. Removing their extra paths will not recover25.5 GB. The checked distinct identical assets offer only about 9.417 MB allocated savings.
- Current007/Explorer presentation assets and their referenced images/depth use about 6.200 GB. Keeping the entire12 selected raw runs instead uses15.143 GB of raw evidence and preserves their raw links/rebuild inputs.
- A bulk archive is not the growth solution. Retaining the 3.061 GB of current viewer images and retiring the other r4 RGB/depth could reclaim 230.152 GB without moving it elsewhere. This preserves every event/motion/resource/result file but sacrifices arbitrary pixel/depth reassessment. Actual dependency verification, an availability amendment and approval must precede removal. Extra failure windows would reduce savings by their bytes.
- Full accounting of all 264 event streams found 100.582 GB observations and 17.110 GB candidate inputs. A corrected sample of 2,304 observations measured 230,400 telemetry row occurrences but only 26,328 distinct rows within windows. Reference-encoding scenarios imply another 69–79 GB observation-only saving, extrapolated from fixed samples; no codec or compression was tested. Exact original-byte reconstruction must be demonstrated before originals can be replaced.
- Proposed future limits are a 30 GB batch target, 40 GB admission ceiling, 150 GB project-evidence ceiling after reduction/normalization, and 100 GB C: reserve. These require measured qualification and a finite cross-campaign retention promise, not indefinite accumulation. External SSD space is optional bounded working/reference capacity.

## Boundaries and verification

No existing experimental evidence, code, scientific record, model asset, viewer, configuration or Git history was changed. No simulation, inference, compression trial or old artifact rebuild ran. The only work products are new audit and session records plus normal additive coordination/closeout metadata.

The census included hidden Git and ignored files with no traversal errors. All files at least1 MB and576 representative frame files received file-identity/allocation checks. The preliminary Windows directory-entry identity/allocation fields were unusable; they were discarded and corrected by explicit handle/file-identity checks. Final claims distinguish complete logical counts from sampled/partial physical verification.

All three read-only compute jobs have official `state=succeeded`, `exit_status=0` receipts: asset hashing `20260927T000230038787Z-80b2721b`; complete event-byte/type profiling `20260927T002013922654Z-3b118f4b`; corrected telemetry sampling `20260927T002524797060Z-a 5b24b6b`. Asset hashing read 38.246 GB. Event accounting read 121.556 GB across all 264 r4 streams. The first optional telemetry sampler expected the wrong nested schema and returned no samples; a separate bounded correction used `telemetry_history.samples`. No savings estimate uses the empty sample, and full event accounting was unaffected.

Viewer checks authenticated 12 manifests and checked 33,332 original RGB/depth paths and sizes, with no missing/size mismatch; image-content hashes were not all recalculated. No exhaustive raw-data hash/duplicate scan was performed. Temporary metadata created by this audit was compacted to small tables after exact count/byte reconciliation; original sources were untouched.

Original manifests and readers bind paths as well as hashes; several reject symlinks/cross-volume playback. A lossless migration needs a versioned compatibility/restoration layer and full roundtrip checks. Selective frame retirement needs explicit recorded capability loss. Never rewrite original manifests or treat sampled viewers as complete raw evidence. The smaller 19.099 GB compact-records-plus-selected-runs option is documented but would lose independent nonselected diagnostic recalculation and historical model/checkpoint content; it is not the default recommendation.

## Resume and closeout

Await Randy's review in the active Audit Storage chat. Do not delete/move/compress evidence, change logging/retention, or launch another campaign merely because a new automated session starts. The original experiment chat remains active as requested.

The existing context summary and workspace README were deliberately left unchanged: this task's explicit prohibition on overwriting existing project data takes precedence over the generic rewrite-at-closeout instruction. This report and the new audit-chat handoff are the additive session6 continuity record.

The audit claim moves to `Work/Done/storage-audit-and-retention-recommendations.md`. Final inbox and path-scoped dry run precede normal commit/push. This report is pre-commit; the actual closeout result establishes publication. The lock owned by this session contains `2026-09-26T16:57:53.2796636-07:00`; remove only that owned lock after successful closeout. No automation changes were made.
