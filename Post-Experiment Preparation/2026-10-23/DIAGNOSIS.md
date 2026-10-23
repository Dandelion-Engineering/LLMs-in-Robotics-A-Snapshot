# Why the arm can look disconnected

Post-experiment inspection, October 23, 2026. Scope: the completed apartment-v4 Baseline and accepted checkpoint-5 Maps continuation preserved through Development Session 74. No historical model, viewer, run, checkpoint, result or evaluation rule was edited; no experiment was rerun.

**The evidence supports an incompletely represented Cartesian mechanism. The arm is attached to the base through joints in the simulator, but several moving blocks have no visible or collidable structure connecting them. This is a physical-model limitation as well as a misleading appearance.** It is not evidence that the arm became an independently flying rigid body.

## What the model actually contains

The nesting in [scene.py](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/scene.py), lines 126–165, is:

`base → arm_lift (vertical slide) → arm_reach (forward slide) → arm_lateral (sideways slide) → wrist (pitch hinge) → two sliding fingers`.

Only the task objects have free joints. The arm bodies remain descendants of the base. These joints constrain relative motion without requiring a solid rail, bearing or link between their visible shapes. The source explicitly describes a “mobile Cartesian arm”; the historical [apparatus contract](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/COMPARISON.md) also identifies a Cartesian arm and idealized planar base. **The Cartesian abstraction is documented; a deliberate decision to omit these connectors is not documented.** I would describe the omission, without inventing its author's intent.

The lift carriage is a small box. The reach body's box translates with the reach joint; it does not stretch back toward the carriage. There is no telescoping geometry between them. Likewise, the lateral slide has no spanning rail. Even with overlapping forward extents, the lift and reach boxes have a **5 cm vertical separation**: their centers differ by .15 m while their vertical half sizes total .10 m. A separate small gap can occur between the lateral block and palm. The fixed upright is attached to the base, rather than serving as a modeled rail enclosing the lift motion.

The same geoms supply collision shapes. There is no separate hidden collision mesh or invisible supporting link in this MJCF. The virtual joints supply the connection, while the absent structures supply neither pixels nor contacts.

## Saved states that reproduce the appearance

These are new native MuJoCo renders of **original recorded samples**, not original screen recordings. Only apartment wall group 1 is hidden for visibility; robot geometry and recorded state are unchanged. Reconstruction sets recorded `qpos`/`qvel` and calls `mj_forward`; it never advances dynamics. Exact coordinates, source hashes, sample indices and analytical checks are in [geometry-inspection.json](geometry-inspection.json).

| Original run / session | Recorded simulation time | Replay locator | Measured gap between lift and reach boxes |
|---|---:|---|---:|
| Baseline / 1 | 524.288 s | `states-000130.npz`, sample 110 | .432300 m |
| Maps / 1, accepted original prefix | 487.648 s | `states-000121.npz`, sample 85 | .432674 m |

[Baseline reconstructed frame](baseline-native-reconstruction.png) · [Maps reconstructed frame](maps-native-reconstruction.png). The gap is visible in native MuJoCo rendering, independently of the browser's mesh renderer. The selected poses illustrate the issue; Randy did not supply a timestamp identifying his particular observation.

For both samples, independent calculations from base pose and the lift/reach/lateral/pitch/finger coordinates agree with all six arm-body positions to better than `1e-10 m`. The fitted gaps follow the declared slide transforms; they do not require a broken constraint or detached body. This checks two representative states, not every physics step in either history.

## Replay and viewer checks

The inspected copies of `scene.py`, `world.py`, `recording.py`, `controller.py`, `viewer.py` and `viewer.html` match the six corresponding hashes in **both runs' original source identities**. This avoids interpreting either history with later active-project code. [Input identities](inputs.json) and [geometry input identities](geometry-inputs.json) preserve the bindings.

The relevant paths are:

- [recording.py](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/recording.py), `geoms` and `Replay.frame`: replay loads original sampled positions/velocities, calls `mj_forward`, and exports `geom_xpos` and `geom_xmat`. It authenticates each consumed replay chunk. It does not interpolate bodies independently or rerun task dynamics.
- [controller.py](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/controller.py), lines 112–116: the live observer uses the same `geoms` exporter.
- [viewer.html](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/viewer.html), `vertices` and `draw`: each local vertex receives the supplied rotation and world position once. Robot boxes use their supplied half sizes. Camera orbit/following changes the projection, not arm attachment. The optional wall cut affects group 1, while robot geoms are group 0.

The source review and native reconstruction do **not** support a replay-specific transform error as the necessary explanation. I did not reopen the original live viewer or claim exhaustive browser/driver QA. Its approximate capsule meshes, wall cutting, perspective and occlusion can alter appearance, but cannot supply the absent arm structures. The exact original screen-viewing episode remains unidentified.

## What this changes about interpretation

**Visible behavior and physical realism:** describe this as an abstract Cartesian manipulator in a physics simulation, not a mechanically complete robot design. Missing links can move through spaces where real rails, cable runs or supports would occupy volume. Their mass/inertia and support mechanics are absent too. In addition, robot geoms use `contype=2, conaffinity=1`; this mask does not enable robot-to-robot self-collisions. The arm bodies have gravity compensation, and the base is constrained to planar motion. Real hardware feasibility, swept-volume clearance, structural loads, energy use, robustness and transfer are therefore unestablished. A cosmetic connector added afterward would not retroactively validate those properties.

Contacts for the **existing** fingers, objects and environment are still simulated. [world.py](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/world.py), `_mechanics`, detects bilateral finger contact and actual object height; task checks use physical object state. That makes the retained grasps and failures observations of this simplified apparatus. It does not make the omitted structure harmless. Nor does an arm command's `completed` receipt guarantee target attainment: `step` ends arm actions on trajectory time, and its explicit attainment/error check is for base actions. Baseline session 6 documents delayed arm motion after a constrained command; see [that report](evidence/baseline-session-006.md).

**Completed experiment outcomes:** retain their accepted status under the frozen model and rules, together with their existing audit caveats. They are not a certification of realistic whole-arm mechanics. This inspection neither rescored outcomes nor estimated how omitted structures would change a task; that would require a newly authorized model revision and experiment. Timed throwing advancement remains practice-window completion, not mastery.

**Filesystem persistence and cross-session continuity:** the geometric omission does not erase independently recorded file writes, checkpoint bytes, later full-file reads or program invocations. [Nine byte-matched links](reuse-links.json) directly document those events. Their interpretation remains “this saved material survived and was later read/used in this apparatus.” They do not demonstrate that memory caused better performance, or that the same manipulation would work on real hardware.

## Limits and retained diagnostic failures

Both historical roots were located. Baseline now resides under `D:/Dandelion Engineering/LLMs in Robotics/Dandelion-Apartment-Experiment/official/apartment-v4/baseline`; its embedded old `D:/Dandelion-Apartment-Experiment/...` locators were preserved. Maps remains at the recorded C: recovered-run root. Consumed sources, event/journal/clock chains, selected checkpoint material and images were authenticated; this is not a repeat of the complete Session 57/74 endpoint audits.

The first queued inspections were interrupted when their sandbox workers disappeared. A subsequent reader failed because it looked for the image sequence inside `packet` rather than its parent payload. Those attempts are preserved beside the successful queue receipts. The first native camera was wall-occluded; its two images are retained as `*-first-camera-occluded.png`. Hiding only the wall display group exposed the original robot. These are inspection failures, not scientific reruns.

See [verification.json](verification.json) for preservation checks and [README.md](README.md) for access and reproduction details.
