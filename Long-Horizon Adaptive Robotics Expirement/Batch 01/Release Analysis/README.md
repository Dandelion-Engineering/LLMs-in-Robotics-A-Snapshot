# Finalized result selection

`collect_results.py` converts the complete protected release plus finalized canonical assessments into the flat input expected by `Runtime/protocol.py analyze`. It creates no seeds and runs no policy. No scored results existed when this helper was implemented.

For every retained terminal attempt it verifies release/manifest binding, the batch's exact terminal hash, explicit finalization and successful official receipt hash, raw result identity, the canonical original's terminal hash and one unambiguous correction chain. Canonical outcomes and clock metrics control the selected result. A raw `independent_outcome.success` cannot override a later correction; unknown clocks remain null. Wrapper-level or original infrastructure invalidity is retained for whole paired-block exclusion. Original evidence is never rewritten.

Missing terminal attempts are explicitly listed and do not become failures. `--complete` refuses any missing terminal attempt. Corrupt, changed or unfinalized evidence fails selection rather than disappearing from the denominator. The output contains `results` for the analyzer and separate exact provenance and missingness. It must be a fresh file.

After all original attempts have official finalization, run from the project root (through the shared queue when part of sustained evidence processing):

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Analysis/collect_results.py' --release-dir 'Long-Horizon Adaptive Robotics Expirement/Evidence/releases/batch01-eval-r1' --output 'Long-Horizon Adaptive Robotics Expirement/Evidence/releases/batch01-eval-r1/selected-results.json' --complete
```

Then use the unchanged protocol analyzer with that output. Freeze these helper bytes and the public analysis settings before evaluation. Fifteen bounded synthetic checks passed for corrections, disconnected/ambiguous supersession, unknown clocks, wrapper breaches, missing integrity, infrastructure exclusions, missing attempts, development/nonterminal rejection and altered/failed/unfinalized queue evidence. Those checks validate selection behavior, not real experiment results or scientific readiness.

`measure_retention.py --output <fresh-directory>` is a separate queue-only storage inventory. It resolves registered development runs through `Runtime/record_attempt.py:registered_storage`, including legacy C locations and explicitly pinned D locations, and verifies terminal raw result/optional raw manifest identities with `verify_raw_identity`. Existing map result references must agree with exact raw result bytes; corrected outcome labels are not interpreted. It does not scan unregistered directories or select evaluation evidence. Registrations without a completed raw result remain explicit. Duplicate run/result identities or assigned paths, mismatched identities/hashes, symlinks and Windows reparse components are rejected. Registration manifests, canonical map bytes and helper dependencies are retained and checked for stability. No evidence is moved, deleted or rewritten.

The `robot-retention-inventory-1.0` summary and existing rate fields remain unchanged: the planning rate is the larger of 3 MiB/task-second or the largest measured completed-bundle rate, applied to 156,600 seconds plus a 50 GiB reserve. `free_bytes` still measures the experiment/project volume; D development inputs confer no scored D storage support. File-size inventories retain failures and do not hash every frame or re-score historical outcomes. Future rates are not guaranteed, and each evaluation batch still needs current headroom. Eight bounded synthetic tests are prepared in `test_measure_retention.py`; their execution is deferred during dev003 physics. An official queued inventory is still required after review and test execution.
# Retention inventory validation update

The C/D registered-development inventory extension passed eight focused tests in 0.422 seconds under official successful job `20260923T115600352214Z-8e78d523`. Its receipt is retained in `../../Evidence/queue-receipts/`. Actual complete inventory and current capacity verification remain pending after the remaining restart prerequisites; test success supplies no storage-capacity claim.
