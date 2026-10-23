# Raw-pickup recovery profile results

Updated 2026-09-23 after the 12:57:17 UTC derivation receipt: the unchanged local A-only profile rule has been accepted and successfully assembled. Both predeclared online A3 checks completed successfully with admissible carry cuts and passing measured absence coverage; both derived records completed without integrity findings. Development validity remains unknown. This record makes no evaluation-readiness claim.

## Scope and decision

The [prospective profile plan](Recovery%20Profile%20Qualification/plan-001.json) tested the first raw A1→fixture transport at clearance **0.25 m**, speed scale **1.0**, vertical approach and no avoid zones, followed by ordinary cancellation, controller hold and recovery to **parking1**. Seven construction trajectories supplied the fixed local cell and route. Three fresh worlds at n=3/6/10 then tested that high profile and the conventional **0.16/0.8** profile against the same unchanged rule. Those paired profile checks are three independent worlds, not six.

At **12:46:28.902892 UTC**, the root [accepted the unchanged provisional rule](Recovery%20Profile%20Assembly%20Tools/acceptance-profile-001.json), with support explicitly limited to the three predeclared high-profile validation rows. The accepted cell is `profile-A1-root-001`, mapped only to `part:A`, with a maximum **five wall seconds from before cancellation through accepted `recover_held` admission**. The numerical cell is available to every entrant; architecture identity does not select it. Unmapped B payloads remain unknown.

The [provisional rule](../Evidence/derived/recovery-profile-provisional-001/provisional-rule.json) retained SHA256 `43e305a51a27ef1c4728dfdc04ca2ba808e179189aee19d3a0f301b24173d593` through validation and acceptance. Validation outcomes did not change its center, bounds, corridors or absence convention. The existing original P1 bundle, earlier raw→inspection support, and all original development failures remain intact.

## Completed measurements

Construction completed **7/7 physical and host-timing passes**, with sources unchanged. The materializer retained all seven numerical and hold preflight passes, while preserving **four in-domain points and three excluded upper-boundary fixtures**. A boundary physical pass does not confer class admission. The rule uses the predeclared 50 mm center-bin hulls with 10 mm materialized padding and a narrow coupled reference cell; these are empirical transfer assumptions, not a continuous coverage proof.

Validation completed **6/6 physical and host-timing passes**, with sources unchanged. The subsequent source-bound [assessment](D:/CodexEvidence/LLMs-in-Robotics/recovery-profile-assessment-001/assessment.json) finished under its official receipt at **12:42:26 UTC** and reported **3 pass, 3 fail, 0 unknown**. Its aggregate `finite_declared_checks_state` remains **fail**.

| High-profile core validation | Assessment | Discrete robot/payload boxes assessed | Outside / unknown | Measured full wall interval |
|---|---|---:|---:|---:|
| n=3, `parking1-high-validation-n3-A` | Pass | 19,760 | 0 / 0 | 5.0247405 s |
| n=6, `parking1-high-validation-n6-A` | Pass | 19,682 | 0 / 0 | 5.0300544 s |
| n=10, `parking1-high-validation-n10-A` | Pass | 19,734 | 0 / 0 | 5.0428439 s |

All **59,176** assessed core boxes were contained. The core rows also passed the required cut, dispatch, hold/absence, sampled contact, settled-placement dwell and host-timing checks. The fixture requested five simulation seconds, but the accepted wall-time claim uses the separately measured before-cancel→admission intervals above.

All three baseline transfer rows failed **only the cut route's `joint_start` and `joint_velocity` membership**. Their grip predicates and other recorded trajectory checks passed, including contained discrete geometry, dispatch invariants, sampled contact, hold/absence, placement and timing. Successful physical recovery did not repair the failed initial membership. These conventional states remain outside the accepted cell; they were neither relabeled unknown nor used to widen it. Existing C0-012 remains separate evidence of conventional task competence.

## Acceptance, assembly and completed online checks

Accepted assembly job `8b1658f1` completed successfully with an official receipt. Its [assembly record](../Evidence/derived/recovery-profile-qualification-001/assembly.json) reports loader validation **pass** and inputs unchanged. The resulting [development freeze](../Evidence/derived/recovery-profile-qualification-001/development-freeze.json) binds the accepted A-only rule and retained evidence. This is development qualification, not a scored release.

The [online A3-005/006 plan](Recovery%20Profile%20Qualification/A3-profile-validation-development.md) was declared before those runs. The original settings were n=3, world seed 2, policy/noise seed 11, restart and cap 300 seconds, with persistent state for A3-005 and no persistence for A3-006. Job `77877d08` ran from **12:48:04 UTC** to **12:55:27.900438 UTC** and officially succeeded with exit 0. Outputs remain in `D:/CodexEvidence/LLMs-in-Robotics/development-A3-profile-001`. These actual supervisor episodes address the fixture's different observation cadence: the fixture checks every physics tick, while the runtime supervisor may observe after a bounded catch-up batch. They do not establish universal equivalence of cut states.

