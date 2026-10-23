# Final construction extraction and compact-cover handoff

Construction 003 completed under [official receipt `20260923T092904839719Z-04533969`](../Evidence/queue-receipts/20260923T092904839719Z-04533969.json), succeeded/0, 2026-09-23 09:29:05.280626–09:40:05.116543 UTC. The completed small summary records 28/28 physical and timing passes, unchanged sources and 12 deferred validation trials. Root's completed metadata aggregation reports zero bad RTF windows and maximum lag 0.05174729999890637 s. Qualification and scored readiness remain false. [Construction 002](../Batch%2001/Recovery%20Construction%20002.md) and its four timing failures remain retained.

[Extraction `20260923T094040234587Z-68225cae`](../Evidence/queue-receipts/20260923T094040234587Z-68225cae.json) succeeded/0 at 09:41:05.891394 UTC; root reports all 40 declared dispositions retained. Root has now queued parking1 compact job `20260923T094229717164Z-170731a4` to the output below. **Do not resubmit steps 1 or 2.** Wait for the active compact job's natural completion and official succeeded/0 receipt before consuming its output or submitting parking2. There is no completed compact result yet. This document update used official receipts and the completed screen's small summary, plus source-only compatibility review; it made no queue calls, physical runs or raw-trace streams.

The queue source was inspected read-only. Exact installed CLI syntax is `submit --project LLMs-in-Robotics --cwd <absolute-project-root> -- <absolute-python> ...`; there is no queue timeout argument. Follow [Queue Limitation](../Batch%2001/Queue%20Limitation.md): submit the next job only after the preceding worker/child naturally exits and its official succeeded/0 receipt is retained. Do not query/submit while a worker is alive. These are separate sequential jobs, not a multi-job submission block.

## Shared values

These inputs identify completed construction 003 and its completed extraction. The parking1 output belongs to the active compact job. The proposed parking2 output must still be fresh when used; choose a new explicit suffix if a path already exists, retaining every earlier result.

```powershell
$corridorProject = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$corridorPython = Join-Path $corridorProject 'venv\Scripts\python.exe'
$corridorQueue = 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py'
$corridorExperiment = Join-Path $corridorProject 'Long-Horizon Adaptive Robotics Expirement'
$corridorScreen = 'D:\CodexEvidence\LLMs-in-Robotics\recovery-construction-003'
$corridorScreenReceipt = Join-Path $corridorExperiment 'Evidence\queue-receipts\20260923T092904839719Z-04533969.json'
$corridorExtraction = 'D:\CodexEvidence\LLMs-in-Robotics\recovery-final-construction-extraction-001'
```

## 1. Extract the completed screen

Retained command reference for the completed extraction job; do not run it again against that output directory.

```powershell
& $corridorPython -X utf8 -B $corridorQueue submit `
  --project LLMs-in-Robotics --cwd $corridorProject -- `
  $corridorPython -X utf8 -B (Join-Path $corridorExperiment 'Batch 01\Recovery Qualification\extract_screen.py') `
  --screen $corridorScreen --queue-receipt $corridorScreenReceipt --output $corridorExtraction
```

The official extraction receipt is now retained:

```powershell
$corridorExtractionReceipt = Join-Path $corridorExperiment 'Evidence\queue-receipts\20260923T094040234587Z-68225cae.json'
```

`extract_screen.py` writes `extraction.json` only on completion. It has schema `recovery-screen-extraction-1`, exact source screen/receipt/archive/index bindings, its own extraction queue identity, all declared trial dispositions and references to per-trial `trial.json`, available `measured-states.json`, and `sampled-geometry.json`. Under the unchanged original plan this includes 28 construction entries and 12 deferred validation entries. Failure/missing status remains explicit. The completion marker or a succeeded extraction receipt grants no qualification.

## 2. Compare compact covers for parking1

Retained command reference for active job `20260923T094229717164Z-170731a4`; do not resubmit it.

```powershell
& $corridorPython -X utf8 -B $corridorQueue submit `
  --project LLMs-in-Robotics --cwd $corridorProject -- `
  $corridorPython -X utf8 -B (Join-Path $corridorExperiment 'Engineering Investigation\compact_construction_corridors.py') `
  --construction-extraction (Join-Path $corridorExtraction 'extraction.json') `
  --screen-receipt $corridorScreenReceipt --extraction-receipt $corridorExtractionReceipt `
  --destination parking1 --output 'D:\CodexEvidence\LLMs-in-Robotics\recovery-final-compact-parking1-001'
```

Retain this job's official succeeded/0 receipt after natural exit before interpreting any output or submitting another job.

## 3. Compare compact covers for parking2

```powershell
& $corridorPython -X utf8 -B $corridorQueue submit `
  --project LLMs-in-Robotics --cwd $corridorProject -- `
  $corridorPython -X utf8 -B (Join-Path $corridorExperiment 'Engineering Investigation\compact_construction_corridors.py') `
  --construction-extraction (Join-Path $corridorExtraction 'extraction.json') `
  --screen-receipt $corridorScreenReceipt --extraction-receipt $corridorExtractionReceipt `
  --destination parking2 --output 'D:\CodexEvidence\LLMs-in-Robotics\recovery-final-compact-parking2-001'
```

Again retain the successful official receipt. Separate comparisons do not choose a destination, bin size or padding.

## Projected compact output contract

| Artifact | Required content |
| --- | --- |
| `compact-corridors.json` | Schema `compact-construction-corridor-diagnostic-1`; own queue identity; current helper dependency refs before/after; completed source extraction/screen/extraction receipts; archived overlap source ref; all declared trial dispositions, original physical/timing outcomes and unknown failures. |
| `<trial>-interval-inputs.jsonl` | Every selected interval/geometry box intersecting cut through settled placement, with original trace/line SHA-256 and geometry identity. Partial failed audits are retained and excluded from covers. |
| `<location>-bin-10mm.json`, `-20mm.json`, `-50mm.json` | Separate actual payload location and exact geometry/bin hulls, unchanged coordinate extrema, counts, source witnesses, geometry inventory and complete zero-epsilon input-containment report. Expected locations under the original plan are A1, B10 and B2; absent data remains explicit. |
| Group comparison records | Each available same-group actual other-movable cut scene, all six fixed padding comparisons, exact Runtime-overlap counts/blockers, signed AABB-gap witness, descriptive volume sums and added-space bounds. No exact union-volume value is fabricated. |
| New official queue receipt | Succeeded/0 and matching diagnostic queue identity; required in addition to the artifact's own completion/status fields. |

The helper consumes the direct extraction; it does not need the expensive exact-pruned construction-geometry diagnostic. Source-only review found no fixed assessor-hash guard: current `assess_validation.py` SHA-256 `300b32a136790802ce57781a7ee8b12e2cfe7923b8702d0d998e3c4f3e783192` retains the used `CompletedExtraction` interface and numeric helpers. The queued helper freshly binds installed dependencies before and after execution. The retained extractor exact-source check and archived Runtime-overlap AST guard remain in force. This compatibility review is not an executed derivation. Keep those bytes unchanged until natural exit. Full containment does not establish continuous geometry, fixed-world/self clearance, a state-product domain, host timing or recovery qualification. All parameter-selection and qualification fields remain false.
