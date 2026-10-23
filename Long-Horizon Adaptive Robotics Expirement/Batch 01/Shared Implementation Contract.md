# Batch 01: shared implementation contract

Randy authorized three architectures in the project chat on 2026-09-22 and clarified in the live session that this includes implementation, complete experiments, and every prerequisite needed to run them. The earlier design-only stop is superseded. The existing arena, observation permissions, independent scoring, and continuity comparisons remain binding.

## One physical job, three places for language reasoning

All candidates tend the same simulated Panda workcell. A1 chooses the next bounded task action from a shared unranked menu of currently admissible public actions. A2 generates a finite list of guarded actions that can make several decisions without another language call. A3 retains a conventional job scheduler and asks the language model for bounded transport clearance, speed scale, vertical approach and named avoidance zones. The shared planner constructs Cartesian waypoints and solves IK; it does not implement the original proposal's receding-horizon cost optimizer. Numerical controllers, contact dynamics, sensing, machine interlocks, and independent verification turn these proposals into physical behavior.

The original architecture design attachments remain proposals. The source-bound implemented revision governs each run. A2 currently supports 1–8 guarded action nodes, at most five guards per node, and ordered first-eligible execution; it has no variables, loops, distinct branch/retry node types or reusable procedure library. A3's requested zone check samples TCP positions, including the return leg, and does not certify whole-arm or payload clearance. Common deterministic restart recovery, observation and bounded-failure paths can issue actions without the model, including in A1.

These are engineering hypotheses, not replications of the papers that helped identify the distinctions. The baseline keeps durable transactions and uses the same sensors and execution library. A weak baseline, hidden detections, or successful transport acknowledgements cannot establish an advantage.

## Runtime and resources

Initial common model target was official Qwen3-4B-GGUF Q4_K_M. Current development uses official Qwen3-14B-GGUF Q4_K_M; see Calibration Changes.md and the retained versioned model manifest and smoke evidence. Thinking remains disabled and inference local only. All candidates use the same exact weights, quantization, inference build and settings; the final release must pin those selected bytes. The author model card identifies Apache-2.0; downloaded artifacts and runtime terms must be pinned and checked before use. Model fit, throughput, structured-output reliability and joint simulator/inference performance require retained measurements. No paid API, account creation, or training is required.

Each episode has one candidate policy process and at most one outstanding model request. The model gateway, sensing workers and executor are shared infrastructure. Model calls receive structured public observations derived from the image adapter and device I/O; this implementation does not feed raw RGB to a vision-language model.

Initial context ceiling is 16,384 tokens including system instructions, retrieved state, public observations and model response; response ceiling 1,024 tokens. The implemented calibrated overflow rule rejects an oversized request before generation; no current order, unresolved action, observation timestamp or historical content is silently truncated. This explicitly replaces the initial proposed pruning rule. Tokenization and actual counters belong in logs. A candidate may call less frequently; that difference is part of the full-system comparison. Invalid output consumes its measured time and tokens and is retained. Bounded repair requests cannot acquire more runtime budget.

The shared compute queue owns every sustained model/simulation/download job. Candidate code must not read evaluator state, protected seeds, repository history or the operator architecture map. Existing Ubuntu 24.04 under WSL and bubblewrap are available on this host; their actual filesystem/network/process restrictions need adversarial checks before a scored release. A typed language is a useful reduction in capability but is not by itself an operating-system security boundary.

## Common evidence and action semantics

Every candidate observes the current structured/text order, public station state, its bounded command receipts, joint/gripper telemetry and image-derived detections with capture/delivery time. It may request current camera packets. No candidate receives a complete hidden inventory, private process history, hidden inspection state, true object poses or future disturbances. The controlled-perception service must derive estimates from rendered RGB/depth.

Each command includes request ID, runtime incarnation, source decision, order version, resource, target and expiry. Candidate continuity separates intent, acceptance, dispatch, execution, feedback and candidate-side verification. Only the independent evaluator assigns physical outcome and final completion. Dispatcher idempotency lasts 60 seconds. After a longer absence, no receipt means unknown, not failure. Recovery obtains fresh observations and public machine status before deciding whether to continue, inspect, observe or escalate.

The candidate filesystem holds its private state in a checksummed `candidate-state.json`. A2 includes its current guarded program and completed-node list in that checkpoint. Writes use a temporary file, flush and atomic replace; no parent-directory fsync or atomic transaction spanning disk and physical action is assumed. This implementation provides neither candidate-readable journal replay nor semantic procedure retrieval. Model context includes the current public packet, retained part records and up to eight recent resolutions. The protected host evidence stream is an experiment record and is unavailable as replacement candidate memory after private-state removal. Old process incarnations lose authority. Every model proposal is checked again against the current order, observation age, resource lease and action preconditions before admission. A proposal created before an order change is discarded or recomputed rather than silently rebound.

The world advances during inference. Numerical control continues only within the current bounded authority. Local renewal is allowed only while current public evidence still satisfies its declared conditions; it cannot choose a new job. On timeout or uncertainty the system holds or brakes under the shared limits. Resume does not restore an old physics snapshot.

## Paired controls and inference

The persistent and no-persistence conditions run the same frozen candidate. In the latter, private writable episode context survives only until a restart; the order service, bounded dispatcher receipts, frozen code and frozen initial knowledge remain identical. Test both interrupted and uninterrupted conditions. Durable baseline memory remains enabled. A supplementary memory strategy or a changed executor needs an explicit diagnostic label.

Candidate comparison and continuity effect are different questions. The first compares entire systems; the second changes persistence within a candidate. Source code, model, prompts, dependencies, scene, evaluator, scenarios, settings and initial knowledge require hashes before evaluation. Development feedback cannot enter frozen evaluation memory. Failures, invalid blocks, rejected commands, timeouts and missing evidence stay in the record.

## Implementation and evaluation gates

1. Establish a contact-based Panda workcell with reachable stock, fixture, inspection and routing sites. No teleporting or attaching a successful part by assertion.
2. Calibrate image-derived sensing, physical transport, machine eligibility and independent placement/recipe/inspection predicates with a competent conventional baseline.
3. Verify world progression during inference and restarts, bounded leases, duplicate suppression, stale-output rejection, quotas and restricted candidate access.
4. Capture actual observations, model input/output, retrieved context, file versions, action lifecycle, physical state and motion/resource evidence. Replay must report missingness and divergence.
5. Give every entrant the same initial development opportunity. Publish any calibrated departure from proposed numerical defaults before the freeze.
6. Freeze a balanced, paired scenario manifest and selection/analysis rules, then run the complete declared matrix and continuity controls through the queue. Do not call a stub test, empty run template or primitive physics probe a completed experiment.

The current status and measured gate evidence live in the batch README and Architecture Map. This document defines the intended shared implementation; implementation revisions must identify what is actually available.

## Primary orientation

- [SayCan](https://say-can.github.io/): language-guided skill selection and feasibility; conceptual input to A1, not imported learned affordances.
- [Code as Policies](https://code-as-policies.github.io/): executable feedback logic; conceptual input to A2, whose constrained language differs from generated Python.
- [VoxPoser](https://voxposer.github.io/): language-composed spatial objectives with numerical motion planning; conceptual input to A3, without importing simulator segmentation masks.
- [Qwen3-4B-GGUF model card](https://huggingface.co/Qwen/Qwen3-4B-GGUF): proposed common local model; runtime evidence remains separate. The original 2507 proposal was replaced before registration because it lacks an official GGUF artifact; this avoids a third-party quantization or an extra conversion step.