| Run | Persistence | Independent outcome | Task wall seconds | Model calls / tokens | Maximum lag | Before-cancel→recovery-admission wall interval |
|---|---|---|---:|---:|---:|---:|
| B01-dev-A3-005 | Persistent | 3/3, success | 201.5759562 | 10 / 36,724 | 0.0390572 s | 0.2957894 s |
| B01-dev-A3-006 | No persistence | 3/3, success | 200.2711454 | 10 / 35,545 | 0.0365645 s | 0.2927943 s |

Both exercised the actual configured `closed_grip_transfer` cut without fallback. All **17 required at-cut predicates passed**, giving recorded admissibility **admissible**. Both actual before-cancel→`recover_held_admitted` intervals passed coverage under the frozen five-wall-second bound. The earlier `restart_ready` observations retained preliminary coverage **unknown**, because the required recovery-admission endpoint had not yet occurred. That earlier status is not overwritten by the later endpoint.

The absence record's `physical_recovery_success` remains **`not_assessed`**. Verified duration coverage, at-cut admissibility and later independent 3/3 task completion are distinct recorded facts; neither task success nor a timing pass silently changes that field. This two-episode development check establishes no persistence benefit.

Canonical finish job `b537850e` then officially succeeded. At this accounting cut the map contains **29 runs, 30 result records and 32 revisions**, with episode totals **C0=13, A1=6, A2=4, A3=6**. The extra result record is retained correction history, not a thirtieth episode. Canonical development validity remains unknown.

The pair's [derived index](../Evidence/derived/development-A3-profile-001/index.json) is **completed**: two selected, two completed, zero failed/partial and zero with integrity findings. Derivation job `a3c8c319` officially succeeded at **12:57:17.815612 UTC**. Derivation completion verifies its recorded processing scope; it grants no scored validity or readiness.

The original A3-003/004 tasks succeeded but had inadmissible carry cuts under the earlier cell because joint-start and joint-velocity membership failed. Those classifications remain unchanged. New common calibration support is not a retrospective correction to those runs.

## Limits and retained evidence

Support is finite and local to the measured A1 high-profile start and unchanged parking1 recovery procedure. It does not qualify other raw/source slots, B or insert payloads, the low-clearance/slow corner, arbitrary intermediate objectives, unmeasured coupled interiors, longer absences or different source/class identities.

Dense geometry covers native evaluated discrete states, with the retained one-step cached-transform alignment limitation. Materialized padding is already part of the declared corridor coordinates; the assessor added no further padding or continuous bound. Hold contact and payload-center height were checked every tick; bilateral forces and relative pose are landmark observations. Other-body/contact checks are at retained coarse times. No all-tick contact or continuous collision guarantee is inferred. Every original construction, boundary, validation and baseline-transfer disposition remains available.

The following official successful receipts identify the completed chain; no raw evidence was reprocessed to write this report:

| Work | Official receipt |
|---|---|
| Seven-trial construction | [e9ef2b6e](../Evidence/queue-receipts/20260923T122451702333Z-e9ef2b6e.json) |
| Construction extraction, compact corridors, dossier | [07ad4741](../Evidence/queue-receipts/20260923T122832749866Z-07ad4741.json), [34c769c8](../Evidence/queue-receipts/20260923T122915149560Z-34c769c8.json), [80ebd2e3](../Evidence/queue-receipts/20260923T123014247798Z-80ebd2e3.json) |
| Materializer tests: 5 passed in 0.003 s; rule materialization | [fc160b88](../Evidence/queue-receipts/20260923T123115643760Z-fc160b88.json), [f93340bb](../Evidence/queue-receipts/20260923T123210291268Z-f93340bb.json) |
| Six validation/transfer trials and extraction | [004fcd7a](../Evidence/queue-receipts/20260923T123302710319Z-004fcd7a.json), [7e331047](../Evidence/queue-receipts/20260923T123602230800Z-7e331047.json) |
| Fixed-rule assessment | [e305c551](../Evidence/queue-receipts/20260923T123645142596Z-e305c551.json) |
| Actual online A3-005/006 pair | [77877d08](../Evidence/queue-receipts/20260923T124804450282Z-77877d08.json) |
| Canonical pair finish | [b537850e](../Evidence/queue-receipts/20260923T125616352142Z-b537850e.json) |
| Pair derivation | [a3c8c319](../Evidence/queue-receipts/20260923T125651721797Z-a3c8c319.json) |

Final checkpoint selection and source-bound freeze/readiness remain separate decisions.
