# Robot-Codex Campaign 001

**Session 12 final:** Campaign 001 stopped after slot 10 under its declared two-consecutive-infrastructure-invalid rule. All 24 slots are recorded: **6 valid successes, 4 infrastructure-invalid attempts, 14 not run**. Ten evaluators observed task completion, but invalid attempts remain unscored. No replacements or framework changes were made. Open the [interactive investigation](investigation/report.html), [findings and limits](investigation/OVERVIEW.md), or [stop record](execution/campaign-stop.json). Work stops here for Randy's review before any follow-on experiment.

Randy's storage approval, including modest explainable overruns, is recorded in the [durable approval](admission/storage-approval-session12.md) and [final external protocol](admission/PROTOCOL-v2.md). Admission used the [v3 certificate](admission/sealed-v3/certificate.json) and identical-source RCI001-C01-frozen-001 release; the 150 GB historical footprint did not block this campaign. All 624 original framework source identities remained unchanged. Storage monitoring raised no alerts; historical evidence was retained.

## Retained Session 11 preparation history — superseded status

The following text is the original preparation account. Its pending-approval and zero-launch statements describe Session 11, not the final state above.

**24 attempts are planned; none have launched.** The [pre-outcome plan](PLAN.md) and [sealed allocation](predeclared-v1/schedule.json) test only exact `RCI001-wsl-010d`: 12 attempts per existing recovery fixture, fixed world seed 173, 24 fresh sensor seeds and fresh episode workspaces. All 624 qualified source files matched during preparation. There are no replacement runs or outcome-driven extensions.

The actual [Batch 01 evidence](design/README.md) supports this smaller scope. That campaign used 264 dispositions and 38.01 measured queue-hours over 59.86 elapsed hours. This plan reserves at most 7.33 host-hours before outer overhead, with a conservative 10-hour scheduling allowance. Twelve repeats per fixture can expose common failure patterns, but their intervals remain broad; this is not a high-reliability or unseen-task claim.

## Admission decision needed

The fresh two-pass read-only [capacity census](admission/census-002/capacity.json), authenticated by successful queue job `20260927T183504273895Z-7d522fdb`, shows:

| Quantity | Decimal GB |
|---|---:|
| Existing `Evidence/` subtree alone | 175.842 |
| Adopted provisional project-evidence ceiling | 150.000 |
| Excess from `Evidence/` alone | 25.842 |
| Conservative total after hardlink deduplication and explicit model exclusion | 182.144 |
| Current free C: | 418.955 |
| Proposed campaign permanent reservation | 28.770 |
| Proposed campaign peak including margin and temporary space | 37.962 |
| Free-space remainder after that peak | 380.992 |

The campaign fits the adopted 30 GB target / 40 GB campaign ceiling and 100 GB free-space reserve **as a conservative planning reservation**. Aggregate wrapper accounting and measured qualification must still be completed before admission; the reservation is not a demonstrated hard bound. The existing project-evidence ceiling fails even after removing known model/hardlink overcount. No historical evidence has been deleted, moved or compacted.

**Proposed decision:** allow this one 24-attempt campaign up to 37.963 GB additional peak storage while retaining the 100 GB free-space reserve and all existing evidence. This is a specific exception to the 150 GB project ceiling, not a request to repeat experiment authorization or permanently waive retention limits. The alternative is to keep that ceiling and defer the campaign until a separately authorized, verified normalization can meet it. The source of the dependency is Randy's September 26 storage instruction, [section 8](../../../chats/Codex-Human/Audit%20Storage/Audit%20Storage%20-%20Active.md): “Project evidence ceiling after normalization: 150 GB.” September 27 authorizes the experiment but does not expressly change that limit.

## Technical preparation and limits

The [timing reconstruction](admission/census-002/retained-timing.json) applies the unchanged frozen TimingMonitor to retained monotonic protected journal samples. The exact 010d pilot passes all 237 reconstructed one-second windows, with no out-of-tolerance windows, 0.040-second reconstructed lag and 0.125-second maximum sample gap. Its separately retained per-tick maximum lag is 0.041 seconds. This is supportive complete-pilot calibration with explicit sampling/origin limits, not invented per-tick window evidence.

The older 010c injected-restart smoke has a preserved 0.107-second per-tick maximum lag and fails the strict 0.1-second target. This campaign has no injected restart; that smoke is not a scored campaign result or evidence that the failed timing gate passed. Additional campaign-specific timing/accounting qualification can proceed under the existing engineering authorization after the storage decision; no relaxed timing rule or changed robot framework is proposed.

The external [assessment tooling](assessment/README.md) separates observed task outcome, evidence validity and scientific admission. It does not turn the pilot's missing late lifecycle receipts into passes, and cannot grant admission. The fixed host's `development-only` metadata remains unchanged and visible; the outer plan scores repeatability on those known fixtures prospectively, without claiming held-out geometry or framework comparison.

The preparation seal is **not a frozen scored release or admission certificate**. Before any score, bind the final assessor, complete aggregate accounting and timing qualification, refresh capacity, record the human storage decision, register the status-only framework freeze and attempt manifests in the Architecture Map, and verify the exact source/asset/runtime identities. Preserve this plan and seal if a pre-outcome revision is needed. No scored result exists, so no result-based investigation is fabricated.

## Resume

1. Read Randy's latest reply and the active human inbox. Resolve the storage exception explicitly; do not infer approval from silence.
2. Finish the remaining external campaign admission/release work while preserving exact 010d executable and prompt bytes. The deterministic schedule is already prepared; no seeds are selected from outcomes.
3. Run the 24 fixed slots through the shared queue, with declared validity/stop rules and no replacements. Preserve invalid, failed and unrun dispositions.
4. Build the investigation from actual results and stop for review before any expansion, ablation, comparison or Maps + Attention work.

The earlier failed census is retained under `admission/census-001/`: it correctly refused concurrent file changes. The successful census used two matching metadata passes while writers were paused. This is a read-only preparation session; there were zero new Robot-Codex or simulator calls.
