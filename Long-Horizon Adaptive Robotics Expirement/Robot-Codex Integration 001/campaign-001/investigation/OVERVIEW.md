# Campaign 001 — completed at the declared stop

The campaign stopped after slot 10 because two consecutive attempts were infrastructure-invalid. All 24 planned slots now have terminal dispositions: **6 valid successes, 0 valid task failures, 4 infrastructure-invalid attempts, and 14 not run**. No replacement, retry, tolerance change, or framework modification followed the outcomes. Start with the [interactive investigation](report.html), then inspect the [stop record](../execution/campaign-stop.json), [full allocation](../predeclared-v1/schedule.json), and individual assessments linked in the report.

This is evidence of successful recovery in six admissible episodes on two known fixtures. It also exposes an unreliable path through the declared execution/measurement requirements: four of ten started attempts were invalid. The ten protected evaluators all observed task completion, but observed success in an invalid attempt is diagnostic evidence and its scored outcome remains unknown. The fourteen unrun slots have no observed outcome.

## Denominators and uncertainty

| Fixed fixture | Planned | Started | Valid successes / valid trials | Infrastructure-invalid | Not run | Descriptive 95% Wilson interval, valid trials |
|---|---:|---:|---:|---:|---:|---|
| Misplaced stock | 12 | 5 | 4 / 4 | 1 | 7 | 51.0–100% |
| Blocked insert home | 12 | 5 | 2 / 2 | 3 | 7 | 34.2–100% |
| Combined | 24 | 10 | 6 / 6 | 4 | 14 | 61.0–100% |

These intervals describe the valid subset under a binomial interpretation; they are not calibrated guarantees under infrastructure-dependent selection and early stopping. Both families share one fixed world seed (173). Sensor seeds and fresh model invocations vary, but there are only two known fixture scenarios, not 24 independently sampled tasks. The pooled percentage does not establish general robot reliability.

Confirmed scored successes are 6/24 planned slots (25%). Treating every invalid or unrun slot as an unresolved success-or-failure gives an identification range of 25–100%, not a confidence interval or a prediction of unrun trials. The report separately displays observed evaluator completion: 10/10 started attempts, including four invalid attempts. The preselected last episode in each fixture was not run; neither is replaced by a favorable earlier episode. Additional failure and unusual-behavior cases are explicitly selected after outcomes.

## What the system actually did

The [first stock episode](stock01-investigation.md) shows a complete evidence chain: public observations located raw A1 in quarantine; the model chose one protected native transport into the fixture; the host dispatched it once; subsequent observations supported placement; accepted handback transferred authority to the conventional controller; processing, inspection, delivery and settled independent evaluation followed. A completed transport receipt alone was not treated as physical or task success.

The [first blocked-home episode](home01-investigation.md) shows adaptation within a single invocation. The model cleared A1 from the insert return pad, but its first handback was rejected. The retained conventional checkpoint had already exhausted its setup-B failure limit. The model then performed the native insert exchange and handed back with B2 transport as the supported next action. This separates physical progress from resumability of the existing controller. All five started home assessments retain two physical requests and two handback requests; the inspected first episode explains the mechanism, while per-episode records support the repeated counts.

Continuity preserved planned request IDs and unresolved action state. In the representative cases, protected continuity could not be updated after authority transferred: the model retained a local note while the protected note still described handback as planned. A future invocation would need to reconcile that note with the command registry and ownership history. There was no injected restart or subsequent recovery invocation, so this campaign does not measure continuity reuse or a causal memory benefit.

Stock02 retained one bounded program invocation with separate admission and final records; those two records must not be counted as two programs. Its source reads public history/status and writes summaries, and the final record reports successful execution. It does not generate a motor controller. The other nine assessments contain no bounded-program records. See the [program investigation](stock02-program-investigation.md) for source and execution detail.

## Infrastructure failures and stop

