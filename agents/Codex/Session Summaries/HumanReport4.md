# Session 4 — first architecture batch and frozen evaluation

Session 4 ran September 22–26, 2026. Experiment accounting, fixed analysis and the Engineering Investigation workspace are complete. This report records the results and limitations; successful Git publication is established by the final closeout commit and push, rather than by this document.

The useful result is a substantial separation between the implemented systems in these simulated cases. The conventional baseline completed the task successfully in **43 of 46 eligible persistent runs**; A3 did so in **45 of 46**. A1 and A2 had **0 of 46** successes each. This supports investigating the concrete failure mechanisms of A1 and A2 and the two discordant baseline–A3 pairs. It does not establish A3's general superiority, a causal benefit from a particular LLM placement, or real-world deployment reliability.

The authoritative aggregate is the [fixed analysis][analysis], with its [provenance][analysis-provenance] and [verified completion record][analysis-complete]. No physical trial was repeated to improve its outcome, and no policy, cap, trace selection or analysis setting was tuned after these results.

## What was compared

The batch tests long-horizon behavior in a simulated machine-tending setting where physics continues during inference. Each architecture is a complete implemented system, with its own decision interface and control arrangement:

| System | Role in the implemented system |
|---|---|
| Baseline | Conventional controller with durable state |
| A1 | LLM selects typed actions |
| A2 | LLM supplies a finite guarded plan, with 1–8 nodes and at most 5 guards |
| A3 | LLM supplies geometry parameters; a conventional scheduler, inverse kinematics and quintic trajectories control motion |

A3 is not model-predictive control. These systems differ in more than the placement of one otherwise isolated component. Their comparison therefore concerns the whole implementations. The persistent/no-persistence controls apply only to the predeclared subset.

The frozen plan contains **264 attempts: 192 main runs and 72 ablation runs**, across **24 case units, 20 scenario families and 48 paired blocks**. Four exact counterpart pairs explain why 24 case units do not represent 24 independent scenario families. The fixed task caps are 300, 600 or 900 seconds. The local model was Qwen3-14B Q4_K_M, served through the recorded llama.cpp configuration with temperature 0, thinking disabled, 16,384-token context, 1,024-token output limit and a 30-second request cap. The release records, rather than a mutable model name, identify the exact implementation and weights.

The [original Runtime 004 release][release] remains frozen. Continuation used the separately adopted [Runtime Recovery 001 execution annex][annex], followed by Analysis 005 and Investigation 005 evidence derivation. Investigation 006 fixes a presentation reader, and Investigation 007 supplies bounded presentation packaging whose production build and browser verification are complete. This is **not an unchanged Runtime 004-only execution claim**. Earlier development, retired releases r1/r2/r3 and external series remain separate historical evidence; they were not restarted or pooled into the r4 primary comparison.

## Accounting, exclusions and unknowns

All **264 planned dispositions** are now accounted for: **132 original finalized records + 131 annex-finalized records + 1 administrative interruption**. There are **263 physical/simulator terminal records**, not 264 known physical outcomes. The [derivation completion record][derivation-complete] reports no missing disposition and no global integrity error.

| Full planned-set accounting | Count |
|---|---:|
| Valid completed executions | 250 |
| Valid failed executions | 10 |
| Infrastructure-invalid completed execution | 1 |
| Infrastructure-invalid failed executions | 2 |
| Administrative interruption with no physical terminal | 1 |
| **Planned dispositions** | **264** |

“Completed execution,” validity and task success are separate fields. A completed execution can end at the task cap without achieving the task. There are **260 valid physical records** before paired-block exclusions.

The fixed whole-block rule excludes **C02 replicate 2 and C24 replicate 2**, removing **11 planned members** in total: three infrastructure-invalid terminals, the administrative interruption and seven otherwise valid records in those blocks. The primary analysis therefore contains **253 eligible records**. Failures that remain valid are not excluded merely because they failed.

The interrupted **C24 replicate 2 A1 persistent** attempt has no original supervisor terminal, finalization or post-run integrity result. Its administrative `aborted`/infrastructure-invalid projection records the missing terminal honestly; it is not a measured task failure. Its physical ending time, task outcome, duration and post-run integrity remain **unknown**, and its diagnostic/continuity derivatives are unavailable. The queue reconciliation timestamp is not its physical ending time. Partial evidence is retained; no replacement trial or fabricated result was created.

