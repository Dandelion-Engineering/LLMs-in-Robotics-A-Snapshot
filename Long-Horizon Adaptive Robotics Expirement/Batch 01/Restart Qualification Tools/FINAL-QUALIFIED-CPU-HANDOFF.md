# Final accepted-bundle CPU benchmark handoff

Prepared from source while primary validation was active on 2026-09-23. No pending output, assessment, acceptance or final bundle was read or created. This adds no tool or optimization. The completed provisional measurement (196,660 canonical bytes, 1,046 boxes, five digests at 2.718–3.753 ms, as reported by root) measures direct rule hashing only; it does not measure the final qualified path.

## Resolve these actual references after acceptance

| CLI input | Exact source of its value |
|---|---|
| `--development-freeze` | The completed accepted assembler's `assembly.json.development_freeze_path`, normally `<accepted-output>/development-freeze.json`. Do not use a `.draft.json` file. |
| `--assembly` | That same accepted output's `assembly.json`, with `status=complete`, `inputs_unchanged=true`, `operator_acceptance_present=true` and `loader_validation=pass`. |
| `--assembly-receipt` | Retained official succeeded/integer-exit-0 receipt matching `assembly_queue`, exact `assemble_qualification.py` entrypoint and its `--output`. The benchmark rechecks the installed queue record. |
| `--cut-states` | In the completed assessment, follow `validation_extraction_ref.path`. In that extraction's `trials`, find the chosen actual `trial_id`, open its relative `path`, then resolve `trial.measured_states.output_path` against the extraction directory. This is the extractor's existing `measured-states.json`. |
| `--events` | `<validation extraction.source_screen>/<same trial_id>/events.jsonl`, the original retained stream. It must appear in the accepted bundle's `artifact_files` with the exact `states.cut.source_ref.sha256`. Do not use an extracted or rewritten event stream. |
| `--output` | A fresh directory beneath an existing operator evidence directory. Preserve any previous benchmark output and choose another unused name. |

Use the completed assessment referenced by `assembly.json.assessment_ref` and the accepted bundle; do not substitute another report. The assessor receipt is **not** a separate CLI argument: the benchmark resolves `qualification.json.assessment_receipt_ref`, checks it against `assessment_queue`, exact assessor entrypoint/output/completion and installed queue state, and rehashes its source dependencies. It also verifies root acceptance, the assembly input inventory and every bundle artifact.

For the mapped cell root chooses to measure, use a source-matched retained validation cut in that cell's explicit accepted `validation_scope.trial_ids`. The assessment's `trials[].numeric_membership.cut` supplies its template, payload and mapped `cell_id`; its cut state and `class_compatibility.cut` indicate whether a full qualified-path replay is expected. Record the chosen trial/cell before viewing benchmark timings. Keep unknown or failed results if returned; do not switch cuts to obtain a faster measurement. This handoff selects no trial or physical cell and adds no required number of benchmark jobs.

The states file must have recorded `states.cut`, with the original `protected_carry_state_before_cut` event and `closed_grip_transfer` exposure. The helper rebinds exact original line bytes, line SHA-256, event ID/type, payload hash, snapshot digest and protected source identities. Its eight required class/source identities must match current Runtime. No reconstructed snapshot or fabricated qualification context is accepted.

## Queue the existing helper once those values exist

Replace the three actual artifact paths and chosen original cut paths below from that reference chain. Run from the project root after the active owned job has naturally exited and its official receipt has been retained; obey the existing queue discipline.

```powershell
$cpuProject = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$cpuPython = Join-Path $cpuProject 'venv\Scripts\python.exe'
$cpuQueue = 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py'
$cpuHelper = Join-Path $cpuProject 'Long-Horizon Adaptive Robotics Expirement\Batch 01\Restart Qualification Tools\benchmark_qualified_restart.py'
$cpuFreeze = '<actual accepted assembly development-freeze.json>'
$cpuAssembly = '<same accepted assembly assembly.json>'
$cpuReceipt = '<retained official assembler receipt.json>'
$cpuStates = '<completed validation extraction\actual trial\measured-states.json>'
$cpuEvents = '<original completed validation screen\same trial\events.jsonl>'
$cpuOutput = 'D:\CodexEvidence\LLMs-in-Robotics\restart-qualified-cpu-001'
& $cpuPython -X utf8 -B $cpuQueue submit --project LLMs-in-Robotics --cwd $cpuProject -- $cpuPython -X utf8 -B $cpuHelper --development-freeze $cpuFreeze --assembly $cpuAssembly --assembly-receipt $cpuReceipt --cut-states $cpuStates --events $cpuEvents --output $cpuOutput
```

No acceptance override is available. The helper always measures exactly five selection/classification calls: first in that process plus four repeats. It separately reports loader verification, protected-input materialization and source-extracted `Evidence.emit` encoding into memory.

After natural completion, retain the benchmark's official receipt and `summary.json`. Inspect `status`, `inputs_unchanged`, all five `calls`, `first_assessment` and `full_qualified_path_measured`. A complete summary with unknown classification is not a measured full qualified route. Keep the before/after byte inventories and any failed attempt.

This is offline CPU cost only: no live capture, native model, physics, renderer, inference, real event write or disk flush. First call is not an OS cold-cache measurement. Actual development003 with the accepted development freeze remains the measurement of capture, classification, serialization, cancellation and recovery timing together. No structural or offline timing result grants readiness.

