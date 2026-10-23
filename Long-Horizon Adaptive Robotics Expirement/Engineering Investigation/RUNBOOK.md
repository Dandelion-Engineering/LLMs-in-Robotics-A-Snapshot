# Freeze, execute and inspect the complete Batch 01 release

This is an operator runbook prepared from the current source, not a readiness declaration. It created no freeze, scored manifest, evaluation seed or queue job. [readiness.json](../Batch%2001/readiness.json) remains false. Recheck the specific dependencies below after the ongoing development/qualification work; source references govern if this preparation note becomes stale.

The fixed release is **264 once-only attempts**: 192 main persistent runs and 72 no-persistence controls, with 24 case units, 20 scenario families and two policy/noise replicates. Task caps total at most **156,600 seconds / 43.5 hours**, before model loading, repeated artifact verification, teardown and analysis. The [release plan](../Batch%2001/Evaluation%20Release%20Plan.md), [evaluation design](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Evaluation.md), [shared implementation contract](../Batch%2001/Shared%20Implementation%20Contract.md) and [resource/retention policy](../Batch%2001/Resource%20and%20Retention%20Policy.md) supply the scientific and resource contract.

## Finish these inputs before the freeze

| Required input | Concrete current dependency |
|---|---|
| Full-task development evidence | Root reports C0-012 now completed 10/10 in 569.689 s under official receipt `20260923T075457882738Z-ba7ff50d`, after the raw-grid change. Earlier C0-007 remains partial 9/10. Finish the declared extended-horizon and matched persistence/restart development and final checkpoint selection; primitive probes and nominal completion do not replace qualified disturbance evidence. Preserve all earlier failures and corrections. |
| Restart qualification and loading | The protected Runtime loader, release/protocol checks and experiment selection/absence events are now integrated. Actual qualified grip/route support, construction/validation trials, absence-duration bounds and transfer assumptions still require prior measured evidence. Freeze the accepted bundle, deterministic template-to-cell mapping and exact timing/endpoint convention. Unsupported exposure remains unknown; later successful tasks cannot retroactively establish admissibility. |
| Resource and timing operation | Obtain actual development evidence for policy `robot-runtime-resource-policy-003` across horizons/restarts. Distinguish OS limits from sampled harness/GPU stops and missing observations. Do not change `resource_caps_enforced: false` into a blanket hard-cap claim. |
| Development opportunity and selected checkpoints | Update [Development Ledger](../Batch%2001/Development%20Ledger.md) from actual attempts. Each entrant's initial opportunity is two sessions or 12 active engineering hours and up to 60 episodes; extensions must be symmetric. Active engineering hours are unmeasured and must stay so. Record latest eligible checkpoints, source/prompt/knowledge identities and any justified departure before concealed seeds. |
| Capacity and retention | Latest official inventory [retention-development-004](../Evidence/derived/retention-development-004/summary.json), receipt `20260923T080629862881Z-ff3a1bbb`, measured 18 raw bundles / 17,640,193,642 bytes. Planning rate is 3.189121856 MiB/task-second; the full 156,600 seconds plus 50 GiB reserve require 577,363,228,951 bytes. C had 588,903,133,184 free bytes at 08:06:46 UTC, a margin of 11,539,904,233 bytes above that requirement. Re-measure before freeze/every batch; this snapshot is not a future capacity guarantee. Development003 will use D with the applied storage option to preserve C for all 264 scored runs. D sandbox startup/persistence passed under receipt `20260923T081119458056Z-1ffe65f6`; sustained D throughput remains to be measured. Do not delete historical evidence or shorten caps. |
| Frozen evidence references | Prepare small immutable measured-summary/reference artifacts with exact supporting identities for all 11 gates below. Declarations and passing schema/unit tests alone do not establish engineering readiness. Include actual sandbox protection of the chosen operator release root. |
| Analysis selection adapter | [collect_results.py](../Batch%2001/Release%20Analysis/collect_results.py) verifies finalized release/terminal/receipt bindings and canonical corrections. [process_evaluation.py](process_evaluation.py) retains all 264 planned dispositions and diagnostic/continuity artifacts. [analyze_results.py](../Batch%2001/Release%20Analysis/analyze_results.py) now wraps the unchanged protocol estimates with exact before/after input lineage. The Investigation builder consumes both index and analysis provenance with official receipts. These paths have synthetic validation; actual evaluation processing and browser QA remain pending. |
| Selected trace availability | [evaluation-trace-selection.json](../Batch%2001/evaluation-trace-selection.json) declares 12 fixed slots before scored outcomes. The source builder now retains missing, empty or explicitly truncated selected streams as unavailable slots with original IDs/reasons and available metadata/source hashes. It never selects replacements. Identity/schema/hash corruption still refuses the build. This adapter passed bounded tests; production rebuild/browser QA is pending. See [selected trace availability](Selected%20trace%20availability.md). |

