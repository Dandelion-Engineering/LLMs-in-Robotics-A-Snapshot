# Final control-index preparation

This is preparation only. The adjacent `final-readiness-draft.json` leaves all eleven gates false, `scored_ready` false, the freeze hash null and final evidence references empty. Its absolute source pointers have **no sealed hashes**. Do not pass it to `protocol.py create` or treat prospective root choices as measured qualification.

Use the existing [final freeze/selection runbook](final-freeze-selection-runbook.md) for commands. This note supplies the pending control-index contents; it creates no new audit or scientific prerequisite.

## One immutable index, then direct readiness references

After the remaining evidence and root's concrete checkpoint decision are available, write a fresh `Batch 01/release-control-index-batch01-eval-r1.json` with:

- A local schema label, release ID, actual creation time and explicit scope.
- The unchanged public settings: 264 attempts (192 main, 72 controls), maximum retries 0, 2,000 bootstrap draws, public analysis seed 0, and the existing twelve fixed trace slots.
- An `artifact_files` array of unique IDs with exact absolute local `path` and ordinary file-byte `sha256` values. Keep a single identity per final file; describe purpose separately. Absolute references support retained D qualification artifacts without moving them.
- Root's selection/extension record and closed ledger/map snapshots, actual resource/storage decision, and accepted qualification decision/artifact references. Do not reference a mutable future ledger as if already closed.
- The final documents and executable sources listed below. Preserve these bytes after sealing.

This is a supplemental evidence index, not a new Runtime authority schema. Put **the index and every directly indexed file** in final readiness `evidence_refs`. `validate_release_gates` checks the direct file references; listing only an index does not transitively freeze its entries. Do not put the final readiness document inside its own reference closure. The control index need not hash the final freeze: create the index first, then the freeze, then readiness bound to the freeze's exact byte hash.

## Existing control and analysis files

The adjacent draft's `source_pointers` contains full existing paths for these exact files:

| Group | Include final files |
|---|---|
| Experiment decisions | Evaluation Release Plan; Shared Implementation Contract; Resource and Retention Policy; Restart Calibration Qualification Plan; actual root selection/extension decision and closed development ledger/map snapshots. |
| Interpretation and display | Continuity Analysis Rules; Investigation Trace Selection; unchanged evaluation-trace-selection.json; actual analysis settings in the index. |
| Collection/statistics | Release Analysis/collect_results.py and analyze_results.py. Their protocol analysis implementation is also covered by the Runtime artifact index. |
| External execution coordinator | Release Analysis/run_release_series.ps1, RELEASE-SERIES.md and its deferred synthetic test source. The actual coordinator, resource policy, retention summary and official measurement receipt must each be direct readiness references before the coordinator is used. |
| Investigation processing | process_evaluation.py; imported process_development.py; evidence_adapter.py; derivative_adapter.py. |
| Investigation analysis/continuity | analysis_adapter.py; analysis_provenance.py; selected_trace.py; continuity.py; qualified_restart.py. |
| Final presentation interface | build_workspace.py; workspace.html; playback.js; playback.css; analysis.js; analysis.css; implementation_narrative.py; current-implementation-narrative.json; IMPLEMENTATION-NARRATIVE.md; RUNBOOK.md; Evaluation processing.md; Qualified restart verification.md; Empty cut reader correction.md; Release interface checklist.md. |
| Qualification provenance | Actual accepted rule, completed assessment, concrete acceptance, assembly/bundle/development-freeze records, their official receipts and artifact closure. Use their real final identities; source-held helper identities stay bound by those records. |

`freeze_artifacts.py` automatically indexes Runtime Python, Architecture Map/map.py, environment/model artifacts and vendor dependencies. It does **not** automatically freeze these sibling Release Analysis and Investigation sources. The supplemental direct references close that gap. Do not overwrite a frozen derived-tool source to repair a later analysis problem; retain a separately identified version and its provenance.

## Fill only the pending handoffs

| Input | What root fills when complete |
|---|---|
| Current-source qualification | Completed construction004/derivations, immutable rule, reserved validation and assessment, all failures/outside rows, explicit support acceptance, final assembly/bundle/development freeze, loader result. The construction003 record remains historical after the route optimization. |
| Qualified-path costs | Existing queued offline benchmark's actual accepted inputs, first/repeated classification and event serialization costs, official receipt and byte-stability record. It cannot grant physical timing; actual candidate timing is separate. |
| Development003 | Original eight rows' terminal canonical dispositions and receipts, exact source/checkpoint bindings, matched persistence evidence and actual restart absence to the accepted endpoint. Account for any additional declared attempts without removing originals. |
| Opportunity/selection | Actual dated symmetric closeout decision, exact attempt/correction accounting and selected checkpoints for all four entrants. Keep historical active hours null/unmeasured and original time-ceiling compliance unknown. |
| Storage | Current C/D free bytes and retained-rate/capacity estimate after prerequisites, full remaining task time plus 50 GiB reserve, and the recorded capacity decision. Old inventory004 free-space margin is not current availability. All scored runs stay on C. |
| Final identities | Fresh successful prepared-artifacts indexes/receipt, exact final control-index and direct file hashes, final freeze bytes and the eleven gate decisions. No Runtime Python edit may silently follow preparation. |

Existing model selection, matrix/caps, zero retries, public analysis settings, fixed trace slots, resource-policy distinctions and reader contracts are fixed configuration to bind. The pending handoffs establish their final evidence/identity; they are not invitations to choose a different matrix or tune against scored cases. Previously completed checks should be cited with their exact source scope instead of rerun without a concrete need.

The presentation builder must receive the final `--implementation-narrative` file explicitly. The source-matched prose describes all four actual implementations, while the original proposals and immutable revision text remain inspectable. The current reader correction distinguishes independently verified instantaneous empty-cut admissibility from qualified carry coverage and from demonstrated recovery. Bind the actual tested versions, including their dependencies and interface assets; do not replace those distinctions with a single generic qualification label.

No gate decision, qualification acceptance, symmetric extension or final checkpoint selection is made by these drafts. Routine evidence-based closeout is within root's existing authorization; a material change to the experiment remains a separate user decision. Actual scored collection, analysis, production HTML and browser QA occur after release execution under the existing runbook.
