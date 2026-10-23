# Carry hold diagnosis: physical calibration 004

The recorded failure is real under the unchanged predicate: A1 remained in gripper contact, but its center fell below the required 75 mm height during the one-second interruption. The evidence supports both arm deflection and small movement within the grasp; it does not establish that the part was dropped or that arm sag alone explains the result. All independent final parking placement predicates passed. This note does not revise the original failed result.

Evidence is the completed `physical-calibration-004/held-recovery` probe. Root verified official receipt `20260923T062117342781Z-c53110e6`, succeeded with exit status 0. This inspection reads retained files only; it performs no simulation or counterfactual numerical replay.

| Measurement | Cut event 146, 7.412 s | After event 168, 8.412 s |
|---|---:|---:|
| A1 center height | 75.1491 mm | 69.9578 mm |
| TCP height | 71.7359 mm | 68.7948 mm |
| A1 lowest bound above table | 56.9729 mm | 51.0795 mm |
| Left finger normal force | 1.05214 N | 1.07520 N |
| Right finger normal force | 1.03988 N | 1.01882 N |
| Jaw width | 41.9127 mm | 41.9249 mm |
| A1 vertical velocity | +100.095 mm/s | -0.3866 mm/s |
| Bilateral force-bearing contacts | true | true |
| Nonhand contact count / upward support force | 0 / 0 N | 0 / 0 N |

The cut occurred during phase 4 while the part was rising. Its initial height exceeded the threshold by only 0.1491 mm. During absence, the TCP fell 2.9410 mm and A1 fell 5.1913 mm. A1's position relative to the TCP changed from `(0.8987, 0.0362, -3.4212)` mm to `(4.0471, -0.0088, -1.2351)` mm. Rotation also changed, so these relative coordinates should not be read as an exact world-vertical slip decomposition. They do establish that the grasp was not perfectly rigid.

All ten retained protected snapshots, at 100 ms spacing during absence, report A1 gripper contact. Both endpoint captures show bilateral load and no support contact. These sampled observations support continued holding; they cannot prove there was no brief loss/recontact between samples. After one second, joint 7 still had velocity -0.1121 rad/s, so the robot was not entirely stationary at that endpoint even though the object’s translational speed was low.

## Source mechanism and minimum correction to test

Archived `Runtime/cell.py` has SHA-256 `6da02d125fb049fc8699599d9783a99d6b08191e78c18117f5a008d241ace463`. Its `Cell.cancel`, lines 593–606, clears future motion and unconditionally replaces the current native arm command with measured q:

```python
self.data.ctrl[:7] = self.data.qpos[:7]
```

At this cut, that changes one joint’s command by as much as 0.0477088 rad. All 100 retained trajectory samples during the one-second absence hold exactly that cut-time measured q; gripper command stays zero. The joint servo must then establish a fresh loaded equilibrium. The resulting pose shift is consistent with cancellation adding load deflection to a moving grasp. The observations alone do not identify how much came from gravity, motion arrest, finger compliance, or contact slip.

For ordinary command revocation during native position, trajectory, Cartesian, or bounded velocity control, test freezing the **last emitted, valid native position target** while clearing queued/future motion and preserving the gripper command. Do not advance the old trajectory or integrate velocity after revocation. This retains the instantaneous setpoint that was supporting the load; it may still allow tracking lag and momentum to settle and is not an immediate zero-motion or protective-stop guarantee. Keep explicit fault/workspace protective behavior separate where it requires a different hold.

Direct effort control is different. `actuation.py` encodes requested effort through a state-dependent inverse of the existing affine position servo. Its current `ctrl` can be an intentional torque-producing position offset. Retaining that value on effort cancellation would retain a stale effort bias. Preserve the measured-q fallback for active effort commands, identifying the prior command mode **before** clearing `self.direct_command`. A gravity-compensated stop, if later desired, needs its own defined controller and physical validation rather than relabeling this fallback.

The useful next check is the same physical held-recovery probe after this common cancellation change, with the 75 mm after-absence threshold, all final placement predicates, and one-second duration unchanged. No result here supports relaxing those requirements.

## Retained identities

- Cut event 146 payload SHA-256: `0884a9becd659c0ecdf4bfacaf496ee03bfccad26f581364ea019ae669a79450`.
- After-absence event 168 payload SHA-256: `75f4c0fca592f738d50d669e474f31fa5d8b1fbf51c903a4925cd1752665b6ee`.
- `events.jsonl`: `c23ae4b9679a4bf3d2a1de3db7c6b887a030e67bb457fc284bd28fa29addfd2f`.
- `trajectory.jsonl`: `2b63cc80d1c68af26b4b82f4a5791da47d844f9bdba23deb9048eab59ecb5c94`.
- `result.json`: `31c7a113ffb707e3822f5a232d73509533c357a22c286544730b4590d9526981`.
