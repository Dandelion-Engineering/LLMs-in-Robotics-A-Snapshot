# Compact construction corridor diagnostic

[compact_construction_corridors.py](compact_construction_corridors.py) is ready for a root-owned queue run after a construction extraction and both official receipts are complete. No actual construction evidence was processed while preparing it. This helper's preparation did not edit Runtime, Calibration Tools, Recovery Qualification or existing geometry/assessment helpers.

Status after construction 003: [official job `20260923T092904839719Z-04533969`](../Evidence/queue-receipts/20260923T092904839719Z-04533969.json) succeeded/0 and ended 2026-09-23 09:40:05.116543 UTC. Its completed small summary records 28/28 physical and timing passes, unchanged sources and 12 deferred validation trials. Root's completed metadata aggregation reports zero bad RTF windows and maximum lag 0.05174729999890637 s. Qualification remains false. Earlier [construction-002 failures](../Batch%2001/Recovery%20Construction%20002.md) remain retained. [Extraction `20260923T094040234587Z-68225cae`](../Evidence/queue-receipts/20260923T094040234587Z-68225cae.json) succeeded/0 at 09:41:05.891394 UTC; root reports all 40 declared dispositions retained at `D:/CodexEvidence/LLMs-in-Robotics/recovery-final-construction-extraction-001`. **The first actual parking1 compact job is active as `20260923T094229717164Z-170731a4`; no completed compact result is claimed.** Its output is `D:/CodexEvidence/LLMs-in-Robotics/recovery-final-compact-parking1-001`. [Final construction derivation handoff](Final%20construction%20derivation%20handoff.md) records the actual inputs, exact queue syntax and projected artifacts. This update read only completed summary/receipt metadata and source; no active output or raw trace was read.

The direct extraction interface avoids the expensive exact-union pruning diagnostic. It uses `assess_validation.CompletedExtraction` to rebind the completed extraction, raw/indexed inputs, archived sources, screen receipt and extraction receipt. The queued helper records its own dependency hashes before and after execution; it does not pin a future in-progress assessor edit by assumption. It streams each selected trial's `whole-geometry.jsonl` and keeps every per-geometry dense interval box intersecting cut through settled placement. Boundary intervals remain whole.

Each original box is assigned by its center to a fixed 0.01, 0.02 or 0.05 m bin. The key also includes the exact geometry inventory identity, and the outer group is the actual payload location. A1, B10 and B2 therefore remain separate. The cover is the min/max hull of boxes assigned to that geometry/bin; bin coordinates never replace or round box coordinates. Grouping is linear dictionary work. It performs no pairwise union pruning.

Every interval input is retained in a compact local JSONL audit with original trace/line hashes. A second pass checks **every input box against its final assigned cover**, with zero containment epsilon and matched counts. The three unpadded cover files per location retain counts, geometry inventory, original coordinate extrema and a source witness for each bin.

For each cover, fixed uniform paddings of 0, 1, 2, 3, 5 and 10 mm are compared against every available same-location construction cut scene's other movable bodies. Chunked NumPy comparisons use the exact archived Runtime overlap formula, requiring an AST match before vectorization: all three overlap depths must exceed 1e-6 m. Reports retain pair counts, strict intersections, Runtime blockers, first blocker, minimum signed axis separation and its witness. They select no bin width, padding, route, measured cell or qualification.

Bin hulls can add unmeasured space and introduce false blockers. Exact added union volume is deliberately `null`: computing it by overlapping volume sums would be wrong. Each bin records its input volume sum and largest member. Reports give algebraic per-bin added-volume bounds and a conservative summed upper bound for global added space, evaluated in floating point; they do not claim certified interval arithmetic. Cover/input volume sums are explicitly not union volumes. Synthetic tests include separated original boxes whose same-bin hull crosses an actual obstacle.

All declared trial dispositions remain in the output, including physical/timing failures, missing or changed input, and unassigned payload groups. A failed partial interval export is retained and excluded from covers. Available cut scenes are still compared even if that trial's later geometry export is missing. Missing group members prevent a complete-route claim; unknown groups are not replaced with favorable trials. Original discrete cached-transform alignment, missing continuous bounds, fixed-world/self-collision limits and original host timing results remain explicit.

Queue payload template, with exact completed paths supplied by root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/compact_construction_corridors.py" `
  --construction-extraction "<completed-extraction.json>" `
  --screen-receipt "<official-screen-receipt.json>" `
  --extraction-receipt "<official-extraction-receipt.json>" `
  --destination parking1 `
  --output "<fresh-derived-directory>"
```

The CLI checks its installed queue process ownership and writes `compact-corridors.json` plus input audits and cover files. The destination is explicit; use another fresh output directory for a separate destination. Output must be separate from source, raw/extracted input, canonical map, candidate state and protected implementation folders. Input mutation or helper changes cannot produce a source-bound completion claim. An official successful receipt is still required for the new derivation.

Run the bounded synthetic checks:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/test_compact_construction_corridors.py"
```

Eleven checks cover exact containment, negative and boundary bins, geometry/location separation, false space, fixed padding effects, scalar/vector overlap equivalence at touching/threshold boundaries, lost-box/audit-mutation rejection, complete synthetic source bindings, retained unknown trials and refusal of an active receipt. No queue, physics or actual evidence run occurs in these tests.
