# Physical calibration 005

All seven declared probes and their separate actual-host timing checks passed. The [official receipt](../Evidence/queue-receipts/20260923T062527913747Z-e554bf44.json) records job `20260923T062527913747Z-e554bf44`, succeeded/exit 0, 2026-09-23 06:25:28–06:27:50 UTC. The [summary](../Evidence/calibration/physical-calibration-005/summary.json) confirms unchanged sources. This is shared prerequisite evidence, not a completed candidate task or scored comparison.

| Probe | Measured outcome and limits |
|---|---|
| Insert exchange | Both B installation and return to A passed independent insert identity, full containment, release and settling checks. Original insert-home coordinates and grasp-height offsets were retained. |
| Held recovery to parking2 | Image-derived A1 pickup, verified carry cut, the unchanged held-height/contact check after one second of advancing physics, then all final raw placement predicates and 0.5 s dwell passed at `(0.46,0.12)` m. |
| Held recovery to parking1 | Same declared seed-0 A1 primitive sequence passed at `(0.34,0.04)` m. This is a separate measured route. |
| Arm interfaces | All five bounded unloaded adapter checks passed; the earlier local-displacement versus absolute-setpoint distinction remains. |
| Effort equivalence | The narrow four-second paired native/inverse-servo comparison passed. It does not establish arbitrary torque-control equivalence. |
| Raw cameras | All three native RGB/float32-depth permission and lossless IPC checks passed; no language-model image understanding is inferred. |
| Static sensors | All 75 center observations in three captures each at 3/6/10 parts were within the unchanged 4 mm scalar, maximum 1.267882 mm, with no missing identities. Scope remains initial static scenes. |

The largest measured lag was 0.0079235 s (parking2 recovery). No timing, containment, height, contact, settling or decoded-payload threshold was relaxed. Every earlier failure remains retained.

## Changes and interpretation

[MotionCalibration003](MotionCalibration003.md) records the fixed kinematic comparisons and source corrections. Common task paths now use at most 10 mm Cartesian steps with the existing whole-phase timing floor distributed across subdivisions. Parking pads moved to the two fixed tested positions. The common solver can perform up to 480 iterations while retaining its convergence tolerances; the original A home was selected over the also-tested relocated alternative. Cancellation of an active task trajectory clears future motion but preserves the last emitted native positional setpoint. Direct adapters retain their measured-position fallback, including direct effort whose inverse-servo control cannot be retained as a position hold.

Calibration 004 already passed final parking2 placement but failed the held-height predicate during absence. Retained snapshots showed bilateral grip with a height decrease and some relative payload movement; they did not establish zero slip. Attempt 005 passed the same predicate after the hold repair. This comparison supports the shared correction for these measured primitive episodes; it is not a universal stability proof.

The two recovery successes cover one seed-0 A1 payload, the retained cut states and routes, and one second of authority absence. Candidate process restart, longer absence, broader state/property transfer, memory benefit, process/rework/order-change behavior and complete tasks remain unmeasured by these probes. The compatibility/export proposal and any prospective qualification must retain that boundary. `scored_ready` remains false. Next work is complete development episodes, operational resource evidence and defensible prefreeze recovery qualification, followed by the full declared scored matrix and analysis.
