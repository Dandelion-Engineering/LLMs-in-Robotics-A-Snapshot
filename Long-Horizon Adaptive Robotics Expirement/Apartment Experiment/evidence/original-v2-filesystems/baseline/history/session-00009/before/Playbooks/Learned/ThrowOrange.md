# Calibrated orange-object throw

## Identity

- Type: learned; version 1; apartment Cartesian-arm robot.
- Source: [session 001](../../SessionReports/2026-10-07-session-001.md), 2026-10-07.
- Status: validated twice per timing setting from one stationary base location; generalization untested.

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
python3 Programs/Learned/throw_orange.py --duration-scale 0.92
```

The optional duration scale multiplies both swing durations. The default 1.0 also succeeded twice. The tested values are 1.0 and 0.92; other accepted values are experimental, not validated.

## Procedure

The program checks task, work time, active action, and grasp feedback. It sets holding width 0.025 m, moves to (0.32, 0, 0.85) in one second, waits 0.5 seconds, and checks bilateral contact. It then executes:

| End x | End y | End z | End width | Duration before scaling |
|---|---|---|---|---|
| 0.63 | 0 | 1.08 | 0.025 | 0.22 s |
| 1.00 | 0 | 1.35 | 0.15 | 0.24 s |

It waits for fresh landing feedback, prints it, and retracts the empty arm to (0.36, 0, 1.16). Completion means a released, observed landing; success requires `throw_feedback.inside_bin=true`, not program exit status or request acceptance. Inspect a fresh image after execution.

## Acquisition notes

Use the default PositionGrasp procedure and current depth, correcting visible surface points to the estimated sphere center. In session 001, after settling at an approximately southward heading, center (0.628, -0.084, 0.919) was repeatable after reset. Approach above at z=1.16 with width 0.15, descend, close to requested width 0.025, then lift to z=1.16. Confirm both contacts and secure lift before retracting or turning. These coordinates are tied to that base pose and must not be reused blindly.

## Evidence

Session 001 recorded four inside-bin throws:

- Scale 1.0: forward/left displacement (-0.149, +0.039) m and (-0.145, +0.037) m.
- Scale 0.92: (-0.033, -0.005) m and (-0.035, -0.004) m.
- The executable was used successfully for the latter three throws.

## Limitations and failure modes

- Only this sphere, bin, relative distance, pitch, and robot configuration were tested. The program cannot perceive its own alignment.
- A faster horizontal candidate using width 0.055 was associated with far-short landing feedback. The landing timestamp preceded the command's completion; freshness relative to command start was not established. Release timing and loss mechanism were not isolated.
- During a separate preparation the object was lost after a prolonged low hold and a subsequent lift. Do not linger at the low swing start; loss timing/cause remains uncertain.
- `secure_lift_confirmed` became false when the held sphere was lowered below its initial support height, despite bilateral contact. A prior high confirmed lift plus current contact is used for the low swing start; do not infer a secure grasp from closure alone.
- A completed request can precede settled motion. Fresh observation and feedback remain necessary.
- On a warning, stop new trials and follow the deployment docking rule. On an error, inspect live status before further physical actions; an exception does not stop an already active primitive.

## Implementation

[Programs/Learned/throw_orange.py](../../Programs/Learned/throw_orange.py); uses only public robot-client primitives. It does not navigate, acquire, reset, or dock.
