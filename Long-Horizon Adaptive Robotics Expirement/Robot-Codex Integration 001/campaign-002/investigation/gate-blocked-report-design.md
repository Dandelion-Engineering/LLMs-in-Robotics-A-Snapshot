# Prospective qualification-only investigation path

Design note only. No report was built, no production source was changed, and no running probe004 output was read. The current qualification goal remains active. This path would be useful only if qualification still prevents a scored campaign launch, or as an explicitly labeled interim status artifact.

## Current concrete blockers

The existing empirical builder is correctly restricted to a settled campaign. `build.py:509` calls `validate_plan` and `require_settled` before reading attempt outcomes: the exact twenty-slot plan and twenty terminal dispositions are mandatory. `export_frames.py:89` has the same gate. Neither should be weakened or satisfied with fabricated `not_run` dispositions.

The current presentation also assumes twenty actual disposition rows. `template.html` selects `DATA.runs[0]`, builds episode controls and valid-trial statistics, and describes the allocation as terminal. `qa.py:40` requires exactly twenty rows and the four outcome-independent examples. Passing an empty run list into this template would fail and would leave misleading outcome language. Creating twenty artificial terminal rows would incorrectly claim campaign execution/settlement and could imply that the campaign stopped under a rule that was never triggered.

## Small additive path

Add a separate qualification-only builder and compact template under `investigation/`, producing `qualification-report.html`, `qualification-data.json`, and `qualification-provenance.json`. Reuse the existing immutable Campaign001 count check and qualification-history link preparation. Keep the empirical builder, exporter, and their all-twenty-settled gate unchanged. This is smaller and less error-prone than threading an empty-campaign mode through episode selection, frame export, all-planned bounds, and the empirical QA contract.

Use a distinct schema such as `campaign002-qualification-investigation-1`. Its main state should be `qualification_pending` or a precisely documented `qualification_gate_unmet`; it must not set empirical `complete`, manufacture slot dispositions, or imply that the overall requested experiment has finished. A provisional diagnostic report is compatible with continued repair and qualification.

The qualification-only input contract should require:

1. The explicit completed qualification-history index. Verify every linked artifact's recorded byte count and SHA-256 before presenting its contents. Before opening any assessment, timing metadata, or raw diagnostics, authenticate that attempt's exact official queue receipt as succeeded with integer exit status zero. A queue cancellation before start is displayed from its queue/cancellation receipts only. Preserve each original revision and failed classification.
2. A bounded, hash-recorded account of the scored-launch state from the prospective schedule/registration and the campaign `execution/` intent/queue-receipt inventory. State “no scored launches” only when that account supports zero starts/submissions. Otherwise say “no scored outcomes admitted to this report; launch status unverified.” Absence of twenty terminal dispositions by itself does not prove that nothing launched.
3. The frozen C001 report data, validated as twenty-four scheduled slots, six valid successes, four invalid attempts, and fourteen not-run slots. Link the original C001 investigation and evidence; do not copy or reinterpret it under the new timing policy.

The page can show C001's existing outcome row beside a C002 status card: readiness gate and reason, admitted scored starts/results, latest completed qualification revision, and exact evidence links. A real sealed plan may be described as twenty prospectively scheduled slots, but unexecuted future slots are not fabricated terminal rows. No C002 success fraction, Wilson interval, all-planned empirical bounds, recovery examples, or robot-performance comparison exists without scored data. Apparatus probes, native reference controls, synthetic boundaries, and the actual model smoke remain separate evidence categories.

The status report should preserve the complete failure history and say what remains unresolved. For example, the retained probe003 observation is absence of measured in-loop GC alongside an unresolved sensor-recording bridge delay and failed memory sample spacing. Below-cap memory or restored collector settings do not turn that attempt valid. A later diagnostic pass would not overwrite it. New results, including probe004, enter only after their official terminal success/zero receipt and separate assessment are available.

A focused QA contract should check that there are no scored outcome rows or episode/frame controls, C001 counts remain exact, linked artifacts match their hashes, queue cancellation is not a qualification pass, failed attempts remain failed, and every missing field is visibly unavailable. Static HTML/JavaScript checks and actual browser layout checks remain separate. The report build should still run through the shared queue when authorized; this note does not initiate one.

## Integration of the 23 new recorder timing phases

The frozen `harness/instrumented_recorder.py` declares these additional names:

| Group | Phase names |
| --- | --- |
| Sensor image preparation | `bridge.rgb_encode`, `bridge.depth_encode`, `bridge.recorder_image` |
| Recorder synchronization | `recorder.lock_acquire`, `recorder.lock_release` |
| SQLite operations | `recorder.sqlite.execute`, `recorder.sqlite.executemany`, `recorder.sqlite.executescript`, `recorder.sqlite.commit`, `recorder.sqlite.rollback`, `recorder.sqlite.close`, `recorder.sqlite.enter`, `recorder.sqlite.exit` |
| Capacity checks | `recorder.quota_guard`, `recorder.physical_guard` |
| Recorder operations | `recorder.image`, `recorder.persist`, `recorder.motion`, `recorder.flush_motion`, `recorder.document`, `recorder.event`, `recorder.trigger`, `recorder.close` |

These are prospective instrumentation around the existing encoding, transaction, retention, and failure paths. Source inspection does not establish which phases occurred or whether the new probe passed. Some construction/finalization calls use a null scope outside the measured interval; missing names must not be shown as zero-cost operations. Earlier revisions did not contain these measurements and should say “not instrumented in this revision.”

For a normally assessed scored run, `build.py:353` already copies all `phases`, `slow_phases`, and `slow_phases_by_name` from the exact assessment-bound `timing-v2.json`; the new names require no list expansion. The present template only shows that payload as raw JSON. A small phase table should show recorded count, inclusive wall/CPU totals, observed maxima, and bounded slow rows, grouped by these declared names with exact metadata links. Keep `adapter.bridge_observe` and its nested children visibly related. Do not add parent and child durations, subtract unrelated selected maxima to invent exclusive duration, or treat wall-minus-CPU as proof of a disk, scheduler, or external-process cause.

There is one real diagnostic-display gap: when strict resource verification fails, the assessment can retain `timing: null`, as probe003 does. The empirical builder intentionally then omits timing attribution. To inspect failed qualifications without promoting them, the qualification-only reader should follow an explicit diagnostic chain: successful official queue → assessment artifact → its bound host-result bytes → `host_result.timing_v2.metadata_sha256` → exact timing metadata and declared binary sample hashes. Label the resulting phase tables `diagnostic_only`, retain the strict assessment error alongside them, and never infer a valid timing/resource pass from raw fields. The current history already links these artifacts; this would add inspectable presentation rather than reclassification.

Show optional GC and native-memory evidence alongside the phase table when present: `campaign_timing.resource_integrity_pass`, `garbage_collection_pass`, `host_memory_pass`, the detailed independent summaries, and the recorded `bounded_host_memory_and_collector_integrity` gate. For a failed raw-diagnostic branch, retain recorded collector transitions/restoration, memory sampling gaps and ceilings, and missing verification explicitly. Do not retroactively impose dev008+ fields on earlier preserved failures. The final report should describe the exact revision used and keep source-read capture versus app-visible projection separate from timing and resource qualification.

This proposed branch changes only presentation. It does not authorize stopping qualification, lowering criteria, changing durability/retention/encoding, launching scored attempts, or treating the current repair work as a completed empirical campaign.
