# Storage audit — September 26, 2026

**Audit and recommendations only. No pre-existing experimental evidence, code, configuration, models, viewers or Git history was deleted, moved, compressed or rewritten. No simulations, inference calls or rebuilds were run. Cleanup remains for Randy's review.**

The project contains **433.084 GB of logical file sizes (403.340 GiB), in 2,782,462 files**. The completed r4 evaluation alone occupies **363.997 GB**. Across the project, saved depth/RGB frames contribute **250.187 GB** and event/motion streams contribute **136.350 GB**. These recordings explain the growth; seven copies of the investigation are not the cause.

There is an important size-accounting correction: the three large model installations already use hardlinks. The census counts each pathname, but verified repeated hardlinks account for **25.536 GB**. Subtracting those gives **407.548 GB / 379.558 GiB of known-hardlink-adjusted logical content**, not an exact physical allocation total. Removing the extra model paths would not free 25.5 GB.

The recommendation is **selective image retention plus lossless removal of repeated event/numerical storage**, with a finite budget for future batches. **Start with [Sustainable Retention](Sustainable%20Retention.md)** for the revised decision and its explicit information tradeoffs. A372 GB archive would nearly fill the available external SSD and postpone the same problem; it is not recommended as the growth solution.

For the current batch, retaining the exact3.061 GB of RGB/depth used by today's viewers and retiring the other r4 frames could recover approximately **230.152 GB** without moving anything to D:. Keep all original event/motion/resource/result data in this first stage. This preserves the inputs used by the current numeric calculations but permanently sacrifices pixel/depth inspection of discarded moments. Nothing has been removed, and actual dependency/retention verification plus Randy's approval must precede such an irreversible change.

Before another large batch, qualify a recorder against a proposed30 GB target/40 GB admission ceiling, separate live sensing from saved imagery, and stop repeating whole telemetry/model/checkpoint payloads in uncompressed event records. These are budgets to demonstrate, not achieved output sizes. Current frozen runs must retain their original identity and interpretation.

## 1. Scope and measurement

The metadata census ran **17:00:00–17:06:06 PDT**, recursively including hidden `.git`, ignored files and `venv`. There were **zero traversal errors and no skipped reparse points**. Only this audit's measurement-output directory was excluded. A few newly created audit/coordination files were included if present when visited; these are immaterial to rounded totals. The filesystem was not frozen, so this is a timed snapshot rather than an atomic volume snapshot.

Units: **GB = 1,000,000,000 bytes; GiB = 1,073,741,824 bytes**. Directory totals include their children; do not add a parent to its descendants. File-type and directory tables are alternative decompositions, not additive savings lists.

The retained measurement is compact: [directory totals](measurement/directories.tsv), [directory/extension groups](measurement/file-groups.tsv), [all files at least 1 MB](measurement/large-files.tsv), [summary](measurement/summary.json), and [physical identity checks](measurement/physical-checks.json). The audit's temporary path-by-path metadata listing was compacted after count/byte reconciliation; no original evidence was copied or altered.

Windows directory-entry metadata did not provide usable file IDs/link counts, and `GetCompressedFileSizeW` did not establish allocation slack for ordinary files. Those preliminary fields were discarded. Ordinary file identity plus `FILE_STANDARD_INFO` was subsequently checked for **all files at least 1 MB and one RGB/one depth file per frame directory: 1,757 checks, including 576 frames**. All sampled frames had one link; no checked non-vendor file had multiple links. Smaller unsampled hardlinks, filesystem metadata, allocation slack, and any links outside this project are not comprehensively measured. Consequently, recommendations quote logical-byte estimates rather than promise exact free-space gains.

Model/executable/archive hashes were verified in shared-queue job **`20260927T000230038787Z-80b2721b`**, officially **succeeded, exit 0**; see [receipt](asset-queue-receipt.json) and [asset checks](asset-verification.json). It read 38.246 GB across 150 asset paths, all without modifying sources. This is not a whole-project duplicate-content scan.

At census completion C: had **204.994 GB free**, and D: had **499.408 GB free**. D: was verified as the USB **SanDisk Extreme 55AE**. Other project evidence already outside the project root was not recursively measured. These free-space values are snapshots, not reservations.

## 2. Where the space is

### Major project areas

