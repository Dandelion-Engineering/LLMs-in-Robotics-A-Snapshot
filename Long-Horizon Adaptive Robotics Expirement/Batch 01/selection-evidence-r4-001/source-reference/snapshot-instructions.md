# R4 development accounting — prepared source only

This is a separate version of the immutable r3 accountant. It uses Runtime 004 queue ownership and Release Analysis 004's exact `current_result` function. It requires 33 terminal development attempts, 34 result records including the original correction, and C0/A1/A2/A3 counts 13/6/4/10. The same 60-episode ceilings leave 47/54/56/50. It retains every failure and supersession; successful outcomes are not required for accounting.

Seven retired evaluation attempts are separate: the one r1 and one r2 attempt plus the five actual IDs from the completed r3 retirement record. The helper requires the Map's evaluation set to equal those seven. Unlaunched schedule members are not fabricated results. Actual all-stage revision counts are computed. Historical and later active engineering hours remain unmeasured; original 12-hour compliance is unknown.

After A3-009/010 are officially complete and canonically finalized, queue this payload from the project root, substituting the actual prepared pair paths:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Lifecycle Repair 001/accounting-tools/snapshot_selection.py' --retirement 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Lifecycle Repair 001/retirement-r3-and-r4-decision-001.json' --pair-plan ACTUAL_PAIR_PLAN --pair-wrapper ACTUAL_PAIR_WRAPPER --output 'Long-Horizon Adaptive Robotics Expirement/Batch 01/selection-evidence-r4-001'
```

`ACTUAL_PAIR_PLAN` and `ACTUAL_PAIR_WRAPPER` are command documentation tokens, not evidence records. Supply existing files; no declaration or output is created by this preparation. Output must be a fresh direct Batch 01 child. The existing r3 snapshot remains the immutable prefix reference. Canonical JSONLs, schema and source references, current Runtime 004 Python files and historical registration manifests are copied; source ZIPs are verified in place. No raw events, images, candidate-private state, model binaries, concealed evaluation manifests or seed files are read.

`accounting.json` remains `complete_non_authorizing`; `snapshot-files.json` binds every output except itself and both carry the owning queue job ID. Require the matching successful official receipt and absence of `snapshot-failure.json`. Failed partial folders remain intact. The sealer separately rechecks current canonical and Runtime identities. This source has not been executed or tested during preparation.
