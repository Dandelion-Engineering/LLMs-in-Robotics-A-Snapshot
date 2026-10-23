# A sustainable retention plan

**Recommendation: reduce what is retained and eliminate repeated serialization. Do not make a 372 GB archive the main solution.** With roughly 400 GB available externally, it would consume nearly the remaining drive and leave the same problem for the next batch. The earlier live499 GB snapshot does not change that conclusion. External storage can support bounded verification/restore work or selected valuable records; it cannot support unlimited full-stream accumulation.

This is still an audit. Nothing has been deleted, moved, compressed or rewritten in the existing evidence. Any irreversible retention reduction is a later action for Randy to review.

## What rigor actually requires

Three distinct promises have different storage costs:

1. **Recompute the reported study statistics.** Preserve every planned disposition, result/terminal, correction, exclusion, paired manifest, exact analysis settings and provenance. Current code does not read camera files or raw event/motion streams to compute aggregate results.
2. **Independently recalculate diagnostics and examine every model decision.** Additionally preserve numerical motion at the original100 Hz and full precision; event identities/clocks/parent links; actual public packet facts; scoring witnesses and protected state/history; model input/output; checkpoints; physical action/feedback; restart qualification and failure evidence. Repeated copies of the same object are unnecessary. Full continuous camera files are not inputs to the present diagnostic or continuity calculations.
3. **Revisit any past camera/depth frame.** This requires keeping every image/depth array. It is a broader capability than 1 and2. Selective images deliberately give up universal pixel-level investigation while retaining the specified calculations and selected visual episodes.

The recommended default preserves1 and2 for every scored attempt and3 for a deliberately bounded selection. A result-only archive is smaller, but it is not the default recommendation: it loses independent recalculation and historical dialogues that compact diagnostics deliberately omit.

Source checks: aggregate analysis uses result/manifests in `Runtime 004/protocol.py:350–365,431–541` and `Batch 01/Release Analysis 005/analyze_results.py:122–155`; result collection in Analysis004/005 verifies compact records rather than raw pixels. Diagnostics reads event and100 Hz motion data in `Runtime 004/diagnostics.py:104–425`. Continuity parses event/state/restart records and hashes motion for provenance but does not numerically consume it (`Engineering Investigation 005/continuity.py:727–756`). Neither calculation reads PNG/NPZ contents. These are source-level dependency findings; no reduced-data rebuild was performed.

Preserve independent scoring witnesses too: initial validity, protected first-success snapshot, completion-claim checks, final-world state, actual outcomes and evaluator configuration. Keeping a success boolean alone is not an independent check of physical success. Current recording is already sampled;400 GB does not provide exact state at every physics tick or guarantee reproducible wall-time-sensitive inference.

## Existing data: a meaningful reduction without filling another drive

### First stage: selectively retire unused camera/depth frames

The r4 evaluation contains **233.213 GB** of saved RGB/depth. The current 12-trace Investigation007 and four-trace Explorer reference **3.061 GB** of those originals. Keeping those exact referenced files and retiring the rest would recover approximately **230.152 GB** on C:, without moving that burden to D:.

Keep **all original event/motion/resource streams, manifests, results, checkpoints, model dialogue, scoring witnesses, compact outputs, frozen sources and currently referenced viewer images** in this first stage. The project would fall from approximately407.548 GB of known-hardlink-adjusted logical content to **177.396 GB**, before filesystem overhead. No claim that historical events can be re-rendered into the missing original images is made.

The loss is explicit and irreversible without another copy: **arbitrary unselected RGB/depth reassessment would become unavailable**, including independent perception reconstruction at discarded times and previously unnoticed visual anomalies. Current numeric analyses and existing viewers have their needed inputs, subject to an actual dependency/compatibility verification before deletion. Future image-centric analyses would be restricted. Keeping additional bookmarked failure windows reduces the saving by their measured bytes; do not promise the entire230 GB if the retained set expands.

Before executing: resolve the current viewers' complete dependency set, define additional must-keep windows, generate an exact proposed removal/retention manifest and byte total, preserve an additive availability/retention record, verify current analysis/diagnostic/continuity outputs and viewers against the retained set, then obtain Randy's approval for that concrete irreversible list. A missing-by-policy frame must be distinguished from corruption. Preserve old run manifests and the historical fact that original validation once checked the full evidence; do not rewrite that history to imply all originals still exist.

