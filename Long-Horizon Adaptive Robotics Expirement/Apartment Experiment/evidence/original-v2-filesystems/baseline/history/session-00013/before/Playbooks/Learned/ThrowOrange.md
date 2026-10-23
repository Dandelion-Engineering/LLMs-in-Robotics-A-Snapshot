# Calibrated orange-object throw

## Identity

- Type: learned; version 2; apartment Cartesian-arm robot.
- Sources: [session 001](../../SessionReports/2026-10-07-session-001.md) and [session 010](../../SessionReports/2026-10-07-session-010.md), 2026-10-07.
- Status: nine inside-bin throws across two sessions at nearly the same stationary-base geometry. Four timing settings have succeeded; other distances and directions remain untested.

## Purpose and scope

Throw the orange practice sphere into the living-room blue bin using ordinary arm and gripper primitives. This provides the release motion only; acquisition, visual aiming, navigation, and reset remain the agent's responsibility.

## Preconditions

- Current assignment is throwing practice; no battery warning; at least ten seconds of work time remain.
- Current RGB-D observation shows an unobstructed release and flight path.
- Base stationary, aimed at the bin center, approximately 1.8 m from it. In the validated setup the bin center was approximately x=1.7, y=-0.65 m before a -0.36 rad base turn. These are perception estimates, not surveyed coordinates.
- Orange sphere has confirmed bilateral contact and secure lift. Measured opening was about 0.089 m. Requested holding width 0.025 m gave effort about 19.17.
- Hold the object at x=0.36, y=0, z=1.16 m, pitch=0 before invocation. Reconcile the current object, wrist, and surroundings visually. Allow base turns to settle before aiming.
- No person or unrelated object lies in the motion or flight path.

## Inputs and invocation

Run from the persistent workspace:

```sh
python3 Programs/Learned/throw_orange.py --duration-scale 0.88
```

The optional duration scale multiplies both swing durations. Scale 0.88 gave the closest repeated landings in session 010, about 1.3 cm from center. The default remains 1.0, which also succeeded twice. Tested values are 1.0, 0.92, 0.90, and 0.88; other accepted values are experimental. Small sample counts and nearly identical geometry do not establish a general optimum or reliability rate.

## Procedure

The program checks task, work time, active action, and grasp feedback. It sets holding width 0.025 m, moves to (0.32, 0, 0.85) in one second, waits 0.5 seconds, and checks bilateral contact. It then executes:

| End x | End y | End z | End width | Duration before scaling |
|---|---|---|---|---|
| 0.63 | 0 | 1.08 | 0.025 | 0.22 s |
| 1.00 | 0 | 1.35 | 0.15 | 0.24 s |

It waits for fresh landing feedback, prints it, and retracts the empty arm to (0.36, 0, 1.16). Completion means a released, observed landing; success requires `throw_feedback.inside_bin=true`, not program exit status or request acceptance. Inspect a fresh image after execution.

## Acquisition notes

Use the default PositionGrasp procedure and current depth, correcting visible surface points to the estimated sphere center. In session 001, after settling at an approximately southward heading, center (0.628, -0.084, 0.919) was repeatable after reset. Approach above at z=1.16 with width 0.15, descend, close to requested width 0.025, then lift to z=1.16. Confirm both contacts and secure lift before retracting or turning. These coordinates are tied to that base pose and must not be reused blindly.

Session 010 reapproached from the kitchen and reconciled the setup at odometry about (0.103, 0.024), heading 3pi/2 for acquisition. Five fresh sphere projections at pixel (275,204) gave visible surfaces x=0.583–0.585, y about -0.098, z=0.947. Estimated center (0.623,-0.103,0.919) supported five confirmed acquisitions. The first used default positioning; subsequent trials used inspected arm approaches, with the final three raising the retracted arm before extending above the pedestal and descending. Each closure/lift was checked separately. Retract to (0.36,0,1.16) before turning +1.2108 to heading about -0.360 for the visually checked throw. These are pose-specific examples, not autonomous acquisition or navigation.

## Evidence

Session 001 recorded four inside-bin throws:

- Scale 1.0: forward/left displacement (-0.149, +0.039) m and (-0.145, +0.037) m.
- Scale 0.92: (-0.033, -0.005) m and (-0.035, -0.004) m.
- The executable was used successfully for the latter three throws.

Session 010 used the unchanged executable for five more fresh, confirmed inside-bin landings:

| Duration scale | Forward displacement m | Left displacement m | Landing simulation time |
|---|---:|---:|---:|
| 0.92 | -0.026 | -0.005 | 6795.460 |
| 0.90 | -0.017 | -0.008 | 6862.044 |
| 0.90 | -0.010 | -0.010 | 6926.816 |
| 0.88 | -0.004 | -0.012 | 6985.092 |
| 0.88 | -0.003 | -0.012 | 7043.004 |

Signed displacement uses the public target-bin frame. All trials started with confirmed bilateral contact and secure lift, then fresh visual alignment. The final object was preserved without another reset. The bin front concealed the landed sphere in post-throw head images; fresh landing feedback established containment. Generic `task_success` remained false for practice and was not used to judge these throws.

## Limitations and failure modes

- Only this sphere, bin, relative distance, pitch, and robot configuration were tested. The program cannot perceive its own alignment.
- A faster horizontal candidate using width 0.055 was associated with far-short landing feedback. The landing timestamp preceded the command's completion; freshness relative to command start was not established. Release timing and loss mechanism were not isolated.
- During a separate preparation the object was lost after a prolonged low hold and a subsequent lift. Do not linger at the low swing start; loss timing/cause remains uncertain.
- `secure_lift_confirmed` became false when the held sphere was lowered below its initial support height, despite bilateral contact. A prior high confirmed lift plus current contact is used for the low swing start; do not infer a secure grasp from closure alone.
- A completed request can precede settled motion. Fresh observation and feedback remain necessary.
- On a warning, stop new trials and follow the deployment docking rule. On an error, inspect live status before further physical actions; an exception does not stop an already active primitive.

## Implementation

[Programs/Learned/throw_orange.py](../../Programs/Learned/throw_orange.py); uses only public robot-client primitives. It does not navigate, acquire, reset, or dock.
