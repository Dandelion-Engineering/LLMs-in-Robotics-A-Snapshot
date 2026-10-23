# Raw A1→fixture profile qualification

Prepared source, 2026-09-23; no physical trial, qualification or readiness is claimed here. This is a separate driver and plan. The original Recovery Qualification files, rules, accepted P1 bundle and failures remain unchanged.

The adopted scope is one common `part:A` cell from clearance **0.25 m**, speed **1.0**, vertical approach, no avoid zones, first raw A1→fixture transport, recovery to parking1. It is available to all entrants under the unchanged template selector. `part:B`, inserts as held payloads, other source slots, the 0.08/0.3 corner and unmatched starts are unsupported. The existing loader accepts an A-only map and returns unknown for unmapped B. No multi-cell mapper or candidate policy change is included.

The fixed [plan](plan-001.json) contains **13 trajectories**:

* Seven high-profile construction trials: five existing mass/friction corners/center at n=10 and center at n=3/6, world/layout seed 931201, noise 0. Upper boundary points retain their out-of-domain status.
* Three fresh high-profile validation trials at n=3/6/10, seeds 931301/931302/931303.
* Three conventional-profile transfer checks at the same three fresh worlds, objective 0.16/0.8. These use the **same unchanged A3-derived rule**. They never contribute construction bounds or corridors. They are not three additional independent worlds.

All six validation/transfer rows run only after the complete provisional rule is fixed. Original C0-012 remains conventional task-competence evidence. A baseline state outside the envelope stays unsupported: retain the existing literal numerical `fail` or `unknown`, without relabeling it or changing task outcomes. The accepted scope may name the three high-profile validation IDs and explain the baseline results; every trial remains in the assessment and assembled record. No aggregate all-six pass is implied.

The cut uses the first eligible selected transport with phase 4/5, jaw width <0.065 m and TCP z≥0.08 m. Protected grip/height/route checks cannot delay it. `verified_cut` means that this public opportunity was captured, not that it was admissible. Every physics tick retains the existing hold and geometry measurements, ordinary cancellation/recovery/settling, caps and host timing checks. Five **simulation** seconds are requested; actual before-cancel→admission wall and simulation clocks remain separate. A prospective wall bound must be justified from those measurements.

The fixture observes the public predicate after each ordinary physics tick; the experiment supervisor may observe after a catch-up batch of up to 50 ticks. The predicate is the same, but exact cut-state equivalence is not claimed. The separately declared online A3-005/006 checks in [A3-profile-validation-development.md](A3-profile-validation-development.md) test the actual supervisor with an accepted/assembled profile rule. They do not retrofit these construction measurements.

## Source and tests

[run_profile_screen.py](run_profile_screen.py) was versioned from original `Recovery Qualification/run_screen.py` SHA256 `281e0e44d81af0258f5bad36f541432635319c016b757df5899038120b77cdd3`. It retains the existing parent/child queue authority, exact source archive, process containment, fresh output requirement, full dispositions and before/after source checks. Local imports keep original fixture/measurement/geometry/extractor files unchanged. Both the new directory and original Recovery Qualification helper files enter the source inventory. Hold every inventoried byte stable across construction and validation, including documentation and the accompanying online development plan.

[profile_fixture.py](profile_fixture.py) contains the exact finite plan, public predicate and A-only launch restriction. `execution-plan-001.json` pins plan file SHA256 `bdfc89079044d21ec46a8a052618c9308214b0f236eedbbe81b31640fe092edb`. The new plan is checked for exact equality; it is not an arbitrary sweep CLI.

Twelve tests in [test_profile_screen.py](test_profile_screen.py) are prepared. They cover exact plans/seeds/phase selection, no baseline construction, no single-validation diagnostic, actual submitted objectives, comparison with the current Runtime public milestone, first-cut capture despite a failed protected grip, A-only actual loader behavior/B unknown, and archive helper availability. The synthetic first-cut counterexample uses the actual driver trial body. Tests do not step physics or inspect actual evidence. Test execution and its official receipt belong to the root; preparation alone is not a pass claim.

