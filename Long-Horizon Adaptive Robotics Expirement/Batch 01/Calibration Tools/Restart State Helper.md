# Protected restart-state helper

`restart_state.py` is outside Runtime and is not integrated into the active pilot revision. Its synthetic tests do not establish a calibrated grip or recovery route. No physical run or queue job was launched for this implementation.

## Integration API

On the physics owner thread, immediately before revoking the old incarnation's authority:

```python
snapshot = capture_restart_state(
    cell,
    zones=ZONES,
    zone_half=zone_half,
    exposure=restart_exposure,
    source_hashes=verified_runtime_source_hashes,
    infrastructure={"status": "valid", "reasons": []},  # only when independently supported
)
assessment = classify_restart(snapshot, calibration=verified_prior_calibration)
# Emit BOTH to protected evaluator evidence before Cell.cancel / process kill.
# Never append either object to candidate observations, feedback or memory.
```

`infrastructure` is optional; omission records `unknown`. It is copied as separate evidence and does not determine the physical-admissibility result. The helper does not decide whether to cut, change a scenario, exclude a paired block, or label an experiment successful/invalid. The supervisor must preserve the configured opportunity and actual exposure separately.

The snapshot retains the existing independent evaluator's complete geometry and histories; expected body IDs; world and TCP-relative object poses; robot/finger positions, velocities, controls and effort; TCP position/rotation; exact registered-object and gripper contact rows; contact normals/frames, force/torque and active-constraint status; per-side finger loads and bilateral load-bearing IDs; supported-object evidence; active request, authority generation, lease, queued segment, planner/direct-planner generations and completion states; guard/clamp/cycle/inspection timers; capture age; scene XML hash; a physical-configuration hash; supplied source hashes; and its own canonical SHA256. Nonfinite capture values become explicit nulls with capture-error paths, so damaged evidence remains serializable.

The contact world-force transform follows MuJoCo's frame convention: the first local axis is the normal, and the force points from geom1 toward geom2. The helper records `frame.T @ force[:3]` as force on geom2, with the negative on geom1. Support additionally needs an active upward force at a lower contact with the world or another registered object. Mere proximity, hand contact, or an inactive constraint does not establish support. [MuJoCo computation documentation](https://mujoco.readthedocs.io/en/stable/computation/index.html), [contact-force API](https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html#mj-contactforce).

## Classifier behavior

`classify_restart(snapshot, *, calibration=None, policy=None)` returns a `predicates` list with `pass`, `fail`, or `unknown`, reasons and observed evidence. Required failures yield `inadmissible`; absent failures with any required unknown yield `unknown`; otherwise the state is `admissible` **within the supplied conditions and measured envelopes**. This is not a claim that recovery will succeed or that all other routes are impossible. `configured_phase_reached` is copied from the exposure even when the physical class is inadmissible.

The declared defaults reproduce the common workcell's rest/containment vocabulary: world XYZ envelope `[.05,-.55,-.003]` to `[.85,.55,.8]` m; unheld collision-bound top at most `.08` m; open jaw width at least `.065` m; nonempty carry width above `.005` m; rest linear/angular speed limits `.05` m/s and `.10` rad/s; active support upward force at least `.01` N; capture age at most `.35` s; contact proximity `.001` m and active contact penetration at most `.003` m. These constants are declared predicate thresholds, not new empirical calibration results. If they change, freeze that policy change before subsequent evidence is collected.

The classifier checks object identity/envelope, all unheld bodies' actual support and rest state, robot configuration, exact contact penetration, source/phase/current-action consistency, owned planner generations, lease state, device/timer state, camera age, finite pad capacity and full destination containment. Unknown device/timer combinations remain unknown, including an active otherwise eligible machine cycle; the present helper deliberately supplies no unmeasured machine-cycle survival rule.

For a carry cut, one exact registered workpiece must contact both gripping sides with positive active loads, measured closed jaws and the existing closing command. This necessary grip evidence still requires a matched measured grip envelope and a matched measured route envelope. An empty pad is only a resource predicate. Other objects intersecting a calibrated route's clearance corridors invalidate that route match even when the target pad is empty. The helper does not perform a new whole-arm collision search. Before-grasp and after-release classes require actually open, empty jaws and a supported slow target part; released classes additionally require full recorded destination containment.

Missing source identity, calibration, payload-relative pose, stale planning ownership, stale imagery, unsupported phase/fallback or incomplete snapshot fields remain explicit unknowns. An unrelated flying body, unilateral/empty/multiple payload contact, closed jaws after a claimed release, occupied pad, moving or boundary-straddling released part cannot silently become admissible. Candidate-caused difficulty is not assigned an infrastructure cause. Do not redraw the seed or discard a hard paired case because the gate is unknown/inadmissible.

## Calibration inputs

The top-level `calibration` object accepts `grip` and `routes` (a list). Each entry contains:

```text
evidence_refs: [{kind: "prior_physical_calibration", artifact_id: <operator ID>,
                sha256: <64 hex characters>, bytes_verified_by_operator: true}]
source_hashes: <nonempty subset of exact matching snapshot source identities>
physical_configuration_sha256: <exact matching snapshot physical configuration>
envelope_basis: "measured_before_this_intervention"
envelope: <the measured numerical scope below>
```

The supervisor verifies referenced artifact bytes before supplying these inputs. The classifier validates explicit provenance syntax and compatibility but intentionally performs no filesystem reads. An arbitrary `final_success` field is ignored; an episode-outcome reference cannot count as prior calibration. A physical-config mismatch remains unknown. The configuration hash includes the number/geometry/masses/friction/contact parameters of movable bodies, native actuator parameters, joint ranges, timestep, integrator, gravity and static zone geometry; a three-part calibration will not automatically authorize a ten-part configuration.

The **grip envelope** requires `kind`, `family`, `jaw_width_m:[min,max]`, `relative_position_m:{min:[x,y,z],max:[x,y,z]}`, `relative_rotation` (3×3 proper reference rotation in TCP coordinates), `maximum_rotation_error_rad`, `finger_normal_force_N:[min,max]` applied separately to each side's summed normal force, `maximum_linear_speed_m_s`, `maximum_angular_speed_rad_s`, and `minimum_payload_bottom_z_m`. All are compared with this capture. These fields describe the measured envelope; they must not be filled by copying the permissive synthetic test fixture.

Each **route envelope** requires `operation:"recover_held"`, `destination`, exact `destination_region_m`, `tcp_start_m` bounds, seven `joint_start_ranges_rad`, seven `joint_velocity_ranges_rad_s`, `maximum_abs_finger_velocity_m_s`, `payload_kind`, `payload_family`, and one or more `clearance_corridors_m` boxes already supported by the prior physical calibration. Each non-payload registered body's complete collision bounds must stay clear of every corridor. The destination must be empty and its region must match exactly. The classifier cannot establish that chosen corridor boxes conservatively cover a whole arm/payload sweep; that is a calibration/integration duty. It only checks the explicitly supplied scope.

The current physical driver did not yet capture this richer helper at its carry interruption. After the active source hold ends, integrate the same helper into the calibration driver's cut event and supervisor's restart event so their measured states can be compared. Do not infer a bilateral grip or route envelope retroactively from a final parking success alone.

## Verification

`test_restart_state.py` has 23 synthetic checks, including a fake MuJoCo-shaped contact adapter without creating a Cell or advancing physics, bilateral versus inactive contacts, both force sign conventions, rotated TCP-relative poses, and counterexamples for false admissibility. Runtime remains unchanged. Actual physical capture and measured envelope coverage remain prerequisites.
