# V28 terminal investigation recipe — preparation only

Prepared from source while Smoke026 was active. No active attempt outputs or mutable campaign results were consumed, no qualifier verdict was recomputed, and no command below was executed. All five V28 qualifiers must first pass their original admissions: Native027, Boundary028, Smoke026, Stock025 and Home025. Their completed ledger will be `qualification/final-qualification-028/completed.json`. Partial qualification does not authorize scoring. Final source anchor: dev090 snapshot SHA256 `a72d7068856370b531a0b5e704ca6e8bf1f8091d5798a5c08fbd0f8c0cd476b9`.

## Terminal evidence before final reporting

Use the admitted fixed `campaign-002/execution-plan.json`, not a reconstructed schedule. It has schema `campaign002-execution-plan-1`, campaign ID `RCI001-Campaign002`, ordinals 1–20, and exactly `RCI001-C02-stock-01`…`stock-10` plus `home-01`…`home-10`, with the original family mapping. The preparer fixes world seed173 and noise seeds23001–23020; no replacements. See [prepare_scored.py](../prepare_scored.py), lines20–54, and [PLAN.md](../PLAN.md), lines7 and39.

Wait for the campaign coordinator to finish at slot20 or a legitimate declared stop. [run_campaign.py](../run_campaign.py), lines164–215, authenticates official terminal status, collects only succeeded/genuine-integer-zero output, settles the original disposition, and requires exact stop accounting. [settle.py](../settle.py), lines207–236, writes every remaining slot as `not_run` only after checking it has no launch/runtime evidence. Do not fabricate missing dispositions or overwrite an existing intent. A missing disposition is a reconciliation blocker, not a reportable unrun assumption.

For an early stop after ordinal N, preserve `execution/campaign-stop.json` with schema `campaign002-stop-1`, `planned:20`, integer `stop_after_ordinal:N` in1–20, original reason/counts, and `remaining_admission_authorized:false`. Every one of the 20 exact `execution/<run_id>/disposition.json` paths must be present in plan order; every ordinal>N must be `not_run`, validity unknown, task outcome not_assessed and unscorable. Earlier terminal states may be completed, failed, timed_out, aborted, not_run, cancelled or canceled. Invalid outcomes remain unknown. A qualification stop before any scored launch is not `campaign_terminal`: that closeout contract requires N≥1 and a completed five-stage ledger; retain the honest qualification state instead.

Before any empirical inspection/export, freshly authenticate the relevant official job identity and genuine integer exit0; then use the unchanged independent assessment and exact disposition/assessment hash. Failed queues provide only separately labeled infrastructure diagnostics, never scored traces or recovered outcomes. The report scripts enforce retained official receipt and integrity gates themselves; keep the fresh operator authentication receipt as well. No running outputs may be consumed. The frame exporter and empirical builder both refuse until all20 dispositions are terminal ([build.py](../investigation/build.py), lines484–505; [export_frames.py](../investigation/export_frames.py), lines86–118).

## Exact qualification-history closeout

After all five passed qualifier rows are settled and indexed, update only the bound `current_status` object of `investigation/qualification-history.json`; preserve all prior rows/verdicts. [qualification_report.py](../investigation/qualification_report.py), lines1108–1206, requires:

```text
schema: campaign002-qualification-closeout-status-1
state: campaign_terminal
basis_run_id: RCI001-C02-pilot-home-025
basis_assessment_sha256: exact original Home025 assessment SHA
final_ledger: {path, sha256, bytes} -> qualification/final-qualification-028/completed.json
terminal_plan: {path, sha256, bytes} -> campaign-002/execution-plan.json
terminal_stop: {path, sha256, bytes} -> campaign-002/execution/campaign-stop.json
terminal_dispositions: 20 {path, sha256, bytes} bindings in exact plan order
artifacts: optional {label, path, sha256, bytes} context bindings
```

