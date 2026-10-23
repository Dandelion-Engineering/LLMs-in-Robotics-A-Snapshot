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
- `Maps/` — fixed spatial structure such as room topology, doorways, furniture/fixture locations, charging stations, and other persistent landmarks;
- `SummaryOfOnlyNecessaryContext.md` — current objective, current state, and active unresolved work;
- recent `SessionReports/` — episode-level chronology and detailed evidence.

If learned information belongs canonically in one of those files, update that file rather than duplicating it here when the agent is authorized to do so.

Dynamic regularities are not fixed-map facts and may still belong here when durable and evidence-backed. For example, "the movable cup has repeatedly appeared on the middle mat" can be a long-term memory even though the cup's current position must not be written into the fixed spatial map.

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

### Recurring green toy: one verified grasp and carry

- **Memory:** A commanded gripper width of 0.005 m held the green toy through lifting, base transport, and controlled placement. Measured aperture was approximately 0.052 m, effort approximately 14, with bilateral contact and secure-lift confirmation.
- **Scope:** The recurring green bedroom toy, with fresh perception and alignment. This does not establish settings for the other toys.
- **Evidence:** `SessionReports/2026-10-08T181847Z-session-002.md`, observations 39–43 and status around simulated times 1368–1440.
- **Status:** Provisional; one successful acquisition and placement.
- **Last updated:** Session 002, 2026-10-08.
- **Notes / limitations:** The measured aperture is contact feedback, not a surveyed object dimension. Use current contact and lift feedback; the command alone does not prove a grasp. Do not reuse the episode's object coordinates without sensing.

### Recurring red and blue toys: verified grips

- **Memory:** Commanded width 0.005 m acquired each of the red and blue toys with bilateral contact and confirmed lift. Both were subsequently placed in the chest and visually confirmed inside. Red's aperture settled to about 0.059 m with effort about 16.4 during carry; blue's immediate post-lift aperture was about 0.087 m with effort about 24.9.
- **Scope:** These recurring red and blue toys, individually, after fresh perception-directed positioning; yellow has separate evidence below.
- **Evidence:** `SessionReports/2026-10-08T183144Z-session-003.md`, observations 61–70 and status at sim 2114–2224.
- **Status:** Provisional; one successful acquisition and placement per toy.
- **Last updated:** Session 003, 2026-10-08.
- **Notes / limitations:** Aperture varied as contact settled and is not a measured object dimension. Closure and initial lift do not replace continued feedback or containment verification.

### Chest containment: resolve rim occlusion with the wrist view

- **Memory:** From an ordinary approach pose, the bedroom chest looked empty in head images even when toys were inside near its front wall. A wrist image from the extended placement pose clearly showed three colored toys on the interior floor; a second session used the wrist view to see all four after the head view showed only part of the contents.
- **Scope:** Verification of this chest when its front wall obscures the head camera's view.
- **Evidence:** `SessionReports/2026-10-08T183144Z-session-003.md`; head observations 66 and 69 versus wrist observation 70 after release, arm commanded (1.03, 0.4, 0.72) m at that session's base pose. Also `SessionReports/2026-10-08T184440Z-session-004.md`, head observation 91 versus wrist observation 92 from a different approach.
- **Status:** Established for the observed chest and these two placement views; other viewpoints remain geometry-dependent.
- **Last updated:** Session 004, 2026-10-08.
- **Notes / limitations:** The coordinates are episode evidence, not a reusable target. Position from current geometry; inspect actual wrist pixels before claiming containment.

### Docking immediately after a base action

- **Memory:** A base action reported completed, but an immediate dock request was rejected with “Stop the robot before docking.” A subsequent 0.8-second wait and dock request succeeded. In session 004, a deliberate 0.8-second wait after the final approach was followed by successful docking on the first request.
- **Scope:** Docking after a final approach segment; completion may precede sufficient physical settling.
- **Evidence:** `SessionReports/2026-10-08T183144Z-session-003.md`, sim 2445.956 rejection and 2456.004 successful docking; `SessionReports/2026-10-08T184440Z-session-004.md`, wait ending 3199.568 and docking at 3199.672.
- **Status:** Provisional timing guidance; one rejection/recovery and one preventive-wait success.
- **Last updated:** Session 004, 2026-10-08.
- **Notes / limitations:** Elapsed tool/decision time also contributed to settling; 0.8 seconds is not established as a universal minimum.

### Recurring yellow toy: verified grip and placement

- **Memory:** Commanded width 0.005 m acquired the yellow toy with bilateral contact; lifting to a retracted carry pose confirmed secure acquisition. Immediate post-lift aperture was about 0.070 m and effort about 19.4. Contact persisted during transport, and release into the chest completed the aggregate toy task.
- **Scope:** The recurring yellow toy after fresh perception-directed positioning.
- **Evidence:** `SessionReports/2026-10-08T184440Z-session-004.md`, observations 88–92; closure at sim 2942.568, lift at 2944.176, wrist observation 92 and `task_success: true` at 2990.672.
- **Status:** Provisional; one verified acquisition, carry and placement.
- **Last updated:** Session 004, 2026-10-08.
- **Notes / limitations:** Measured aperture is contact feedback, not object dimensions. Recheck alignment, contact, lift and containment every time.
