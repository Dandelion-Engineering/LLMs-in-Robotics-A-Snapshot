# Session 007 — Ten successful practice throws; safely docked

## Session identity

- Session ID: 2026-10-10-session-007.
- Start: 2026-10-10; first public status at simulation time 3957.992 s. Exact wall-clock start not separately recorded.
- End: physical dock at simulation time 4537.604 s; filesystem closeout after 2026-10-10 19:18:33 UTC.
- Agent / model: Robot Codex / GPT-6.
- Runtime: persistent Maps Edition, public robot client and RGB image tool.
- Project / robot revisions: supplied ProjectDetails.md and RobotDetails.md, unmodified; no revision identifiers exposed.

## Startup context consulted

Read RobotAgentPrompt.md, README.md, RobotDetails.md, Playbooks/Index.md, ProjectDetails.md, Maps/Apartment.md, SummaryOfOnlyNecessaryContext.md and LongTermMemory.md. Read reports 006, 005 and 004 newest first; reread 005 fully because part of the combined output was truncated. Followed the throwing-capability pointer to session 001, HorizontalThrow.md and throw_horizontal.py. Also read the default PositionGrasp playbook/program and SessionReportTemplate.md. The default positioning program was not invoked.

Observation 178 showed the charging backstop. Scan 179 showed the sink/counter, three mats and drawer cabinets, identifying the kitchen against apartment topology. Loaded Kitchen.md as the current map and LivingRoom.md for destination planning. At the transition in 183–184, the sofa, coffee table, television and practice fixtures confirmed the living room. Reloaded LivingRoom.md on entry before further navigation. Apartment.md remained the global topology. No unrelated room maps, hidden simulator state or control implementation were inspected.

## Objective on entry

Live assignment: use the working window to learn to throw the orange object into the living-room bin, using ordinary controls, landing feedback and authorized resets. Continue useful work until the warning, dock normally and complete required records. This was a new throwing assignment; the prior cup-to-B task remained completed historical context.

## Starting state

At 3957.992: no active action, docked false, battery 99.365%, work_seconds_remaining 573.32, task_success false and throw_feedback null. Gripper open and empty; arm retracted, head near (0,.65). Noisy odometry about (4.081,-.902,yaw -2.4784). Room and relevant geometry were reconciled with live sensing before travel.

## Work performed

- Backed off the kitchen charger, inspected the opening and navigated through it using bounded base segments and current RGB/lidar clearance. Re-identified the living room and loaded its map on entry. No base action reported blocked.
- Located the orange object on the pedestal, approached through the open floor and measured fresh surfaces. Established a visually checked setup close to the previous tested alignment; old odometry was not treated as a route program.
- Acquired the object ten times with requested width .04, requiring bilateral contact, a separate secure lift and retained possession before dependent rotation/throwing. Reset only after release and landing feedback from each of the first nine throws. No reset followed the last throw.
- Executed the existing learned throw program ten times, varying stroke duration and once varying lateral y. Viewed each pre-throw alignment and used fresh feedback for each result.
- Retracted/lowered the empty arm after the last throw. Used remaining work time for analysis, playbook/index and map maintenance, plus charger-route observation and approach.
- Observed the warning, docked successfully on the first request, and completed filesystem closeout. No physical command followed docking.

## Results and evidence

### Bounded throwing assignment complete

All ten intentional throws returned fresh `throw_feedback.inside_bin: true`. Each used Programs/Learned/throw_horizontal.py with verified possession and current visual alignment. `task_success` stayed false, as in the earlier bounded practice assignment. Under ProjectDetails.md, completion consists of useful practice through the warning, successful docking and clean closeout.

Distances are signed public landing feedback in the bin's throwing frame, in meters; they are not release velocities or a calibrated flight model.

| Trial | Duration per stroke (s) | Lateral y (m) | Landed simulation time | Forward | Left | Inside bin |
|---|---:|---:|---:|---:|---:|---|
| 1 | .18 | .10 | 4143.176 | +.322 | -.018 | true |
| 2 | .18 | .10 | 4187.796 | +.322 | -.021 | true |
| 3 | .20 | .10 | 4216.136 | -.250 | +.115 | true |
| 4 | .19 | .10 | 4249.748 | -.242 | +.098 | true |
| 5 | .182 | .10 | 4279.892 | +.211 | -.007 | true |
| 6 | .183 | .10 | 4307.716 | +.123 | .000 | true |
| 7 | .184 | .10 | 4338.860 | +.046 | +.035 | true |
| 8 | .184 | .10 | 4365.780 | +.050 | +.032 | true |
| 9 | .184 | .065 | 4402.228 | -.189 | +.036 | true |
| 10 | .184 | .10 | 4432.556 | -.156 | +.064 | true |

