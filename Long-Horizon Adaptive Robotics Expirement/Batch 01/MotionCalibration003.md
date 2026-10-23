# Common motion calibration 003

The shared executor now has a measured basis for 10 mm Cartesian continuation, the two revised parking centers, and a 480-iteration IK budget while retaining the original insert A home. These are engineering changes to the common body/controller. They are not scored architecture results or evidence that the full physical prerequisites have passed.

## Completed attempts and receipts

Each receipt below was read from the retained official queue response and reports `state: succeeded`, `exit_status: 0`. That establishes completed execution, separately from the physical or kinematic result.

| Attempt | Official job and UTC execution interval | Result |
|---|---|---|
| Recovery kinematics 002 | [20260923T061631439898Z-a2dfca30](../Evidence/queue-receipts/20260923T061631439898Z-a2dfca30.json), 2026-09-23 06:16:31.872–06:16:34.038 | Both proposed parking routes converge; both old routes fail. Retained-branch insert continuation fails. |
| Physical calibration 004 | [20260923T062117342781Z-c53110e6](../Evidence/queue-receipts/20260923T062117342781Z-c53110e6.json), 2026-09-23 06:21:17.792–06:21:37.787 | All final parking placement predicates pass, but the one-second held-height predicate fails. Overall physical predicates remain false. |
| Insert kinematics 003 | [20260923T062244327184Z-5fe6fdc2](../Evidence/queue-receipts/20260923T062244327184Z-5fe6fdc2.json), 2026-09-23 06:22:44.774–06:22:46.190 | Original A home fails at 120 iterations and converges at 480. Proposed relocated A converges at both budgets. |
| Physical calibration 005 | [20260923T062527913747Z-e554bf44](../Evidence/queue-receipts/20260923T062527913747Z-e554bf44.json), 2026-09-23 06:25:28.350–06:27:50.934 | All seven declared probes and their separate actual-host timing checks pass; sources remain unchanged. |

## Parking selection and limits

[Declared comparison 002](Recovery%20Diagnosis/PLAN-002.md) evaluated exactly four routes from archived physical-calibration-002 post-absence robot states, using the archived solver, unchanged endpoint heights and grip/phase sequence, and at most 10 mm spacing between Cartesian targets. It advanced no physics.

| Parking region | Old center (m) and result | Selected center (m) and result |
|---|---|---|
| parking1 | `(0.27, 0.05)`: failed during approach, residual 2.79084 mm | `(0.34, 0.04)`: all declared route waypoints converged |
| parking2 | `(0.20, -0.09)`: failed during approach, residual 13.19098 mm | `(0.46, 0.12)`: all declared route waypoints converged |

Both old-route failures reached joint index 3 at -3.0568 rad, the original solver’s 0.015 rad margin above the joint lower limit. Both new routes included close/carry/lower/open/retract and the declared empty-jaw HOME return. Their 106 mm parking regions are disjoint from the other fixed regions and conservative ten-part raw-stock envelope. The two parking regions have 14 mm horizontal separation; parking2 is also separated from the fixture on both horizontal axes. These checks establish declared region non-overlap, not collision-free arm or carried-object motion.

See [002 summary](../Evidence/calibration/recovery-kinematics-002/summary.json), retained public inputs, and intermediate FK samples in that evidence directory. The common geometry adopted these two parking centers; no part was teleported in a physical episode.

## Insert A path and solver budget

The companion [002 insert comparison](../Evidence/calibration/recovery-kinematics-002/insert-descent/summary.json) exposed the old retained endpoint interpolation’s curved open-jaw descent: its sampled maximum lateral error was 49.5967 mm, true orientation error reached 0.15223 rad, and frozen-scene hand/insert clearance reached -11.3721 mm. Those are counterfactual static target geometries, not measured contact forces or an exact reproduction of the physical trajectory.

The 10 mm continuation alternative reduced early lateral errors but did not finish: phase 2, substep 11 failed at target height 69.9814 mm with position residual 1.27592 mm after 120 iterations. Its joint-index-3 margin was 0.08117 rad, so this particular failure was not simply the old parking joint-bound failure. Its unexecuted lower path cannot be described as clear or successful.

[Declared comparison 003](Recovery%20Diagnosis/PLAN-003.md) then tested exactly four combinations from the **same archived common HOME**: original A or proposed A at `(0.34, -0.43)` m, each with 120 or 480 iterations. Every combination included the full approach, descent, close and lift, phases 0–4, with the same source height, 4 mm insert TCP offset, 160 mm clearance, 1 mm position criterion and 0.01 orientation criterion. Reports used true SO(3) angle as an additional guard against false cross-product convergence. Both solver variants used archived physical-calibration-002 source; no current Runtime motion implementation entered the diagnostic.

