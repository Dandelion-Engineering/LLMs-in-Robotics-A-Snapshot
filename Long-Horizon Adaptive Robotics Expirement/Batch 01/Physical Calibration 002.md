# Physical calibration 002

Queue job `20260923T052756618789Z-973807c8` officially succeeded with exit 0; all source hashes stayed unchanged. All seven probes passed their separate actual-host timing checks. Queue and timing success do not establish the failed physical predicates. Exact results, source bundle and trajectories remain in [physical-calibration-002](../Evidence/calibration/physical-calibration-002/summary.json).

| Probe | Recorded result | Evidence and implication |
|---|---|---|
| Insert exchange | Failed | B installation passed every containment/release/settling predicate at simulation 30.214 s. On the later A installation, A tipped during pickup from its home and remained there; final fixture was empty. The check timed out. |
| Held recovery to parking2 | Failed | A1 was picked up, authority was revoked and physics continued; subsequent IK did not converge for pad-above target `(0.20,-0.09,0.181)`. No recovery trajectory was dispatched. |
| Held recovery to parking1 | Failed | Same class of planner failure at `(0.27,0.05,0.181)`. This is not a measured successful recovery envelope. |
| Arm interfaces | Infrastructure failure | First check raised a NumPy Boolean JSON serialization error. Its original partial measurements are retained; no adapter pass is inferred. |
| Effort equivalence | Passed | Four simulated seconds of the declared paired native/inverse servo test; same narrow unloaded scope as attempt 001. |
| Raw cameras | Passed | All three actual native RGB/float32-depth captures traversed normal IPC and decoded to matching bytes inside the isolated stdlib fixture. No image-understanding claim. |
| Static sensors | Collection passed | All IDs were visible in all three captures at each 3/6/10-part development scene. Across 75 observed centers, none exceeded 4 mm; maximum error was 1.267882 mm. Initial static scenes do not establish accuracy during occlusion/motion. |

The maximum observed timing lag over the seven probes was 0.008150 s. No timing tolerance, geometry, physical success predicate, or decoded payload cap was relaxed. After the receipt, the arm fixture's vector conversion was corrected to native Python floats, so its computed Boolean/error fields serialize without changing the measurement. The 49 bounded helper tests passed. A new adapter-only attempt is declared separately; insert pickup and recovery IK remain under diagnosis before further architecture runs.

## Adapter-only follow-up 003

The [declared follow-up](physical-calibration-plan-003.json) officially succeeded with exit 0 in queue job `20260923T053325905477Z-02905f95`, with unchanged source hashes. All five [actual arm-interface checks](../Evidence/calibration/physical-calibration-003/adapters/result.json) passed their unchanged thresholds. Joint position/velocity/timestamped-trajectory local displacement errors were 0.0000222812, 0.0000210476 and 0.0000574207 rad. Cartesian endpoint error was 0.00431323 m; the short bounded-effort hold's joint error was 0.00621609 rad. Native absolute position error remains separately reported and exceeds 0.005 rad in these gravity-loaded poses; this is not an absolute accuracy claim. Actual-host timing passed all five complete windows, maximum lag 0.001886 s. The earlier serialization failure remains retained.