| Area | Logical GB | Meaning |
|---|---:|---|
| `Evidence/` | 388.980 | Raw development/scored recordings, compact provenance, calibration and derivation records |
| Three Runtime trees combined | 38.364 | Primarily the same hardlinked model/runtime assets; about 25.536 GB is repeated pathname accounting |
| `Engineering Investigation 007/` | 3.106 | Current lossless normalized trace packages and HTML |
| `Engineering Investigation 006/` | 0.785 | Superseded monolithic presentation plus source; historical packaging failure evidence |
| Original `Engineering Investigation/` | 0.061 | Earlier generated viewer and supporting files |
| `Task and Architecture Explorer/` | 0.034 | Four projected episodes, exact selected payloads, code and compact index |
| `.git/` | 1.535 | Git history plus temporary object garbage; not the hundreds-of-GB cause |
| `venv/` | 0.151 | Installed Python environment |
| Other project areas | about 0.067 | Maps, Batch 01, sources, literature and coordination |

Investigation002/003/004/005 are approximately **0.5 MB each**, mainly distinct source generations. They are not full raw-data copies and several are active dependencies of 007.

### Evidence areas

| Directory | GB | Disposition |
|---|---:|---|
| `Evidence/releases/batch01-eval-r4/` | 363.997 | Final release: 264 planned dispositions, including failed/invalid/interrupted records |
| `Evidence/raw/` | 17.651 | Distinct development attempts, including failures |
| `Evidence/releases/batch01-eval-r3/` | 3.263 | Retired release history |
| `Evidence/releases/batch01-eval-r2/` | 2.240 | Retired release history |
| `Evidence/releases/batch01-eval-r1/` | 0.000475 | Compact retired-release record; not another complete batch |
| `Evidence/calibration/` | 1.005 | Calibration and validation evidence, mixed compact and raw assets |
| `Evidence/derived/` | 0.501 | Diagnostics, continuity, retention inventories and validation outputs |
| `Evidence/runtime-environments/` | 0.293 | Root filesystem archive and registered WSL virtual disk; not ordinary cache |
| `Evidence/diagnostics/` | 0.024 | Diagnostic reports |
| Remaining Evidence areas | about 0.005 | Queue receipts, release-series assessments, decisions and prepared artifacts |

Within r4, **363.719 GB** is inside the 264 `attempts/<run>/evidence/` directories; about **0.279 GB** is the surrounding release/control record. Its raw data includes **152.115 GB depth, 81.098 GB RGB, 121.556 GB events and 8.617 GB motion**. Other JSONL and small files explain the remainder.

### File categories across the whole project

| Category | Files | GB |
|---|---:|---:|
| Depth NPZ under frame directories | 1,339,741 | 163.630 |
| RGB PNG under frame directories | 1,339,742 | 86.556 |
| `events.jsonl` | 319 | 127.148 |
| `motion.jsonl` | 288 | 9.203 |
| GGUF weight paths | 6 | 34.497, mostly repeated hardlink paths |
| Ordinary `.log` files | 493 | 0.033 |
| Bytecode caches | 4,044 | 0.030 |
| Everything else | 97,829 | 11.986 |

PNG/NPZ elsewhere, such as calibration, are included in “everything else.” Ordinary `.log` files are small; the large logs are explicitly the raw event/motion JSONL streams. No large independent video library or hidden extraction tree emerged as an unexplained dominant category.

### Largest individual files and run directories

Each Runtime model directory has a **9.002 GB 14B GGUF** and **2.497 GB historical 4B GGUF**. For each model, all three paths have the same file identity and three hardlinks: one physical file, not three independent copies.

The largest unique raw event file is `Evidence/releases/batch01-eval-r4/attempts/batch01-eval-r4-C20-rep1-baseline-persistent/evidence/events.jsonl`, **1.719 GB**. Its whole raw directory is **3.336 GB**, preserving the baseline pipe-budget failure. The file's size is not the candidate's 32 MiB transport usage; it contains supervisor-expanded evidence.

Other large examples:

| Path below the experiment root | GB |
|---|---:|
| `Evidence/raw/B01-dev-C0-007/` | 3.010 |
| `Evidence/raw/B01-dev-C0-007/events.jsonl` | 1.232 |
| r4 `C24-rep1-baseline-persistent/evidence/` | 2.927 |
| r4 `C24-rep2-baseline-persistent/evidence/` | 2.925 |
| r4 `C24-rep1-A3-no-persistence/evidence/events.jsonl` | 1.182 |
| r4 `C24-rep1-baseline-persistent/evidence/events.jsonl` | 1.162 |
| `Engineering Investigation 007/site-r4-003/` | 3.106 |
| `Engineering Investigation 006/site-r4-001/index.html` | 0.785206 |

Here “r4” abbreviates `Evidence/releases/batch01-eval-r4/attempts/batch01-eval-r4-`. [The sortable/searchable large-file inventory](measurement/large-files.tsv) retains full paths, including every individual file at least 1 MB. [Directory totals](measurement/directories.tsv) include every nonempty directory.

## 3. Provenance and actual duplication

The recording source explains the volume:

- `Runtime 004/experiment.py:799–806` requests RGB/depth every 0.1 simulation seconds. `sensor_worker.py:184–224` writes individual 640×480 PNG and compressed depth NPZ files. **Both formats already compress each frame**; large further lossless archive savings must not be assumed.
- `experiment.py:739–744` records motion at 100 Hz. Its observations and candidate steps additionally contain overlapping one-second/100-sample telemetry windows (`:163–201`, `:443–446`, `:582–590`, `:768–772`). This repeats many state values.
- `experiment.py:420–435` writes each complete event payload into uncompressed JSONL. Model request content appears in the candidate reply, separate model-request event and model-context evidence (`:887–900`; `candidates.py:913–918`).
- `candidates.py:127–170` records complete checkpoint text on reads and changed writes. It skips unchanged state; no uncontrolled recursive checkpoint-growth claim was established. IPC compression is expanded before durable evidence is written (`candidate_worker.py:115–140`, `sandbox.py:76–111`).
- Live sensing derives detections from RGB/depth (`sensor_worker.py:282–294`). The model receives text/structured observations, not the saved PNG files. Retention frequency can therefore be separated from sensing frequency in a **new** release; deleting depth still removes unique perception-debug information.

The earlier [r4 development retention inventory](../Evidence/derived/retention-development-r4-001/summary.json) already planned **577.363 GB including a 50 GiB reserve**, using a measured planning rate of 3.189 MiB/task-second over 156,600 maximum task-seconds. Its capacity check passed at that time. This was a capacity forecast with limitations, not a small-data retention policy. The observed growth is consistent with retaining a large batch's complete streams.

The investigated duplication is more specific than “copying all the evidence”:

| Apparent duplication | What is actually retained |
|---|---|
| Runtime/vendor in three trees | Large files already hardlinked by `Batch 01/Release Infrastructure Repair 001/clone_runtime.py:23–33` and `Release Lifecycle Repair 001/copy_runtime.py:51–59`. Hash verification found only **9.417 MB of distinct allocated identical model/runtime assets** beyond one content copy, not25.5 GB of recoverable space. Small other vendor links explain the census's slightly larger hardlink adjustment. |
| Development versus release raw roots | Distinct attempts with separate identities. They are not established duplicate experiments or copied recordings. |
| Architecture Map release copies | Small frozen code bundles and freeze records (`release_runner.py:428–446`), deliberately binding provenance. |
| Investigation005 derivatives | Diagnostics/continuity/status outputs and compact references, not copies of all camera streams (`process_evaluation.py:123–146`, `:330–363`). |
| Investigation006 and007 | Two representations of selected trace evidence.006 is a 785 MB monolithic HTML snapshot;007 is3.106 GB of bounded sidecars/HTML.007 solves browser allocation, not total disk minimization. Both refer to original images. |
|007 validation first-trace output | About95.321 MB of package material under `Evidence/derived/investigation007-package-validation-004/first-declared-trace`; source-bound validation output. Candidate for archive/rebuild only with receipt/dependency preservation. |
| Explorer versus007 | About33.8 MB of derived display projections and deduplicated selected exact payloads. Reuses original frame paths. |
| Failed005/007 build attempts | Failure records with distinct causes;001/002 did not leave another full published007 package. Empty output folders do not enter byte totals. |

No exhaustive hash comparison of all 2.78 million files was attempted. Similar images and repeated-run names are not proof of byte identity or dispensability.

