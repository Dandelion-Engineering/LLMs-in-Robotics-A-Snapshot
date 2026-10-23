# Session-009 — seven successful throws, default retained, living-room docked

## Session identity

- Session ID: session-009.
- Start time: 2026-10-10 UTC; first public status sim 6116.428. Exact wall-clock invocation start was not separately recorded.
- End time: docking sim 6702.632; filesystem closeout following the 2026-10-10 05:50:09 UTC clock read.
- Agent / model: Codex, GPT-6 family.
- Runtime / configuration: simulated apartment robot; public robot_client primitives, default positioning, learned throw program and robot_image.
- Project revision: not exposed; ProjectDetails.md read without modification.
- Robot configuration revision: not exposed; RobotDetails.md read without modification.

## Startup context consulted

Read RobotAgentPrompt.md, then README.md, RobotDetails.md, Playbooks/Index.md, ProjectDetails.md, SummaryOfOnlyNecessaryContext.md and LongTermMemory.md in the required order. Read immutable reports 008, 007 and 006 newest first; reread 007 separately because its portion of the combined output was truncated.

Current public status selected throwing practice, superseding the summary's unknown next assignment. Consulted the throwing playbook/program, living-room and kitchen maps, session-006 trial evidence, default positioning playbook/program and session-report template. Existing indexed capabilities supplied positioning and throwing; no irrelevant library or simulator internals were inspected. No external communication, Internet or host inspection was used.

Obtained current status and head RGB-D before physical movement. Observations 228–229 confirmed the charger backstop and clear rear floor. All cited images used for decisions were actually rendered from their exact public observation sequences. Historical cup completion and map estimates were not treated as proof of current task state.

## Objective on entry

Use the current throwing-practice window to test and refine the learned orange-sphere throw through ordinary controls and landing feedback. Continue useful work until the ordinary warning, return promptly to a charger, dock and complete filesystem closeout. Do not assume the previous cup assignment remains active.

## Starting state

At sim 6116.428, recharged/undocked at the former kitchen dock near (4.094,-.954), yaw 22.4286. Empty open gripper, retracted arm, no action, no warning and 554.14 working seconds remaining. Current task_success=false belonged to throwing practice. Rear sensing showed both drawers extended; the cup's precise current state was not assessed.

## Work performed

1. Checked rear clearance, reversed .65 m and raised the empty retracted arm. A westward view showed the charger/backstop crossing the direct line, so moved north into the aisle before proceeding west.
2. Traversed the kitchen aisle near y=-.198. A subsequent northwest segment was blocked beside the living-room bin near (2.511,.018). Reobserved, turned north, advanced .38 m and resumed westward travel around y=.385. Reached the practice area near (.016,.002) through further sensed segments.
3. Reobserved the pedestal sphere, projected visible surfaces and used the default open-gripper positioning capability. Inspected alignment before each closure and verified an actual lift for all seven pickups. Retracted before each base rotation and inspected the current throwing scene before every program run.
4. Executed seven actual learned-program throws: default .28/.137 with no arguments three times, .28/.136 twice and .28/.138 twice. All landed inside. Reset only after confirmed release/landing between trials; no reset after the seventh.
5. Compared paired variants and repeated defaults. Retained .28/.137 because the small samples did not establish an improvement. Stowed the empty arm, identified the charger and began evidence maintenance during remaining work time.
6. Replaced one stale charger point request with a fresh observation/projection. Turned toward the charger while working time remained. After the warning, drove the direct 1.20/.70/.20 m approach with intermediate sensing, settled and docked successfully on the first request.
7. Issued no physical command after docking. Saved final status, completed trial/navigation evidence, expanded the existing throwing playbook/index, updated maps/summary/README, reviewed memory and program promotion, and created this immutable report. No protected/default capability or earlier report was changed.

## Results and evidence

**Throwing practice complete: seven fresh inside-bin landings, ordinary warning respected, safe docking and required continuity maintenance completed.** General task_success remained false under the bounded practice assignment, as in earlier practice sessions; landing feedback and the required warning/dock cycle support completion.

| Trial | Acceleration / release, s | Landing sim time | Forward / left error, m |
|---|---|---|---|
| 1 | .28 / .137 | 6298.064 | -.001 / +.011 |
| 2 | .28 / .137 | 6344.240 | -.001 / +.011 |
| 3 | .28 / .136 | 6389.436 | +.019 / +.005 |
| 4 | .28 / .138 | 6440.312 | +.013 / +.007 |
| 5 | .28 / .138 | 6488.080 | +.013 / +.008 |
| 6 | .28 / .136 | 6534.776 | +.019 / +.006 |
| 7 | .28 / .137 | 6585.524 | -.010 / +.016 |

- [Trial evidence](../Artifacts/session-009-trials.md) links seven raw program logs, exact CLI settings, acquisition checks and images. Every landing timestamp is fresh relative to its throw start. Reported radial errors range .0110–.01993 m.
- All seven pickups had bilateral contact, approximately .089 m measured aperture, effort 19.173 and secure-lift confirmation after a real vertical lift to z=1.20. No carrying drop was detected. The learned preparation again lowered the lift flag while contact persisted; subsequent throws succeeded.
- Three no-argument default invocations physically exercised the default path edited in session-006. The program itself was unchanged this session. Paired variants repeated closely, but did not establish a simple monotonic timing trend or a superior setting.
- [Navigation evidence](../Artifacts/session-009-navigation.md) records current sensing, actual route, one blocked segment, successful recovery, charger geometry and warning response. Contact body/bin displacement were not isolated.
- First recorded low_warning=true was sim 6670.584 in the saved trace. Afterward, only three forward segments, settling wait and dock commands occurred. No task manipulation followed the warning.
- Dock da4cbcb4a9f54345b57ba780e6ae1d87 completed at sim 6702.632. [Final status](../Artifacts/session-009-final-status.json), sim 6702.740, confirms docked=true, action=null, empty gripper and final inside-bin feedback.
- Validation parsed all seven logs and 1,218 public trace rows, checked fresh successful landings, six resets, seven positioning calls, final docking and absence of post-dock commands. Artifact links and README discovery were checked before report creation, with only this report pending then.

