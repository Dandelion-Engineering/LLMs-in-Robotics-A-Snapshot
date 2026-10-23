# Long-Term Memory

This file stores durable learned knowledge that may remain useful after the recent session-report window has passed.

It is semantic memory, not a chronological log, not current task state, and not a duplicate of other startup files.

## What belongs here

Add or update a memory when the current session has reasonably evidence-backed knowledge that:

- is likely to matter beyond the current episode or task step;
- is reusable across future sessions;
- would be costly, unsafe, or wasteful to repeatedly rediscover;
- is not merely temporary world state;
- is not already represented adequately in another canonical startup file.

Examples may include learned failure modes, reusable environmental regularities, empirically discovered constraints, robust strategies, or other generalizable knowledge.

## What does not belong here

Do **not** copy information that already belongs in or is already adequately represented by:

- `README.md` — filesystem structure;
- `RobotDetails.md` — robot embodiment, hardware, sensors, interfaces, intrinsic limits, calibration, or built-in capabilities;
- `ProjectDetails.md` — deployment, environment, task, authority, safety, or evaluation rules;
- `SummaryOfOnlyNecessaryContext.md` — current objective, current state, and active unresolved work;
- recent `SessionReports/` — episode-level chronology and detailed evidence.

If learned information belongs canonically in one of those files, update that file rather than duplicating it here when the agent is authorized to do so.

## Memory-entry requirements

Each long-term memory should be concise and include enough provenance to understand why it exists.

For each memory, record:

- **Memory:** the durable claim, lesson, or reusable knowledge;
- **Scope:** where and when it is expected to apply;
- **Evidence:** session-report or artifact pointers supporting it;
- **Status:** provisional, established, contradicted, or superseded;
- **Last updated:** session identifier or timestamp;
- **Notes / limitations:** important exceptions, uncertainty, or context.

A memory may be updated when later evidence confirms, narrows, contradicts, or supersedes it. Preserve provenance when doing so.

## Promotion rule

At the end of each session, the active agent decides whether anything learned deserves long-term retention. Promotion is selective: most session details should remain only in the immutable session report.

Do not promote a claim merely because it was observed once if the evidence is too weak to justify retaining it. When useful but uncertain knowledge is worth preserving, mark it as provisional and include its limitations.

## Current memories

### Allow base motion to settle before using precise visual coordinates

- **Memory:** Several completed base requests still had small residual motion. A 0.5–0.6 second settling interval followed by a fresh observation reduced mismatch between projected targets and the pose used for the next action.
- **Scope:** Precision grasping, aiming, and docking with this apartment robot's public base primitives.
- **Evidence:** [Session 001](SessionReports/2026-10-07-session-001.md): completed turn yaw -0.3137 settled to -0.3598; a completed 1.2 m drive reported x=-1.070 and settled near -1.105. Similar turn settling occurred repeatedly.
- **Status:** Established that request completion can precede settling; the adequacy of a fixed half-second interval is provisional.
- **Last updated:** 2026-10-07, session 001.
- **Notes / limitations:** Compare current observations and status rather than assuming a fixed correction. Noise and contacts can change the result. This does not imply every motion requires the same delay.

### Retracted arm height can hide a floor target

- **Memory:** The central arm structure can completely occlude a floor toy even with the gripper shifted sideways. Lowering the empty, retracted arm exposed the target for a fresh depth projection.
- **Scope:** Head RGB-D perception of reachable floor objects with this robot; only lower the arm after checking its swept space is clear.
- **Evidence:** [Session 003](SessionReports/2026-10-07-session-003.md), observations 64–66. Red was hidden at arm (0.25,0,0.70) and with lateral gripper shift to (0.25,0.30,0.80), then clearly visible after commanding (0.22,0,0.25). Its measured projection supported a subsequent successful grasp/lift.
- **Status:** Provisional; directly observed for one target/viewpoint.
- **Last updated:** 2026-10-07, session 003.
- **Notes / limitations:** These are tested viewing postures, not universal collision-free settings. Lowering a held object or an extended arm may be inappropriate. Reobserve after moving the arm.

### Verify articulated fixture motion visually

- **Memory:** The public bilateral-contact and secure-lift flags stayed false while a grasp on a drawer handle support successfully pulled drawer B open. Those flags alone did not establish whether this articulated fixture was engaged; the before/after images established the opening.
- **Scope:** Manipulating kitchen drawer handles through ordinary arm/gripper primitives; evidence is limited to B in this deployment.
- **Evidence:** [Session 006](SessionReports/2026-10-07-session-006.md), observations 159–160 and pull request `ea3869a3cc494a789b4fcee33e0d2bbd`; measured geometry and preceding press attempt are in [kitchen notes](Maps/Kitchen.md).
- **Status:** Provisional; one successful opening, with an unresolved contribution from a preceding orange-block press.
- **Last updated:** 2026-10-07, session 006.
- **Notes / limitations:** This does not relax contact/lift verification for carrying loose objects. Do not infer that a requested pull succeeded without observing the fixture, or that this handle grasp works for other drawers.