A further read-only [event profile](event-profile.json) accounted for every byte in all 264 r4 event streams: **100.582 GB observation records**, **17.110 GB candidate-input records**, **2.837 GB candidate replies**, and about 1.027 GB of other event types. Thus observation plus input packets occupy **96.82%** of the 121.556 GB event total. Both contain the repeated telemetry window. This is measured type/byte accounting, not a claim that96.82% can all be deleted. Job `20260927T002013922654Z-3b118f4b` officially succeeded with exit0; its [receipt](event-profile-queue-receipt.json) is retained. The initial optional telemetry sample used the wrong nested-schema assumption and returned no samples; only its full event accounting is used. The corrected bounded sampler is separately documented.

## 4. What must survive, and what viewers need

The current chain is:

`frozen code + manifests + raw runs → Investigation005 readers/derivatives + Analysis005 → Investigation006 reader fix → Investigation007/site-r4-003 → Task and Architecture Explorer`

The current viewer selects12 traces from 264 dispositions. It retains observation samples at target2 Hz **plus linked parent/final observations**, motion at 5 Hz plus final sample, and all non-observation events. Its normalized payload codec is lossless for those retained inputs; it is not a lossless replacement for every raw sample.

[Viewer dependency measurement](viewer-dependencies.json) checked12 trace-manifest hashes and sizes, then statted their referenced originals: **16,666 RGB and16,666 depth files, totaling3.061 GB**. No missing files or size mismatches were found. Image hashes were not all recalculated. Together with 007's3.106 GB and Explorer's0.034 GB, the existing presentation plus its referenced RGB/depth is approximately **6.200 GB**. This excludes full raw-source click-throughs, rebuild inputs and compact records elsewhere. The Explorer's four traces are a subset, not another 3 GB: its RGB totals0.161 GB and its depth references0.311 GB.

As an alternative archive boundary, retaining **all raw data for the 12 selected runs uses15.143 GB**, instead of extracting only selected frames. Their local viewers, raw links and selected-run rebuild inputs then remain coherent. The remaining252 raw directories total348.576 GB. Preserved compact manifests/results support aggregate statistical recomputation; independent raw diagnostics/continuity recalculation or new trace inspection would require restoring those runs. This remains an alternative, not the recommended finite-capacity strategy.

| Storage category | Scientific/reproducibility value and unique information | Current viewer dependence | Smaller representation and exact-regeneration limits | Tracking |
|---|---|---|---|---|
| Raw event/motion streams | Original order, timing, requests, observations and high-frequency motion; required for full re-analysis and alternate investigations | Packaged playback does not stream the raw JSONL; raw-source links and rebuilding require it | Metrics and selected packages omit information. Re-running asynchronous simulation/inference is not exact reconstruction | Ignored raw/scored evidence |
| RGB/depth streams | Exact captured sensor data and perception-debug inputs; unique pixels/depth | Referenced selected RGB/depth required; most frames are outside current selection | Detections and sparse samples do not reconstruct originals. Rendered replay is not original observation | Ignored, including relevant calibration formats |
| Frozen manifests, source bundles, prompts, model IDs, terminal records, receipts, exclusions, partial-run provenance | Essential identity and interpretation, including failures and unknowns | Needed for provenance and readers | No replacement by aggregate results; preserve exact historical records | Mostly tracked; raw manifests also inside ignored bundles |
| Diagnostic/continuity/analysis outputs | Compact interpreted/derived evidence with source bindings | Current estimates and trace eligibility depend on these | Measurements can be regenerated with complete frozen inputs; creation times, job IDs and historical file bytes are not promised identical | Mixed;405.770 MB of derived content tracked |
| Current007 package | Exact selected normalized reader outputs and browser payloads | Direct dependency | Rebuildable in meaning from complete bound sources; entire historical bytes not guaranteed because build timestamps/paths enter output | Generated package ignored; source tracked |
| Explorer generated data | Selected four-run display and exact model/file disclosures | Direct dependency | Likely deterministic with identical007 inputs/code/paths/environment; exact rebuild was not run during audit | Data ignored except compact index; code/QA tracked |
|006/original older HTML | Historical presentation, including documented oversized-package failure | Not current playback; preserve referenced provenance and any legacy use | Rebuild may differ in timestamps/bytes. Archive originals rather than assume exact recreation |006 generated HTML ignored; original60.041 MB HTML tracked |
| Development, retired, failed and interrupted runs | Unique experimental/engineering history, failures and exclusions | Mostly historical; compact records stay relevant | Not exact duplicates of later runs; do not erase failed attempts or unknown endpoints | Large raw ignored; compact records tracked |
| Calibration/validation/scratch | Qualification and failure evidence; some generated fixtures are reconstructible | Indirect source/qualification dependencies | Trace producer and receipt first; a folder named intermediate can contain irreplaceable execution observations | Mixed |
| Weights/binaries/licenses | Exact model/execution identity and usable historical runtimes | Static viewers need none; reruns need compatible exact assets | Downloads may be hash-verifiable if still available; availability/environment reproducibility not guaranteed | Vendor ignored; compact identity tracked |
| Python environment, bytecode, WSL environment | Environment supports rebuilding/running; bytecode is derived | Static viewers need none | Bytecode can regenerate; reinstalling pins is not byte-exact environment recreation. Registered WSL VHD is a live dependency | Ignored payloads; pins/config tracked |
| Git objects | Project source/history; temporary objects have a different role | Not runtime playback, but history matters | Preserve repository history; verify garbage status/integrity before any approved cleanup | Git internal data; no current LFS files |