This is a possible first reduction, not a final storage architecture. It leaves the 121.556 GB event logs and8.617 GB motion logs untouched and preserves their current byte/path compatibility.

### Second stage: losslessly remove repeated storage from event/numerical data

The observation packet contains a sliding window of the latest100 telemetry samples. Recording it repeatedly duplicates most of a second's numerical history. Candidate inputs repeat packet data, and model/checkpoint objects appear in multiple event contexts. Instead, store exact numerical samples once and link packets to their exact ordered sample ranges. Store exact model/checkpoint objects once with authenticated references, retaining original envelopes and timing.

For existing data, a codec must reconstruct the **original bytes and hashes**, not merely similar decoded objects, before deleting any originals. A separately versioned storage reader or lossless restore layer is necessary because frozen software expects old filenames and paths. Migrate one bounded bundle at a time, verify full roundtrip, and keep the original until verification and approval. This requires temporary space for one bundle, not another 372 GB archive. No codec conversion or compression benchmark has been executed during this audit.

For future data, the canonical format can natively use exact typed chunks plus reference envelopes. It must reconstruct exact delivered observations and model/file content; summary text is not a substitute.

The full read-only [event profile](event-profile.json) measured all 264 r4 event streams: observation records occupy **100.582 GB**, candidate inputs **17.110 GB**, replies2.837 GB, and other types about 1.027 GB. Observation plus candidate-input packets constitute **96.82%** of event bytes; that is not a deletion percentage.

The corrected [telemetry profile](telemetry-profile.json) examined36 fixed windows:64 observations each, at 10/50/90% byte offsets in C01/C14/C24 replicate1 for all four persistent entrants. Its2,304 observations occupy183.644 MB. Their telemetry arrays serialize to163.046 MB (**88.78%** of those observation bytes). There are230,400 stored row occurrences but only 26,328 distinct canonical row values within the windows, occupying18.602 MB. The repeated rows are directly measured; no compression was performed.

Accounting illustratively for either80 bytes per individual row reference or100 bytes per exact range reference yields a **68.6–78.5% reduction of sampled observation bytes**. Applying that ratio to all 100.582 GB of observation records gives a **69–79 GB savings scenario**. This is a fixed-window extrapolation, not a confidence interval or measured codec output. It excludes potential additional savings in the 17.110 GB of candidate-input records and from compact numerical representation. Together with the camera-retention option, it suggests a current-project footprint around **98–108 GB**, but only the camera arithmetic is directly established; the lossless part still needs implementation and full roundtrip verification.

Both read-only jobs officially succeeded with exit0: full event accounting `20260927T002013922654Z-3b118f4b` and corrected sampling `20260927T002524797060Z-a 5b24b6b`. Their [event receipt](event-profile-queue-receipt.json) and [sample receipt](telemetry-profile-queue-receipt.json) are retained. The initial optional sample in the first job mistakenly expected `telemetry_history` to be a list and returned zero samples; the corrected sampler uses `telemetry_history.samples`. No estimate uses the empty sample, and the full byte/type census was unaffected.

### Smaller, more lossy alternative — available, but not recommended by default

All existing compact r4 records, current per-run diagnostic/continuity outputs, statuses/selection and Analysis005 total about **0.831 GB**, before shared code/map/calibration/receipt dependencies. Keeping those plus all 12 selected raw runs and current viewer packages totals **19.099 GB** for that evidence/presentation set. This could discard348.258 GB of nonselected heavy files while retaining the other252 runs' compact records.

That does **not** preserve independent raw diagnostic recalculation or all nonselected model/checkpoint history. Final `candidate_state` files are not historical dialogue; `contexts/` directories are empty, and diagnostic outputs omit prompts/model text/state. Do not market the 19 GB alternative as equivalent scientific evidence. It is a separate permanence choice only if Randy accepts those losses, ideally after a compact exact decision/event extraction.

## Future batches: a storage contract, not “save everything then archive”

