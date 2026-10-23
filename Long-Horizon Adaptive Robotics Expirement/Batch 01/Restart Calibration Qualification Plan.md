# Restart calibration qualification before concealed evaluation

Status: proposed qualification and protected schema only. No new measurements, calibrated ranges, readiness pass, runtime changes or evaluation seeds are created by this document. The current physical probes remain development evidence. Their exact outcomes and limits must be read before using them.

Prefirst-screen execution decision, 2026-09-23 07:13 UTC: the fixed 40-trial fixture will execute the 28 construction trials first, then the original 12 reserved independent-world trials only after a provisional rule is saved and hash-bound. Both destinations retain every declared trial. Parking1 is the primary destination because the unchanged common candidate recovery adapter tries parking1 before parking2; this choice precedes screen outcomes and does not alter candidate control. Parking2 remains a separately measured secondary destination, not an outcome-selected replacement.

The fixture will retain grip checks through actual admitted recovery, including the sensing wait after the five-second hold. It will accumulate conservative geometry AABBs at every discrete physics tick and retain interval unions at the ordinary trace cadence. This can measure discrete sampling undercoverage; it is not a formal continuous collision proof. Any provisional state-cell or route transfer beyond measured tuples must be explicit, frozen before independent validation, and remain separate from the observed data. Missing support stays unknown. See [Recovery Qualification](Recovery%20Qualification/README.md) for the versioned execution plan and eventual exact evidence.

## Decision and authority

Keep the exact physical-configuration hash for provenance. Add an explicit, separately versioned **qualified physical class** matching mode for prospective evaluation. A class match says that the actual scene obeys a frozen specification supported by prior development tests; it does not say that this concealed instance was tested, that every value between tested points was measured, or that recovery is guaranteed. Do not make the existing exact-hash comparison silently ignore fields.

The original Experiment Design/Evaluation.md requires calibration before candidate selection, then concealed layout, mass/friction and interruption samples after freeze. It also limits the recovery denominator to exercised, admissible events. Requiring a physical rehearsal on every concealed world would defeat that order. The achievable prerequisite is measured development support for a declared domain and recovery procedure, with fixed prospective checks on each actual exposure. Generalization across previously unseen values remains part of the experiment.

The present Runtime/restart_state.py `_calibration` requires the entire `physical_configuration_sha256` to match. Its snapshot hash includes complete mass, inertia, friction and geometry arrays, actuator parameters, joints, timestep, integrator, gravity and zones. Population and independently sampled properties change it. A three-part seed-0 reference therefore cannot authorize a different concealed world. The hash is also not a complete substitute for source/model identity: retain scene XML, compiled descriptor and dependency hashes rather than assuming the current selected field list captures every relevant physics setting.

## Separate what is fixed, variable and measured

The reviewed `cell.build_scene` samples the main collision geom mass in `[0.09, 0.11)` kg and its sliding-friction coefficient in `[1.1, 1.3)`. The tag and process mark each add `0.0001` kg; the compiled body mass and inertia must be recorded, not equated to the main geom mass. This sampling also applies to inserts. The workpiece collision half-sizes are `[0.021, 0.021, 0.018]` m; inserts have a separate shape. Layout jitter is independently sampled within ±0.003 m in each raw-stock planar coordinate. These are source-derived generator specifications, **not measured successful operating ranges**. Publish their meaning before freeze; do not expose any realized evaluation values or seeds to candidates.

Use three distinct records:

1. **Declared generator domain:** allowed parameter distributions, bounds, populations and template rules, with exact generator source identity. Membership establishes only that an instance belongs to the intended arena.
2. **Measured calibration evidence:** actual parameter points, cut snapshots, absence durations, routes, failures and outcomes from named development probes. Preserve the precise mass/inertia/contact settings; do not replace points with an enclosing box labeled measured.
3. **Prospective transfer qualification:** an explicit engineering assumption, accepted before freeze, that the shared procedure may be applied to unseen in-domain instances when all unchanged state predicates also pass. State the finite evidence supporting it and its untested combinations. An accepted empirical transfer assumption is not a proof over a continuous parameter interval.