**Preserve the evidence needed for the declared claims:** every disposition and exclusion, original identities/frozen sources/licenses/receipts, scoring witnesses, current viewer dependencies, and numerical/event/model/checkpoint history if independent all-run diagnostics and decision inspection remain promised. Preserve the interrupted C24 A1 run's unknown outcome; never replace it with a successful rerun. Unique unselected pixels may be deliberately retired under an approved retention amendment, with the resulting loss of pixel-level reassessment made explicit. Neither “not used by this viewer” nor “unique byte” alone decides permanence.

## 5. Proposed actions and estimated savings

These are alternatives and overlapping stages, not amounts to add indiscriminately. **No action below was executed.**

| Class | Recommendation | Approximate C: saving / future avoidance | Conditions |
|---|---|---:|---|
| Safe/reversible candidate | Inspect Git's53 temporary `tmp_obj_*` garbage files | **0.654 GB** | Verify repository integrity and no active Git writer before approved cleanup; no history rewrite. Currently only identified as garbage, not certified safe to delete |
| Safe/reversible candidate | Remove generated bytecode, or reinstall venv if needed | **0.030 GB cache**; venv at most**0.151 GB**, overlapping its cache | Negligible benefit; preserve dependency/environment records. Do not prioritize over raw storage |
| Rebuildable/archive candidate | Archive006 monolithic HTML, earlier original viewer and007 first-trace validation package | Roughly**0.785 +0.060 +0.095 GB** | Preserve original hashes/receipts and recoverable originals. Tracked original HTML removal would not remove its Git history |
| Rebuildable but useful locally | Current007 package and Explorer data | At most**3.140 GB** | Removing them breaks current use until rebuilt/restored; retain locally instead |
| Exact duplicates | Consolidate remaining distinct identical runtime assets | Only about**0.009 GB allocated** in checked assets | Large weights already hardlinked. Preserve frozen path resolution; not a meaningful saving |
| Recommended reduction for review | Retain currently referenced RGB/depth and retire other r4 frames | Up to **230.152 GB** | Irreversible loss of discarded pixels/depth; keep all event/motion/resource/result files. Verify dependencies, designate extra failure windows, record retention and obtain approval |
| Archive alternative, not growth solution | Development raw plus retired r1/r2/r3 releases | **23.154 GB** | Valuable historical evidence, but moving it does not reduce total retained data |
| Archive alternative, not growth solution |252 r4 raw directories outside the 12 current traces | **348.576 GB** | Would nearly fill external storage when combined with other history; not recommended as primary strategy |
| More aggressive archive alternative | All r4 raw except current selected RGB/depth assets | Up to **360.658 GB** | This overlaps the 348.576 GB option; additional saving only about 12.082 GB. Raw-log links and rebuilds require restoration. More complex and not the first recommendation |
| Future pipeline | Save2 Hz rather than 10 Hz RGB/depth, while live sensing stays10 Hz | Up to **186.570 GB per similar r4 batch** | Arithmetic scenario:80% of 233.213 GB frames, before rich-event windows/parent-linked exceptions. Changes future retained information; needs approved retention contract |
| Existing/future lossless storage proposal | Store telemetry once and reference exact ranges; then evaluate additional lossless compression | **69–79 GB observation-only savings scenario** from measured bounded redundancy | Fixed-window extrapolation, not measured codec output. Candidate-input duplication is additional but unquantified. Require byte-exact roundtrip before existing originals can be retired; no compression was performed |
| Future pipeline | Lower stored motion rate where permissible | At most about**8.186 GB** for 100→5 Hz on r4 motion | Loses high-frequency history; keep full critical dynamics if required. Prefer lossless column/chunk representation before thinning scored evidence |

