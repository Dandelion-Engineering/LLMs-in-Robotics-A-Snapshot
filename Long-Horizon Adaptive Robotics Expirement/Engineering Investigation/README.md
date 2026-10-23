# Engineering investigation workspace

Open [index.html](index.html) after rebuilding. It is a standalone, read-only HTML snapshot of the five canonical [Architecture Map](../Architecture%20Map/README.md) JSONL collections. Its purpose is to connect the shared machine-tending job to a selected architecture's mechanism and then to recorded attempts, assessments and evidence.

The current verified production page contains nine development runs and compresses the complete snapshot. [Rebuild and QA 003](Rebuild%20and%20QA%20003.md) identifies its successful queue receipt, exact file hash, 74 passing bounded tests and completed browser checks after the desktop restart. [Browser QA 002](Browser%20QA%20002.md) preserves the earlier build's checks.

[RUNBOOK](RUNBOOK.md) connects the existing freeze, readiness, bounded execution, finalization, result selection, analysis and final workspace commands for all 264 planned scored attempts. It records missing inputs and is preparation only; it creates no evaluation seeds or readiness pass.

No scored comparison is available. [Physical calibration 002 and its adapter follow-up](../Batch%2001/Physical%20Calibration%20002.md) establish narrow sensor, raw-camera and arm-interface checks; insert exchange and both held-recovery routes failed. The earlier C0-002 full-completion claim is withdrawn in its current canonical partial/invalid assessment because both inserts remained in the fixture. Original evidence and the superseded assessment remain available.

The source is [workspace.html](workspace.html), a self-contained HTML/CSS/JavaScript template, and [build_workspace.py](build_workspace.py), a Python standard-library builder. [evidence_adapter.py](evidence_adapter.py) reads real log bundles; [playback.js](playback.js) and [playback.css](playback.css) are inlined into the generated page. There are no libraries, CDNs, analytics, runtime data fetches, accounts or services. Recorded frame images load only from their linked local evidence paths. Opening the generated file does not run an experiment or write the map. The workspace can also be served by an ordinary local static server.

Optional [source-matched implementation descriptions](IMPLEMENTATION-NARRATIVE.md) distinguish the implemented A1/A2/A3 mechanisms from their preserved original proposals and also describe the conventional C0 baseline. Supply `--implementation-narrative current-implementation-narrative.json` to the builder: it displays the new prose only for implemented/frozen revisions whose immutable source ZIP matches all named Runtime hashes. Historical mismatches keep their original text; live Runtime files are never substituted. These changes and the [empty-cut reader correction](Empty%20cut%20reader%20correction.md) passed within the **full 164-test suite in 27.477 seconds**, official job `20260923T115431720868Z-38d34027`, succeeded/exit `0`. See [validation 002](Interface%20validation%20002.md) and its [receipt](../Evidence/queue-receipts/20260923T115431720868Z-38d34027.json). Production HTML and browser QA still predate these changes.

[analysis_adapter.py](analysis_adapter.py), [analysis.js](analysis.js) and [analysis.css](analysis.css) add the paired-analysis view and a separate catalogue of small run metadata. They read existing output; they do not run statistics, create example outcomes or change eligibility.

The source now also retains explicitly declared missing or incomplete selected traces as unavailable inspection slots. [Selected trace availability](Selected%20trace%20availability.md) records this change and its 81 passing bounded tests. The current production page predates that adapter; rebuild and browser QA remain pending, while the declared evaluation selection is unchanged.

The current source additionally accepts a complete evaluation diagnostic index and its receipt (`--evaluation-index`, `--evaluation-receipt`), retaining all 264 planned rows, missing/failed reports, report links and descriptive group denominators. Optional `--analysis-provenance` and `--analysis-receipt` bind unchanged protocol estimates to the exact wrapper inputs; legacy reports keep a weaker verification label. The fixed 12 trace slots are independent of these complete catalogues. Local development references on another Windows drive retain exact path/hash checks; cross-drive metadata remains visible while playback/browser links are explicitly unavailable. The earlier **124-test / 21.086-second** result is historical, preserved in [Interface validation 001.json](Interface%20validation%20001.json); validation 002 records the current 164-test suite above. Production HTML was not rebuilt. See [release interface checklist](Release%20interface%20checklist.md) and [RUNBOOK](RUNBOOK.md).

