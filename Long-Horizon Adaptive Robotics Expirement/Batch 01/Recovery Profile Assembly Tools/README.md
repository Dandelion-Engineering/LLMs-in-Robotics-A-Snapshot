# A1 profile provisional materializer

Source-only preparation. `root-profile-choices-001.json` records root's choices before construction (SHA-256 `862c6b1f1b33e44de1548951575ac58ce287de5ff6f681bce6e496da02f953f7`). Do not edit it after observing outcomes. The base allowance declaration remains unchanged at `0dc4687822db5229e6d9fead06c39516facd06c6452f047d90e2e25b5ba406a5`.

`materialize_profile_rule.py` reuses the existing `CompletedExtraction`, official receipt verifier, dossier regeneration, compact-cover/source binding, exact numerical formula adapter, hold/clock/timing preflight, thin point references and provisional schema validator. It accepts only completed construction from the fixed 13-trial plan: all seven high-profile A1 construction trials, with all six validation rows still deferred. It never opens a validation trial artifact. No Runtime, fixture, old helper, prior rule or evidence is rewritten.

The sole cell is `profile-A1-root-001`, destination `parking1`, mapping only `part:A`. The exact cut q/qd and relative rotation come only from `parking1-high-corner-A-5`. q/qd retain half-widths 0.03 rad/0.10 rad/s; every other original A1 scalar, grip and TCP bound stays fixed. No averaging, extrema fitting, rounding, widening or alternate reference selection occurs. The actual source-bound class bytes are copied unchanged. All seven cuts must pass the original physical numeric formulas, including calibration-boundary points; these boundary points remain class-excluded and are not in-domain measured cell points. No fabricated class observation is used.

Geometry uses the actual A1 compact cover's 50 mm center-bin hulls, materializing exactly 10 mm padding with zero additional allowance. Exact original-box containment and zero recorded movable-body blockers at that padding are required for every construction cut scene. This is discrete empirical geometry with an explicit transfer assumption, not a continuous bound. The unchanged hold preflight requires five wall seconds from before cancellation through accepted `recover_held` admission, all recorded hold checks, placement flags and actual-host timing. As in the existing rule builder, the final independent settled-dwell event is explicitly unassessed here and remains required in final validation assessment.

After official construction/extraction/dossier/compact receipts exist, root may queue:

```text
venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Batch 01/Recovery Profile Assembly Tools/materialize_profile_rule.py" --choices "Long-Horizon Adaptive Robotics Expirement/Batch 01/Recovery Profile Assembly Tools/root-profile-choices-001.json" --construction-extraction "<completed-extraction.json>" --screen-receipt "<official-construction-receipt.json>" --extraction-receipt "<official-extraction-receipt.json>" --dossier "<construction-dossier.json>" --dossier-receipt "<official-dossier-receipt.json>" --compact "<compact-corridors.json>" --compact-receipt "<official-compact-receipt.json>" --output "<fresh-output-directory>"
```

This template does not submit a job. The actual child requires installed queue ownership for its exact script. It verifies successful original receipts, source identities before/after and unchanged Runtime bytes relative to construction. A contradiction retains `construction-membership.json` and all original trial/status entries, exits unsuccessfully and writes no provisional rule. Success writes exact `class-spec.json`, a single `provisional-rule.json`, and the full membership report. It grants neither qualification nor readiness. Existing assembler/validator can consume the A-only provisional schema after prospective validation and explicit acceptance.

Five meaningful synthetic tests are prepared (not yet run): exact choice/allowance tamper rejection; exact coupled center copying/no mutation; seven-construction/six-deferred selection and prospective ordering; boundary numerical comparison without synthesized class admission; and failure/unknown rejection for every selected point. Root may queue them when physical timing jobs have ended:

```text
venv\Scripts\python.exe -X utf8 -B -m unittest discover -s "Long-Horizon Adaptive Robotics Expirement/Batch 01/Recovery Profile Assembly Tools" -p "test_materialize_profile_rule.py" -v
```
