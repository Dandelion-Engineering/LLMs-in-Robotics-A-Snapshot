# Final checkpoint selection and freeze

Operational preparation, 2026-09-23. This document creates no selection decision, qualified cell, gate approval, freeze, release, seed or queue job. The eight original development003 attempts and their derivations are complete. Execute final selection/freeze only after the remaining carry-profile qualification, current retention and source-bound prerequisite disposition are complete; the successful C0-013 public-milestone repair probe is recorded separately below. It supplements the existing [execution runbook](../../Engineering%20Investigation/RUNBOOK.md), not a second readiness audit. The unchanged release is **264 attempts: 192 main and 72 controls**, with 300/600/900-second caps, 24 cases, 20 scenario families and two policy/noise replicates. Maximum original task time remains 156,600 seconds.

## 1. Close development opportunity and choose checkpoints

Before closing development, root records one dated, immutable decision, for example `Batch 01/development-selection-decision-001.json`, and appends its summary/reference to the [Development Ledger](../Development%20Ledger.md). This is an operator record, not a new Runtime schema. Give it these explicit fields:

| Field | Required content |
|---|---|
| `recorded_at_utc`, `operator`, `release_id` | Actual timezone-qualified decision time, responsible operator and `batch01-eval-r1`. |
| `initial_opportunity` | All four entrants; two working sessions or 12 active engineering hours and at most 60 development episodes each. |
| `historical_effort` | `active_engineering_hours: null`, `measurement_state: unmeasured`, `initial_time_ceiling_compliance: unknown`; identify the accounting cutoff and missing instrumentation. Do not substitute elapsed sessions, parallel-agent wall time, model latency, tokens or policy runtime. |
| `episode_accounting` | Per entrant: exact registered attempt IDs, terminal/missing dispositions, current canonical result/correction IDs, source snapshot references, total attempts and remaining episode allowance. Failed/invalid episodes still count; shared primitive probes and model smoke are reported separately. |
| `symmetric_extension` | Actual adoption time, the same opportunity offered to C0/A1/A2/A3, rationale, exact remaining development-plan references and stopping rule; retain `total_episode_ceiling_per_entrant: 60` unless a separately recorded symmetric episode extension is genuinely needed. Record acceptance/unused opportunity separately from consumption. |
| `selection_rule` | Adopt before final checkpoint selection: retain all four architectures; select the latest checkpoint whose mechanism, common interface, model/configuration and persistence implementation have the required development support. Do not require every LLM entrant to succeed, select a winner, or optimize against concealed/scored cases. |
| `selected_checkpoints` | For each entrant: architecture ID, actual development revision/attempt IDs supporting the choice, exact final source/configuration/prompt/development-knowledge identities, known limitations, and the reason any earlier checkpoint was rejected. Record shared-source changes after an episode and their supporting checks; do not relabel the earlier run as testing new bytes. |
| `evidence_refs`, `limitations` | Exact local path/SHA-256 references to plans, ledger/map snapshot, retained results/receipts and the decision basis; separate historical unmeasured effort from measured later effort. |

The symmetric closeout extension was already adopted at `2026-09-23T08:40:38.4259164Z` in [development-opportunity-extension-001.json](../development-opportunity-extension-001.json). It retains all four entrants, the cumulative 60-episode ceiling per entrant, the original eight development003 episodes and necessary common prerequisite repairs. Historical active engineering hours remain unmeasured; initial time-ceiling compliance remains unknown. The stopping rule closes the extension when named prerequisites have terminal evidence and the common implementation is eligible for freeze. Further entrant-specific tuning requires a separately declared symmetric opportunity. This runbook records that prior decision; it neither adopts another extension nor chooses final checkpoints.

This amendment cannot retroactively prove the original time limit was met. Report that limitation in the final comparison. From adoption onward, record participant, entrant/shared scope, actual active start/stop intervals and measured duration; retain overlapping participants separately, and leave absent records unknown. Equal opportunity is not equal realized effort or equal maturity.