Confidence is high in actual acquisition, fresh landings and docking. Exact surveyed geometry, causal timing sensitivity, contact identity and fully visible settled sphere position remain unestablished.

## Robot / world state at exit

- Robot: stationary at the living-room pad near (-1.861,-.936), yaw 22.4559, equivalent -2.6768. Arm (.22,0,.70), pitch 0, empty gripper open .15; head pan 0 / tilt .55.
- Environment: final orange sphere inside the bin by landing feedback; no reset after trial 7. Settled sphere mostly occluded. Both kitchen drawers were seen extended at departure; prior cup containment was not newly evaluated. Toys were not manipulated.
- Active or pending actions: none.
- Authority/control: docking closed physical control for this invocation. Reset battery fields do not authorize further action.
- Safety: docked, idle and empty, with backstop ahead. Future departure requires fresh rear/side sensing.
- Important uncertainty: next assignment, exact bin movement during the blocked approach, settled sphere pose, broader throwing reliability and historical drawer mechanisms/A failure.

## Durable artifacts created or materially changed

- Artifacts/session-009-trials.md and session-009-trial-1.jsonl through session-009-trial-7.jsonl — new curated comparison and actual public output from all seven learned-program runs. Narrow local evidence, not a general reliability model.
- Artifacts/session-009-public.jsonl — new public command/status, observation metadata and point trace from first base departure through docking. Initial sensing, RGB pixels and learned-program internal calls are excluded; dedicated trial logs cover those program runs.
- Artifacts/session-009-navigation.md — new route/obstruction/recovery and verified docking evidence, including failed and successful segments.
- Artifacts/session-009-final-status.json — verified docked, idle, empty final state and preserved inside-bin feedback.
- Playbooks/Learned/ThrowOrange.md and Playbooks/Index.md — expanded evidence, three no-argument default runs, paired nearby variants and limitations. Default retained; executable unchanged.
- Maps/living-room.md and Maps/kitchen-route.md — blocked near-bin approach, farther-aisle recovery, safe high-arm kitchen departure and current living-room dock. Prior current-state labels made historical where applicable.
- SummaryOfOnlyNecessaryContext.md and README.md — completed practice, current dock, relevant warnings and accurate discovery of new artifacts/report.
- This report — new immutable session record. Earlier reports were not rewritten.

## Learned constraints, procedures, or reusable knowledge

The .28/.137 default now has five successful examples across two sessions, three of them no-argument runs in this episode. .136 and .138 release variants each repeated closely but did not clearly improve the reported radial error. Small timing changes did not establish a simple monotonic response. These specific findings belong in the indexed throwing playbook and evidence, with uncertainty preserved.

The near-bin route at y about .018 was blocked; moving north to around y=.385 enabled westward passage once. This geometric evidence belongs in maps and the navigation artifact. Exact contact and any bin movement remain unknown, so throwing results do not prove the bin was untouched.

Reviewed LongTermMemory.md and canonical startup files. Left long-term memory unchanged: acquisition feedback and checking actual attained poses are already represented, while the new timing/navigation details belong in their playbook/map. No independent general lesson warranted duplication. Inline polling/logging helpers added no learned motion capability and were not promoted to Programs/Learned. No executable was created or modified.

## Failures and negative results

- rg unavailable; used find/direct reads. The combined report output truncated part of 007, which was reread fully.
- Northwest base request 7a881666453948d28a8b365df2fd368e was blocked beside the bin. Reobserved and changed clearance/direction before continuing; did not repeat the failed request.
- One charger point request against observation 267 was rejected for age over 30 simulated seconds. Fresh observation 268 and projection replaced it before navigation.
- Some observations immediately after completed commands captured residual settling. Observation 251's shifted surface point was interpreted alongside the actual settled pose and subsequent alignment; later turns included a short settling delay.
- The paired timing variants did not justify changing the default. No throw missed, no pickup failed, no dock request failed and no physical command followed docking. The blocked route prevents claiming no incidental environmental contact.

## Unresolved work

No required practice, warning response, docking or closeout work remains. Optional future investigation includes broader repeatability, acquisition/settling variation and route clearance by the bin. Exact contact identity, bin displacement and historical drawer issues remain uncertain, not incomplete parts of this finished practice assignment. Next assignment must come from fresh status; no future invocation is assumed guaranteed.

## Corrections / supersessions of earlier reports

Fresh status selected throwing practice, superseding session-008's unknown next assignment. Its completed cup task was neither resumed nor contradicted by the practice task_success=false. Kitchen dock is superseded by the current living-room dock. Session-006's default evidence is expanded by later no-argument executions, while its original observations remain valid historical evidence. No earlier report was changed.

## Summary update

Summary marks practice complete, records seven successful landings, retained default, final living-room docking and closed physical authority. It links current evidence and maps, flags the blocked near-bin route and unknown next assignment, and keeps historical cup/A uncertainties separate from current required work.

## Session ending

- Task status: complete — useful practice window, seven successful throws, ordinary warning, docking and filesystem closeout completed.
- Reason for ending: successful docking after the ordinary warning and completion of required continuity maintenance.
- Robot left in safe unambiguous state: yes.
- Immediate future verification: current assignment/status, actual charger and rear clearance, current object/bin geometry and whole-robot clearance before departure or replaying any route.
