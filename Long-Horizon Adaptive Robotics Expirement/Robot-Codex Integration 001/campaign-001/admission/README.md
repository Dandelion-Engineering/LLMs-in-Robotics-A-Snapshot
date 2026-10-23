# Campaign 001 admission review

**Session 12 supersession:** the [explicit approval](storage-approval-session12.md) resolves the historical storage dependency below. The 37.963 GB estimate is a flexible planning allowance; preserve the 100 GB free reserve and all historical evidence. The [final external protocol](PROTOCOL-v2.md) specifies the binding and monitoring work now being completed. Earlier census outputs and qualification flags remain unchanged as historical evidence.

**Storage remains the human decision.** Fresh counting confirms that removing repeated hardlink paths and model files cannot meet the existing 150 GB evidence ceiling. The exact 010d pilot supports the proposed one-invocation timing envelope, with the measurement limitations below. No campaign was admitted, no model/robot run was started, and no historical policy or qualification flag was changed by this review.

The successful read-only job is `20260927T183504273895Z-7d522fdb` (`succeeded`, exit 0). Its [binding](census-002/binding.json) authenticates the [source](inspect_admission.py), [official receipt](census-002/queue-receipt.json), [capacity measurement](census-002/capacity.json), and [retained timing calculation](census-002/retained-timing.json). Four counterexample tests passed. Two complete metadata inventories agreed across 481,773 files, while all experiment writers were paused. The earlier [census 001](census-001/invalid-census.json) refused changed design files; its [failed receipt](census-001/failed-queue-receipt.json) is preserved and is not used for capacity.

## Fresh capacity and the concrete decision

All figures use decimal GB. The successful inventory finished on 2026-09-27 at approximately 18:35:59 UTC.

| Scope | Bytes | GB |
|---|---:|---:|
| Whole canonical experiment, every ordinary pathname | 219,195,676,563 | 219.196 |
| Whole experiment, distinct volume/file identities | 193,642,566,701 | 193.643 |
| Repeated hardlink pathname bytes removed by that accounting | 25,553,109,862 | 25.553 |
| Explicit model-only file identities | 11,499,033,216 | 11.499 |
| Conservative non-model remainder | 182,143,533,485 | 182.144 |
| Evidence subtree alone, distinct identities | 175,841,532,293 | 175.842 |
| Completed r4 subtree alone, distinct identities | 150,859,067,391 | 150.859 |
| Current C: free space | 418,954,551,296 | 418.955 |

The whole-tree count excludes nothing. The additional non-model count subtracts only the six exact model paths enumerated in `capacity.json`, and only an identity whose every observed path is one of those model paths. A model identity also referenced by evidence is retained. Source, code, prototypes, failed runs, viewer data, and every other file remain counted. File identity deduplication removes hardlink pathname duplication; it does not measure allocated clusters, filesystem compression, or content-identical separate files. The authenticated metadata digest covers each path, device/file identity, size, modification time, and link count. Two-pass agreement is not an atomic volume snapshot or file-content authentication.

Even the Evidence subtree alone exceeds 150 GB by **25,841,532,293 bytes**. The conservative non-model remainder exceeds it by **32,143,533,485 bytes**. This is a real retained-evidence issue, not just duplicated model accounting.

The [selected campaign plan](../PLAN.md) reserves **1 GiB per attempt for 24 attempts**, including host evidence and the external transcript/runtime backing allowance, plus 2 GB for investigation and 1 GB for qualification:

| Selected reservation | Bytes |
|---|---:|
| Permanent campaign allowance | 28,769,803,776 |
| Peak with 25% uncertainty and 2 GB temporary allowance | 37,962,254,720 |
| Free space after that peak, at this measurement | 380,992,296,576 |
| Conservative non-model evidence plus permanent campaign allowance | 210,913,337,261 |

The 30 GB permanent target, 40 GB peak limit, and 100 GB free reserve fit this reservation; **the project evidence ceiling does not**. These are planning limits, not observed campaign consumption. The submitted census also retains an earlier, smaller 768 MiB-per-attempt planning alternative. That alternative is superseded by the selected 1 GiB-per-attempt reservation above; the completed report is preserved unchanged.

The concrete reviewable choice is a **one-campaign exception to the 150 GB project evidence ceiling**, with a maximum **37,962,254,720-byte additional peak**, the existing **100 GB free-space reserve**, no historical deletions, and admission/resource stops as frozen in the plan. This does not reset the lifetime ceiling or authorize another campaign. If the exception is not granted, retain the plan and decline new scored work; normalization of old evidence would require its own authorized, verified process.

Source authority: [Sustainable Retention](../../../Storage%20Audit%202026-09-26/Sustainable%20Retention.md) defines the 150 GB evidence ceiling after normalization, separately budgets model/source/environment, and keeps the 100 GB free reserve as an additional condition. The [qualified recorder README](../../../Storage%20Retention%20Implementation%20001/future/README.md) permits a separately qualified physical-identity/model-exclusion census, while requiring all scientific evidence to remain counted. The present external census refines that accounting without changing `admission.py`; it does not turn the original rejected admission into a pass. Fresh admission still requires current free space and a census no more than one hour old.

## Timing evidence on the unchanged framework