At the completed development003 accounting cut, the 26 original attempts comprise C0=12, A1=6, A2=4 and A3=4; 27 canonical result records include the historical C0-002 correction. All eight development003 attempts completed execution and passed recorded actual-host timing. C0 and A3 completed their three-part jobs, A1 completed 0/6, and A2 completed 1/10 in each condition. All canonical validity labels remain `unknown`; differing tasks and these development outcomes do not establish a ranking or persistence benefit. The [Development003 report](../Development%20003%20Results.md) binds execution `10f91c9b` and derivation `75d4a1dc`, retaining the original inadmissible C0-010 release cut and both A3 carry cuts outside joint-state support.

The subsequent common-milestone probe **C0-013** is an additional episode, not a replacement for C0-010. Official execution `5a73938e` and finalization `9c91a9d8` succeeded. It completed 3/3 in 168.1155432 s, with maximum lag 0.0169045 s and no model calls. Its first configured after-release opportunity, without fallback, recorded 0.1000000000000334 s of open-jaw dwell and admissible required predicates. This is instantaneous empty-state evidence, not carry-duration qualification. The small canonical map read now contains **27 registered/completed attempts and 28 result records: C0=13, A1=6, A2=4, A3=4**, leaving respectively 47/54/56/56 episodes under the unchanged ceiling. C0-013's final derived interpretation was not yet available at this refresh. Re-read the map at actual closeout and retain every later attempt; these are dated counts, not a fixed selection.

The current source preparation also retains **164 Investigation tests in 27.477 s** (`38d34027`) and, after the registrar/public-milestone applications, **436 Runtime tests in 41.761 s plus 10 focused milestone tests in 0.009 s** (`dd45dfa8`), all officially succeeded/0. The registrar now retains exact frozen snapshots inside `Architecture Map/releases/<release_id>/code-bundle.zip` and `freeze.json`; the reader's Map containment remains intact. Milestone version 1.2 adds the public 0.10 s dwell while preserving the 60 s fallback and other cut families. Synthetic passes do not qualify the remaining carry profile. See the [non-authorizing evidence index](final-gate-evidence-candidates.json) for exact application, source and receipt references. Production Investigation HTML remains unrebuilt; scored execution has not begun.

