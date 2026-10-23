# Empty-cut interpretation before freeze

Source correction prepared on 2026-09-23 during development003, with tests deferred during physics. Testing is now complete: the **full Investigation suite passed 164 tests in 27.477 seconds**, official job `20260923T115431720868Z-38d34027`, state `succeeded`, exit `0`; see the [retained receipt](../Evidence/queue-receipts/20260923T115431720868Z-38d34027.json) and [validation 002](Interface%20validation%20002.md). Production HTML remains unrebuilt, and no actual scored data were used. No Runtime, qualification artifact, original result or intervention trigger is changed by this correction.

The measured qualification cell explicitly supports `closed_grip_transfer`. The same episode can instead exercise `after_acceptance`, `after_release` or `before_outcome`, whose frozen classifier checks instantaneous empty/released support, velocity, contact and placement predicates without a grip/route cell. Reader version `qualified-restart-reader-1.1` no longer requires those empty cuts to issue `recover_held` to satisfy the carry-cell endpoint.

This note narrows the unqualified wording about all qualified-mode exposures in [Qualified restart verification](Qualified%20restart%20verification.md): its measured-absence requirement applies to the carry scope. Its source-authority requirements continue to apply to all cuts in a qualified-mode release.

Every interpreted cut still requires independently bound freeze/helper/artifact files, snapshot integrity, exact deterministic selection (including no selected cell), embedded calibration equality and recorded/recomputed classifier equality. Empty cuts also retain the existing capture/classification/revocation landmark checks. Missing independent context, unknown or failed empty predicates, unsupported cuts and stale capture/revocation timing are not upgraded. The carry path's original clock, endpoint, first-control and tamper checks remain unchanged.

For verified empty cuts, `admissibility_scope` is `instantaneous_empty` and `absence.state` is `not_applicable`. This is no claim of actual duration coverage or future recovery. Restored task validity and useful resumption remain independently required by the continuity rubric. At-cut records and original later absence observations remain unchanged.

Counter meanings:

- `known_admissible_qualified_context` counts admissible cuts with independently verified source authority; it includes empty and carry cuts and does not mean all used measured carry cells.
- `known_admissible_carry_qualified` and `known_admissible_empty_instantaneous` separate those two admissible subsets.
- `qualified_restart_exposures` retains its existing meaning: exposures sent to the independent-context reader. `independently_verified_restart_exposures` counts those whose source/snapshot/classifier verification completed.
- `qualified_carry_exposures` counts verified `closed_grip_transfer` scope, including physical failures or unknown coverage. `qualified_absence_coverage_pass` and `qualified_absence_coverage_unknown` apply only to that carry scope.
- `qualified_absence_coverage_not_applicable` identifies verified empty-cut scope, including failed or unknown instantaneous predicates. `qualification_scope_unknown` retains missing-context and unsupported-cut cases. Missing legacy counter fields remain unknown, not zero, in the evaluation processor.

Completed synthetic checks include the existing qualified-reader tests plus empty-cut pass across all three families, physical failure, unknown predicate, missing context, changed artifact/snapshot/identity/selection/calibration/classifier, capture/revocation failures, unsupported fallback, and compact/grouped counter propagation with legacy missingness. These passed as part of the 164-test suite; they do not establish physical performance or actual-data results.

For future relevant changes, the focused command from this directory is the project Python executable with `-X utf8 -B -m unittest -v test_qualified_restart test_continuity test_process_evaluation`. The source UI labels now distinguish verified context, instantaneous empty cuts and carry absence coverage. The production HTML has not been rebuilt or browser-checked against this correction.