Propose an initial **30 GB target and40 GB admission ceiling for a comparable full batch**, subject to a bounded qualification actually demonstrating fit. The numbers below are a budget allocation, not measured output or a promise that an unimplemented recorder meets it.

| Permanent batch component | Proposed allowance | What it preserves |
|---|---:|---|
| Exact event/public-packet/model/checkpoint objects, stored once | 12 GB | All-run causal linkage, complete decision evidence, restart and scoring witnesses |
| Full-precision100 Hz numerical motion | 5 GB | Current motion/jerk/pause/tracking diagnostics, including gaps and flags |
| Selective RGB/depth and sparse progress imagery | 6 GB | Fixed representative episodes, important failures/anomalies, current-viewer-quality footage; not full video of every run |
| Compact all-run results/provenance | 1 GB | Every disposition, comparison denominator, exclusions and exact metric/settings record |
| Bounded derived packages/views | 4 GB | Readable current investigations without copying originals |
| Development/debug allowance associated with the campaign | 2 GB | Decisive failures and bounded qualification, not unlimited scratch |
| **Target** | **30 GB** | About one twelfth of the present r4 release |
| Additional allowance before admission ceiling | **10 GB** | Measured uncertainty/build/temporary margin; explicit rejection if projection exceeds40 GB |

The numerical budget has a concrete starting calculation: existing diagnostics consume32 float64 quantities per motion sample,256 bytes/sample. At100 Hz over the entire156,600-second planned cap matrix, that is **4.009 GB before extra fields, headers and missingness metadata**, without any compression. Additional safety/contact fields must be preserved where required. Downsampling to5 Hz would change the present jerk/peak/pause diagnostics and is not the default proposal.

The image budget can combine the current kind of 12 selected2 Hz trace imagery (about 3 GB in this batch) with sparse progress frames and bounded anomaly/bookmark windows. Keep RGB/depth together when perception verification is the purpose. Select a representative component before outcomes are known; label extra failure-selected windows as explanations, not a representative performance sample. Every failed/invalid/interrupted attempt still retains its complete numerical/event/scoring evidence and honest disposition.

**Do not generate full 10 Hz image files for every run just to delete them later.** Separate rendering/live sensing from persistence. Keep a bounded in-memory or disk ring buffer for rich windows, write the declared sparse stream, and commit triggered windows within the agreed budget. Live detections and candidate permissions must stay unchanged. This is an implementation proposal requiring timing/CPU/I/O checks and a new frozen release, not a modification to r4.

Exact all-run numerical/event evidence remains mandatory under the proposed contract. If it exceeds the projection, stop admission or use a declared evidence-recording failure endpoint; do not silently truncate core evidence or silently lower its quality during scored runs. Compression ratios, codec reconstruction, quotas, frame availability and all metric equivalence must be measured before the next large batch is authorized.

## Lifetime capacity: finite disks need a finite retention promise

A30 GB batch repeated forever still fills any finite disk. Set a **project evidence ceiling**, proposed initially at **150 GB after the existing-data reduction/normalization**; keep model/source/environment and transient headroom separately budgeted. A **100 GB C: free-space reserve** is an additional admission condition, not permission to grow until only 100 GB remains.

Within the ceiling, distinguish active investigations, completed reference campaigns and compact history. Keep compact all-run result/provenance history; reserve rich/numerical evidence for an explicit number of active/reference campaigns and valuable failures. At a campaign review checkpoint, either retain its full numerical/event contract within the budget, reduce an older campaign to a clearly labeled summary-plus-selected-evidence level, or decline new work until space is available. Reducing an older campaign relinquishes its all-run independent recalculation and must be an explicit human decision. Do not automatically delete failed runs or use silence as acceptance.

External storage is optional for a few specifically valuable references or temporary verified transformations. It is not the growth plan. The most valuable next implementation, after review, is a bounded compact-recorder/compatibility prototype and a concrete existing-frame-retention manifest—not a bulk archive or another full batch.

This plan intentionally distinguishes guaranteed arithmetic from hypotheses: the 230.152 GB image-retirement saving is measured against a defined retained viewer set; the 30–40 GB future budget requires qualification; codec savings require exact roundtrip evidence; permanently retained history must fit a finite capacity. No cleanup is authorized by this document.
