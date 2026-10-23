# Protected restart physical class: implementation handoff

Status: helper implementation, synthetic verification and actual compiled-model diagnostics. The root task owns Runtime integration and its tests; this folder does not attest their completion. Physical recovery qualification remains absent; the inspected experiment.py still supplies no restart calibration. These helpers cannot pass readiness or launch evaluation.

`descriptor.py` checks the complete generated XML after a narrow whitelist for 3/6/10 alternating A/B populations, two inserts, declared raw-slot jitter, population-index tag palette, sampled main-geom mass and sliding friction. All other XML fields and object template fields remain exact. Insert initial positions come from the actual XML zones; no parking coordinates are hardcoded. Class identity pins sources, Panda assets and MuJoCo binary bytes. Exact scene/configuration hashes remain provenance.

The proposed Cell hook seals the complete public compiled-model data surface immediately after the source-bound `MjModel.from_xml_string` call. Capture must still match that seal. The sole post-compilation exception is the source-declared binary process-mark color. All other compiled changes, missing seals, nonfinite arrays and unsupported exposed fields fail closed. Actual body mass, COM and full body-frame inertia are separately checked against the box construction, including both marker masses and inertial-frame rotation.

This design relies on the pinned protected compile-site source, exact compiler/assets and the no-mutation seal. It does not claim that selected compiled arrays alone describe the whole model. Both queued probes passed all actual compiled-model and mutation checks at 3/6/10 parts with stable before/after source bindings:

| Implementation | Initial seal range, 3 models | Export range, 9 exports | Median export | Official receipt |
|---|---:|---:|---:|---|
| Python finite-value loop, [probe 001](../../Evidence/calibration/descriptor-probe-001/summary.json) | 0.254709–0.261489 s | 0.252228–0.269132 s | 0.255106 s | [succeeded / exit 0](../../Evidence/queue-receipts/20260923T063120447987Z-0aa3e34a.json) |
| NumPy vectorized check, [probe 002](../../Evidence/calibration/descriptor-probe-002/summary.json) | 0.025622–0.026395 s | 0.023764–0.025152 s | 0.024014 s | [succeeded / exit 0](../../Evidence/queue-receipts/20260923T063740296044Z-eea059a3.json) |

The observed median export is about 10.6 times faster. Each probe compiled three declared development models, made one seal and three ordinary exports per model, rejected a changed fixed solver field, and accepted the declared binary process-mark toggle; both mutations were restored. No physics step, renderer, inference process or recovery trajectory ran. These costs exclude rich contact/geometry snapshot capture and classification, so integrated physics-owner pause and actual-host timing still need their own measurement. No operating absence/grip/route bound follows from these probes. An unsupported runtime property yields unknown class evidence. Keep sources frozen while a process runs; file hashing cannot attest imported code after concurrent on-disk source edits.

`qualification.py` requires a independently supplied frozen class/bundle digest, prior artifact byte verification and timestamps, one payload template, one joint grip/route cell, explicit absence support, measured point references, route coverage/allowance and a documented empirical transfer assumption. It labels class use `empirical_transfer`, with `instance_previously_calibrated: false`. It invents no bounds or minimum trial count. `actual_absence_coverage` records whether the later observed absence remained covered; later task success cannot repair a duration overrun.

The descriptor patch preserves legacy exact-configuration matching and every existing actual grip, contact, clearance, velocity, support, device, capacity and route predicate. Qualified grip and route entries must name the same measured cell. Matching is opt-in through `classify_restart(..., qualification_context=...)`; omitted mode remains exact, and omitted context stays unknown. A separate loader/absence proposal is now ready for review; no candidate packet receives the protected descriptor.

Files:

- `runtime-integration.patch`: delivered Runtime helper modules plus Cell construction/capture and classifier hooks; root owns application. Do not regenerate or reapply while its integration/source hold is active.
- `integration-manifest.json`: exact Runtime source bases and patch/helper hashes; source changes can stale it.
- `build_integration_patch.py`: regenerates only this folder's proposal after reviewing changed source; never applies it.
- `test_descriptor.py`, `test_qualification.py`, `test_runtime_patch.py`: synthetic whitelist, counterexample and in-memory proposed Runtime tests.
- `validation.json`: recorded bounded verification outcome.
- `calibration_loader.py`, `build_loader_patch.py`, `runtime-loader-integration.patch`, `loader-integration-manifest.json`: separate unapplied protected input/mapping/absence proposal. This does not regenerate the already delivered descriptor patch. The frozen A/B template mapping selects one exact cell per unique held payload; grip/route share its fixed destination, and actual absence is assessed later with explicit clock/endpoint semantics. See [Wiring](WIRING.md) for the reader interface and authority boundary.
- `test_calibration_loader.py`, `test_loader_patch.py`: 14 synthetic artifact, mapping, absence and in-memory integration checks; passed in 0.519 s. All proposed modules compile and the separate patch passes `git apply --check`. No integrated episode or physical qualification ran here.

The descriptor command below records its historical pre-application validation; its old exact-anchor generator/tests must not be rerun against an already integrated Runtime. For the separate loader proposal, from project root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s "Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools" -p "test_*loader*.py"
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/build_loader_patch.py"
git apply --check "Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/runtime-loader-integration.patch"
```

Recorded verification after vectorization: all 51 top-level tests passed; the in-memory Runtime test additionally runs the existing restart-state regression suite against the proposed classifier. Patch syntax compiled and `git apply --check` passed against the manifest's source bases. This helper task made no physics or compute-queue call, evidence mutation or evaluation seed generation. Actual physical success/qualification remains the root task's subsequent work.
