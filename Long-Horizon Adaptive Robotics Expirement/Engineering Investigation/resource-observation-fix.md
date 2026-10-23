# Required resource observations: unapplied proposal

The current supervisor ignores absent metrics and does not check the age of `ResourceSampler.latest()`. A missing GPU query, unavailable process counter or stopped sampler can therefore leave the sampled watchdog silent. This proposal closes that observation gap; it does not turn samples into hard resource caps.

[resource-observation-fix.patch](resource-observation-fix.patch) is **unapplied**. It changes only `Runtime/experiment.py` and its existing `test_experiment.py` check. It was prepared against these exact files:

```text
experiment.py       67ca1ecaf566256905829fee42baff497b33b621360606acf6fd83f453ee5ca5
test_experiment.py  6b55f8d68fab1cfd223d696c18d24d2c082b3684517089e8dc7112a93e633b83
patch               b25d80acbbb31d8f1cdf2f3abf96592155602ae172671be90c07aa4aa38f7a3d
```

Policy revision 003 gives the asynchronous sampler one initial **7-second grace**, explicitly the existing 5-second sampling period plus 2-second GPU-query timeout. It is measured from sampler monotonic startup, never restarted with the episode clock or candidate incarnation. After grace, harness RSS, active-model private commit with the matching owned PID, and memory on every reported GPU must be finite, nonnegative observations. A baseline with no active model does not require model commit. Missing/malformed observations become `infrastructure_failure`; they are not attributed to the candidate.

The latest completed sample's `capture_monotonic_s` must be within the sampler's lifetime and at most 7 seconds old. Future/pre-start timestamps fail even during initial grace; missing timestamps fail after it. Existing measured overages remain immediate, including during grace: harness/model overages are infrastructure failures, while whole-device GPU excess remains `host_resource_invalid` with attribution explicitly unknown. Exact existing byte caps are unchanged. Evidence retains the failed sample, reasons, supervisor check clock and sampler origin.

The supervisor's 0.25-second loop check is labeled a **target poll cadence**, not a measurement or guaranteed detection interval. The resource query is still asynchronous and may miss transient peaks. `resource_caps_enforced` stays false, with model/candidate hard limits reported separately. No additional OS query, subprocess or wait enters the physics thread; `resources.py` is unchanged. Short execution ending inside initial grace does not thereby establish measurement coverage.

[resource_observation_proposal_checks.py](resource_observation_proposal_checks.py) passed **19 synthetic checks in 0.049 seconds**. It applies the patch to strings, extracts only pure policy/check/classification definitions through the AST, and verifies the original Runtime files are unchanged. It neither imports Runtime nor queries the OS/GPU, simulates physics, calls a model or uses the compute queue. Cases cover grace/age boundaries, invalid clocks, independently absent mandatory values, absent/partial GPU lists, active-model PID mismatch, inactive baseline, cap equality, immediate overages and infrastructure classification. The file is outside default `test_*.py` discovery because it tests an unapplied proposal; `--applied` checks the actual source after operator application.

```powershell
& './venv/Scripts/python.exe' -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/resource_observation_proposal_checks.py'
# After the parent applies the patch, use the same command with --applied.
```

The parent must apply sequentially after source-hold release and run the focused Runtime supervisor suite. A later registered development attempt must retain actual current-source sampling/coverage and watchdog behavior. These synthetic checks do not establish host measurement availability, restart/resource performance or readiness. Previous results remain immutable.
# Application record

Root applied the staged patch after official completion of physical calibration 003, with no queue job active. The 19 proposal checks passed against the applied source (0.049 s), followed by all 28 supervisor tests (0.346 s). Actual runtime measurements remain pending. The historical preparation discussion below describes the proposal before application.