| Slot | Attempt | Original per-tick maximum lag | Reconstructed journal maximum lag | Out-of-tolerance one-second RTF windows | Actual invalidity |
|---:|---|---:|---:|---:|---|
| 3 | home02 | 0.099 s | 0.113 s | 0 / 315 | Reconstructed lag exceeds strict 0.1 s limit |
| 6 | home03 | 0.327 s | 0.334 s | 3 / 322 | Both lag checks fail |
| 9 | stock05 | 0.040 s | 0.042 s | 0 / 200 | Unrecognized client/transport failure at closure |
| 10 | home05 | 0.108 s | 0.115 s | 1 / 334 | Both lag checks fail; second consecutive invalid |

The three timing-invalid episodes still satisfy the less-than-1% bad-window fraction. The separate maximum-lag requirement invalidates them. The original per-tick metric and reconstructed journal metric use different observation/origin details; subtracting their maxima cannot repair a failed gate. Journal RTF is reconstructed with the unchanged TimingMonitor from sampled protected wall/simulation observations, not retained per-tick window data. See [home02](home02-timing-investigation.md), [home03](home03-timing-investigation.md), and [home05](home05-timing-investigation.md).

Home05's maximum retained journal delay occurred before invocation activation and the model turn. This is evidence against attributing that peak to the model's later task reasoning. It does not identify the host/OS cause. Home03's larger transient preceded the first physical request. The retained artifacts cannot isolate scheduling, logging, model-service or other host contributions, and no counterfactual rerun was added.

In [stock05](stock05-transport-investigation.md), the protected host completed successfully, but the client later aborted with a qualified transport failure. A late continuity request following host closure is the supported interpretation; the exact failing request-to-broker-error association is not retained and remains an inference. Required namespace retirement, source, isolation, evaluator and evidence checks passed. A successful terminal host is insufficient to turn an unrecognized client disposition into an admissible trial.

The ordinary-invalid counter across started slots was 0, 0, 1, 0, 0, 1, 0, 0, 1, 2. The frozen [protocol](../admission/PROTOCOL-v2.md) therefore ended admission after slot 10. This was not a storage stop or a task-performance stop.

## Resources, provenance, and limits

The ten attempts occupied the shared compute queue for 2,945.976 seconds (49.10 minutes); summed host duration was 2,802.452 seconds (46.71 minutes), including invalid attempts. Queue success with integer exit 0 was verified before consuming every completed scientific output. Model service and tool time are not independently isolated by these duration totals. Existing ChatGPT authorization was used; no new spending was introduced.

Randy's [storage approval](../admission/storage-approval-session12.md) was implemented as a planning allowance with protected capacity, not a rigid campaign byte ceiling. All ten monitors covered their queue intervals without an alert. Sampled aggregate positive growth reached 430,748,225 bytes (0.431 GB) before final report/export work. This is a sampled lower bound including conservatively counted shared-service growth, not exact per-run physical allocation. See [storage closeout](storage-closeout.md) for minimum free capacity, post-run accounting and explicit measurement scope. No historical evidence was deleted to make room.

The framework remained exact RCI001-wsl-010d: all 624 frozen source identities were reverified after stopping. The metadata-only scored revision is RCI001-C01-frozen-001; its [registration](../../../Architecture%20Map/releases/RCI001-C01-frozen-001/registration.json) binds the final [admission certificate](../admission/sealed-v3/certificate.json). Original plan, schedule and manifests remain unchanged. The superseded pre-outcome v2 seal is retained; v3 was finalized before the first model launch. No post-outcome tool change alters an assessment.

The interactive report connects ownership, model/tool text, requested/dispatched/admitted/verified actions, continuity and independent evaluation. Original retained camera PNG bytes are exported through the queue with a fixed image quota and paired-depth verification; absent frames and unrun cases remain labeled. Capture simulation time and later publication time remain distinct. The investigation's images do not imply that the model inspected those pixels; representative model notes describe use of structured observations.

Static report validation and original-image inspection are recorded in [QA](qa.json). Browser visual and interaction QA is unavailable because the browser tool explicitly rejected the local report URL and prohibited alternate-route workarounds. The report is retained for Randy to open locally; browser execution must not be claimed as verified.

## Review boundary

Campaign 001 is complete at its declared stop. Infrastructure reliability, terminal continuity publication and repeated handback rejection are concrete findings for review. Any framework repair, new qualification, changed timing track, replacement experiment, expansion, ablation, architecture comparison or Maps + Attention work belongs to a separately directed next step. None has been started here.
