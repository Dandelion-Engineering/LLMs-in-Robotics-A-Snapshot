# Tools and Programming Interface

**Status:** UNBOUND TEMPLATE. The capabilities below are requirements to bind, not executable commands or claims that endpoints already exist.

The builder must replace this template with tested call signatures, parameter schemas, examples, result formats, and failure behavior for the actual runtime. Keep unavailable capabilities explicitly disabled. Do not expose a name without an implementation.

## 1. Files and observations

Provide working methods to read/search permitted files, create/edit `Continuity.md`, `notes/`, and `programs/`, and atomically replace continuity while retaining a last-good version outside the agent's writable view.

Observation access must include requesting current public robot/device state, obtaining fresh observations of a chosen view or area where available, and opening permitted images. Describe what is directly visible, inferred, stale, or unavailable. The method must not return off-camera objects or hidden evaluator state unless the experiment explicitly declares an oracle condition.

Provide focused history lookup by event range, action ID, object ID, or incident ID. This may read JSONL directly or use a small read-only helper; do not require a separate search platform. Missing records stay missing.

## 2. Conventional skills

Expose the skills used by the conventional robot, rather than requiring the agent to recreate known successful behavior.

For each skill, document: name and version; purpose; exact signature; argument types, units, frames, IDs; observable prerequisites; expected duration and normal waits; intermediate/terminal feedback; cancellation; known failure cases; and how to verify the physical outcome. Document where its readable implementation or interface reference is available when useful.

`{{TESTED_SKILL_CATALOG_AND_EXAMPLES}}`

A high-level skill is not a bypass around the common actuator gateway. Its internals must use the same protected execution route. Where source is exposed and reuse is permitted, the agent may adapt a copy in `programs/`; it cannot overwrite the conventional stack or protected client implementation.

## 3. Bounded manual controls

Bind useful lower-level operations appropriate to the body, such as a small Cartesian displacement, a target pose, gripper opening/closure, camera acquisition, or a guarded stop/cancel. Joint/trajectory interfaces may be exposed when their checks are actually supported. Raw motor effort, unrestricted middleware publishing, and simulator setters are not default capabilities.

Document named coordinate frames, translation/orientation conventions, maximum increments, speeds, deadlines, feedback, and supported contact behavior. A manual “move up” request must become a bounded movement in an explicit frame, not unrestricted motor access. Validate the motion along execution, not only its endpoint.

`{{TESTED_MANUAL_CONTROLS_AND_EXAMPLES}}`

If the existing stack cannot enforce the required bounds for a primitive, the builder must implement and test that protection or report the primitive unavailable. Do not silently replace manual control with a task-menu choice and claim the requested capability exists.

## 4. Agent-written programs

Provide a real local code workspace and a supported language/interpreter. Bind a client API for observation, skills, manual movement, status, cancellation, and handback through the same gateway. Include a minimal tested example and the permitted dependencies.

The agent can create or revise a program with conditional logic, loops, repeated sensing, and composed actions. All child processes inherit the same restrictions. No direct simulator/driver imports, unapproved networking, privileged files, or host control endpoints are accessible.

Provide a syntax/import/interface check, a declared simulation-only rehearsal option if implemented, and bounded execution/status/cancellation. A rehearsal must not silently rewind the live world or read a hidden solution. Executing a program pins its content and dependencies to a version/hash; later edits create a new version, not hot edits to running code. Internal physical calls receive their own recorded IDs, linked to the program run.

`{{LANGUAGE_CLIENT_API_TEST_AND_RUN_BINDINGS}}`

## 5. Control ownership and return

Document how to request and confirm recovery ownership, inspect current owners and in-flight commands, cancel or supersede within supported rules, query an earlier action, request handback, report a blocker, or yield until an event/deadline.

The supervisor—not a file flag written by the agent—grants and revokes control. No conventional controller and agent may issue conflicting commands to the same resource. Handback must reconcile real state and conventional program state, not merely resume the old line of code.

`{{CONTROL_STATUS_HANDBACK_AND_YIELD_BINDINGS}}`

## Shared command semantics

Every physical operation carries an episode/run identity, runtime generation, stable request ID, relevant task revision, target resource, and bounded lifetime. The trusted wrapper may attach these automatically. Document the exact returned action ID and receipt fields.

Receipt states distinguish accepted, executing, terminal, rejected, cancelled, expired, and unknown; physical verification is separate. Repeating a request ID must not dispatch another movement. Query status after a lost reply; unresolved dispatch remains unresolved until reconciled with evidence. A transport receipt is never a guarantee of exactly-once physical effect across all possible device failures.

All requests are checked at admission and relevant execution boundaries. Old-generation commands, stale task revisions, missing ownership, and unsupported inputs are rejected. Program and tool errors remain observable. A preflight pass is not a promise of successful motion or task completion.