A calibration point for a part does not qualify inserts as carried payloads. A successful parking2 recovery does not qualify parking1, inspection or quarantine. Identical part dimensions do not erase the two families' distinct visual identities. Source/layout variation affecting perception still needs the shared sensor calibration; protected geometry cannot become a substitute observation.

## Minimal sequential physical qualification

First inspect the already planned probes. A single valid carry and placement supplies one measured state and trajectory. Static sensor checks at 3/6/10 parts supply visibility/error evidence, not recovery evidence at those populations. A transport receipt or final containment alone cannot supply the missing grip, absence-survival or swept-route measurements.

Qualify one destination first, preferably the moved parking2 if its actual probe passes. A second destination gets its own evidence. A single qualified route is enough to demonstrate an opportunity in matching states; it is not enough to classify every possible occupied-buffer state as admissible. Apply shared development effort and any extensions symmetrically, and record calibration episodes separately from entrant task-performance episodes.

The following is a bounded **initial development screen per destination**, not a statistical certification or a claim that a fixed number of trials guarantees coverage:

| Work | Actual trajectories | Purpose |
|---|---:|---|
| Main-geom mass/friction corners `(0.09,1.1)`, `(0.09,1.3)`, `(0.11,1.1)`, `(0.11,1.3)` plus center `(0.10,1.2)`, both A/B payloads, ten-part population | 10 | Probe both ends and center without assuming monotonic grip behavior |
| Center setting, both families, three- and six-part populations | 4 | Exercise population/contact-solver and scene differences |
| Independent declared development worlds, one new world for each population and family combination | 6 | Check transfer away from the construction points after fixing the provisional rule |
| **Initial total per destination** | **20** | Finite development evidence only |

Boundary fixtures require a separately hashed development-only scene-construction option; the present seed-only driver cannot guarantee exact corners. Set parameters before constructing/settling the model, with retained XML and compiled values; use real image-derived pickup, contacts and motion. Do not search seeds until a desired result appears, move objects during the trial, or patch a scored model. The endpoint 0.11/1.3 is a conservative development boundary outside the generator's open upper endpoint. Non-payload property settings and layout choices must be explicit in the fixture manifest. They are not silently covered by payload-only sweeps. Independent development worlds sample the complete generator, including insert and non-payload values.

The six validation worlds are fixed development inputs selected without examining their outcomes and without drawing evaluation seeds. All attempts, including failed calibration construction, missed carry triggers and rejected recoveries, are retained. If failures show an important coupling, revise the common mechanism or split/narrow its qualification cells and repeat the relevant screen plus untouched development validation. Do not take a successful subset, widen a limit, or call an unscreened interval calibrated. Changing the evaluation generator domain would be a separate public prefreeze protocol revision, not a hidden consequence of this plan.

Distribute these development trajectories across the intended early/late carry and source-position conditions only if each resulting qualification cell retains actual supporting evidence. A broad min/max box assembled from unrelated successful traces does not demonstrate all combinations inside it. Record measured starts and conservative local cells, retain their joint/velocity/contact correlations, and leave starts outside supported cells unknown. Low-clearance A3 trajectories need their own measured support if they lie outside the initial cell. The same applies to other raw slots, processing-station pickup and tray pickup; the initial raw-pickup probe does not qualify all sources.

At each carry cut, retain the full rich snapshot before cancellation, then trace actual authority revocation, hold, physics during absence, fresh sensing, recovery and independent settled placement with open empty jaws. Record bilateral active finger forces, payload-relative pose, linear/angular motion, jaw and finger velocities, payload bottom clearance, joint state, timers, actual routes and all other objects. Measure both the intended carry ambiguity and the common guarded-hold behavior. The current public TCP threshold of 0.08 m identifies an opportunity only; it proves neither a payload nor payload-bottom clearance.

