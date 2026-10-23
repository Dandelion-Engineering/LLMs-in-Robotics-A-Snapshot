# Session 001 — Living-room throwing practice

## Session identity

- Session ID: 2026-10-10-session-001.
- Start time: 2026-10-10; exact wall-clock start not separately recorded. First public status was simulation time 23.664 s.
- End time: 2026-10-10T16:47:40Z; physical docking completed at simulation time 671.428 s.
- Agent / model: Robot Codex / GPT-6.
- Runtime / configuration: persistent Maps Edition filesystem; public robot client and RGB image tool.
- Project revision: supplied ProjectDetails.md, unmodified; no revision ID exposed.
- Robot configuration revision: supplied RobotDetails.md, unmodified; no revision ID exposed.

## Startup context consulted

Read RobotAgentPrompt.md, then README.md, RobotDetails.md, Playbooks/Index.md, ProjectDetails.md, Maps/Apartment.md, SummaryOfOnlyNecessaryContext.md and LongTermMemory.md. SessionReports contained only its template: no prior reports existed. Read Maps/RoomMapTemplate.md, SessionReports/SessionReportTemplate.md, PositionGrasp playbook and its supplied program. Later read Playbooks/PlaybookTemplate.md. Inspected only authorized public status, observations, images and point projections for world state.

Current room was identified from RGB observation 4 (sofa, coffee table, television and bed visible through doorway), together with observations 1 and 3 (practice bin and pedestal). Created and loaded Maps/Rooms/LivingRoom.md before continuing task work. Topology was initially empty. No remembered location or hidden simulator labels were used.

## Objective on entry

Live assignment: use the working window to learn to throw the orange object into the living-room bin; ordinary arm/gripper experimentation, landing feedback and reset were available. Continue useful work until the battery warning, then dock and close out cleanly.

## Starting state

First public status: no active action; battery 99.446%, work time about 576.74 s; empty/open gripper around .140 m; dead-reckoned pose (0,0,0). Live assignment was throwing. Initial room label was unknown until visual identification. No prior maps, reports or learned procedures existed.

## Work performed

- Inspected head RGB views and points to locate the bin, pedestal and orange object. Scanned the sofa/television side and rear charging pad. Mapped fixed structure and the visually identified bedroom connection.
- Turned toward the nearby pedestal with retracted reach. The initial rotation ended at a different pose than requested: odometry shifted about .15 m and yaw reached about -1.387 rather than -1.57. This was treated as measured state; no exact cause was established.
- Tried the supplied open-gripper positioning capability. Subsequent positioning/retreat displaced the object, so re-observed it instead of assuming the original target remained valid.
- First pickup requested .065 m closure, measured about .089 m opening and effort 7.3, with bilateral contact and a confirmed lift. Later the object fell before the intended first trajectory release; reset after release.
- Subsequent resets were followed by current RGB inspection and fresh point projection. Repeated surface estimate near (.566,-.177,.947) m in the pickup base frame supported target center (.60,-.18,.935). Approached at z 1.10, lowered, requested .04 m closure over .7 s, lifted to 1.15 over 1.5 s, and retracted to x .36 before turning. Confirmed bilateral contact and secure lift; effort about 14.7, measured opening about .089.
- Tested a horizontal throw from preparation (.36,.10,1.15), through (.65,.10,1.15) with width .04, then (1.0,.10,1.15) opening to .15. Varied each stroke waypoint duration while retaining the observed base alignment. Six such throws landed inside.
- Promoted the local throw into a program and semantic playbook, with fresh-perception and grasp preconditions. The program physically executed five successful throws. No default capability was modified.
- Used the remaining work window for trial analysis, map/capability maintenance and a fresh charging-route observation. Stopped practice at the warning. Rotated toward the pad, drove in observed segments, corrected an initial no-contact dock position by advancing .18 m, and successfully docked.

## Results and evidence

### Throw trials

Distances are signed public feedback in the bin's throwing frame, meters. They describe landing outcomes and are not measured release velocities.

| Trial | Motion / closure | Landed simulation time | Forward | Left | Inside bin | Interpretation |
|---|---|---:|---:|---:|---|---|
| 0 | Weak .065 closure; intended rising .20/.20 s stroke | 225.992 | -1.369 | +.472 | false | Object fell before intended trajectory completed at 235.916; not a valid comparison of release timing |
| 1 | Horizontal, .04 closure, .18/.18 s | 289.776 | -.082 | +.014 | true | First successful throw; grasp geometry differed slightly from following resets |
| 2 | Horizontal program, .18/.18 s | 356.952 | +.253 | -.052 | true | Repeated reset pickup geometry |
| 3 | Horizontal program, .18/.18 s | 394.556 | +.267 | -.052 | true | Replication |
| 4 | Horizontal program, .20/.20 s | 424.172 | -.226 | +.080 | true | Slower stroke, successful |
| 5 | Horizontal program, .19/.19 s | 455.364 | -.227 | +.066 | true | Intermediate timing did not produce a centered settled landing |
| 6 | Horizontal program, .185/.185 s | 488.512 | -.212 | +.060 | true | Final throw; no later reset |

Confidence: six successful landings are confirmed by public feedback. Scope is a single object/setup/session. `task_success` remained false; this bounded practice assignment ends through warning, docking and clean closeout, per ProjectDetails.md. The final object was occluded by the near bin wall in observation 21; containment is supported by feedback, not an invented visual confirmation.