Queued test payload, from project root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s "Long-Horizon Adaptive Robotics Expirement/Batch 01/Recovery Profile Qualification" -p test_profile_screen.py -v
```

## Execution and derivation handoff

The following are **payload commands for separate installed-queue jobs**, not permission to run them concurrently or directly. After natural completion of all retained owned PIDs and absent queue locks, obtain/save the official successful receipt before the next job. Preserve partial outputs on failure and use a fresh output suffix for any new attempt. Do not invoke queue status/submit while a worker or child remains alive.

Variables below use paths relative to the project root only for source arguments. Output and receipt variables are absolute. Set each receipt variable to the actual saved official receipt of the named completed job; none exists merely because its path is shown here.

```powershell
$ProfileProject = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$ProfilePython = Join-Path $ProfileProject 'venv\Scripts\python.exe'
$ProfileQueue = 'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\compute_queue.py'
$ProfileExperiment = 'Long-Horizon Adaptive Robotics Expirement'
$ProfileDriver = "$ProfileExperiment/Batch 01/Recovery Profile Qualification/run_profile_screen.py"
$ProfilePlan = "$ProfileExperiment/Batch 01/Recovery Profile Qualification/plan-001.json"
$ProfileExtractor = "$ProfileExperiment/Batch 01/Recovery Qualification/extract_screen.py"
$ProfileTools = "$ProfileExperiment/Batch 01/Restart Qualification Tools"
$ProfileInvestigation = "$ProfileExperiment/Engineering Investigation"
$ProfileData = 'D:/CodexEvidence/LLMs-in-Robotics'
$ProfileRule = Join-Path $ProfileProject "$ProfileExperiment/Evidence/derived/recovery-profile-provisional-001/provisional-rule.json"
```

Submit a payload using the existing queue wrapper, for example construction:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B $ProfileDriver --plan $ProfilePlan --destination parking1 --phase construction --output "$ProfileData/recovery-profile-construction-001"
```

The remaining individual queue submissions are listed below. All inputs named as receipts must be the preceding official successful receipts, never guessed IDs.

1. **Construction extraction**, after setting `$ProfileConstructionReceipt`:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B $ProfileExtractor --screen "$ProfileData/recovery-profile-construction-001" --queue-receipt $ProfileConstructionReceipt --output "$ProfileData/recovery-profile-construction-extraction-001"
```

2. **Compact corridors**, after setting `$ProfileConstructionExtractionReceipt`:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B "$ProfileInvestigation/compact_construction_corridors.py" --construction-extraction "$ProfileData/recovery-profile-construction-extraction-001/extraction.json" --screen-receipt $ProfileConstructionReceipt --extraction-receipt $ProfileConstructionExtractionReceipt --destination parking1 --output "$ProfileData/recovery-profile-compact-parking1-001"
```

3. **Construction dossier**, retaining its own receipt:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B "$ProfileTools/bundle_construction.py" --construction-extraction "$ProfileData/recovery-profile-construction-extraction-001/extraction.json" --destination parking1 --output "$ProfileData/recovery-profile-construction-dossier-001"
```

4. **Complete the provisional rule before validation.** This is a root-authored numerical decision from construction, not an automatic fit. Start with `provisional-rule.draft.json` in that dossier, write a fresh `$ProfileRule`, and supply exactly one `part:A` cell with the unchanged full grip/route schema, source/class and measured-point refs, compact cover choice/padding, coupled local scope, untested combinations and absence metadata. Include `envelope_basis`, `maximum_qualified_absence_s`, `absence_timebase` and `absence_endpoint` now; assembly cannot add/change those physical fields after validation. Bind only the seven high-profile construction rows. Preserve the measured upper-boundary distinction, discrete/coarse limitations and all failed rows.

There is deliberately no fabricated materialization command: the existing `assemble_provisional_rules.py` pins old root-choice SHA, old Runtime SHA, both parking destinations and A1/B10 groups. It cannot author this A-only profile rule unchanged. Its old inputs and outputs must remain intact. The existing `bundle_construction.validate_provisional_rule(rule, expected_destination='parking1')`, original `measurement.provisional_identity` and new `profile_fixture.profile_rule_identity` are the applicable completeness/launch checks. A small new materializer may be prepared only once the root has selected concrete construction-based values; it must not choose the values itself or use validation outcomes.

Concrete choice fields required by that rule are:

| Scope | Required choices or exact copied observations |
|---|---|
| Identity | One new `cell_id`; `payload_template_to_cell={"part:A":cell_id}`; `selection_rule="unique_bilateral_payload_template"`; template hash from the exact class spec; exact construction extraction/class refs and seven original measured-point refs |
| Grip | `kind="part"`, `family="A"`, `jaw_width_m`, `relative_position_m` min/max, one exact proper `relative_rotation` reference, `maximum_rotation_error_rad`, `finger_normal_force_N`, `maximum_linear_speed_m_s`, `maximum_angular_speed_rad_s`, `minimum_payload_bottom_z_m` |
| Route start | `tcp_start_m` min/max; seven `joint_start_ranges_rad`; seven `joint_velocity_ranges_rad_s`; `maximum_abs_finger_velocity_m_s` |
| Route and geometry | `operation="recover_held"`, `destination="parking1"`, `payload_kind="part"`, `payload_family="A"`, exact cut `destination_region_m`; `clearance_corridors_m` from every high-profile construction interval's 50 mm bin hull, each materialized with 10 mm padding; complete containment/obstacle refs; no baseline route inputs |
| Absence and provenance | `envelope_basis="measured_before_this_intervention"`; both cell `maximum_qualified_absence_s=5.0` and rule `absence.prospective_absence_bound_s=5.0`; timebase `wall`, endpoint `recover_held_admitted`; `measured_state_cell_basis`, `source_scope`, `route_coverage_method`, `route_sampling_clearance_allowance_m`, `untested_combinations`, rule `empirical_transfer_rule`, `validation_outcomes_used_for_fitting=false`, creation time before validation |

Root prospectively retained 50 mm bins, 10 mm padding and the five-wall-second endpoint. Verify their containment, obstacle and actual-duration support on all seven new construction trials. A materialized-padding implementation may retain the old convention `route_sampling_clearance_allowance_m=0` only with the explicit note that no additional allowance is added; zero is not a continuous error bound.

The **old actual joint policy was center ±0.03 rad and velocity center ±0.10 rad/s**, not min/max across trials plus those margins. `root-provisional-choices-001.json` gives explicit centers and `assemble_provisional_rules.make_cell` constructs symmetric ranges. A new exact center from the prospectively named `parking1-high-corner-A-5` cut would keep that narrow construction-centered policy, conditional on its actual support; separately taking seven-trial extrema and adding margins is a new broader assumption. No baseline/validation value may choose a center or widen a range. Other old grip/TCP numbers are historical measurements/choices, not automatically applicable to the new higher-speed fixture profile. If any in-domain construction point contradicts the selected complete cell, retain the contradiction and stop before validation rather than silently expand it.

5. **All six validation/transfer trials**, using the one completed rule:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B $ProfileDriver --plan $ProfilePlan --destination parking1 --phase validation --provisional-rule $ProfileRule --output "$ProfileData/recovery-profile-validation-001"
```