The existing one-second absence probe qualifies only that observed absence. Measure the real supervisor restart/reconciliation duration and qualify a declared duration bound that includes its operational allowance, or report longer absences unknown. A queued RPC restart can take longer than the authority-cut probe. Duration is an independent qualification coordinate; do not infer it from eventual recovery. Other cut families require their corresponding conventional development evidence and existing predicates; a carry screen does not establish active-cycle/inspection-timer survival.

For each usable route, derive a conservative whole-arm-and-payload swept region from retained trajectory geometry, with an explicit sampling/clearance error bound. Exact static geometry and actual other-object bounds must be checked against that coverage. A series of TCP boxes or an empty destination alone cannot establish whole-arm clearance. If the current classifier's coarse corridor boxes intersect an unrelated body despite a safe route, the result stays unknown/fail under the frozen rule until a separately validated representation is implemented; do not erase the obstruction check. No claim of formal continuous collision proof follows from sampled trajectory images.

## Proposed protected descriptor

The following schema sketch is not a ready calibration file. `null` qualification and evidence fields deliberately cannot pass. It belongs to the operator/evaluator only; no seed, realized mass/friction, privileged pose/contact, reference path or assessment is copied into candidate observations or memory.

```json
{
  "schema_version": "restart-physical-class-proposal-1",
  "match_mode": "qualified_class",
  "class_id": "to-be-frozen",
  "descriptor_sha256": null,
  "fixed_identity": {
    "required_source_hashes": {},
    "mujoco_build_sha256": null,
    "robot_assets_sha256": null,
    "static_geometry_sha256": null,
    "normalized_compiled_physics_sha256": null,
    "controller_and_recovery_semantics_sha256": null,
    "sensor_semantics_sha256": null,
    "predicate_policy_sha256": null
  },
  "declared_domain": {
    "basis": "generator specification; not an empirically measured interval",
    "generator_source_sha256": null,
    "allowed_part_counts": [3, 6, 10],
    "allowed_insert_count": 2,
    "main_geom_mass_kg": {"min": 0.09, "max": 0.11, "max_exclusive": true},
    "main_geom_sliding_friction": {"min": 1.1, "max": 1.3, "max_exclusive": true},
    "raw_xy_jitter_m": {"min": -0.003, "max": 0.003},
    "entity_template_hashes": {},
    "permitted_variation_paths_sha256": null
  },
  "qualification": {
    "status": "planned_unmeasured",
    "method": "finite development screen plus independent development validation",
    "measured_parameter_points": [],
    "failed_and_missing_attempt_refs": [],
    "validation_attempt_refs": [],
    "prospective_transfer_assumption": null,
    "untested_combinations": [],
    "maximum_qualified_absence_s": null,
    "accepted_before_release_freeze": false
  },
  "grip_and_route_cells": [],
  "evidence_refs": [],
  "frozen_at": null
}
```

The normalization must be an explicit whitelist with units and semantic object names, not "delete all mass/friction arrays." Pin every nonvarying relevant setting: robot/hand collision geometry and assets, transforms and joints, actuator gain/bias/transmission/control/force bounds, damping/armature, contact masks and contact-law parameters, solver/integration options, timestep/gravity, station/fixture walls, pads and zone regions, shared planning/recovery/cancel behavior. Validate all objects against the appropriate part/insert templates, with expected identity/population and compiled inertia derived by the frozen construction rule. Normalize only declared sampling paths and legal population expansion; reject any unexplained field difference. Keep full exact XML/model hashes alongside the normalized class identity.

Every snapshot's proposed `physical_class_observation` includes its exact configuration hash, descriptor hash, compiled invariant digest, actual population, per-object template and realized mass/inertia/friction values, and per-field domain-membership results. The whole snapshot stays protected. The current snapshot only keeps the aggregate hash for several physical fields; this richer observation requires a future implementation, not reconstruction from a hash.