The first two .184/.10 trials were within about .06 m of center, but their third repeat was less centered. The .065 lateral adjustment did not improve centering and also changed forward displacement. No optimum, smooth timing law or isolated causal mechanism was established. Program defaults were retained.

Final trajectory request 6170770381344fae88a7c19d5bf0d053 completed at 4431.620. Landing feedback at 4432.556 persisted through docking. Observation 210 showed the bin after withdrawal, but the settled object was occluded by the near wall. Containment is supported by feedback, not an invented visual sighting. No required work remains for this practice assignment.

### Setup and acquisition

Observation 186 point (288,184) estimated an orange surface at (.6397,.9937,.9422) in the then-current base frame. After navigation/rotation, observation 188 point (319,220) estimated (.5747,-.2155,.9471). Target (.61,-.215,.935), pitch 0, used visible geometry and the distinction between surface and center.

The first diagonal extension from the low retracted arm toward (.61,-.215,1.10), request c0f577e66af3434ea321716b9e10f100, encountered an obstruction at the pedestal. Despite the open command, measured width fell to .0707, effort was 23.76 without bilateral contact, and odometry briefly shifted from about (.111,.041) to (.108,.138), with yaw change. Exact contact attribution was not exposed. Subsequent lowering completed, the base settled back, and observation 189 showed the object between open fingers. No lift/acquisition was claimed from the obstructed approach.

Closure .04 over .7 s, request d7fd99b82ca9481b835d28d355ca0d49, achieved bilateral contact, opening about .090 and effort 14.72. Separate 1.5 s lift to z 1.15 confirmed possession; observation 190 showed the suspended object. Retraction to (.36,0,1.15) preceded rotation.

Later reset pickups started with the arm already raised, extended to (.61,-.215,1.10), lowered separately to .935, closed, lifted and retracted, with possession guards before further handling. Fresh observations 192, 194, 196, 198, 200, 202, 204, 206 and 208 showed the object on the pedestal; new projections stayed near (.573,-.215,.944), supporting reuse of the nearby target for each trial. All ten acquisitions retained contact and secure lift through setup, with opening generally .088–.090 and effort about 14.71. No premature drop was observed.

Observation 191 measured the near rim at pixel (236,172): (1.4012,.0235,.4011), and a rear inner surface at (232,144): (2.2277,.0742,.2474). The lower front-wall sample (229,190), (1.3498,.0712,.2901), was not treated as the rim. Images 191, 193, 195, 197, 199, 201, 203, 205, 207 and 209 confirmed the throwing corridor before their respective program runs. Throw poses were approximately (.106–.111,.041–.044), yaw -.425 in noisy dead reckoning, not surveyed coordinates.

### Warning and docking

Observations 185, 187 and 211–214 showed the station's green pad, yellow mark and backstop. With the empty arm retracted, the robot turned toward it and approached in 1.2 m and .95 m segments with intermediate sensing. Observation 213 point (233,260) estimated pad surface (1.242,.0443,.0077). Observation 214 at 4527.648 showed the final pad/backstop view and 3.66 s work remaining.

First observed low_warning true was status at 4531.620. The only subsequent physical command was docking. Request b4a188ac8cc449088a5531ccf70af5d7 completed at 4537.604 on its first attempt. Final status: docked true, battery 100%, empty gripper, no active action. Refreshed work-time counters in dock status did not authorize starting another assignment within this invocation; physical control closed.

## Robot / world state at exit

- Robot: stationary and docked in the living room, noisy odometry about (-1.813,-.925,yaw -2.6743), battery 100%.
- Arm/gripper: last command (.20,0,.50), pitch 0; open width about .1496, effort 0, no contact or secure lift. Final pre-dock status had reach about .1202 and lift .0695. Head commanded (0,.8).
- Orange object: final feedback confirmed inside bin; no reset/manipulation followed trial 10. Exact settled pose visually occluded.
- Other objects: cup and toys were not manipulated. Prior completed results were not independently re-evaluated during this assignment.
- Active/pending operations: none. Physical control closed after dock; filesystem closeout only.
- Safety: stationary, docked, empty and retracted.
- Uncertainty: next externally selected assignment unknown until fresh startup; reobserve room and relevant state then.