The [calculation](census-002/retained-timing.json) extracts and executes the exact `TimingMonitor` class from frozen `Runtime 004/experiment.py`, hashing both complete source and class text. It applies that monitor to the protected journal's monotonic `wall_elapsed_s` and `sim_time_s` from the unique `episode_started` through `episode_stopped` records. The monitor itself uses linear interpolation of adjacent fresh wall/simulation samples and retains the maximum sample gap; it imposes no additional sampling-period gate.

| Retained attempt | Exact revision | Journal samples | Complete one-second windows | Outside 0.95–1.05 RTF | Maximum journal lag | Maximum gap | Original per-tick maximum lag |
|---|---|---:|---:|---:|---:|---:|---:|
| One recovery pilot | 010d | 2,433 | 237 | 0 | 0.040 s | 0.125 s | 0.041 s |
| Interrupted/fresh-invocation smoke | 010c | 7,821 | 784 | 2 (0.255%) | 0.119 s | 0.219 s | 0.107 s |

The **010d pilot passes** the unchanged `<0.1 s` maximum-lag and `<1%` out-of-tolerance-window rule under this explicit journal sampling. Its original host's 118,562 per-tick lag samples corroborate a 0.041-second maximum. This is supportive full-pilot-loop calibration for the one-invocation experiment, including real inference, recovery, handback, conventional completion, and sustainable recording.

It is an offline journal measurement, not a claim that per-tick RTF windows were originally retained. Journal samples are event-driven, acquisition is distinct from publication, and interpolation leaves sub-gap timing unresolved. The journal origin precedes the host-loop clock initialization; the final journal record follows terminal cancellation. Original `wall_elapsed_s` includes initialization/finalization and must not be divided by simulation duration as if it used the same boundary. A successful 237-second pilot does not by itself qualify every longer or higher-load future episode. Freeze the same assessor and the original per-tick lag check before scored runs; handle timing failures under the predeclared infrastructure/candidate rules, preserving evidence.

The **010c restart smoke fails** the maximum-lag rule; its source revision and failure remain visible. It is outside this campaign's predeclared no-injected-restart envelope and does not invalidate the observed 010d one-invocation result. It must not be promoted to strict timing qualification for a future scheduled-restart campaign. If additional pre-score timing qualification is needed after the storage decision, a bounded exact-010d qualification may be added under the existing engineering authorization without changing the framework, relaxing thresholds, or tuning against scored outcomes. No such new run occurred here.

The [experiment contract](../../../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Contract.md) establishes the actual-host rule and separate controlled-delay diagnostic. A generic claim of a lagged diagnostic track is unnecessary for the passing pilot and would not waive the campaign's frozen timing gates.

## Exact freeze, implementation limits, and stops

The source authority is [RCI001-wsl-010d snapshot](../../../Architecture%20Map/releases/RCI001-wsl-010d/snapshot.json), with `code.zip`, `manifest.json`, and `mechanism.md` beside it. The snapshot was created at 2026-09-27T16:56:21.425564+00:00, from Git head `d35f825ef32f03a7d73167ec160378a66fb91047`, and binds pilot-manifest SHA-256 `337ff5eb4c173b80aa9a47ae4ae8623704e49bb67e29af339ab14a46b7d2dfe6`. Verify the applicable bytes immediately before submission; this review edits only the new campaign admission package.

- The unchanged host has a 512 MiB manifest storage cap checked periodically, a journal admission guard, and **50,000,000-byte core / 12,000,000-byte image recorder quotas**. It persists sparse image pairs every two seconds. These are the actual 010d bounds; generic future-recorder 30-second sparsity or representative-span settings must not be substituted silently.
- Host capacity does not include every WSL/runtime backing copy and retained transcript. The selected per-attempt allowance must cover those separately; an allowance alone is not an enforcement mechanism. Reserve build/finalization duplication, check observed usage, and stop new admission on insufficient remaining budget or free reserve.
- `RecordingFailure` or an unclosed/failed container invalidates complete scientific evidence. Stop the host/attempt and preserve the explicit failure; never truncate core evidence to rescue a score. Available selected-image hash failures are errors; policy-unavailable images remain explicitly unavailable.
- Enforce the frozen model-turn, wall/simulation, action, observation, program, and authority limits. Host failure stops and invalidates the episode; no silent supervisor restart is qualified. Source/isolation/evaluator/receipt violations and timing/resource failures receive the predeclared disposition, never a success retry.
- The pilot's two unobserved late shutdown receipts remain a documented observation gap; the [separate terminal lifecycle supplement](../../readiness-session-10/assessment/pilot-001-terminal-lifecycle-supplement.json) is corroboration, not fabricated late receipts. Do not weaken assessment to erase the gap.
- Only consume new queued run outputs after official `succeeded` / exit 0, while also checking the independent outcome and infrastructure/evidence gates. Queue success alone is not physical success or scientific validity.

`sustainable-evidence-3` format qualification remains reusable within its measured scope. The old generic `runtime_timing_qualified=false` and `frozen_release_bound=false` flags remain untouched. Campaign-specific qualification and source/protocol binding must be additive and scope-correct; neither this census nor the pilot timing calculation provides a storage exception.