### Docking

Observation 5 identified the green pad, yellow mark and charging backstop beside the sofa. Re-observed in 22–26. Turned -2.273 rad from throw heading, drove 1.2 m then .85 m with intermediate sensing. First dock request at approximate odometry (-1.755,-.855,-2.698) was rejected: no charging contact. Advanced .18 m, stopped, inspected observation 26 and docked successfully. Request e585f002cf8c43b1b837d4db6130e75f completed at 671.428; status at 671.556 reported docked true, 100% battery and no active action.

## Robot / world state at exit

- Robot state: stationary and docked in living room; final odometry approximately (-1.917,-.932,-2.698). Gripper open around .150 m and empty; no bilateral contact or held object. Last arm command x .25, y 0, z .50; measured reach about .171, lift joint .071. Head pan 0, tilt .85.
- Environment / object state: final landing feedback confirms object inside bin; no reset after final throw. No other task objects manipulated.
- Active or pending actions: none.
- Authority / control state: docking closed physical control for this invocation; only filesystem closeout followed.
- Safety state: successful charging contact, stationary, arm retracted, no object held.
- Important uncertainty: next assignment is unknown; odometry is not surveyed localization. Re-establish state next session.

## Spatial map use and updates

- Current room: living room throughout; no doorway crossed and no room transition occurred.
- Active detailed map loaded: Maps/Rooms/LivingRoom.md, created after visual identification and read during operation/closeout.
- Added living room, visually identified bedroom and observed connection beside television to Maps/Apartment.md.
- Living-room fixed landmarks: sofa, coffee table, television cabinet, pedestal, target bin and charging pad. Evidence: observations 1, 3–5, 11–12, 22–26; public point projections and docking contact.
- Created minimal Maps/Rooms/Bedroom.md from the room template using only the bed, bedside cabinet and doorway observed in image 4. Bedroom was never entered; this was not an active navigation map.
- Charger position is recorded coarsely near (-2.0,-1.0) in initial dead-reckoned coordinates, reflecting repeated sensing rather than claiming exact surveyed center.
- No prior map facts required correction. Fixed structure only: no orange-object positions or transient state added to maps.
- Map uncertainty: cabinet-facing opening is not yet identified as a room; bedroom interior and its charger are not surveyed.

## Durable artifacts created or materially changed

- Maps/Apartment.md and Maps/Rooms/LivingRoom.md: grounded topology and landmarks, including the charging station actually reached.
- Maps/Rooms/Bedroom.md: minimal distant-view room map; untraversed.
- Programs/Learned/throw_horizontal.py: local horizontal throw, public controls only; live contact/effort/opening checks, battery guard, fresh-feedback polling. Physically used successfully five times. Does not provide pickup, navigation, target recognition or general ballistic calibration.
- Playbooks/Learned/HorizontalThrow.md: procedure, perception/contact preconditions, inputs, evidence, limitations and failure caveats. Registered in Playbooks/Index.md.
- README.md: filesystem tree and capability descriptions updated for the new artifacts/report.
- SummaryOfOnlyNecessaryContext.md: rewritten to the safe docked state, completed practice outcome and relevant artifact pointers.

## Learned constraints, procedures, or reusable knowledge

The stronger grasp and horizontal release merit retention as a locally validated capability, so their canonical details reside in the indexed playbook/program. Fresh possession checks remain essential; a past secure-lift flag alone did not prevent the first dropped-object outcome. Landing displacement changed nonmonotonically with timing, so no general flight model was inferred. Primitive joint readings and Cartesian gripper commands are different quantities; do not equate their numerical values. Request completion may precede brief settling.

Reviewed LongTermMemory.md and other startup files: no separate entry added. All useful durable candidates from this session are adequately represented in Maps or the learned playbook; copying them into long-term memory would duplicate canonical sources. No temporary script required promotion beyond the actual tested throw program.

## Failures and negative results

- `rg` unavailable; used filesystem listing/find fallback.
- Initially treated image-tool return as structured content; it was a text label plus data URI. Corrected rendering by extracting the data URI and then actually viewed images before using them.
- Early positioning displaced the object; reacquisition used a fresh image/point, not stale coordinates.
- First weak-grasp attempt dropped the object early. Closure strength, grasp geometry, handling and wait time were not isolated experimentally; do not claim closure alone caused it.
- First dock request failed despite visible partial pad overlap. A short, observed .18 m advance established actual contact. Visual overlap is not proof of docking.

## Unresolved work

No required work remains for this bounded practice session. Generalization to different poses/objects and improved landing consistency are unvalidated future capability questions, not a pending assignment. Bedroom interior and cabinet-facing room remain only partially/unknowingly mapped. The next externally assigned task must be read from live status in a fresh invocation.

## Corrections / supersessions of earlier reports

None: no earlier reports exist.

## Summary update

Replaced initial operator continuity with completed throwing practice, six confirmed successes, docked living-room state, unknown next assignment and pointers to the report, maps and indexed capability. Fixed spatial details remain in Maps.

## Session ending

- Task status: complete — bounded throwing practice, warning response, physical docking and filesystem closeout.
- Reason for ending: prescribed successful docking and normal invocation boundary.
- Robot left in safe unambiguous state: yes, confirmed docked with no active action.
- Next session must immediately verify: live assignment, physical status, current room identity and current observations before relying on any stored coordinates.