All 263 normal terminals have completed, source-bound diagnostic and continuity derivatives with no reported integrity findings or missing evidence in those derivations. This verifies the recorded processing chain; it does not independently prove evaluator correctness or authenticate every underlying physical claim.

## Task success and paired estimates

Each persistent entrant had 48 planned runs and 46 eligible runs. The main comparisons retain 24 case units and use 20 scenario families as bootstrap clusters.

| Persistent entrant | Successes / eligible | Success rate |
|---|---:|---:|
| Baseline | 43 / 46 | 93.48% |
| A1 | 0 / 46 | 0% |
| A2 | 0 / 46 | 0% |
| A3 | 45 / 46 | 97.83% |

The original numerical protocol was retained: **2,000 bootstrap draws, global analysis seed 0**, with the original deterministic comparison-specific seed derivation. The following are paired success differences, in percentage points, with individual 95% scenario-family cluster bootstrap percentile intervals. They are not multiplicity-adjusted simultaneous intervals.

| Left minus right | Paired runs | Difference (pp) | 95% interval (pp) |
|---|---:|---:|---:|
| Baseline persistent − A1 persistent | 46 | +93.48 | [82.05, 100.00] |
| Baseline persistent − A2 persistent | 46 | +93.48 | [82.93, 100.00] |
| Baseline persistent − A3 persistent | 46 | −4.35 | [−14.63, 0.00] |
| A1 persistent − A2 persistent | 46 | 0.00 | [0.00, 0.00] |
| A1 persistent − A3 persistent | 46 | −97.83 | [−100.00, −92.30] |
| A2 persistent − A3 persistent | 46 | −97.83 | [−100.00, −92.50] |
| A1 persistent − A1 no-persistence | 23 | 0.00 | [0.00, 0.00] |
| A2 persistent − A2 no-persistence | 23 | 0.00 | [0.00, 0.00] |
| A3 persistent − A3 no-persistence | 23 | 0.00 | [0.00, 0.00] |

The baseline–A3 comparison contains **43 shared successes, 1 shared failure and only 2 A3-only successes**. Its interval reaches zero. A3's higher observed count does not prove a general superiority claim.

Each persistence ablation comparison has **23 eligible pairs, 12 case units and 8 scenario families**. A1 and A2 each have zero successes in both conditions; A3 has **22/23** in each condition. The identical observed paired outcomes produce zero-width intervals under this fixed empirical bootstrap. They do not establish population equivalence or prove that memory has no effect. A1 and A2's success floor further limits what this ablation can reveal. The order-change stratum is outside the planned ablation subset and has **N = 0**, with no estimate.

Across the 253 eligible records, there are **110 measured successful completion times and 143 right-censored task failures**. Failure markers at the protocol cap are a plotting convention, not measured completion times. Observed wall duration and observed censor time remain distinct from time to successful completion.

## Failures retained and diagnosed

The evidence chain preserves technical failures, unsuccessful approaches and unresolved causes. None of these is silently converted into successful execution.

