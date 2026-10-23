# Proposed carry-cut height correction — not applied

Prepared during the active pilot source hold, before scored release. `restart-height-fix.patch` is an unapplied change to `Runtime/initial_conditions.py`, `experiment.py`, and their two source test files. No Runtime bytes, active jobs, historical exposures or recorded outcomes were changed.

Patch SHA256: `498a6a50219ceea1ad8dec712ed494a12c843e58d08d800d953864ff63c83c67`. Exact base and proposed source hashes, plus synthetic test output, are retained in `restart-height-fix.validation.json`. `git apply --check` passed against the current held source. Root owns application and subsequent checks after the batch finishes; this patch is not permission to change a running revision.

The existing `closed_grip_transfer` selector can fire at phase 4 entry as soon as the jaws are closed, while the tool is still at pickup height and the part is supported by the table. That exposure is different from the intended elevated carry ambiguity and the physical calibration's verified carry interruption.

The proposed selector additionally requires **finite public TCP Z ≥ 0.08 m**, while retaining phase 4 or 5 and measured jaw width < 0.065 m. The supervisor supplies `float(cell.data.site_xpos[cell.tcp][2])`. The selector reads no protected payload pose, contact state, history or future result. This is a cheap public telemetry comparison at the existing polling point, not a rich per-tick protected snapshot.

The 0.08 m threshold admits the declared low-clearance A3 trajectory whose nominal tool height is approximately source height 0.018 m + clearance 0.08 m = 0.098 m. It also admits equality at 0.08 m. Actual successful gripping, bilateral load, payload clearance and recoverability remain separate protected calibration/admissibility measurements. Reaching this milestone still does not prove a held object.

Configuration version changes from `robot-restart-opportunity-1.0` to `1.1`, and records `closed_grip_min_tcp_z_m` plus the public telemetry source. Exposure records retain the threshold, actual `measured_tcp_z_m`, `tcp_height_status` (`available`, `missing`, or `invalid`) and `tcp_height_qualified`. A missing, nonnumeric, Boolean or nonfinite height cannot qualify a carry cut. The exposure records null rather than NaN/Infinity if a fallback occurs with unavailable height.

The existing deterministic seed domain, transport ordinal, all four cut families, and **60 s fallback** are unchanged. The other three families do not require TCP height. Invalid/missing height postpones a carry match but does not disable the fallback or turn it into an exercised carry opportunity. No seed redraw or retrospective relabeling is proposed.

The patch includes tests for omitted/None/low/NaN/infinite/Boolean/string height; exact 0.08 m and low-clearance 0.098 m triggers in both phases; unchanged jaw/phase requirements; unchanged other three families; unchanged deterministic selection and fallback; and exact exposure values. The supervisor fixture is amended to assert that the current 0.098 m telemetry is actually forwarded.

Validation performed without applying the patch: all four proposed sources compile; **nine selected synthetic restart tests pass in memory**, including the new counterexamples and existing family/fallback checks; dry-run patch applicability passes; original Runtime file hashes remain identical. The amended supervisor fixture is included but was not executed in this isolated staged validation. No Cell, renderer, model, queue job or physical experiment was run. The corrected source requires a new preregistered physical continuity exposure after application and before any scored-readiness claim.