## Rebuild and verify

From the repository root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/build_workspace.py"
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/test_workspace.py"
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/test_evidence_adapter.py"
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/test_analysis_adapter.py"
```

The builder uses the canonical map's `read_store` and `validate_records`, including immutable revision-attachment hashes. An invalid input leaves the previous HTML untouched. It records the exact store and file hashes in the embedded snapshot. These checks validate record structure and local revision attachments, not the scientific claims or availability of general external evidence. The canonical map's own `build` and `validate` workflow remains separate.

`--map-root` and `--output` allow isolated fixture builds. The tests use temporary synthetic stores only. They check an empty store, hostile record text at the HTML boundary, failed builds preserving earlier output, altered attachment rejection, current-result filters, inherited correction-note subjects, and unsafe link rejection. JavaScript unit checks use an existing Node.js installation and skip when it is unavailable. Browser interaction and responsive checks are separate from these regression checks.

## Explore without losing the evidence boundary

- **Mechanism:** search across architecture and revision records; filter latest-revision status; select an exact revision; inspect its reasoning, motion-feedback and continuity descriptions, immutable attachments, sources and raw canonical record.
- **Compare:** compare the latest revision of every architecture matching the sidebar filters. Click its name to inspect that mechanism. Expected strengths and risks remain hypotheses.
- **Runs & evidence:** select an architecture or all architectures; filter stage, current validity and current outcome; search run/current-result content; inspect condition, scenario, pairing, replicate, metrics, denominators, missing reasons and evidence references. No result means no recorded terminal assessment. Zero-valued metrics stay zero; missing values remain explicitly missing. Failed, invalid and unstarted attempts remain available.
- **Notes:** distinguish observation notes, source reports, interpretations, hypotheses, questions and corrections. Corrected notes retain their inherited subjects. Superseded notes can be revealed without overwriting them.
- **Recorded timeline:** select a loaded real run, filter event type, and move between actual events using a selector, keyboard-operable slider, or previous/next controls. Inspect captured frames, exact attempted candidate dispatches, privileged state, retained motion, stored/read/supplied context, model inputs/outputs and action records at a shared event cutoff. Export the compact snapshot with its source hashes and sampling rules.
- **Paired analysis:** inspect the complete planned denominator, every recorded disposition, infrastructure-block exclusions, six main contrasts and three persistence contrasts. Compare observed pair/case/family counts and retained bootstrap intervals; inspect unavailable-pair reasons and horizon/disturbance strata. The time table separates measured successful completion, actual censor exposure, missing clocks and the protocol-cap plotting convention. No analysis file means explicitly unavailable statistics.

Only terminal results not superseded by another result drive the run filters. All old assessments stay under their run's history. Revision selection follows canonical append order; it is a browsing default, not an endorsement. All quantitative values are displayed with the units and denominators recorded by their authors; there is no automatic pooled score, ranking or causal inference.

Canonical references show availability declarations, access labels, locators and hashes. `available` on a canonical reference is not a live availability check. For explicitly supplied raw run bundles, the adapter checks local artifact existence and hashes during the build. Evaluator-only labels describe the intended audience and do not enforce security; keep this operator workspace outside candidate access. Absolute local canonical paths and unsupported schemes display as text rather than active browser links. Relative canonical references resolve from the map directory; HTTP(S) source links open separately.

## Revision metadata used for concise explanations

The canonical schema's open `revision.details` object may supply these optional fields. Missing fields display as unrecorded; they never receive invented prose.

| Field | View |
|---|---|
| `llm_role` | What the LLM changes |
| `control_loop` | What controls motion and closes feedback |
| `continuity` | What persists and how it is reconciled |
| `expected_strength` | Design hypothesis |
| `failure_risk` | Design hypothesis |
| `implementation_status` | Recorded implementation status |
| `batch_id` | Available to full-record search and inspection |
| `sources` | Array with `label`, `url`, and optional `locator`, `relevance`, `why` or `note` |

Other details remain available through raw-record inspection. This presentation metadata does not constrain the allowed architecture mechanisms.

## Load actual event evidence

Supply one or more completed `Runtime/experiment.py` run directories:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/build_workspace.py" --run-dir "Long-Horizon Adaptive Robotics Expirement/Evidence/raw/<actual-run-id>"
```