- **Three infrastructure-invalid terminals:** C02 replicate 2 A2 persistent failed the actual-host timing gate; its cause remains unassigned. C24 replicate 2 A3 in both persistence conditions failed the resource-sampler/watchdog requirement. The recorded sampler ages exceeded the 7-second limit; these are infrastructure findings, not evidence that A3's task policy failed. The fixed paired-block exclusions above apply.
- **Nine valid model-request timeouts:** all are A2 runs, retained under the fixed 30-second request cap. They are C18 replicate 1 persistent; C17 replicate 2 no-persistence; C24 replicate 2 in both conditions; C23 replicate 1 persistent; C23 replicate 2 in both conditions; C20 replicate 2 persistent; and C14 replicate 1 persistent. The C24 members remain visible although their block is excluded. A timed-out call has unknown token usage; a missing token total is not zero.
- **One valid baseline budget failure:** C20 replicate 1 persistent exceeded the frozen **32 MiB combined stdout/stderr pipe-output cap**. The supervisor classified it as `candidate_transport_failure`, with a partial task outcome. The [recorded assessment][baseline-assessment] distinguishes actual wire output from the much larger evidence JSONL file. Exact consumed wire bytes were not recorded. The final candidate resource interval is missing; observed usage remains a lower bound, without imputation.
- **Queue recovery candidate 001 failed its native Windows sharing test.** `FILE_SHARE_DELETE` alone did not prevent replacement failures. That failed validation and its evidence remain. Candidate 002 instead serialized reads under the queue's existing lock; its official validation passed **65 recovery/analysis tests**, preserving equality of the original 132 results. The adopted queue repair and annex were recorded separately rather than modifying frozen Runtime 004.
- **Investigation 005 production build failed.** It compared entire annex-reference dictionaries: selection supplied path/hash, while verified analysis added the actual byte count. The same file was rejected because of optional metadata enrichment. The [failure assessment][reader-assessment] records the exact error, failed receipt, log and test-fixture gap. No failed output was consumed.
- **Investigation 006 repaired the reader and passed 167 tests**: the unchanged 157-test Investigation 005 suite plus 10 new regressions. Its real-analysis check reproduced the old refusal, verified the new binding and preserved the estimates. The production build officially succeeded, but generated a **785,205,562-byte HTML file** containing a snapshot that expands to **2,301,938,781 bytes**. That monolithic allocation is unsuitable for the intended browser workflow. The [packaging assessment][packaging-assessment] records the issue. Browser creation was aborted; the cause of the app closure remains unknown.
- **Investigation 007 has three retained failures.** [Validation 001][package-validation-failure] stopped on a missing closing bracket in a synthetic Node test fixture, before the JavaScript tests ran. [Production build 001][package-import-failure] then exposed an import-path assumption: an unchanged upstream reader expected `load_map_module` from the new entry point. Both were corrected in separate source-bound iterations. [Validation 003][package-validation-complete] passed **184 Python tests and 15 Node tests (199 total)**, checked all 264 actual derivative dispositions and unchanged analysis, and hashed the retained 006 artifact. It did not package an actual selected trace. [Production build 002][package-metadata-failure] subsequently rejected the first selected trace's full metadata because it exceeded the **256 KiB compact-descriptor allowance**; no page was produced. Synthetic fixtures had incorrectly assumed that metadata was small. Source 004 preserves exact full metadata in bounded authenticated shards, with a display summary/reference in each descriptor. [Validation 004][package-validation004-complete] passed **188 Python tests and 15 Node tests (203 total)** and exercised the first fixed trace: all **335,505 metadata bytes** survived exact reconstruction, while its compact descriptor used **4,187 bytes**. No physical trial, numerical analysis or trace-selection change resulted from these failures.

Normal trials and receipts were admitted and collected in ready chunks through the shared compute queue. Queue-worker liveness and official `succeeded`/integer-zero receipts were treated separately from scientific outcome. A worker exiting successfully did not turn a failed child job into a passing job. No other project's active work was preempted or altered.

## What the investigation can and cannot show

The fixed [12-trace selection][trace-selection] contains C01 replicate 1 for all four persistent systems; C14 replicate 1 for A1/A2/A3 in both persistence conditions; C17 replicate 1 baseline persistent; and C24 replicate 1 A3 persistent. It retains the **C14 replicate 1 A2 persistent timeout**. The verified presentation preserves the original **2 Hz observation and 5 Hz motion** sampling, images, contexts, actions, restarts, failures and source references. Traces explain particular episodes; they do not replace the all-record aggregate.

The current implementation includes narrowly qualified restart behavior. Finite qualification and successful startup/restart checks do not certify continuous recovery under every possible interruption. Establishing an observed restart is also different from establishing a task recovery caused by durable memory. Missing or inadmissible continuity evidence must remain unknown.

The simulation does not establish factory reliability, safety or transfer to hardware. The selected cases and family bootstrap do not define a representative population of industrial tasks. The comparison does not isolate the causal contribution of the LLM, memory, geometry parameterization or any single component. The original **12 active engineering-hour constraint was not measured sufficiently to establish compliance**. Runtime duration and calendar elapsed time do not substitute for that measurement.

Investigation 007 now has a completed, separately versioned, bounded, lazy-loading [production package][package-build-result]. Build 003, job `20260926T174127003399Z-af82f271`, officially succeeded with exit 0 at **2026-09-26 18:11:15.881917 UTC**. It contains all **264 metadata records and 264 derivative dispositions**, with exact reconstruction verified for **all 12 fixed traces' full metadata, motion and every retained event payload**. Original observations, motion sampling and analysis estimates were preserved. The initial HTML is **8,883,152 bytes**, versus 785,205,562 bytes for retained 006; its decoded compact snapshot is **27,180,968 bytes**. Large trace content is loaded separately under the recorded allocation limits. These are engineering bounds, not a proven optimal browser configuration. [Browser verification][browser-qa] exercised all twelve packages, the analysis denominators, the administrative unknown, actual camera images, candidate/evaluator separation, keyboard navigation, restart cutoffs, lazy metadata and reloadable event links. Desktop 1280×900 and narrow 375×900 layouts passed without document overflow; console warning/error logs were empty. A roughly317-pixel pane can require horizontal scrolling in the header. Planned-run search includes shared provenance, so an interrupted-run ID can match the132 administrative/annex records; selection and denominators remain correct. Corrupt/missing/oversized-package handling is covered by the passing Node suite; production evidence was not deliberately corrupted for browser QA. The retained 006 artifact is not a verified usable viewer and should not be opened blindly.