Read-only source entry points: [freeze_artifacts.py](../Runtime/freeze_artifacts.py), [release_runner.py](../Runtime/release_runner.py), [protocol.py](../Runtime/protocol.py), [experiment.py](../Runtime/experiment.py), [analysis_adapter.py](analysis_adapter.py), [derivative_adapter.py](derivative_adapter.py), [analysis_provenance.py](analysis_provenance.py). The release runner's introductory “future supervisor integration” paragraph is historical; its actual checks govern. [Release interface checklist](Release%20interface%20checklist.md) records the remaining concrete handoff dependencies.

## Shared command setup and queue discipline

Run from the project root. These are commands for the later operator, not commands executed by this document.

```powershell
$runbookRoot = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$runbookPython = Join-Path $runbookRoot 'venv\Scripts\python.exe'
$runbookQueue = 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py'
$runbookExperiment = Join-Path $runbookRoot 'Long-Horizon Adaptive Robotics Expirement'
$runbookRuntime = Join-Path $runbookExperiment 'Runtime'
$runbookRelease = Join-Path $runbookExperiment 'Evidence\releases\batch01-eval-r1'
$runbookPrepared = Join-Path $runbookExperiment 'Evidence\prepared-artifacts\batch01-eval-r1-final'
$runbookFreeze = Join-Path $runbookExperiment 'Batch 01\freeze-batch01-eval-r1.json'
$runbookReadiness = Join-Path $runbookExperiment 'Batch 01\readiness-batch01-eval-r1.json'
```

The release ID/path match the existing predeclared trace slots. Any necessary change must update that declaration transparently before scored outcomes. Create needed parent directories deliberately; the preparation output and release directory themselves must be fresh.

Follow [Queue Limitation](../Batch%2001/Queue%20Limitation.md): while an owned worker/child is alive, do not call queue submit/status/list/doctor. Monitor only that job's log and read-only OS process state; wait for natural exit before the official status call. Do not signal reused PIDs, modify queue state or bypass the queue. All sustained hashing, physics/model work and substantial evidence processing use the queue. No source edits, dependency/driver changes or frozen-evidence rewrites during the release.

## 1. Prepare exact executable identities

After final source and model settings are fixed:

```powershell
& $runbookPython -X utf8 -B $runbookQueue submit --project LLMs-in-Robotics --cwd $runbookRoot -- $runbookPython -X utf8 -B (Join-Path $runbookRuntime 'freeze_artifacts.py') --output-dir $runbookPrepared
```

Optional `--model-config <JSON>` supplies **every effective** `ModelConfig` setting; omit only when verified defaults are the intended final model. Optional `--dependency <name>` adds installed dependency identity; defaults include NumPy/MuJoCo. Default probes capture actual WSL Python, bubblewrap and GPU/driver identity. This is an identity check, not a physical or isolation experiment.

