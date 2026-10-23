# Physical experiment runtime

This is the Batch 01 implementation workspace. It currently supports **development** attempts, with explicit refusal of scored evaluation until shared readiness and a frozen release exist. See [readiness](../Batch%2001/readiness.json) and [the batch entry point](../Batch%2001/README.md) before running anything.

| Component | Responsibility |
|---|---|
| `cell.py` | Pinned Panda body, generated tending geometry, contact transport, numerical IK, image-derived color-tag positions, public device services and private physical predicates |
| `candidates.py` | A1 task dispatcher, A2 guarded procedure, A3 geometric objectives and durable conventional baseline; candidate-owned observations/continuity only |
| `candidate_worker.py`, `sandbox.py` | Isolated WSL/bubblewrap worker, restricted filesystem/network/process access, quotas and JSON IPC |
| `model_setup.py`, `model_runtime.py`, `MODEL.md` | Official pinned local model/runtime acquisition, terms, bounded structured inference and lifecycle |
| `experiment.py` | Independent physical supervisor, real time, model concurrency, restart boundaries, event/motion/frame capture and terminal assessment |
| `record_attempt.py` | Immutable source/environment revision and attempt registration before execution; result registration afterward |
| `restart_state.py`, `restart_physical_class.py`, `restart_compatibility.py`, `restart_qualification.py` | Protected rich cut evidence, pinned physical-class identity and opt-in prior measured-cell matching; compatibility alone supplies no recovery qualification |
| `development_batch.py`, `freeze_artifacts.py`, `release_runner.py`, `protocol.py` | Sequential registered development, exact artifact preparation, gated once-only scored execution/finalization and paired analysis |

The candidate never imports the simulator/evaluator. Its sandbox receives copied candidate code and one private writable episode directory. The operator map, hidden state, model service, seeds and full repository are outside that boundary. The model receives only the prompt supplied through the controlled gateway. No paid external inference is used.

## Run discipline

Use the project `venv`. Every sustained operation goes through the installed shared compute queue. Read the [current queue limitation](../Batch%2001/Queue%20Limitation.md) before submission. Concurrent submissions currently expose a Windows process-liveness defect; do not create a second heavy job while one is active.

For a new development attempt, first use `record_attempt.py prepare` with a fresh run ID, candidate, condition, scenario, seed, part count and cap. This freezes source bytes in the Architecture Map before execution. Then queue `experiment.py` with the identical arguments. After the worker exits, require the official queue status to be `succeeded` and `exit_status` 0 before treating the supervisor's output as a completed attempt; physical task outcome is a separate field. Register failed or interrupted attempts honestly, including missing evidence when no terminal output survived. Never silently reuse a run ID.

`record_attempt.py finish --run-id <id> --queue-job-id <actual-id>` imports an existing terminal result through the map's safe append API. The map does not certify that an experiment was fair, complete or physically successful. Development records must retain readiness limitations.

Large raw evidence lives under `../Evidence/raw/<run-id>/`, ignored by Git. Each attempt retains manifest, protected event log, 100 Hz motion records, delivered/available sensor evidence, candidate continuity and terminal result. The investigation builder can ingest these local runs; do not mount them inside a candidate. Compact identities and source snapshots belong in Git.

## Verification limits

Candidate unit tests use synthetic public packets. Sandbox tests exercise actual local OS permissions with harmless adversarial probes. Model adapter tests mock HTTP except the separately queued and recorded live smoke. Contact calibration is an actual physical simulation, but one successful transport does not establish workcell readiness. A complete nominal baseline job, repeatable sensing, insert exchange, lifecycle behavior, timing/resource budgets and evidence acceptance must be established before the complete frozen experiment matrix can start.

The controlled-perception implementation uses explicitly simplified colored tags and a calibrated camera rather than unlicensed vision weights. No exact simulator pose enters its detections. Pose errors are measured against private truth only by the calibration/evaluator. Visibility remains real: an occluded tag is unavailable. Any extension of sensing permissions or a numerical calibration change must be published uniformly before the freeze.

The current physical and timing checkpoint is [Calibration Changes](../Batch%2001/Calibration%20Changes.md), with retained failed attempts and exact probe records. As of the September23 development002 launch, the full408-test suite and instrumented carry probe006 pass, but `experiment.py` still supplies no measured restart qualification. The [execution runbook](../Engineering%20Investigation/RUNBOOK.md) describes remaining freeze and complete264-run work; it does not declare those experiments complete.
