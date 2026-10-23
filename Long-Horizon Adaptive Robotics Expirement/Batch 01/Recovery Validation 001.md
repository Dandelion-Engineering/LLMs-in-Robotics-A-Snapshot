# Original fixed-rule recovery validation

Both original six-trial destination sets completed on 2026-09-23 without changing their rules, seeds, timing limits or physical source class. Each physical screening job reported six task/hold/timing passes. The independent fixed-rule assessment is stricter and its failures remain in the record.

The primary destination was parking1 before validation outcomes were known. Its unchanged A1 and B10 cells were accepted by the root operator under Randy's authorization to implement and run the complete experiment. This is limited empirical development qualification, not a scored-readiness decision or a proof over every state in the numerical cells.

| Destination | Fixed-rule assessment | Engineering disposition |
|---|---|---|
| parking1 | 4 pass, 2 fail, 0 unknown | Accept unchanged A1 and B10 cells for the predeclared local scope and at most 5 wall seconds through accepted recovery admission. |
| parking2 | 1 pass, 5 fail, 0 unknown | Leave unqualified. Recorded active-contact penetration exceeded the existing limit in five trials. |

For parking1, A1 passed at the original n3, n6 and n10 cuts; B10 passed at n10. All four passed the required cut/dispatch checks, full wall-time absence, dense discrete geometry containment, recorded contact policy, independent settled dwell and timing checks. Measured wall intervals to accepted dispatch were 5.021625000001222, 5.033234300000913, 5.044872500000565 and 5.044621099999858 seconds. Their 18,850, 18,876, 18,902 and 15,834 assessed dense boxes had no containment failures or unknown records.

The n3/n6 B2 states fail the unchanged predeclared numerical cut predicate and dense corridor containment. These are actual out-of-cell results, not missing observations or removed trials. The overall six-trial assessment remains `fail`; acceptance does not rewrite it to pass. Numerical grip/route checks recorded at later recovery landmarks are descriptive because those bounds were explicitly defined at the cut; required dispatch invariants were assessed separately.

For parking2, only n10-A passed all checks. Maximum recorded active penetrations were 0.0035165942713707952 m (n3-A), 0.003849892166350028 m (n3-B), 0.003440425507538038 m (n6-A), 0.0036403963061621414 m (n6-B), 0.0028377182570434 m (n10-A), and 0.0034181211920984497 m (n10-B). The existing approximately 3 mm threshold was not relaxed. B2 additionally retained its predeclared numerical/containment failures.

Parking1 acceptance is supported by four untouched A1/B10 validation trajectories. Validation checked dense discrete geometry containment and native active-contact penetration at recorded coarse/forced observations. Construction supplied source-bound measurements and corridor evidence, but its trajectory contact policy was not assessed. Every-tick hold checks cover hand contact and payload height; bilateral force and pose are landmark measurements. No continuous-motion or every-tick contact-policy guarantee is claimed. Unmeasured Cartesian interiors, other phases, boundary classes, destinations, payload states, durations and source changes are outside this acceptance.

## Retained identities

- Original physical jobs: parking1 `20260923T101804870942Z-e21545c0`; parking2 `20260923T102107481352Z-c4ee3b98`.
- Original extraction jobs: parking1 `20260923T102415243216Z-2a00ba15`; parking2 `20260923T102426176556Z-fabe4abc`.
- Assessment jobs: parking1 `20260923T102437045469Z-f4cdd2cf`; parking2 `20260923T102909648121Z-c6e98900`.
- Each official successful integer-zero receipt is retained in `../Evidence/queue-receipts/`. The completed derivation index is `D:/CodexEvidence/LLMs-in-Robotics/recovery-validation-derivation-001/coordinator-complete.json`.
- Raw, extraction and assessment roots are respectively `D:/CodexEvidence/LLMs-in-Robotics/recovery-validation-parking{1,2}-001`, `recovery-validation-extraction-parking{1,2}-001`, and `recovery-validation-assessment-parking{1,2}-001` under the same evidence parent.
- Parking1 assessment SHA-256: `7205aa1d97ece696141d9df995f1e49491af9e59b78537b0f741663afc7b83c3`.
- Unchanged rule files: `../Evidence/derived/recovery-provisional-001/parking1/provisional-rule.json` (`a448f8ada8758c6c191e27c786baa2f55323942c72bd67158c8fa3cbb946ca95`) and parking2 (`b0423179b261f88ee9f0a36c8e5145146877920910410259c10ecf2db2f4b96e`).
- Explicit root decision: `Restart Qualification Tools/acceptance-parking1-001.json`, accepted at `2026-09-23T10:32:14.293150+00:00`. No parking2 acceptance was issued.

The first assembly attempt, `20260923T103519277953Z-6d12ff42`, failed because the helper expected plain-file source references while the actual assessment retained archive-member references. This packaging failure and official failed receipt are retained. Repairing that interface does not change the physical results, rules or acceptance. Successful assembly, actual complete-classifier CPU measurements, the original eight development003 episodes, final readiness and the 264 scored dispositions remain separate steps.

## Completed assembly and offline CPU measurement

The archive-member interface was repaired without changing the rule, assessment, acceptance or Runtime. Whole-archive identity and exact unique member bytes are verified and retained. Ten regression checks passed in 1.849 seconds under official successful job `20260923T104420085253Z-216806f1`. Actual assembly `20260923T104450857818Z-45492f17` completed at 10:44:53 UTC with unchanged inputs and runtime loader validation `pass`. Its files are `../Evidence/derived/recovery-qualification-parking1-001/{assembly,qualification,development-freeze}.json`; its successful official receipt is retained.

The first original parking1 n3-A cut was selected before measuring CPU cost. Actual benchmark `20260923T104542571877Z-05ac4fc2` completed successfully with all five calls traversing the full qualified path and returning the same admissible assessment. Selection plus classification took 21.2822–22.8352 ms; encoding the approximately 303 kB protected event into memory took 5.6788–5.8704 ms. Inputs remained unchanged. The exact report is `D:/CodexEvidence/LLMs-in-Robotics/restart-qualified-cpu-001/summary.json` with the official receipt in the usual directory. This measurement excludes native capture, physics, inference, real event writes and flushes, and does not establish live timing by itself.

The original unchanged development003 plan began under job `20260923T104637848546Z-10f91c9b` at 10:46:38 UTC using that actual development freeze. Its output is `D:/CodexEvidence/LLMs-in-Robotics/development-batch-003-001`, with raw episodes under `D:/CodexEvidence/LLMs-in-Robotics/development-raw`. Development completion and interpretation are pending; no scored release has been created.