The archive combination is **about 371.730 GB** (348.576 +23.154). It is arithmetic, not the recommendation. Even the earlier499.408 GB free-space snapshot would leave only about 127.678 GB externally; Randy reports roughly 400 GB available, making the constraint tighter. One transfer consumes most of the remaining capacity and does not make the next simulation sustainable. Prefer the measured230.152 GB selective-image option and a validated compact recorder, detailed in [Sustainable Retention](Sustainable%20Retention.md).

### Archive compatibility must be solved first

Original metadata binds absolute paths and bytes (`Runtime 004/release_runner.py:103–108`, `:653–654`). The selected-trace reader rejects symlinks/escapes, explicitly withholds cross-volume playback and compares the terminal's result path to the actual result path (`Engineering Investigation 005/selected_trace.py:24–25`, `:63–79`, `:105–111`). Images in published HTML use relative URLs; raw image hashes occur inside authenticated event records.

Therefore a simple move to D:, junction, rewritten manifest, or replacement of `.jsonl` with `.jsonl.gz` is **not** an immediately compatible cleanup. The proposed first archive procedure is: build an identity/location catalog without changing originals; copy a complete chosen raw bundle with its original relative layout; verify hashes/byte counts; test restoring a representative bundle to its original C: location and validating it; preserve receipts and exact archive inventory; only then, with Randy's cleanup approval, remove selected source copies. Verification/restoration may need temporary space, which belongs in the plan. A later separately versioned reader can resolve immutable artifact identities through a location catalog while preserving original manifests.

## 6. Storage architecture for future experiments

1. **One canonical immutable raw-evidence store, separate from code and views.** Identify runs and artifacts by immutable ID/hash; keep location in an append-only catalog. Store model assets once with compatible read-only references. Distinguish original event identity from current storage location and preserve candidate/evaluator separation.
2. **Small records for every attempt.** Always retain manifest, exact revision/config/model identities, seeds or protected references, scoring inputs/outputs, execution/validity/task status, failure/exclusion reason, timing/resource accounting, actions and responses, and a declared evidence-availability manifest. Failed, invalid and interrupted attempts stay in the denominator/history. Missing rich evidence must have an explicit reason, never appear as zero or success.
3. **Predeclare tiers.** Scored runs get the evidence required by their scientific contract plus an outcome-independent representative rich subset. Development gets bounded debug windows and preserved decisive failures/qualifications. Add rich capture around declared events/anomalies where feasible, with explicit byte limits; do not keep only favorable examples. An event-triggered rich subset is explanatory, not a representative performance sample. Existing runs are not retroactively thinned by this proposal.
4. **Record exact payloads once.** Event envelopes keep time, ordering, parent IDs and hashes. Content-addressed checkpoint/model objects and indexed telemetry chunks avoid repeating full text/window arrays. Preserve exact reconstruction of what was supplied to each candidate, including timing and order; lossy summaries cannot replace that audit trail.
5. **Separate sensing, control and persistence rates.** Continue live sensor/control timing as required. Store selected RGB/depth plus declared rich windows. Evaluate lossless temporal image/depth representations and chunked binary motion/text storage; ordinary PNG and NPZ are already compressed. A lossy RGB video can be a clearly labeled preview, not a substitute for original inputs if pixel-level evidence is required. Retain depth precision, timestamps, camera calibration and correspondence where relevant.
6. **Views reference evidence.** Keep small indices and lazy packages; share content hashes across views.007 already avoids copying camera streams and uses content addressing. Improve duplicated telemetry before replacing a viewer that works. A build scratch directory needs a manifest, a verified published result and a tested reconstruction recipe before automatic expiry; failed execution evidence is not automatically scratch.
7. **Budget before admission and during recording.** Run a representative bounded qualification under the proposed recorder, measure bytes/minute by category including worst-case failures and long contexts, and project the complete run matrix plus invalid-attempt allowance, derived outputs and reserve. Proposed budgets are a **30 GB target/40 GB admission ceiling per comparable batch**, a **150 GB project-evidence ceiling after reduction**, and a separate **100 GB C: free-space floor**. These are reviewable engineering limits, not proven attainable rates. Define a predeclared safe stop/storage-failure outcome rather than silently truncating evidence or changing quality mid-scored-run.
8. **Finite retention across campaigns.** Keep compact all-run history, bounded active/reference numerical evidence and selected rich traces. At review checkpoints, deliberately choose which campaigns retain independent raw recalculation and which retain only metrics plus selected evidence. Preserve failure history and label sacrificed capabilities. External storage is optional for selected references or bounded verification, not the default sink for unlimited raw output.