| A home / iteration budget | Measured static outcome |
|---|---|
| Original / 120 | Failed phase 1, substep 45; 1.52552 mm position residual at the joint-index-3 margin. |
| Original / 480 | Completed 98 waypoints; at most 338 iterations, maximum endpoint position error 0.99861 mm, maximum endpoint true orientation error 0.0018153 rad, minimum joint margin 0.015 rad. |
| Proposed relocation / 120 | Completed 114 waypoints; at most six iterations, maximum endpoint position error 0.96171 mm, minimum joint margin 0.32646 rad. |
| Proposed relocation / 480 | Same completed path and reported bounds as the 120 variant. |

The original-home 480-iteration descent has 187 retained interpolation samples. They have no reconstructed hand contact in the frozen original scene, maximum lateral source error 1.77560 mm and maximum true orientation error 0.006151 rad. Finite samples do not prove continuous clearance or executed grasp behavior. Relocated-path object contacts are explicitly not applicable because that diagnostic did not move scene objects. Its region checks pass, but relocation remains an unselected alternative.

The selected common change keeps insert A home `(0.18, -0.25)` m and raises only the fixed solver iteration budget to 480. The retained public source XY in this episode was `(0.18761797, -0.24695528)` m; this observed offset must not be confused with changing the home center. Keeping the original home avoids an additional geometry change while the static path can converge. The higher iteration requirement and proximity to a joint bound remain limitations to examine in physical development. No scored seeds or outcomes informed this choice. See [003 summary](../Evidence/calibration/recovery-kinematics-003/summary.json); its script and plan remained unchanged during execution.

## Physical carry result and cancellation correction

Physical calibration 004 used the new parking2 center and Cartesian continuation. A1 subsequently satisfied every independent final placement flag, including full containment, single occupant, no gripper contact, open jaws, slow part, settled arm/fingers, raw state and no pending work, with the required 0.5 s dwell. Nevertheless its overall result is false because it did not remain above 75 mm during the declared one-second absence.

At the verified cut, A1 was rising and its center was 75.1491 mm high, only 0.1491 mm above the threshold. After one second it was 69.9578 mm high. Bilateral finger force persisted in the two endpoint captures (approximately 1.05 N per finger), both had no nonhand support contact, and all ten retained intermediate protected snapshots report gripper contact. Thus the recorded failure is a loss of the required height, not evidence that the part was dropped. The finite observations cannot exclude brief contact changes between samples.

The TCP fell 2.9410 mm while A1 fell 5.1913 mm, and A1’s relative position within the grasp also changed. Archived `Cell.cancel` had replaced the current position target with measured joint positions; all 100 retained trajectory samples during absence then held that measured-q target. The maximum command change at cancellation was 0.0477088 rad. These observations support testing a cancellation-induced hold deflection correction, while preserving uncertainty about the contributions of motion arrest, load deflection and slip. See [Carry Hold Diagnosis004](Insert%20Pickup%20Diagnostics/Carry%20Hold%20Diagnosis004.md) for exact event IDs, source hashes and numerical evidence.

The implementation follow-up is deliberately narrow: ordinary active **task-trajectory** cancellation freezes its last emitted valid native position target while discarding future trajectory authority. Direct adapters retain their existing measured-q cancellation fallback, including direct effort, whose native control encodes a torque-producing offset. This change does not extend the old trajectory, alter the jaws or weaken any physical predicate; holding a target is not an instantaneous-stop guarantee.

[Physical calibration 005](Physical%20Calibration%20005.md) subsequently passed all seven declared probes and all seven actual-host timing checks with unchanged sources, as recorded in its [summary](../Evidence/calibration/physical-calibration-005/summary.json) and official receipt above. Both insert installations passed their independent identity, containment, release and settling checks. The separate seed-0 A1 recovery routes to both parking pads passed the unchanged one-second held-height/contact predicate and final placement/dwell checks. The adapter, effort-equivalence, raw-camera and initial static-sensor checks also passed within their declared scopes; maximum observed host lag was 0.0079235 s.

This fresh physical evidence supports the integrated common changes for the measured primitive episodes. It does not change calibration 004's failure or establish candidate process restart, longer absence, transfer across payload/state classes, memory benefit, complete task performance or scored readiness. The two recovery routes cover the retained seed-0 A1 cut states and one-second absence only. Full development episodes and prefreeze recovery qualification remain separate work.
