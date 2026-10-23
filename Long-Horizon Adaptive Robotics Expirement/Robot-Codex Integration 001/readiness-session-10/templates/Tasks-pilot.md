# Machine-tending recovery task

**Binding:** `robot-codex-integration-001`, simulation only, native r4 workcell. This runtime copy is CONFIGURED for one development-only recovery pilot. The trusted host has published the current activation, per-invocation endpoint, task revision and public state. Act only while the gateway acknowledges current robot ownership.

**Writer:** trusted task service. Record plans in `Continuity.md` or `notes/`; do not edit task instructions.

## Current job

The effective order is `packet.order` returned by `python -B robot.py status`. Its `version` must equal the activation's `order_version`. The order supplies required family, recipe, count and destination tray. Do not infer requirements from an old note or examples here. The public process contract maps family A to recipe A and family B to recipe B.

Help the conventional machine-tending sequencer recover from the incident in `live/activation.json`, then return a state it can reconcile. The incident is a reported symptom, not a prescribed solution. Use part, insert, pad and tray IDs established by current public observations or relevant public history.

Maintain current recipe, processing and inspection requirements. A delivery requires matching process eligibility and passing inspection linked to its cycle; a processed visual mark alone does not establish eligibility. A single rework cycle is permitted only when the current inspection explicitly requests it and the gateway admits it. Do not substitute parts, change quantities or recipes, reinterpret task updates, or bypass equipment interlocks.

Completion requires evidence of ordered counts in assigned trays, processing/inspection provenance, an idle reconciled station and an observably empty open gripper. A completed command receipt does not establish this. Hidden evaluator facts and scoring are unavailable to the robot agent.

## Normal work and handback

Your recovery is complete when the repaired, observed state supports protected handback. Return control at that point so the conventional controller performs the remaining productive work. Final order completion is judged independently after conventional operation resumes.

Normally the controller selects a freshly observed part, exchanges the fixture insert when necessary, loads the compatible part, starts its recipe, waits for the process, moves it to inspection, waits for the instrument, then delivers an eligible passing part. A process cycle normally lasts 8-10 simulation seconds; inspection takes 2 seconds. Motion/planning duration varies. Physics, sensing and an independently accepted process cycle continue during agent reasoning and tool latency.

Use actual skills/manual interfaces in `Tools.md`. Reacquire evidence after movement. Cancelling a robot action does not cancel or reverse an independent process cycle. Do not interrupt productive conventional operation merely because an activation file exists.

Before handback, update continuity and identify relevant incident, command and observation IDs. The supervisor checks current ownership/epoch/revision, freshness, unresolved commands, idle robot, open jaws and compatibility with the conventional next step. Rejected handback does not return ownership or complete the job.

## Budgets and blockers

Only host-granted recovery ownership permits actuation. Select a stable request ID before every action and query uncertain results before considering another action. The host bounds each activation to 20 action requests and 50 explicit observation requests; the trusted launcher supplies wall-clock/model budgets. This file grants no additional budget or automatic new invocation.

If the endpoint is absent, activation unconfigured, ownership changed, evidence insufficient, a fault persists, or an interface cannot express the needed recovery, record the specific blocker and required operator help. Do not invent state or weaken a limit. There is no event-driven yield endpoint: record the event/evidence needed and end the activation for supervisor scheduling. `skill wait` is an immediate recorded no-op, not a wake subscription.

Agent-written Python recovery programs are authorized through the immutable-snapshot bounded runner documented in Tools.md. All calls retain the same invocation ownership, native protections and gateway budgets.

## Task updates

This host uses a fixed order with epoch/revision fencing; it has no authenticated live task-revision update endpoint. Every request carries the activation's pinned epoch/order revision. A stale invocation must stop for authorized replacement; editing a note does not change an order or grant authority. Dynamic task updates require a separately implemented and authorized interface.