Recording changes can alter CPU/I/O load and inference/physics timing. They require a new frozen runtime/recorder release and bounded timing, resource, evidence-roundtrip and viewer validation before a new scored campaign. They do not amend the completed r4 experiment.

## 7. Git and configuration recommendations

The pre-audit tree has **7,331 tracked files totaling886.415 MB**. Tracked derived outputs account for 405.770 MB, compact release records284.412 MB, and the largest tracked file is the original60.041 MB viewer. `.git` is1.535 GB, of which Git reports639,024 KiB (**654.361 MB**) of temporary garbage. There are **no current LFS-tracked files**; installed LFS filters do not imply data is using LFS. LFS would not reclaim ignored local raw evidence.

Existing large untracked assets are covered by current ignores. The unignored untracked items during this audit were new audit/coordination files and Randy's new chat, not an exposed raw-data tree. Future patterns remain fragile:

- Root `.gitignore:20–21` names006 `site-r4-001` and007 `site-r4-*`; later names may escape.
- `Evidence/.gitignore` excludes `raw/` and release-attempt `evidence/`, appropriately separating raw from compact records.
- Calibration exclusions and named validation generations are specific to current formats/paths.
- Runtime vendor/scratch and Explorer generated data are ignored, with Explorer's compact index kept tracked.

Recommend a stable ignored output root for new generated packages, an explicit allowlist for compact manifests/receipts, and a staged-file size/large-binary check with reviewed exceptions. Do not blanket-ignore `*.jsonl`: canonical maps use it. Preserve `.gitattributes`'s `-text` rule for exact experiment bytes under `core.autocrlf=true`. Keep code, manifests and release identities versioned; decide deliberately which large derived payloads merit Git. **No ignore, LFS, attributes, hooks, history or pipeline setting was changed.**

## 8. Review decision and reproduction

Recommended next task after review: a **bounded compact-recorder/roundtrip qualification plus an exact proposed frame-retention manifest**. Preserve all-run numerical/event/decision evidence, while accepting a clearly declared limit on image retention. Verify that the new format actually fits the agreed budget before another large batch; present the concrete irreversible image-removal list before cleanup. Cache cleanup and a bulk external archive do not solve continued growth.

This audit stops here. It does not authorize cleanup, relocation, changes to scientific evidence requirements or a new batch.

Reproduction tools are [inventory.py](inventory.py), [summarize_inventory.py](summarize_inventory.py), [verify_assets.py](verify_assets.py) and [viewer_dependencies.py](viewer_dependencies.py). They write only audit outputs; do not rerun them against existing output names. Use a fresh audit workspace/output location for a new snapshot. The full inventory is metadata-only; sustained asset hashing belongs in the shared queue. `summarize_inventory.py` intentionally compacts only the audit's own temporary metadata listing. The saved inventory helper was corrected after detecting unusable Windows directory-entry physical fields; final measurements use only logical census values plus explicit physical checks. No full census was repeated.

[Audit facts](audit-facts.json) retain Git/current-viewer/coarse-archive totals and the starting commit. [Retention options](retention-options.json) retain the revised non-archive arithmetic and budget scenarios. [Physical checks](measurement/physical-checks.json), [asset hashes](asset-verification.json), [queue receipt](asset-queue-receipt.json), [viewer dependency checks](viewer-dependencies.json), [full event accounting](event-profile.json) and [corrected telemetry samples](telemetry-profile.json) separate verified observations from estimates. The report contains no external literature or hardware-performance claim.