Use absolute paths and genuine integer byte counts. The final ledger must have schema `campaign002-final-qualification-completed-1`, native/boundary/smoke plus exactly two pilots covering `misplaced-stock` and `blocked-insert-home`. Each ledger entry's manifest, snapshot, queue and assessment must match one unique passed history row; the basis is the final pilot. The closeout validates terminal metadata, not scored task outcomes or scientific admission anew. Before campaign termination, `qualified_campaign_in_progress` uses the same final-ledger/basis bindings without claiming terminal plan/stop coverage.

## Preserve build006 before build007

The existing recipe is the four `investigation/qualification-report-build-006-{intent,submit,queue,receipt}.json` records and `build-006-inputs/`; reuse their receipt structure under a fresh unused `qualification-report-build-007-*` identity and exclusive `build-007-inputs/`. Freeze the final history and report-source input bytes for that build; retain argv/cwd, submission, fresh official terminal receipt, exit status and resulting hashes. Do not execute an old build intent.

Distinguish the **19 existing tracked export bindings**: four current qualification exports, plus15 files in `build-006-retained/` (four export copies, four build records, six exact input copies and the retention manifest). Verify the existing retention manifest/copies before replacement; never overwrite `build-006-retained`. Its relative-link base remains the original investigation directory. Build007 intentionally replaces the four current `qualification-report.html`, `qualification-data.json`, `qualification-provenance.json`, `qualification-qa.json` files, while their old bytes remain retained. Do not claim all19 current path hashes remain unchanged after that intentional replacement. Keep old and new export identities explicit. Preserve Campaign001 and all other protected artifacts/prefixes.

## Four queued jobs, with manual notes between jobs2 and3

These are exact child CLIs. Use repository cwd and the shared queue, one submission per fresh retained intent. After each submission, wait boundedly, authenticate official succeeded/genuine-integer-zero, and only then inspect its output or proceed. Retain all four jobs' intents/submissions/official statuses/results; queue failure is not success and must not be silently retried. The commands below are preparation, not present authorization to bypass qualification or terminal gates.

```powershell
$reportRepo = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$reportPython = Join-Path $reportRepo 'venv\Scripts\python.exe'
$reportQueue = [IO.Path]::GetFullPath((Join-Path $reportRepo '..\tools\compute_queue\compute_queue.py'))
$reportCampaign = Join-Path $reportRepo 'Long-Horizon Adaptive Robotics Expirement\Robot-Codex Integration 001\campaign-002'
$reportInvestigation = Join-Path $reportCampaign 'investigation'
$reportPlan = Join-Path $reportCampaign 'execution-plan.json'
$reportHistory = Join-Path $reportInvestigation 'qualification-history.json'
$reportSnapshot = Join-Path $reportRepo 'Long-Horizon Adaptive Robotics Expirement\Architecture Map\releases\RCI001-C02-dev-090\snapshot.json'

# Job1: qualification companion build007 and its static/integrity QA.
& $reportPython -X utf8 -B $reportQueue submit --project LLMs-in-Robotics --cwd $reportRepo -- $reportPython -X utf8 -B (Join-Path $reportInvestigation 'qualification_report.py') --history $reportHistory --output $reportInvestigation --qa

# Job2, only after Job1's authenticated completion: original frame export.
& $reportPython -X utf8 -B $reportQueue submit --project LLMs-in-Robotics --cwd $reportRepo -- $reportPython -X utf8 -B (Join-Path $reportInvestigation 'export_frames.py') --plan $reportPlan --snapshot $reportSnapshot --qualification-index $reportHistory --max-per-run 32 --max-total-bytes 128000000

# STOP HERE for authenticated evidence inspection and durable manual notes.

# Job3, after notes are complete: actual-results investigation.
& $reportPython -X utf8 -B $reportQueue submit --project LLMs-in-Robotics --cwd $reportRepo -- $reportPython -X utf8 -B (Join-Path $reportInvestigation 'build.py') --plan $reportPlan --output $reportInvestigation --qualification-index $reportHistory

# Job4, after Job3's authenticated completion: static artifact QA.
& $reportPython -X utf8 -B $reportQueue submit --project LLMs-in-Robotics --cwd $reportRepo -- $reportPython -X utf8 -B (Join-Path $reportInvestigation 'qa.py')
```

