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

### Render the image data returned by the orchestration tool

- **Memory:** In session 018, `robot_image` returned a string containing a label and a `data:image/png;base64,...` URI. Assuming an MCP `content` array displayed nothing; printing the raw result produced a very large text dump. Extracting the returned data URI and passing it to the orchestration `image(...)` helper displayed the actual pixels. A tool call without rendered pixels is not visual inspection.
- **Scope:** The current `functions.exec` wrapper around the public `robot_image` tool; check the return type without printing an entire image or enumerating every character key. This is an observed transport behavior, not a robot calibration change.
- **Evidence:** [Session 018](SessionReports/2026-10-07-session-018.md), startup image handling and thirty rendered observations. The working extraction was `result.match(/data:image\/png;base64,[A-Za-z0-9+/=]+/)[0]` followed by `image(...)`.
- **Status:** Established for the thirty images displayed in this session; persistence across tool deployments is provisional.
- **Last updated:** 2026-10-07, session 018.
- **Notes / limitations:** Only use the exact sequence returned by a public observation. If the return becomes structured content, use its actual image block instead. Do not infer visual semantics from a successful observation call alone.

### Leave margin when commanding a rearward head view

- **Memory:** A head pan request of 3.14159 radians was rejected with `Camera pan/tilt limit` despite the nominal documented range. Pan 3.0 succeeded in session 003, and pan 3.10 succeeded repeatedly in session 009. Use an observed working value inside the nominal boundary for rearward inspection and still verify the view.
- **Scope:** Rearward head-camera commands through this deployment's public interface; this is an empirical interface discrepancy, not a revised calibration or exact bound.
- **Evidence:** [Session 003](SessionReports/2026-10-07-session-003.md), failures section; [session 009](SessionReports/2026-10-07-session-009.md), initial rejection followed by observation 236 and later observation 251.
- **Status:** Established for the tested values; the actual effective boundary is unknown.
- **Last updated:** 2026-10-07, session 009.
- **Notes / limitations:** A rejected request has no assumed physical effect. Protected embodiment documentation was not changed. Check current encoders and images because command completion may precede full settling.

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

- **Memory:** The public bilateral-contact and secure-lift flags stayed false while grasps on a drawer handle support successfully pulled drawer B open in three sessions. Those flags alone did not establish whether this articulated fixture was engaged; the before/after images established the opening.
- **Scope:** Manipulating kitchen drawer handles through ordinary arm/gripper primitives; evidence is limited to B in this deployment, across sessions 006, 012, 014, and 021.
- **Evidence:** [Session 006](SessionReports/2026-10-07-session-006.md), observations 159–160 and pull request `ea3869a3cc494a789b4fcee33e0d2bbd`; measured geometry and preceding press attempt are in [kitchen notes](Maps/Kitchen.md). [Session 012](SessionReports/2026-10-07-session-012.md), observation 330 and pull request `3bd7a967e0ae459cbd8c5262f213a29b`, reproduced visible opening with both flags false. [Session 014](SessionReports/2026-10-07-session-014.md), observation 393 and pull request `1aba69ba56784be197e90e0e72b145c3`, confirmed a third opening with both flags false.
- **Additional evidence / limitation:** [Session 021](SessionReports/2026-10-07-session-021.md), observations 594–595, confirmed a fourth opening after the press/approach/close/pull sequence with both flags false. Closure was only 0.0141 m with effort 0.243, unlike the earlier sustained handle-contact examples, and pull-end effort was near zero. No intermediate view isolated the opening phase. The visual outcome is confirmed; a secure handle grasp or a specific opening mechanism is not.
- **Status:** Established visual outcomes for four B openings with differing contact feedback; general repeatability and the orange fitting's mechanism remain provisional.
- **Last updated:** 2026-10-07, session 021.
- **Notes / limitations:** This does not relax contact/lift verification for carrying loose objects. Do not infer that a requested pull succeeded without observing the fixture, or that this handle grasp works for other drawers.

### Use a cleared wrist viewpoint to inspect behind a container front

- **Memory:** A wrist-camera view above an open container exposed floor that the tall front concealed from the head camera. It provided drawer search coverage and direct visual confirmation of a placed cup, and later exposed colored toy patches near the chest front without touching placed objects.
- **Scope:** Visual inspection of the kitchen's open drawers and the bedroom chest, after establishing clearance for the empty arm. Direct overhead evidence covers A, B, and three chest inspections at nearly the same recorded viewpoint.
- **Evidence:** [Session 007](SessionReports/2026-10-07-session-007.md), head observation 188 versus wrist observation 190; [session 011](SessionReports/2026-10-07-session-011.md), occluded head observation 319 versus wrist observation 320 showing the cup upright inside A. [Session 012](SessionReports/2026-10-07-session-012.md), wrist observation 341, directly showed the cup upright in B after head observation 340 concealed it. [Session 014](SessionReports/2026-10-07-session-014.md), wrist observation 404, repeated direct upright-cup confirmation in B after an occluded head view 403. [Session 016](SessionReports/2026-10-07-session-016.md), wrist observation 453, exposed blue/yellow patches near the chest front after head observation 452 concealed the toys; red/green were not individually identified. Pose-specific examples and limitations are in [kitchen notes](Maps/Kitchen.md) and [apartment notes](Maps/ApartmentRoutes.md).
- **Additional evidence:** [Session 019](SessionReports/2026-10-07-session-019.md), wrist observation 541, repeated the cleared chest viewpoint after head observation 540 concealed the contents. Green/yellow surfaces were visible near the front; the image did not enumerate all four toys. Physical task success confirmed aggregate containment. The empty arm did not touch placed toys.
- **Additional evidence:** [Session 020](SessionReports/2026-10-07-session-020.md), wrist observation 577, repeated the cleared chest viewpoint after head observation 576 concealed the contents. Blue/green/yellow patches were visible near the front; red was not individually distinguished. All-four physical success persisted. No placed toy was touched.
- **Additional evidence:** [Session 021](SessionReports/2026-10-07-session-021.md), wrist observation 606, repeated direct upright-cup confirmation inside B after head observation 605 concealed it. Actual task success persisted; the cleared empty arm did not touch the placed cup.
- **Status:** Established for two tested A viewpoints, three B inspections at nearly the same viewpoint, and three limited chest inspections at nearly the same viewpoint. Broader geometry remains untested.
- **Last updated:** 2026-10-07, session 021.
- **Notes / limitations:** The cabinet top can still conceal the rear, and the chest view did not distinguish every contained toy. An empty image covers only the visible region. These postures are not an autonomous or universally safe inspection procedure; visual confirmation supplements actual task-success feedback.