6. **Validation extraction**, after setting `$ProfileValidationReceipt`:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B $ProfileExtractor --screen "$ProfileData/recovery-profile-validation-001" --queue-receipt $ProfileValidationReceipt --output "$ProfileData/recovery-profile-validation-extraction-001"
```

7. **Assessment**, after setting `$ProfileValidationExtractionReceipt`:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B "$ProfileTools/assess_validation.py" --rule $ProfileRule --validation-extraction "$ProfileData/recovery-profile-validation-extraction-001/extraction.json" --validation-receipt $ProfileValidationReceipt --extraction-receipt $ProfileValidationExtractionReceipt --output "$ProfileData/recovery-profile-assessment-001"
```

8. **Draft assembly**, after setting `$ProfileAssessmentReceipt`:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B "$ProfileTools/assemble_qualification.py" --rule $ProfileRule --assessment "$ProfileData/recovery-profile-assessment-001/assessment.json" --assessment-receipt $ProfileAssessmentReceipt --output "$ProfileData/recovery-profile-assembly-draft-001"
```

Complete that job's `acceptance.draft.json` as a separate source-bound root decision if warranted. The core validation IDs are `parking1-high-validation-n3-A`, `parking1-high-validation-n6-A`, and `parking1-high-validation-n10-A`. Name them explicitly if they support the accepted scope, explain baseline transfer outcomes, and retain every assessment row. Actual reference hashes and support artifacts come from the completed assessment; they cannot be filled from this document. Acceptance does not change the provisional numerical cell.

9. **Accepted assembly**, after setting `$ProfileAcceptance` to the completed decision:

```powershell
& $ProfilePython $ProfileQueue submit --project LLMs-in-Robotics --cwd $ProfileProject -- $ProfilePython -X utf8 -B "$ProfileTools/assemble_qualification.py" --rule $ProfileRule --assessment "$ProfileData/recovery-profile-assessment-001/assessment.json" --assessment-receipt $ProfileAssessmentReceipt --acceptance $ProfileAcceptance --output "$ProfileData/recovery-profile-qualification-001"
```

Successful accepted assembly independently loads the resulting A-only bundle and writes `development-freeze.json`. Retain its official receipt before the separately declared online checks. This remains a development qualification; it creates no scored release or seeds.

The existing extractor and assessor accept the unchanged screen schema and the same full thirteen-row plan in both phases. The source ZIP must include the original `Batch 01/Recovery Qualification/extract_screen.py` and `fixture.py` at their exact paths; the driver does so. The compact helper groups by payload ID, but only high-profile construction exists here, so its A1 group cannot pool baseline routes. No new validator, multi-cell selector or evidence-schema bypass is required.