`--run-dir` is repeatable, with a maximum of 12 detailed bundles. It is retained for explicit small ad hoc builds; use a predeclared `--trace-selection` file for the investigation batch. `--observation-hz` defaults to 2 and `--motion-hz` to 5 for the compact display. All non-observation events are retained. Observation sampling also retains the last capture and any capture explicitly parent-linked from another retained event. Motion retains real samples at the requested interval and the final sample. Full raw logs stay on disk and are linked with exact hashes; no values are interpolated. The interface exposes source counts, retained counts, sampling rules and event-ID gaps. It records motion intervals over 30 ms for inspection against the logger's stated 100 Hz target.

The complete snapshot—including all canonical records, selected evidence, metadata and any supplied analysis—is embedded with lossless gzip compression and decoded locally using the browser's native `DecompressionStream`; no network or external library is involved. Before enabling the panels, the reader checks compressed and decoded lengths and the decoded SHA-256 using native Web Crypto. Missing browser support, a malformed archive or a hash mismatch produces an explicit error and leaves data controls inactive. Compression reduces the file size, not the size of the decoded records in browser memory. Compact JSON export contains decoded records and can be larger than the HTML.

The supported schema is `robot-evidence-1.0`: `manifest.json`, `events.jsonl`, optional `motion.jsonl`, optional `result.json`, and run-relative frame paths. The adapter rejects payload-hash mismatches, non-increasing IDs, backwards event clocks, malformed/incomplete records, run-identity mismatches and artifact references escaping the run directory. A missing image remains missing. A local run bundle need not already have a canonical map run; the UI labels that association as absent and does not infer a design revision from an architecture nickname.

The page distinguishes gateway captures from exact `candidate_input` attempted dispatches. A dispatch is not ingestion; inspect the corresponding worker reply and its events. Captured observations alone do not prove that those bytes reached a candidate. `context_write`, `context_read` and `model_context_supplied` remain separately inspectable. Model response envelopes retain incarnation, stale-output and after-episode flags. The evaluator view is persistently labeled privileged. Every selected pane exposes its earlier sample's age.

## Complete metadata, bounded traces, optional paired analysis

These are independent inputs. All five canonical map collections are always retained. `--metadata-root` recognizes both direct development `<run>/manifest.json` and the exact release-attempt `<run>/evidence/manifest.json` shape, with optional `result.json` beside either manifest, preserving the full manifest, a concise result summary, and links/hashes for both originals. It never reads event logs, motion logs or frames, and it does not recurse beyond that one declared `evidence` level. Pass `Evidence/releases/<release-id>/attempts` for release attempts; direct and nested manifests in the same run directory are rejected as ambiguous. Directories without manifests are listed explicitly and are not invented as known runs. A directory without a result stays unassessed. Raw metadata is not merged with or substituted for canonical supersession history. Timeline and metadata views show the current canonical assessment first, including any correction, and label immutable raw outcome/completion claims as historical. Compact trace exports retain the current canonical assessment separately from the raw result.

`--analysis-file` accepts the exact `robot-evaluation-analysis-1.0` JSON produced by `Runtime/protocol.py analyze`. It retains all statistics, paired rows, unavailable pairs, exclusions, censor observations and limitations exactly. The adapter checks the schema, complete disposition count, paired-table counts and all nine contrast identities. It does not validate the scientific authenticity of that report, choose selected result records, resolve result supersessions or recompute intervals. Its source hash remains inspectable. No supplied file produces an explicit unavailable state, with only the nine named expected comparison slots shown.

The analysis report's planned denominator is independent of detailed trace selection and metadata availability. Successful task completion, execution success, timing validity, statistical eligibility and readiness remain distinct. Failed-run cap markers are never presented as measured successful completion times; actual observed censor exposure and missing exposure are visible separately. The time table is paginated in groups of 25 without dropping observations. Stratum and interval tables identify observed case units and scenario-family clusters rather than treating repeated pairs as independent cases.

Declare a detailed trace set before the build using a JSON file with this shape (the paths and IDs below are placeholders, not a production fixture):

