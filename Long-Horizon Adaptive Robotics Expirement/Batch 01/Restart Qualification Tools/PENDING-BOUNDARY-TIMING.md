# Integrated boundary-operation timing instrumentation

Status: **integrated after root authorization on 2026-09-23**. Construction002 completed with official receipt `20260923T085627326649Z-366dbd1a`, succeeded/0, before root released the source hold and authorized application. This instrumentation responds to remaining operational timing failures; it makes no claim about their cause. No active physical output was read for implementation.

The exact base is archived verbatim as [run_screen.644ea18c35950a996eba4b031d8dfaddc8163cfa9aee280c2cfea273afa23604.py](source-archive/run_screen.644ea18c35950a996eba4b031d8dfaddc8163cfa9aee280c2cfea273afa23604.py). [The original patch builder](pending_boundary_timing.py) rejects any other source identity and can only create [the reviewed patch, retained under its original name](pending-boundary-timing.patch); it contains no target-write command. Application checked the exact base hash, reviewed patch hash, generated-diff byte equality, and archive bytes before writing the target. The instrumentation-only intermediate source was `ba0dfca14cd75386494ea25242bdd680a7b9cc794790d40ab1965a7c9e709136`; the final source including the separately authorized diagnostic selector is **`7af9eb67b5b367b545682785069859cb9a7cb9a9f2f670d25ebd6894a70ade11`**.

The patch adds one small `try/finally` wrapper and a list in the existing child details. It measures every invocation at both `capture_restart_state` call sites, including repeated cut-candidate probes; the existing `classify_restart(cut)` call; and all seven existing forced `GeometryTrace.sample` calls before transport, before/after cancel, after absence, before dispatch, after admission, and after settled placement. Each record retains:

- The stage and a unique operation/boundary label.
- `wall_start_s`, `wall_end_s`, and `wall_cost_s`, measured with `perf_counter` relative to the existing `loop.start`.
- Absolute simulator `sim_start_s` and `sim_end_s` from the same cell.
- `success`, meaning the wrapped function returned normally; it is not a physical or timing pass predicate.

Calls remain in their current positions with identical arguments. No event, snapshot, physics tick, wait, timing-monitor observation, or geometry sample is removed, reordered, or added. Ordinary per-tick geometry sampling is unchanged. The wrapper preserves return-object identity and propagates the original exception, recording unsuccessful calls in `finally`. No snapshot is moved outside the existing clock. The small timing records are appended in memory under `details['boundary_operation_timings']` and written with the normal terminal details; there is no per-call disk write. Adjacent event-writing costs, the instrumentation append itself, and other unwrapped work are not attributed to these operation durations. Instrumentation adds a small, unmeasured overhead and introduces no pass gate.

[Four bounded synthetic tests](test_pending_boundary_timing.py) originally passed in **0.059 s**. After integration they use the archived base and additionally verify installed wrapper/trial-body AST equality with the reviewed patch. Together with [four diagnostic selector tests](test_diagnostic_selection.py), all **eight tests passed in 0.102 s**. They compile only selected source functions with stub imports, compare complete operation logs and outputs before/after, exercise repeated candidate captures, verify expected operation costs and clocks, preserve partial outputs and exact exception objects at capture/classification/forced-sample failures, retain a per-tick failure without relabeling it, and guard the unchanged `QualificationLoop` AST and target bytes. No Runtime import, physical model, actual physics, or queue was used.

## One original construction trial as a diagnostic

`--diagnostic-trial` is optional and construction-only. It requires exactly one retained original construction ID in the selected destination; it rejects validation, an independent-generator row, a missing/duplicate ID, an empty ID, or a destination mismatch. The selected row and the full 40-trial prospective plan are unchanged. All other **39 original IDs**, across both destinations, are explicitly deferred in original order. Normal full-phase selection remains unchanged.

The parent manifest, child probe/result and terminal summary mark `diagnostic_only: true`, `is_full_phase_screen: false`, `qualification_evidence_eligible: false`, and `execution_scope: single_original_construction_trial_diagnostic`. The child validates this selection/scope and deferred list against the immutable parent manifest before trial execution; it cannot accept a separate diagnostic override on its child CLI. Full-phase physical/timing pass flags are false for diagnostics, while `all_executed_physical_checks_passed` and `all_executed_host_timing_checks_passed` preserve the diagnostic outcome without implying full coverage. Existing extractor/assessor full-phase selection guards were not modified and were checked to reject this diagnostic selection.

The confirmed target `parking1-corner-B-5` is the original family-B n10 construction world/layout seed 901001, main mass 0.1 kg, main sliding friction 1.2, expected fresh public selection B10. Queue through the existing parent authority using a fresh output path:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement\Batch 01\Recovery Qualification\run_screen.py' --phase construction --destination parking1 --diagnostic-trial parking1-corner-B-5 --output 'D:\CodexEvidence\LLMs-in-Robotics\recovery-boundary-timing-001'
```

This implementation task did not submit that command. Inspect diagnostic raw evidence only after its successful official receipt. It is not a replacement construction phase or an untouched validation run.

Patch SHA-256: `ffd85bf3edd5a741f19a87605481468e5114611a257b50112748460fa8c6bea8`.

Builder SHA-256: `024e47d385c91661c7f4c43456def4b0123f89239f8eaa4b63f9fd074df31fba`.

Original regression SHA-256: `92f4fe08ed6b37e8958c799163063733b304ccd09304ebb14da5639d528dad9c`. Post-integration regression SHA-256: `3f5a16af2792f9ca516b5defca2564022ae602b449bf2206a3f799534222c834`. Selector-test SHA-256: `cd1a8439a7bff7ad8164f00949cb36c75fcb91d1b8e4d1e888436a906fed3724`.

To rerun the bounded tests from the repository root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement\Batch 01\Restart Qualification Tools' -p 'test_pending_boundary_timing.py' -v
```