## Provenance and handoff

The completed scientific chain is anchored by the following records. Detailed source inventories and exact command arguments are in the linked completion records and official receipts.

| Artifact | SHA-256 |
|---|---|
| Original r4 release | `ed65f8b33e16daaa081031cfe7ccc7ac65644af3522546aad0d2fa76a1d72fe1` |
| Adopted Recovery 001 annex | `90951370dc7843e441f2fd0223943ccdcf4185d387e90a739ab4ffa0263b6152` |
| Investigation 005 derivative index | `1e3892295b4d0f3817c3767656919b9462cec42632cd6bf5684e675375dbb168` |
| Analysis 005 output | `57f19a04be17e6bbc22b853b5bd40a0ca9e89b2e6caee9caea634c122a366018` |
| Analysis 005 provenance | `25da0fcb0e77dedfc06a63c186d7e42c63f0d5c3a655d7d6b3ec4810917e8d6d` |
| Fixed 12-trace selection | `84e16491903c35b5ad7f9ea115b5a843d47df432d0e7313ee7fefd94e3fffe25` |

The final physical accounting marker is [batch 069 complete][batch-complete]. Derivation job `20260926T051829425032Z-f5098b2d` and analysis job `20260926T082100299990Z-ef3848d4` both have official successful zero-exit receipts. Their completion audits verified 1,488 and 947 unique compact source/output references respectively, without rereading raw streams. Successful processing and reference checks do not replace the scientific limitations stated above.

Open the [investigation workspace][viewer] through the loopback server documented in the [experiment entry point][experiment-home]. Start with **Paired analysis** for all eligible results, then use **Recorded timeline** for the twelve predeclared examples and their exact evidence. The [browser QA record][browser-qa] names tested behavior and remaining interface limitations. Full generated packages, raw streams and images are retained locally; compact provenance, source identities and reproducible builders are versioned. A clone alone does not contain all raw evidence or the generated viewer.

The next useful scientific work is a human review of the A1/A2 failure mechanisms, the two discordant baseline–A3 pairs and the limits of the persistence comparison. That review may motivate a new experiment; this session does not authorize a new scored campaign or change the frozen completed one. The session claims and human chat are closed before final scoped Git closeout. Exact bound bytes must survive staging. Only after successful commit and push may the owned lock be removed and the completion follow-up disabled; the separate paused robotics cron remains unchanged.

[analysis]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/derived/evaluation-r4-analysis005-001/analysis.json
[analysis-provenance]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/derived/evaluation-r4-analysis005-001/analysis-provenance.json
[analysis-complete]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-analysis005-001-complete.json
[derivation-complete]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-derivation005-001-complete.json
[batch-complete]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/batch-069-complete.json
[release]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/releases/batch01-eval-r4/release.json
[annex]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Batch%2001/Release%20Queue%20Recovery%20001/execution-annex.json
[trace-selection]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Batch%2001/evaluation-trace-selection-r4.json
[baseline-assessment]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/batch-058-failure-assessment.json
[reader-assessment]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation005-001-failure-assessment.json
[packaging-assessment]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation006-001-packaging-assessment.json
[package-validation-failure]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/investigation007-package-validation-001-failure-assessment.json
[package-import-failure]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation007-001-failure-assessment.json
[package-validation-complete]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/investigation007-package-validation-003-complete.json
[package-metadata-failure]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation007-002-failure-assessment.json
[package-validation004-complete]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/investigation007-package-validation-004-complete.json
[package-build-result]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/evaluation-investigation007-003-build-result.json

[browser-qa]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Evidence/release-series/batch01-eval-r4-manual-001/investigation007-browser-qa-001-complete.json
[viewer]: http://127.0.0.1:8778/Engineering%20Investigation%20007/site-r4-003/index.html#view=analysis
[experiment-home]: ../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/README.md