Require official `succeeded`/integer exit 0 and retain its exact UTF-8 receipt. The helper creates `started.json`, `runtime.zip`, `code.json`, `environment.json`, `model.json`, and `prepared-artifacts.json`. It does **not** create freeze/readiness or seeds. The prepared file's `official_queue_completion_verified: false` is an immutable creation-time statement; keep the later receipt separately.

`code.json` hashes **every current Runtime/*.py, including test/helper files**, plus `Architecture Map/map.py`; the ZIP contains the exact Runtime Python set. Environment and model indexes bind requirements, Panda assets, runtime/probe identities, actual weights, installed executable/DLL/license files and full model settings. The runner rehashes/reprobes these before and after every episode. Adding or editing even a Runtime test after preparation invalidates this identity and requires fresh preparation before freeze.

## 2. Write the freeze, then evidence-bound readiness

No current CLI writes either document. Construct them explicitly from the successful prepared references and established measured evidence. Minimal **executable** freeze shape (angle-bracket text below denotes required real values, never usable placeholders):

```json
{
  "release_id": "batch01-eval-r1",
  "frozen_at": "<actual timezone-qualified timestamp>",
  "code_sha256": "<prepared code index SHA-256>",
  "environment_sha256": "<prepared environment index SHA-256>",
  "model_sha256": "<prepared model index SHA-256>",
  "protocol_sha256": "<prepared exact protocol.py SHA-256>",
  "artifacts": {
    "code": {"path": "<actual code.json>", "sha256": "<same code index hash>"},
    "environment": {"path": "<actual environment.json>", "sha256": "<same environment index hash>"},
    "model": {"path": "<actual model.json>", "sha256": "<same model index hash>"}
  },
  "selection_criteria": "<actual predeclared checkpoint selection, analysis and fixed trace-selection rule/references>",
  "maximum_retries": 0
}
```

The protocol generator checks the top-level fields; the runner additionally requires the exact `artifacts` object and its real indexes. Do not use a syntactically sufficient freeze that cannot execute. Hash the final immutable freeze bytes **before** writing readiness; do not create a circular freeze↔readiness reference.

For qualified matching, also set `restart_matching_mode: qualified_class` and `restart_qualification` with the actual bundle `path`, byte `sha256`, canonical `bundle_sha256`, canonical `class_spec_sha256`, supported `selection_rule`, frozen `payload_template_to_cell`, `prospective_absence_bound_s`, `absence_timebase` and `absence_endpoint`. Use [restart_calibration_loader.py](../Runtime/restart_calibration_loader.py) and [construction contract](../Batch%2001/Restart%20Qualification%20Tools/CONSTRUCTION.md) for the exact measured shapes. Bundle acceptance must predate the freeze. Omitting these fields selects legacy exact-configuration behavior; it does not establish class qualification.

Retain/freeze the external collector, analysis wrapper and Investigation helper identities and fixed analysis settings before evaluation too. The Runtime preparation ZIP does not automatically include these sibling folders. The wrapper records exact helper identities and verifies the frozen Runtime protocol; it does not invent an external analysis-method freeze.

Readiness requires `release_id`, `scored_ready: true`, `freeze_sha256` matching those exact bytes, nonempty `evidence_refs: [{"path":"<real evidence>","sha256":"<real hash>"}]`, and a `gates` object with every following value explicitly Boolean `true`:

`physical_workcell`, `public_perception`, `independent_evaluator`, `conventional_baseline`, `candidate_implementations`, `model_and_terms`, `isolation`, `timing_and_resources`, `evidence_retention`, `disturbance_admissibility`, `equal_development_opportunity`.

Resolve relative references from their containing JSON's directory. Keep measured support and interpretation for each gate inspectable. A field being true is not proof; if support remains missing, continue prerequisite work and retain false readiness. Calibration/restart artifacts must be hash-bound and actually loaded by the final runtime; adding extra JSON fields that execution ignores is insufficient.

## 3. Create the protected complete matrix once

After the readiness interpretation and all bytes are final:

```powershell
& $runbookPython -X utf8 -B (Join-Path $runbookRuntime 'protocol.py') create --release-dir $runbookRelease --freeze-manifest $runbookFreeze --readiness $runbookReadiness
```

This explicit operation generates concealed seeds. It refuses existing output, requires the parent directory already exist, verifies gate references and writes `release.json` plus 264 hash-bound `runs/<run-id>.json` manifests with a complete randomized schedule. Keep them outside all candidate mounts, prompts and observation packets. The ordinary `describe` command creates no seeds. Do not inspect concealed seeds to fix a case or select a policy.

## 4. Run one bounded batch, verify, finalize, repeat

```powershell
& $runbookPython -X utf8 -B $runbookQueue submit --project LLMs-in-Robotics --cwd $runbookRoot -- $runbookPython -X utf8 -B (Join-Path $runbookRuntime 'release_runner.py') run --release-dir $runbookRelease --limit 4
```

Use the stored schedule and omit `--run-id` for routine execution. Limit is 1–16, default 4; changing batch size does not change the 264-run matrix. Without incidents, limit 4 means 66 batches. The driver verifies identities, automatically registers frozen revisions and each exact manifest before execution, runs the proper model only for LLM entrants and retains failures. It creates:

- `batches/<queue-id>/{planned,finished}.json`, with selected, terminal and unlaunched IDs explicitly accounted for;
- `attempts/<run-id>/{claimed,registered,started,terminal}.json` as each stage occurs;
- `attempts/<run-id>/evidence/` for actual supervisor manifest/result/events/motion/frames/context, plus any model-server log beside it.

After the worker/child naturally exit, save the official status JSON without a BOM and verify success. Replace the string below with the actual returned ID:

```powershell
$runbookJobId = '<actual queue job ID>'
$runbookReceipt = Join-Path $runbookExperiment ('Evidence\queue-receipts\' + $runbookJobId + '.json')
$runbookStatusText = & $runbookPython -X utf8 -B $runbookQueue status $runbookJobId
if ($LASTEXITCODE -ne 0) { throw 'Official status query failed' }
$runbookStatus = ($runbookStatusText -join [Environment]::NewLine) | ConvertFrom-Json
if ($runbookStatus.state -ne 'succeeded' -or $runbookStatus.exit_status -ne 0) { throw 'Queue completion is not usable' }
[IO.File]::WriteAllText($runbookReceipt, ($runbookStatusText -join [Environment]::NewLine), [Text.UTF8Encoding]::new($false))
& $runbookPython -X utf8 -B (Join-Path $runbookRuntime 'release_runner.py') finalize --release-dir $runbookRelease --verified-queue-job-id $runbookJobId --queue-status $runbookReceipt
```

`finalize` compares the official receipt to installed queue state and the batch journal, checks immutable terminal hashes, appends actual map results, rebuilds/validates the map and writes `finalized.json`. It does not execute a policy again. Do not launch the next batch before that marker exists. Recheck remaining space and incident state; repeat until all 264 original manifests have honest terminal dispositions. Queue success, task success, timing validity and statistical eligibility remain distinct.

**Incident path:** invalid/unknown results stop the batch even when its queue process exits 0. Finalize completed terminal evidence first. `release_runner.py review --release-dir $runbookRelease --input <actual-review.json>` can record a supported isolated host-timing, queue or runtime incident; it cannot waive integrity breaches or unresolved started attempts. Required review fields are `review_id`, `reviewer`, `rationale`, supported `classification`, `continuation_scope: all_original_unattempted`, `retains_original_results: true`, `exclude_affected_blocks_from_primary: true`, `no_source_readiness_or_evaluator_integrity_breach: true`, `automatic_retries: 0`, exact `terminal_refs` with run IDs/path/hash, sorted `excluded_paired_block_ids`, and small hashed `evidence_refs`. The command adds schema/time/release hash. See `validate_review` for exact validation. Preserve the whole affected paired block's primary exclusion and run remaining original manifests for descriptive evidence when authorized by that record. A source/evaluator/oracle breach or unresolvable interruption requires a new documented release decision; do not retry under the old ID or edit a terminal result.

## 5. Select result records and analyze the full denominator

After official finalization, the source [evaluation processor](process_evaluation.py) calls [collect_results.py](../Batch%2001/Release%20Analysis/collect_results.py) to write fresh `selected-results.json` with a flat `results` list plus source-bound selection provenance. Current canonical corrections control outcome and metrics; stale raw independent-success fields cannot override them. Wrapper/raw infrastructure failures and missing post-run integrity remain invalid/unknown. The selection binds the protected release, original terminal, canonical supersession history, batch finalization and official receipt. Missing values never default to success, failure, zero time or `valid`.

The parser rejects duplicate/unknown IDs but allows absent results so it can report `unrun`; that is not permission to call an incomplete release complete. Verify accounting against all 264 manifests. Do not pass map results directly: their measured values live in `metrics`, and their infrastructure flags may live in `details`, while this analyzer expects top-level fields.

Queue the derivations once against a fresh directory outside the release/originals/candidate/map. The processor proves queue ownership before reading evidence, then runs diagnostics and continuity functions sequentially, without nested jobs:

```powershell
$runbookDerived = Join-Path $runbookExperiment 'Evidence\derived\batch01-eval-r1-analysis-001'
& $runbookPython -X utf8 -B $runbookQueue submit --project LLMs-in-Robotics --cwd $runbookRoot -- $runbookPython -X utf8 -B (Join-Path $runbookExperiment 'Engineering Investigation\process_evaluation.py') --release-dir $runbookRelease --output-dir $runbookDerived
```

Retain the official receipt after natural exit and inspect `index.json`. Every planned run keeps its disposition, selected canonical result, per-derivative status and linked artifact/failure. Missing terminals/evidence remain missing; nothing is replaced. Exit 0 means every derivation completed, not every task succeeded. Exit 1 means a finalized partial/integrity-failed index was retained; preserve its failed queue receipt and inspect the explicit failures. Exit 2 is entry refusal. An interrupted job without `index.json` is not finalized. Never hide missing/failed derivatives to obtain a successful receipt. See [evaluation processing](Evaluation%20processing.md) for the exact output and summary denominators.

The source-bound analysis wrapper uses the unchanged predeclared defaults: analysis seed 0 and 2,000 bootstrap draws. It verifies selected-result/release/frozen-protocol identity and hashes all required inputs before and after calling the existing analyzer:

```powershell
$runbookSelected = Join-Path $runbookDerived 'selected-results.json'
$runbookAnalysisRoot = Join-Path $runbookExperiment 'Evidence\derived\batch01-eval-r1-paired-analysis-001'
& $runbookPython -X utf8 -B $runbookQueue submit --project LLMs-in-Robotics --cwd $runbookRoot -- $runbookPython -X utf8 -B (Join-Path $runbookExperiment 'Batch 01\Release Analysis\analyze_results.py') --release-dir $runbookRelease --selected-results $runbookSelected --output-dir $runbookAnalysisRoot
$runbookAnalysis = Join-Path $runbookAnalysisRoot 'analysis.json'
$runbookAnalysisProvenance = Join-Path $runbookAnalysisRoot 'analysis-provenance.json'
```

Require the analysis job's official successful receipt. The wrapper refuses an existing output directory. Its unchanged estimate schema is `robot-evaluation-analysis-1.0`: complete dispositions, whole-block exclusions, six main and three persistence contrasts, paired rows, unavailable pairs, horizon/disturbance strata, family-cluster intervals and actual completion/censor clocks. `analysis-provenance.json` must have schema `source-bound-evaluation-analysis-1`, status `complete`, unchanged before/after inputs and an exact analysis reference. A failed sidecar cannot establish bound statistical output even if an analysis file was written before failure.

The paired analyzer does not replace the processor's continuity/movement diagnostics. Its descriptive summaries group architecture, persistence condition and horizon with explicit run and opportunity denominators. Whole infrastructure-invalid paired blocks are excluded from the primary derivative subset; valid task failures stay eligible. Unknown admissibility, missing reports and integrity findings remain separate. No new threshold, significance test, winner or causal claim is added. The [qualified restart reader](Qualified%20restart%20verification.md) independently binds qualified calibration/classifier and actual absence evidence; legacy records keep their recorded-predicate interpretation. Its remaining production dependency is final freezing and measured qualification of the now-integrated Runtime loader. `process_development.py` still accepts development records only.

## 6. Build and check the final investigation page

Once the actual analysis is available, the source builder can retain unavailable selected slots explicitly:

The optional implementation narrative can be included with `--implementation-narrative (Join-Path $runbookExperiment 'Engineering Investigation\current-implementation-narrative.json')`. It is shown only when the selected implemented/frozen revision's retained source ZIP matches all declared hashes; it never replaces an older revision with live code. Preserve its JSON, reader, builder and template identities in the external control index. See [implementation narrative](IMPLEMENTATION-NARRATIVE.md) for exact matching behavior and [validation 002](Interface%20validation%20002.md) for the completed full suite: 164 tests in 27.477 seconds, official job `20260923T115431720868Z-38d34027`, succeeded/exit `0`. The production HTML remains unrebuilt and needs corresponding browser QA.

```powershell
$runbookDerivedReceipt = Join-Path $runbookExperiment 'Evidence\queue-receipts\<actual diagnostic job ID>.json'
$runbookPairedReceipt = Join-Path $runbookExperiment 'Evidence\queue-receipts\<actual analysis wrapper job ID>.json'
& $runbookPython -X utf8 -B $runbookQueue submit --project LLMs-in-Robotics --cwd $runbookRoot -- $runbookPython -X utf8 -B (Join-Path $runbookExperiment 'Engineering Investigation\build_workspace.py') --metadata-root (Join-Path $runbookRelease 'attempts') --trace-selection (Join-Path $runbookExperiment 'Batch 01\evaluation-trace-selection.json') --evaluation-index (Join-Path $runbookDerived 'index.json') --evaluation-receipt $runbookDerivedReceipt --analysis-file $runbookAnalysis --analysis-provenance $runbookAnalysisProvenance --analysis-receipt $runbookPairedReceipt
```

Replace both placeholder IDs with the actual retained receipts after natural completion. All canonical map records and all 264 diagnostic-index rows are included; full per-run reports remain linked rather than embedded. Metadata reads only direct manifests or exact `attempt/evidence` manifests; directories without one stay explicitly missing. The builder verifies that analysis and diagnostic inputs bind the same release and selected results. Preserve the fixed 12 trace slots, including failures/missingness, and all original evidence separately. After official queue success, repeat bounded browser QA for actual counts, corrections, nine contrasts and denominators, clocks/censoring, diagnostic groups, error links, selected traces, original images, missing-data states and layout. [Rebuild and QA 003](Rebuild%20and%20QA%20003.md) supplies the last real nine-development-run QA baseline; it is not scored-release QA.

Development metadata on D is supported through explicit `process_development.py --evidence-root <D root>` and local absolute canonical references, retaining exact path/hash checks. The viewer deliberately marks cross-drive playback/browser links unavailable while retaining manifest/result metadata and hashes; it reads no D raw streams for that placeholder. It does not emit `file:` links or relax URL restrictions. All scored-release originals and the final Investigation output are still planned on C.

Finish the original AgentPrompt closeout only after the complete authorized experiments, honest analysis and investigation artifact are complete, or document an actual unresolved external dependency. This runbook is preparation, not that completion.