`--qualification-index` means the completed **history JSON**, not the admission qualification index. Do not use exporter's `--build-report`, because manual notes must precede the empirical build. Exporter writes fixed `investigation/frames/index.json` and original PNGs below `frames/`; there is no output-directory flag. At most32 originals per selected episode and128,000,000 aggregate PNG bytes, including existing exports; no resizing, recreation or deletion. Missing/retired images remain unavailable. [export_frames.py](../investigation/export_frames.py), lines39–50,86–118,192–218, binds the exact frozen recorder and source snapshot. The empirical builder writes `report.html`, `data.json`, `provenance.json`; `qa.py` has no CLI arguments and writes fixed `investigation/qa.json`. Node must be available for syntax checks. See [build.py](../investigation/build.py), lines554–604, and [qa.py](../investigation/qa.py), lines31–100.

Manual notes: create `investigation/stock01-investigation.md`, `home01-investigation.md`, `stock10-investigation.md`, `home10-investigation.md` for the first/last **scheduled** episode of each family, even when unrun. Do not substitute the last executed/successful run. Also cover the first valid task failure per family and first instance of each distinct infrastructure or unexpected behavior category, explicitly labeled outcome-selected. The selector is [build.py](../investigation/build.py), lines423–469; the note linker accepts `<stock|home><two digits>*-investigation.md` at lines262–265. It links the notes but does not verify that human inspection happened; complete and review them before Job3. For each executed, authenticated case, link observation/publication and image identity → public model/tool receipt → authority epoch and accepted/rejected action → physical follow-through → original protected outcome, with exact paths/line IDs and uncertainty. Program execution alone is not actuation, sampled images are not continuous observation, and model claims are not measurements. For unrun examples, link the stop/disposition and state no trace exists. For failed queues, stay within settled diagnostic metadata. Preserve Campaign001's24-slot denominator (six valid successes/four invalid/fourteen unrun); compare observed patterns without causal improvement claims.

Static QA checks20 slots, all four preselected identities, links, event ordering, invalid/unrun display boundaries, PNG hashes/caps and inline JavaScript syntax. It does **not** establish browser interaction/visual QA; retain the existing browser-policy limitation without a workaround. Remaining prerequisites are genuine five-stage completion, admission/campaign termination, final closeout bindings, preserved exports and completed notes—not another report framework or speculative source repair.

## Source identities used for this recipe

| Campaign-relative source | SHA256 |
|---|---|
| `investigation/qualification_report.py` | `6a3aff7d5375dae6d12cdea26ce485ec40818c148e6f0be47083cfe03ced1090` |
| `investigation/export_frames.py` | `5c537cdf0288f7c4cf84a39fd314f589e2d0d56c4f0e8b99b67f7e3e359b9fa7` |
| `investigation/build.py` | `e31bc6f537db1289a394b46725305bd0a10e39e7c59189b1e70a633cc337c645` |
| `investigation/qa.py` | `c8093e95280b232c64d79f7fd9da28962c5c2ec2aab5269832d1a322003fbd22` |
| `run_campaign.py` | `e02fb089a1ac1993608e552a569fe0e93a01acd09e8215463120c92584976d3d` |
| `settle.py` | `86cd98500c91beb46480a0c00a267c7b06d2cc43ceb42dc629cae342569b3f0a` |
| `prepare_scored.py` | `196993f1c35c8f9da94617f31b9155367e253e82d2b1b72606ce739cef257c79` |
| `PLAN.md` | `505a6c9add61fe51c4dc05cb53485c091a22b8087007f95e8ccaba211fe6ed3a` |