```json
{
  "schema_version": "investigation-trace-selection-1.0",
  "declared_at": "2026-09-23T00:00:00Z",
  "selection_basis": "State the inspection rationale and whether selection occurred after outcomes were known.",
  "runs": [
    {
      "run_id": "<actual-run-id>",
      "path": "../Evidence/raw/<actual-run-id>",
      "reason": "Explain why this real trace is retained for detailed inspection."
    }
  ]
}
```

Paths resolve from the selection file's directory. The builder checks the declaration and its 12-slot limit before opening detailed logs, verifies every present run identity, and embeds the unchanged declaration plus its source hash. Missing required files, an empty event log or an explicitly incomplete final stream record yields an unavailable slot with its original reason, available metadata and source hashes. No partial trajectory or replacement run is invented. Malformed/schema/identity/hash errors still refuse the build. Valid failed/invalid traces remain inspectable. Selected, loaded and unavailable counts stay separate from the complete metadata catalogue and analysis denominator. Legacy `--run-dir` remains strict because it supplies no declared identity for a missing directory. A declared inspection subset is not a statistical sample or proof of preregistration. Do not select examples as substitutes for complete denominator reporting. `--trace-selection` and `--run-dir` cannot be combined.

For the later operator-controlled build, supply the actual paths:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/build_workspace.py" --metadata-root "Long-Horizon Adaptive Robotics Expirement/Evidence/raw" --trace-selection "<actual-selection-file>" --analysis-file "<actual-protocol-analysis-file>"
```

Omit `--analysis-file` until a real analysis exists. Omit trace inputs to retain metadata without loading any detailed evidence. Builds over substantial raw evidence belong in the project's serialized job workflow; this documentation does not start one.

The analysis tests use temporary synthetic files only, including hostile text, incomplete denominators, missing contrasts, fixed selection bounds, missing results, excluded blocks and censoring distinctions. A small Node DOM fixture checks the display logic; it is not visual browser QA or physical-performance validation. No test fixture enters the canonical map, checked-in production HTML or project evidence.

## Operator continuity extraction

[continuity.py](continuity.py) implements the conservative automatic subset of [Batch 01/Continuity Analysis Rules.md](../Batch%2001/Continuity%20Analysis%20Rules.md). It writes only a new operator artifact outside the original run and candidate state. Legacy extraction imports no Runtime module; explicit qualified verification imports only the independently frozen read-only helpers described below. Root runs any actual extraction through the serialized job workflow:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/continuity.py" --episode-dir "<actual-completed-run-evidence-directory>" --output "<new-operator-continuity-json>"
```

The input directory contains immutable `manifest.json`, `result.json`, `events.jsonl` and `motion.jsonl`. Events are parsed without sampling; motion is only hashed, never used to invent physical predicates. Every input, the rubric and the extractor are hashed before and after extraction. Event IDs must be contiguous, parents must refer to earlier events, payload hashes must match, and clocks must be valid. The explicit `episode_clock_started` reset is handled separately from initialization. Invalid inputs are refused rather than reordered or reconstructed. Output creation is exclusive; it cannot silently replace an earlier annotation or any input. Frozen runtime hashes and available evaluation authorization remain attached.

The in-memory API is `extract(manifest, result, events, *, annotations=(), sources=None, rubric_sha256=None, qualification_context=None)`. It returns one row per declared restart, protected scenario order-event definition, or single scripted rework opportunity. It retains unreached opportunities, fallback modes, affected identities, exact source IDs/clocks, terminal status, assistance and missingness. Unplanned exposure events are integrity findings. Order amendments require identity/version correlation with their protected `scenario_exposure`, including its actual list payload. Optional full `protected_snapshot` data are retained with a hash; lightweight position/history snapshots are not upgraded into geometric or settling evidence.

The `restart-admissibility-reader-1.0` adapter accepts an explicit `restart_begin.payload.restart_admissibility` decision of schema `restart-admissibility-1.0`, bound to `protected_restart_state` of schema `protected-restart-state-1.0`. It verifies snapshot hash, exact cut simulation clock/identity and the aggregate of recorded required predicate states. The containing protected event is an exact citation; optional `predicate_evidence_event_ids` must name protected current/prior events. Unknown required predicates remain unknown, while optional infrastructure predicates remain separate from physical admissibility and never assign paired-block exclusions. Snapshot geometry, milestone matches and final success cannot supply missing decisions. Unsupported schemas stay unknown with their evidence citation and recorded decision retained.

