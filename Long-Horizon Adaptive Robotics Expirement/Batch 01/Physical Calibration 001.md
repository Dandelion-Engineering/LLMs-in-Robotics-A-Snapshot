# First shared physical calibration

Seven probes ran under [plan 001](physical-calibration-plan-001.json), queue job `20260923T050529437896Z-06e48539`, officially succeeded/exit 0 at 2026-09-23 05:06:10 UTC. [The receipt](../Evidence/queue-receipts/20260923T050529437896Z-06e48539.json), [summary](../Evidence/calibration/physical-calibration-001/summary.json), source bundle and raw files are retained. Source hashes were unchanged throughout. Normal queue completion does not mean the physical predicates passed.

| Probe | Result | Actual timing | Finding |
|---|---|---|---|
| Insert B then A exchange | Failed after the first return leg | 13 windows passed; maximum lag 8.676 ms | Insert A physically reached home, but the calibration driver omitted the supervisor's fresh-capture setup-resume call. No B insertion was attempted. |
| Held recovery to parking2 | Failed before pickup | No complete one-second window; gate therefore false | All initial part marks were unknown under the first occlusion-aware detector. No recovery feasibility was tested. |
| Held recovery to parking1 | Failed before pickup | No complete one-second window; gate therefore false | Same detector issue in a separate fresh world. |
| Arm interfaces | Failed at joint position check | One timing window passed | Fixture assumed zero native-servo gravity deflection; normal completion also replaced the command target with measured position and added another deflection. |
| Effort equivalence | Passed | Four timing windows passed | 2,001 native physics steps, 4.002 simulation seconds: identical all-body positions/velocities and actuator forces, maximum control difference 8.67e-19. Only the declared matched unloaded 500 Hz inverse-servo comparison is established. |
| Raw cameras | Failed at wrist payload | Two timing windows passed | Lossless float32 wrist depth NPZ was 825,230 bytes; with RGB/Base64 it exceeded the unchanged line cap. Earlier cameras decoded; this is not a passed complete three-camera round trip. |
| Static sensors | Measurement collection passed | Two timing windows passed | Nine captures across three horizons completed. Measurement collection does not establish perception readiness. |

The insert's final protected position was approximately `(0.187348, -0.247849, 0.007892)` m, with its full bounds inside its home and no gripper contact. Public captures 131–133 also observed it at `insert_home_A` with the fixture empty. The driver called `poll_sense()` but never `resume_setup_if_fresh()`, unlike `experiment.py`. Adding that call after overhead capture preserves every public witness check; it does not declare the full exchange successful.

The marker crop's five columns included neighboring tag/body pixels. The corrected detector uses the marker's central three columns, retains the 90% depth-consistency requirement, and requires two adjacent supported dark or white columns without opposite-class pixels. Exact retained raw, processed and robot-occluded crops remain regression fixtures. No protected process state supplies the classification.

For joint position, initial native hold already differed from measured joint 4 by 0.006435 rad. Building every target from measured position and resetting control to measured position again at interval completion compounded this offset. Normal position-family completion now preserves its final bounded native target; effort expiry and cancellation retain their stop behavior. The revised probe explicitly measures local physical displacement at the unchanged 0.005 rad tolerance and reports absolute setpoint error separately. The original trace still fails the revised displacement criterion (0.006309 rad); it is not retrospectively passed.

Static position errors were at most 1.268 mm for three parts and 1.785 mm for six parts. In the ten-part scene, B10 was missing in all three captures; six of 33 observed positions exceeded the 4 mm scalar, with maximum 11.229 mm. These findings remain unresolved at this record cut. Missing tags are not zero error, and a detector threshold cannot be justified by the collection script's passed status.

All failures require fresh attempts after their documented corrections. No development architecture result, held-out seed, scored readiness declaration or complete-task claim is created by this calibration.