## Spatial map use and updates

Kitchen and living room were explicitly identified from perception plus Apartment.md. Kitchen.md was the startup active map. LivingRoom.md was loaded for destination planning and reloaded on entry in 184, then remained active through docking. No other room was entered.

Apartment.md and both room maps now record the kitchen-to-living-room traversal, supplementing the previously documented opposite direction. Refreshed living-room furniture, practice-fixture and charger evidence, including the successful dock estimate with its dead-reckoning limitation. No new fixed landmark/room required creation, and reliable perception did not contradict stored topology. Unknown adjoining spaces remain unknown.

No movable-object positions, current drawer extension, throw outcomes or procedures were added to fixed maps.

## Durable artifacts created or materially changed

- Playbooks/Learned/HorizontalThrow.md: semantic version 2, adding ten physical trials, tested timing/lateral options, repeat variability and raised-before-extension clarification. Its program stayed unchanged and succeeded ten times this session.
- Playbooks/Index.md: refreshed evidence to 16 successful throws across sessions 001/007, 15 performed by the program, with scope/variability limits.
- Maps/Apartment.md, Maps/Rooms/Kitchen.md, Maps/Rooms/LivingRoom.md: traversal and observed fixed-structure/charger verification. These maps were used in navigation.
- SummaryOfOnlyNecessaryContext.md: completed practice, final living-room dock, unknown next assignment and relevant pointers.
- README.md: added this report to the runtime inventory.
- SessionReports/2026-10-10-session-007.md: this immutable report, created once.

## Learned constraints, procedures, or reusable knowledge

Reviewed candidates against canonical sources. Throw results and approach clarification belong in the indexed playbook; fixed structure in Maps; progress in continuity/report. LongTermMemory.md was left unchanged to avoid duplication.

The initial obstruction supports separating vertical clearance from extension, while exact contact attribution remains uncertain. The .184 timing is a useful locally tested option but does not guarantee centering. Inline client polling and perception-specific pickup sequences remained ephemeral; no new generalized program was justified. No default capability, protected contract or earlier report was modified.

## Failures and negative results

- rg unavailable; used find and ordinary reads.
- Combined history truncated part of 005; reread it fully.
- Observation 180 occurred during active head motion. It was not used as the final navigation view; waited for idle and used 181.
- First low-to-high extension was obstructed and briefly displaced the base. Acquisition was established only by subsequent settled view, closure and lift. Later approaches began raised.
- Third .184/.10 repeat was less centered; lateral .065 did not improve centering. These limit optimization claims despite all throws landing inside.
- First closeout patch was rejected because it targeted the summary with two operations. No report was created by that rejected patch; wrote the summary separately and created this report once in a corrected patch.
- No missed intentional throw, premature drop, blocked base action, dock rejection or observed damage occurred.

## Unresolved work

No required work remains for this bounded assignment or lifecycle. Centering variability and generalization beyond this setup remain optional capability questions; unidentified adjoining spaces remain optional mapping gaps. No operation is active, and a future invocation is not assumed guaranteed.

## Corrections / supersessions of earlier reports

Session 006's unknown-next-assignment state was resolved by live status to a new throwing window. Its cup completion was not contradicted or reworked. Session 001's single-session throw evidence is extended by this replication; its original outcomes remain unchanged. Earlier reports were not rewritten.

## Summary update

Replaced completed-cup/kitchen-dock continuity with ten successful throws, completed lifecycle, final living-room dock, empty/retracted state, unknown next assignment and pointers to the updated playbook, room map and this report. Fixed spatial details remain in Maps.

## Session ending

- Task status: complete — bounded practice through warning, ten successful throws, successful dock and filesystem closeout.
- Session lifecycle: complete.
- Reason for ending: prescribed docking boundary and completed required records.
- Safe unambiguous state: yes; docked, empty/retracted, no active operation.
- Future startup must verify: live assignment/status, current room from perception, its map and relevant object/fixture state. Do not infer the next assignment from this report.