For legacy exact-configuration records, when `restart_calibration` is embedded, its hash must match the decision's `calibration_input_sha256`. Prior artifact references, operator byte-verification assertions, source hashes and physical-configuration matching remain inspectable. Those legacy checks read metadata only: external calibration paths are not opened and physical envelopes are not recomputed. A recorded measured-envelope pass with contradictory embedded reference compatibility is an integrity error. Absent input stays unavailable; no calibration is reconstructed from final outcome.

Qualified-class records use the separate [independent qualified restart adapter](Qualified%20restart%20verification.md). Supply `--release-dir` to bind release/run/freeze, verify frozen helpers and calibration files and recompute selection/classification. Held cuts additionally require actual absence against the frozen clock/endpoint; missing context, exceeded duration and an unsupported first control stay unknown, and annotations cannot waive them. Independently verified empty cuts retain instantaneous admissibility with carry coverage explicitly not applicable, without a future-recovery claim. Legacy, independently verified empty and carry-qualified admissibility have separate coverage counters. The Runtime loader is integrated; production use still requires final frozen measured qualification. These fields remain operator-only.

An exact `candidate_input` is an attempted dispatch. Confirmed delivery additionally requires its linked successful `candidate_reply`. Fresh visual delivery requires a parent-linked observation with matching sequence/incarnation/capture time acquired at or after exposure. A new public order can be delivered with an older image; those landmarks stay separate. A visible affected tag is not correct reconciliation, and no field-attention claim is made. Ingestion time is bounded between dispatch and reply rather than assigned an invented instant.

Automatic useful resumption is limited to processing: a post-fresh admitted current-incarnation action, current-order linkage, protected `cycle_complete`, matching accepted/completed history, and a conservative unmet recipe quota or explicit rework authorization. Protected completion during runtime absence stays separate from resumed candidate work. Routing, setup, safe holds and trajectory endings do not establish physical success without the additional frozen predicates. Candidate resolution assertions remain claims; a linked protected cycle fault can refute a current assertion, while correct reconciliation remains unknown without sufficient independent adjudication. Generic observe/help, final success and milestone matching never establish recognition, admissibility or recovery.

Optional `--annotations <operator-json>` binds human adjudication to the exact `run_id`, `events_sha256` and `rubric_sha256`. Its `annotations` list records `annotation_id`, `opportunity_id`, `reviewer`, `rule`, `basis`, `label`, `verdict`, and `evidence_event_ids`. Supported labels are `admissibility`, `behavioral_detection`, `correct_reconciliation`, `restored_validity`, and `resumed_useful_work`; verdicts are `established`, `incorrect`, `inadmissible`, `unknown_evidence`, and `unresolved_at_end`. Optional `time_event_ids` names two cited protected lower/upper events (the same ID for an exact event). Snapshot brackets are retained as brackets. Record confidence, competing interpretations and any masking details as additional fields; they are retained verbatim. This adapter verifies references, not the annotator's physical predicate. Conflicting verdicts or time bounds remain unknown with both annotations retained.

Recovery requires exercised, explicitly admissible exposure, independently established restored validity and useful work before the unchanged simulation/wall cap. It uses the later endpoint, preserves interval bounds and leaves detection-relative time unknown when detection is unknown. Logging wall times never become measured physical actuation times. Unknown admissibility remains outside the known-admissible denominator and is counted separately; development traces cannot supply evaluation denominators. Original validity and final completion are never upgraded.

[test_continuity.py](test_continuity.py) uses temporary synthetic fixtures for all rubric counterexamples: capture without delivery, late old-incarnation output, suppressed versus admitted duplicates, authorized rework, unreached cuts, deadline fallbacks, processing during absence, wrong resolution, useful progress without recognition, safe hold without work, and snapshot-bounded time. Additional checks cover order/image clocks, missing protected exposure correlation, optional full snapshots, disagreement, source corruption, clock origins and immutable output. These are extractor checks, not robot performance results.

## Queue-only completed-development processor

