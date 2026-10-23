# Batch 01 — from architecture to physical evidence

Randy's current assignment is to design **three different architectures, implement the necessary experimental system, run the complete experiments, and build the engineering investigation workspace around actual evidence**. The live clarification on 2026-09-22 supersedes the previous stop before architecture design.

## The three approaches

| Candidate | What the LLM decides | What physically executes |
|---|---|---|
| [A1: Durable Task Dispatcher](../Architecture%20Map/designs/B01-A1-r1.md) | The next typed task and recovery action | Shared numerical planner and bounded motion executor |
| [A2: Guarded Procedure Composer](../Architecture%20Map/designs/B01-A2-r1.md) | A short reactive program with conditions and task steps | A constrained interpreter plus the same execution services |
| [A3: Grounded Objective Composer](../Architecture%20Map/designs/B01-A3-r1.md) | Geometric movement objectives | A durable conventional scheduler and numerical motion planner |

Each uses a persistent episode filesystem and reconciles it with new observations. A conventional durable sequencer is a separate comparator. The [shared implementation contract](Shared%20Implementation%20Contract.md) keeps information permissions, body, model budget and evidence standards aligned. These initial immutable revisions are **proposed mechanisms**, not performance claims.

## Work in progress

The runtime is under active calibration in [Runtime](../Runtime/). Nine development attempts now cover the conventional comparator and all three LLM candidates using the common local Qwen3-14B model in the latest batch. **No valid full-task completion is established.** C0-002's earlier completion claim was withdrawn after the independent insert-state check exposed both inserts in the fixture; its raw evidence and append-only correction remain available. The latest five-pilot batch passed its host-timing checks while retaining physical, policy and transport failures. No scored release or scored result exists.

The immediate shared manipulation blockers are now cleared at the measured primitive scope: [Physical Calibration 005](Physical%20Calibration%20005.md) passed both insert exchanges, both interrupted-carry parking routes, and the other four declared probe classes, with all timing checks passing. [Physical Calibration 002](Physical%20Calibration%20002.md) and [MotionCalibration003](MotionCalibration003.md) preserve the preceding failures, fixed kinematic comparisons and exact corrections. These primitive successes do not establish complete-task feasibility or broad recovery qualification.

[Development Ledger](Development%20Ledger.md), [Calibration Changes](Calibration%20Changes.md), the [readiness follow-up](Readiness%20Audit%20Follow-up.md) and exact Architecture Map records distinguish measurements, corrections and remaining prerequisites. The full declared 264-run scored matrix and paired analysis are still pending.

The [Engineering Investigation workspace](../Engineering%20Investigation/README.md) reads the real Architecture Map and can ingest recorded run evidence. Empty or missing evidence remains explicit. There is no provisional leaderboard.

Sustained work uses the shared compute queue. A Windows process-liveness defect was discovered when concurrent submissions interrupted a model download. This project's queue use is temporarily serialized: no second submission or lock-contention poll while a worker is active; final official status must still report `succeeded` and exit 0 before outputs are used as completed. The queue itself is unmodified. Interrupted/failed calibration attempts remain evidence, not successful outputs.

Current implementation records and numerical calibration departures will be consolidated here before a scored release. The existing [Evaluation](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Evaluation.md) and [Contract](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Contract.md) remain the comparison standard; implementation stubs and failed readiness gates do not satisfy the request to run complete experiments.