Source-bound map lookup syntax is:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py' status --json
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py' lookup --kind run --stage development --limit 1000 --json
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py' lookup --kind result --limit 1000 --json
```

Check `displayed == total`; increase the lookup limit if needed. Use exact map snapshots and correction chains in the decision. The runner registers the eventual frozen revision and each scored attempt automatically; do not invent scored run/result records during selection.

## 2. Fix the external control documents and executable identities

Finalize the selection record, actual public resource policy, analysis settings (**2,000 bootstrap draws, public analysis seed 0**), complete matrix/counterpart rules, and the existing [12 fixed trace slots](../evaluation-trace-selection.json). Keep missing/failed trace slots; do not replace them with favorable examples. Keep all 264 dispositions in analysis. Preserve the predeclared broader diagnostic interpretation rules separately from this fixed display subset.

Retain a small control index with direct `{path, sha256}` references to those final records, the release plan, continuity/trace rules, `collect_results.py`, `analyze_results.py`, and the actual Investigation Python sources used for processing/reading/building. Include the source-matched implementation narrative JSON and its reader, template and script identities when that optional display is used. Add the index **and each directly referenced file** to final readiness `evidence_refs`; the protocol verifies those direct bytes. The artifact-preparation helper automatically covers Runtime Python plus `Architecture Map/map.py`, not these sibling folders. Supplemental freeze fields alone are not executable verification. Preserve these files unchanged after freezing; a later derived-tool repair must be a separately identified version, not an overwrite of frozen bytes.

Run from the project root, after all owned workers have naturally exited:

```powershell
$freezeRoot = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$freezePython = Join-Path $freezeRoot 'venv\Scripts\python.exe'
$freezeQueue = 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py'
$freezeExperiment = Join-Path $freezeRoot 'Long-Horizon Adaptive Robotics Expirement'
$freezeRuntime = Join-Path $freezeExperiment 'Runtime'
$freezePrepared = Join-Path $freezeExperiment 'Evidence\prepared-artifacts\batch01-eval-r1-final'
$freezeManifest = Join-Path $freezeExperiment 'Batch 01\freeze-batch01-eval-r1.json'
$freezeReadiness = Join-Path $freezeExperiment 'Batch 01\readiness-batch01-eval-r1.json'
$freezeRelease = Join-Path $freezeExperiment 'Evidence\releases\batch01-eval-r1'
& $freezePython -X utf8 -B $freezeQueue submit --project LLMs-in-Robotics --cwd $freezeRoot -- $freezePython -X utf8 -B (Join-Path $freezeRuntime 'freeze_artifacts.py') --output-dir $freezePrepared
```

Create the output parents deliberately first; `$freezePrepared` and `$freezeRelease` themselves must not exist. Keep the scored release on C under this path; development's D raw-root override is rejected for evaluation. Use `--model-config <actual JSON>` only if verified final settings differ from the intended defaults; it must enumerate the effective `ModelConfig` values. The prepared `model.json` records every effective setting either way.

Apply [queue discipline](../Queue%20Limitation.md): no concurrent submit/status/list/doctor while an owned worker/child is alive. After natural exit, save the actual successful official status receipt; use the receipt block in the [execution runbook](../../Engineering%20Investigation/RUNBOOK.md). The preparation job must be `succeeded`, integer exit status 0. Retain `started.json`, `runtime.zip`, `code.json`, `environment.json`, `model.json`, `prepared-artifacts.json` and receipt. Their creation-time `official_queue_completion_verified: false` remains unchanged. Adding or editing **any Runtime Python file**, including a test, after preparation requires fresh preparation.

## 3. Write the freeze, then bind readiness to its exact bytes

No current CLI authors these two documents. Use the executable freeze template in the [execution runbook](../../Engineering%20Investigation/RUNBOOK.md) with actual values:

| Freeze field | Source |
|---|---|
| `release_id`, `frozen_at` | `batch01-eval-r1`; actual timezone-qualified final freeze time, after checkpoint selection and qualification acceptance. |
| `code_sha256`, `environment_sha256`, `model_sha256`, `protocol_sha256` | Exact successful `prepared-artifacts.json` values; the first three identify artifact indexes. |
| `artifacts` | Exactly `code`, `environment`, `model`, each with actual index `path`/`sha256` matching its top-level hash. |
| `selection_criteria` | Nonempty text stating the adopted checkpoint rule and exact selection/control references, fixed trace rule, unchanged family-cluster analysis settings and no scored-result selection. |
| `maximum_retries` | Integer `0`; no hidden scored-policy retries. |
| `restart_matching_mode` | `qualified_class` only with the independently supported accepted bundle described below. Do not use legacy default mode as a substitute for missing qualification. |
| `restart_qualification` | Actual bundle `path`, ordinary file-byte `sha256`, canonical `bundle_sha256`, canonical `class_spec_sha256`, `selection_rule: unique_bilateral_payload_template`, fixed `payload_template_to_cell`, measured `prospective_absence_bound_s`, and explicit `absence_timebase`/`absence_endpoint`. Copy the already accepted values; this runbook selects no cells or bounds. |

The accepted bundle must be `prior-restart-class-qualification-1`, `status: measured_development`, have `accepted_at_utc < frozen_at`, retained `artifact_files` and complete measured cells/support. Mapped A/B cells share one fixed destination, with supported source and absence conventions; unsupported states remain unknown. Keep the provisional rule, construction/independent validation, failures, untested combinations and discrete-sampling/empirical-transfer limitations intact. The protected loader rehashes every indexed artifact. D qualification references may be absolute local paths. Byte hashes and canonical hashes are distinct.

After writing the final immutable freeze, compute its byte SHA-256, then write fresh final readiness (do not relabel the historical working `readiness.json` as frozen evidence):

```powershell
$freezeByteSha256 = (Get-FileHash -LiteralPath $freezeManifest -Algorithm SHA256).Hash.ToLowerInvariant()
```

Final readiness requires `release_id`, `freeze_sha256: $freezeByteSha256`, `scored_ready: true`, a nonempty `evidence_refs` array of real `{path, sha256}` references, and these eleven Boolean `gates`: `physical_workcell`, `public_perception`, `independent_evaluator`, `conventional_baseline`, `candidate_implementations`, `model_and_terms`, `isolation`, `timing_and_resources`, `evidence_retention`, `disturbance_admissibility`, `equal_development_opportunity`. Set each true only when its retained evidence and stated limits justify it; this document changes none. Bind the decision record and control files as well as measured summaries/receipts. Relative references resolve beside the containing JSON. Avoid a freeze/readiness circular hash dependency.

Use the existing [evidence checkpoint](prefreeze-evidence-checkpoint.md) once as the starting index, replacing pending items with completed evidence and identifying source changes since its cut. In particular, use the final timing-repair evidence, actual matched restart development, accepted qualification and current storage estimate. Do not convert `resource_caps_enforced: false` into a continuous hard-cap claim: state the actual hard limits, sampled stop policy and unknown peaks/attribution. Historical unmeasured hours remain unknown even if documented symmetric opportunity supports that readiness gate.

## 4. Create once, execute the stored schedule, preserve result selection

Only after the actual final documents exist and every gate is justified:

```powershell
& $freezePython -X utf8 -B (Join-Path $freezeRuntime 'protocol.py') create --release-dir $freezeRelease --freeze-manifest $freezeManifest --readiness $freezeReadiness
& $freezePython -X utf8 -B $freezeQueue submit --project LLMs-in-Robotics --cwd $freezeRoot -- $freezePython -X utf8 -B (Join-Path $freezeRuntime 'release_runner.py') run --release-dir $freezeRelease --limit 4
```

The first command creates concealed seeds and `release.json` plus exactly 264 `runs/<run-id>.json` manifests. Keep them outside candidate mounts and do not inspect seeds for development. The second queues at most four original attempts in stored schedule order; omit `--run-id` for normal execution. All substantial verification/hashing/model work stays in the queue.

After each natural queue completion, retain the successful official receipt and finalize before the next batch:

```powershell
& $freezePython -X utf8 -B (Join-Path $freezeRuntime 'release_runner.py') finalize --release-dir $freezeRelease --verified-queue-job-id '<actual completed job ID>' --queue-status '<actual retained receipt JSON>'
```

Recheck actual remaining capacity and incidents between batches; preserve every original attempt and full caps. A successful queue exit is not successful task work. Follow the existing runbook's explicit incident-review path; do not waive integrity faults, retry a claimed manifest or drop a weak entrant. Complete all 264 honest dispositions. Source/policy improvements after scored evidence require a new release and fresh manifests.

For the final handoff, use the exact [execution runbook, steps 5–6](../../Engineering%20Investigation/RUNBOOK.md): queued `process_evaluation.py --release-dir ... --output-dir <fresh>` creates `index.json` and `selected-results.json`; queued `analyze_results.py --release-dir ... --selected-results ... --output-dir <fresh>` creates `analysis.json` and `analysis-provenance.json`. Require both official receipts. The final builder takes `--evaluation-index`, `--evaluation-receipt`, `--analysis-file`, `--analysis-provenance`, `--analysis-receipt` and the unchanged trace-selection file. Supply `--implementation-narrative` with the frozen narrative artifact to display current mechanisms only where the immutable revision archive matches its source identities. Exact selected canonical corrections, before/after input hashes and release bindings govern; preserve missing/invalid outcomes and whole-block infrastructure exclusions. Finish real browser QA and interpretation after the actual complete analysis.

## Decision authority

No current freeze field, protocol check or project document reserves routine checkpoint selection, an explicitly symmetric development extension, evidence interpretation, local artifact preparation or execution of the already authorized full experiment for a new user-only signature. Root may complete those engineering decisions within the existing authorization and document the rationale. `selection_criteria` is not a winner-selection or approval field. Qualification acceptance still needs its concrete engineering evidence; structural validation alone cannot supply it.

Ask Randy only if a material unresolved choice would change the authorized experiment or its purpose: for example, reduce/replace the 264-run comparison, drop an entrant, add a different scientific question, relax a failed validity requirement, incur new spending, or make a broader external commitment. A missing measurement or failed prerequisite calls for bounded authorized repair and honest reporting, not a ceremonial approval request. This runbook neither makes those changes nor asserts that any current missing gate is satisfied.