[process_development.py](process_development.py) prepares independent diagnostics and continuity artifacts for one to 32 explicitly named completed development attempts. It does not submit jobs, call the queue CLI/status, select scored attempts, append map records or modify original evidence. Its first operation proves current queue ownership through `Runtime.release_runner.queued_job(expected_script=__file__)`. Run it as the exact script entry point inside the existing serialized queue. This is an argument template, not a submitted job:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/process_development.py" --run-id "<B01-dev-run-id>" --receipt "<official-execution-batch-receipt.json>" --output-dir "<fresh-operator-output-directory>"
```

Repeat `--run-id` for each selected development attempt and `--receipt` for each distinct execution job, including older jobs when selected. Every receipt must explicitly establish `succeeded` and integer `exit_status: 0`, and match the installed queue's read-only record through `verify_queue_receipt`. Each run must have one unambiguous current canonical terminal result with the same `details.queue_job_id`, plus exact canonical hash bindings to its original result, event and motion logs. Manifest/result identity and development stage must agree. A later canonical correction is preserved separately from the immutable raw outcome; a historical raw success is never upgraded over a current partial/invalid assessment.

`--map-root` and `--evidence-root` optionally select explicit stores; defaults are this project's canonical Architecture Map and `Evidence/raw`. The output directory must be fresh and outside canonical map, Runtime, raw evidence and candidate state. There is no recursive discovery of attempts. The source identity snapshot includes canonical map hashes, receipts, original files and the processor/reader/diagnostic/rubric dependencies; original and implementation hashes are checked again around derivation.

The output contains `selection.json`, an append-only `progress.jsonl`, `index.json` and one subdirectory per selected run. Each subdirectory contains `canonical-assessment.json`, distinct `diagnostics.json` and `continuity.json` when successful, and `status.json`. A failed derivation produces a separately hashed `*-failure.json`; the other derivation can still complete. Verification failures produce no derived reports for that run. Source changes invalidate that run's derived status. The compact index retains original/canonical distinctions, file hashes, derivation failures and integrity findings requiring operator review. Derivation completion does not establish task success or scored validity.

Exit status is 0 when all selected derivations complete, 1 for a finalized index with run-level failures, and 2 for an entry refusal. No automatic retry or overwrite is attempted. An interrupted process can leave selection/progress or partial artifacts without a final index; absence of `index.json` means the batch has not finalized. Any later acceptance of the operator batch still requires its own official successful queue receipt. Tests use mocks and temporary synthetic files only, including separate older receipts, correction preservation, source changes and partial failures; they never contact the queue or process real traces.

## Queue-only complete evaluation processor

[process_evaluation.py](process_evaluation.py) now uses the protected release collector to retain all 264 planned run dispositions and derive independent per-run diagnostic/continuity files sequentially inside one verified queue process. Canonical corrections, missing/failed attempts and whole paired-block infrastructure exclusions remain visible. Compact descriptive summaries group architecture, condition and horizon with explicit run/opportunity denominators; full traces stay in linked files. Source changes and derivative integrity findings exclude measurements without rewriting original validity. See [evaluation processing](Evaluation%20processing.md) and the exact command in [RUNBOOK.md](RUNBOOK.md).

The earlier processor/qualified-reader check sets (11 and 19 tests respectively) are historical. The current full 164-test suite includes their counterexamples plus the new empty-cut interpretation, separate coverage counters and source-matched narrative checks; see [validation 002](Interface%20validation%20002.md). All use synthetic fixtures. No actual scored data have been processed or production page rebuilt by these changes.

## Honest limits

The shared job diagram is explicitly schematic. The workspace does not synthesize motion, sensor images, action events, success rates or plausible-looking example runs. Summary metrics cannot reconstruct a trajectory or show what the candidate observed.

The event browser aligns views by the selected recorded event, using only samples at or before that event. It does not perform deterministic physics re-execution, animate interpolated robot geometry, calculate causal failure labels, or align paired runs on a shared timeline. Those remain future adapters requiring representative evidence and the [Evidence and Investigation](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Evidence%20and%20Investigation.md) acceptance cases. A source-reported finding or a note's claim type does not become measured evidence because it appears in this interface. Compact export does not include all raw frames or every 100 Hz sample.

User-visible controls are native buttons, labels, selects, search inputs, checkboxes and disclosure elements. Navigation and filtering work by keyboard; focus is visible; the layout adapts to narrow viewports and honors reduced motion. The URL hash records the selected revision and view. Rebuild and repeat browser QA when changing the template or adding an evidence adapter.