Each measured cell retains existing `evidence_refs`, verified artifact hashes, source identities, `envelope_basis: measured_before_this_intervention`, and all present grip/route envelope fields. Add the contributing exact configuration/snapshot IDs, tested parameter points, source-region/phase scope, absence support and route-coverage method. Evidence must predate the scored release; artifact bytes are independently verified. A machine-readable `qualified_class` entry also names the frozen empirical-transfer rule. Preserve `exact_configuration` as a separate legacy mode. Never accept an omitted match mode as permission to use the broader one.

## Prospective assessment and denominators

Retain three-valued predicates. Under the proposed qualified-class mode, distinguish `fixed_class_identity`, `declared_parameter_domain`, `prior_qualification_evidence`, and the existing observed grip/route/state checks. A passed class/domain predicate is **compatibility**, not a measurement of recovery at that hidden parameter point. Output `evidence_basis: empirical_transfer` and `instance_previously_calibrated: false` when applicable; expose the transfer qualification's hash and scope in protected analysis. Never relabel these as exact-instance calibration.

The following remain necessary without relaxed thresholds: exactly one bilateral active workpiece grip; valid jaw/closing command; measured contact-force, relative-pose, velocity and payload-clearance scope; valid joint/finger/TCP route-start scope; current command ownership and safe device state; intact supported other objects; fresh permitted sensing; finite available capacity; exact destination containment region; and an unobstructed supported route. Missing, nonfinite or unmatched evidence is unknown; a contradictory physical predicate fails. A mass inside the public range, an empty pad, or a later successful recovery cannot override these results.

Before evaluation, freeze the descriptor, measured cells, transfer assumption, compatibility validator, acceptance/classification policy and the same public opportunity/fallback rules for every entrant and persistence condition. The readiness gate attests that the declared experiment and recovery procedure have sufficient development support for prospective testing; it does not attest that every as-yet-unseen trajectory will be admissible. Keep the complete 264-run matrix and independent outcome rules.

After readiness and freeze, create concealed manifests once. Apply the frozen automatic initial-world validity and domain checks to them without giving candidates hidden data or conducting policy-specific rehearsals. Capture the actual cut and classify it with only prior qualification plus contemporaneous state. Do not redraw a difficult seed, defer a cut until the chosen policy produces an easier state, select a different calibrated route in the candidate's place, or use final success to repair its classification. Configured opportunity reached, actual physical exposure, admissibility, and useful post-cut progress remain separate recorded facts.

Primary task success keeps valid candidate-caused failures. For recovery rates, report exercised admissible events separately from unknown/inadmissible and missed/fallback exposures, by entrant and condition; these denominators can differ and are not an unbiased stand-alone causal comparison. Provide explicit exact-instance versus empirical-transfer coverage where relevant. Difficulty created by candidate motion or occupied buffers is not automatically infrastructure invalid. A proven shared descriptor/generator/supervisor defect follows the already frozen paired-block invalidity rule; unknown admissibility alone is not such a defect. Preserve all records and report the original paired task/persistence contrasts.

## Concrete prefreeze implementation boundary

No file other than this plan was changed for this task. Still required before using the proposal: implement and test the descriptor/whitelist and protected actual-property capture; construct the bounded development fixtures; execute and retain calibration plus independent development validation; derive defensible local grip/route cells and absence support; wire verified calibration input (currently `restart_calibration=None` in experiment.py); and freeze the resulting rule and evidence. Counterexamples must reject an unlisted solver/actuator/geometry change, malformed inertia/template, out-of-domain property, unsupported population, missing source/hash, extrapolated state cell, excessive absence, unilateral grip, low clearance, occupied/blocked route and post-outcome calibration reference. No extra held-out-seed rehearsal is required or permitted to fill these prefreeze duties.
