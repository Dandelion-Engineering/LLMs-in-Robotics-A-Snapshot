# Raw pickup geometry diagnostic 001

Prospective static diagnostic only. No physics step, sensor rendering, grasp outcome, task performance, hidden-pose rescue, Runtime edit or qualification grant occurs.

The question is whether the native Panda open-finger collision geometry can intersect a neighboring raw block at the current 74 mm row pitch, and which small shared layout/orientation alternatives merit physical validation. C0-007 (n10, world/layout seed 2) retained a tipped B6 after nearby A3 pickup; the temporal association is not itself proof of the contact mechanism.

Pinned inputs: C0-007 manifest SHA-256 `b4c9b17a320fd44a793890bc5ac7184f0d05435bcb8e505f9e706d335f5395b4`; its `cell.py` SHA-256 `ac13595b62ae51bb1cc5dd7387ab0ec605253fa65a0a276c5c85395929cb40fa`. Every native Panda asset is checked against physical-calibration-005 manifest SHA-256 `6572278756b0491719d68d285518d4b5bcfa24411ce892837adcaecb02e265e0`. Archive all consumed source/assets, generated XML, helper and this declaration. Abort if a pinned identity differs.

Exactly five fixed variants, with unchanged 85 mm column pitch, 42 × 42 × 36 mm workpieces and 40 mm displacement of each open finger:

| Variant | Row pitch | Constant row-zero y | Tool yaw |
|---|---:|---:|---:|
| Current control | 74 mm | -310 mm | 0° |
| Pitch 90 | 90 mm | -358 mm | 0° |
| Pitch 95 | 95 mm | -373 mm | 0° |
| Pitch 100 | 100 mm | -388 mm | 0° |
| Quarter-turn control | 74 mm | -310 mm | 90° |

Each origin is constant across populations 3/6/10. The fourth nominal row remains at -88 mm. No mass/friction/jitter range, population, time cap, source identity, source height or grasp threshold is narrowed. None of these alternatives is selected before results.

Native hand collision probe: clone the exact Panda hand/fingers and collision geoms into a static diagnostic scene, preserving finger meshes/pads and the TCP offset. Set the exact prescribed top-down orientation and open finger displacement; do not claim arm reach from this isolated-hand probe. Query signed native geom distances at TCP z = 18 through 180 mm inclusive in 1 mm increments, for five predetermined planar observation offsets: zero, ±4 mm in x, ±4 mm in y. These are independent declared test points, not a measured perception guarantee. Report seed-2 nominal A3-relative stock positions separately from four pairwise conservative cardinal-neighbor positions with relative inward jitter 6 mm (85-6 mm in x and pitch-6 mm in y). The four inward positions are separate pairwise extreme tests; they need not be jointly realizable with one target jitter. Keep actual source seed-2 geometry distinct. Blocks are frozen upright with center z=18 mm, a geometric settled proxy; this is not a replay of B6's actual post-contact pose or a gravity/contact-settled state.

For each case retain the minimum native signed distance, responsible hand geom/neighbor/TCP pose, every negative-distance sample, and the actual sample spacing. The static mesh convex collision shape is authoritative for the query; outer AABB overlap alone is not treated as contact. Positive results concern these sampled poses only; no continuous collision or successful pickup claim follows.

Whole-Panda reach check: compile the pinned generated n10/seed2 scene once; construct each counterfactual fixed layout in separate diagnostic state data, leaving object poses static throughout each test. For every one of ten public nominal raw-slot targets, use the pinned 480-iteration IK with unchanged 1 mm position/cross-product tolerances, original HOME, and the common lift/travel/descent approach subdivided at no more than 10 mm. Keep source TCP z=18 mm, open fingers and 180 mm approach plane. For the quarter-turn variant only, substitute the explicitly declared target rotation in the otherwise identical local IK method. Record every attempted waypoint, q, residual, true rotation-angle error, joint-limit margin and native robot-to-other-raw contact; reject the orientation's 180° false convergence rather than calling it success. Stop only the failed path, retain its failure, and continue the remaining fixed paths. No physical arm path is executed. These checks do not validate a timed path, tracking error, carry, perception, other processes or source-height grasp quality.

The queue-only helper has a 300-second internal wall budget checked between bounded operations; it preserves partial output if this limit or an integrity check fails. Fresh output is required. Root must retain official succeeded/0 status before interpreting the completed report. Physical validation of any selected common repair remains a separate task.

Run inside the shared queue:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement\Batch 01\Raw Pickup Geometry\raw_pickup_geometry.py' --output 'Long-Horizon Adaptive Robotics Expirement\Evidence\diagnostics\raw-pickup-geometry-001'
```
