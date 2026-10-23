# Apartment v4 Maps — prelaunch storage blocker

**Maps was not launched. At 09:01 PDT on October 10, 2026, D: failed the inherited storage headroom gate.** Randy's [08:48 PDT authority](authority-original.md) authorizes the existing second condition only if current gates pass, and explicitly requires a stop at a capacity failure. The [immutable admission receipt](admission-blocker.json) records `blocked_before_launch`, `passed=false`, and no scientific submission. No Maps queue identity exists.

| Admission quantity | GiB | Result |
|---|---:|---|
| Actual free space | 133.921875 | Windows APIs and Python agree |
| Fixed minimum free-space gate | 50 | Pass |
| Inherited run/preparation allowance | 94.083008 | Three times the larger retained v2/v3 Baseline allocation, plus 2 GiB |
| Free space required with full reserve | 144.083008 | Allowance plus 50 GiB |
| Reserve remaining after that allowance | 39.838867 | Fail |
| Shortfall against inherited headroom gate | 10.161133 | Capacity dependency |

The drive allocates files in **1,048,576-byte units**. Small journals, filesystem versions and checkpoint files therefore consume much more physical space than their logical byte totals. The existing `session-41/admission_checks.py` was used unchanged; its source and census hashes are in the receipt. The native 20 GiB runtime stop is not an admission substitute. No gate was lowered, and nothing was deleted, moved, compressed, reformatted or repaired.

**Freeing 10.162 GiB would only clear the inherited planning threshold; it would not establish that the complete Maps run has sufficient headroom.** Session 41 measured 253.271484 GiB free after preparation and Session 57 measured 133.946289 GiB at Baseline completion: a net volume decline of 119.325195 GiB during Baseline and operator work. That is not a measured Baseline-root allocation and cannot be attributed exclusively to the experiment, but it exceeds the older 94.083008 GiB allowance. Maps may need a different number of sessions and accumulate different filesystem histories. A later capacity remedy must be assessed against the retained v4 growth evidence as well as the unchanged minimum before launch. No whole-drive census or cleanup was performed here.

The [bounded preservation readback](preservation-readback.json) passed all nine checks:

- The Session 57 endpoint matches its external copy, and all **31 referenced evidence files** still match their hashes. The original scientific job `20261010T035451057091Z-9b1fda10`, full-history audit `20261010T115828597924Z-ffa43a8e`, and supplemental audit `20261010T120908134386Z-8c0c8ce5` retain `succeeded` with integer exit 0. Both retained audits still report five passed gates.
- Baseline still records **21 advancements in 35 sessions**, final checkpoint `session-00035`, 491 files, manifest `84ef12f0d1e39e05cc4cc3325451374f12afe104efdb21f91487dde65856fd97`, and state `405262ee52202745424b14e55c5232751702b4d73c1077143ec2c0298f7d0c79`. Manifest and state bytes were rehashed; full checkpoint files, journals and replay were not re-audited.
- `D:/Dandelion-Apartment-Experiment/official/apartment-v4/maps` is unlaunched, has no continuation history, and contains only the five original prepared root entries. All **19 filesystem files** match its original inventory, run template and prepared-pair manifest. No learned file was imported. Its source-identity records, configuration and hidden schedule match Baseline; no schedule contents were exposed to a robot.
- Source-manifest hash remains `ee865baf93b83dafb8fc3daa49c22c7718527ef5a6774e99c8124e1eadac85b0`; certificate hash remains `49ac8e59a7af7b0e7b14c9c66eb3a5007984762c33e9382761cd44346d64054f`. These are current anchor checks, not a fresh complete source/environment qualification.
- No queue jobs are running, queued or awaiting cancellation. Both v4 running locks are absent, former Baseline viewer port 49645 is closed, and all four existing apartment monitors are **PAUSED**. No new viewer or monitor was created. The accepted Session 57 retirement evidence is authenticated; a new complete process/mount census was not run.

The accepted Baseline interpretation remains unchanged: fourteen latched household successes and seven completed throwing-practice windows, with mastery unassessed. Session 7's drawer later closed below criterion; session 16's first sample at +16 ms had above-threshold toy speed but its closeout state passed. Those sampling/persistence caveats remain visible and do not change the frozen latch rule.

Full source/environment verification, fresh runtime/isolation admission, official submission, native sensor/journal startup, live-viewer verification, monitoring and Maps checkpoint/endpoint audits are **NOT RUN**. The scientific condition has not failed or consumed an assignment; the failed attempt is operator prelaunch admission. No comparison was performed.

The next dependency is an authorized capacity remedy and renewed complete prelaunch assessment. The existing conditional Maps authority remains the governing launch instruction, subject to later human direction. This stop does not authorize automatic retries, cleanup of protected evidence, a new pair, source changes or a recovery lineage. No scheduler is watching for newly available space. The focused human chat remains active for this unresolved dependency. Session 58 closes with a blocker handoff; subsequent work belongs to Session 59.
