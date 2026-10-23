# Session-006 — seven successful throws, timing refined, living-room docked

## Session identity

- Session ID: session-006.
- Start time: 2026-10-10 UTC; first public status sim 3630.044. Exact wall-clock invocation start was not separately recorded.
- End time: physical docking sim 4233.624; filesystem closeout prepared after the 2026-10-10 05:11:46 UTC clock read.
- Agent / model: Codex, GPT-6 family.
- Runtime / configuration: simulated apartment robot; public robot_client primitives, default positioning, learned throwing program and robot_image.
- Project revision: not exposed; ProjectDetails.md read without modification.
- Robot configuration revision: not exposed; RobotDetails.md read without modification.

## Startup context consulted

- Read RobotAgentPrompt.md, then README.md, RobotDetails.md, Playbooks/Index.md, ProjectDetails.md, SummaryOfOnlyNecessaryContext.md and LongTermMemory.md in the specified order.
- Read the three most recent immutable reports, session-005, session-004 and session-003, newest first. Re-read session-004 separately because its portion of the combined response was truncated.
- Current public status assigned throwing practice, superseding the summary's unknown-next-task state. Followed relevant pointers to the throwing playbook/program, Maps/living-room.md, Maps/kitchen-route.md, session-001 report and trial evidence. Read default positioning playbook/program and the session-report template.
- Obtained current status and head RGB-D before physical departure. Images 133 and 134 established the charger backstop and rear departure scene. All RGB images cited for decisions were actually rendered using exact public observation sequences; failed initial rendering attempts were not treated as visual evidence.
- Did not inspect simulator/controller internals, access external communication, load irrelevant manipulation libraries or infer the assignment from historical task state.

## Objective on entry

Use the externally assigned working window to learn to throw the orange object into the living-room bin with ordinary arm/gripper controls, landing feedback and authorized reset. Reuse relevant learned work, continue until the ordinary warning, return promptly to a charging pad, dock and complete continuity maintenance.

## Starting state

At sim 3630.044 the robot was recharged/undocked at the former kitchen dock pose, approximately (4.114,-.941), yaw 10.1334. No action was active, the gripper was empty/open and the arm retracted. Work time remaining was 563.02 s; no warning. Current task_success=false referred to the newly assigned practice, not a reversal of historical cup completion. Rear sensing showed extended kitchen drawers. The living-room practice geometry remained historical until reobserved after travel.

## Work performed

1. Inspected departure clearance and backed .65 m off the kitchen pad. Turned north, observed the drawers and advanced .78 m. Turning west brought the low arm beside the near drawer and was blocked. An attempted arm disengagement was constrained; the following forward segment was also blocked.
2. Reobserved instead of replaying the obstruction. Requested a higher, laterally offset retracted arm pose; measured lift remained low. Turning south subsequently freed the arm, which rose toward the earlier target without a new arm command. Recentered high, moved south into the aisle and continued west with intermediate sensing.
3. Passed through the kitchen opening and alongside the blue bin, then approached the historical practice origin on currently observed clear floor. Final practice pose was approximately (.002,.001–.003), with pickup heading equivalent to south and throwing heading -.3208.
4. Inspected the orange sphere on its pedestal, projected a fresh surface point, used default open-gripper positioning, deliberately closed to .025 requested aperture and verified an actual lift to z=1.20. Repeated fresh pedestal sensing, alignment inspection, contact checks and actual lifts for all seven trials. Retracted before each base rotation.
5. Executed seven real runs of Programs/Learned/throw_orange.py, initially with its original default and subsequently with explicit duration arguments. Checked the scene before each throw, waited for fresh landing feedback and viewed the bin after each. Used reset only between released, landed trials. All seven landed inside.
6. Repeated .28/.135 timing, explored acceleration-only and release-only variations relative to those repetitions, then tested .28/.137 twice. Both final trials landed about 1 cm from center. Preserved the last result and stowed the empty arm. Updated the learned default durations and began evidence maintenance while the work window remained.
7. At the first recorded warning, turned toward the freshly identified living-room charger and drove 1.20/.70/.20 m with intermediate views, followed by settling and successful first-attempt docking.
8. Issued no physical commands after docking. Saved final status, finished trial/navigation artifacts, updated the learned playbook/index, maps, scoped memory, summary and README, and created this immutable report. Earlier reports and deployment-supplied/protected capabilities remained unchanged.

## Results and evidence

**Practice complete: seven trials, seven fresh inside-bin landings, ordinary warning handled and docking verified.** The general task_success flag stayed false, consistent with the documented bounded-practice assignment and historical observations. Completion is supported by landing feedback and the required window/dock cycle.

| Trial | Acceleration / release, s | Landing sim time | Forward / left error, m |
|---|---|---|---|
| 1 | .27 / .13 | 3859.860 | +.099 / -.029 |
| 2 | .28 / .135 | 3916.388 | +.023 / -.003 |
| 3 | .28 / .135 | 3969.120 | +.025 / -.004 |
| 4 | .29 / .135 | 4016.600 | +.026 / -.004 |
| 5 | .28 / .14 | 4061.464 | -.024 / +.013 |
| 6 | .28 / .137 | 4106.208 | -.006 / +.008 |
| 7 | .28 / .137 | 4154.464 | -.009 / +.009 |

- [Trial evidence](../Artifacts/session-006-trials.md) links all seven raw program logs and records exact commands, pickup checks, images and limitations. Every landing time was later than its corresponding throw start. Final two radial errors were .010 and approximately .0127 m.
- Actual pickups were confirmed by bilateral contact, about .089 measured aperture, effort 19.173 and secure-lift confirmation at z=1.20. Prethrow images showed the held sphere and alignment. Lowering to z=.90 again made the lift flag false while contact persisted; all ensuing throws succeeded.
- Observation 147 clearly showed the orange sphere inside the bin after trial 1. Later low settled poses were partly or wholly occluded by the front wall; final containment is grounded in fresh landing feedback, not a claim of fully visible final geometry.
- First recorded low_warning=true was sim 4195.640. Subsequent commands were only charger return, sensing, settling and docking.
- Dock request eb66098caa3145f69202e0cfff766982 completed at sim 4233.624. [Raw final status](../Artifacts/session-006-final-status.json), sim 4233.968, records docked=true, action=null, empty gripper and preserved final inside-bin feedback.
- Static validation parsed the modified throwing program and confirmed its defaults are .28/.137. Both settings were physically run together twice before the edit using explicit arguments; the newly edited no-argument invocation was not physically rerun. Only default values changed, not motion or safety logic. Markdown links were checked during closeout.
- Confidence is high in the observed landings and dock state. Timing reliability outside this local setup, exact contact bodies and surveyed coordinates remain unestablished.

## Robot / world state at exit

- Robot state: stationary at the living-room charger, approximate (-1.875,-.938), yaw 9.8893, equivalent -2.6771. Empty gripper open to .15; arm (.22,0,.70), pitch 0; head pan 0 / tilt .55.
- Environment / object state: final orange object inside the bin by landing feedback; no reset after trial 7. Pedestal expected empty. Both kitchen drawers were open on departure; incidental contact may have changed the near drawer's exact extension. Cup and toys were not deliberately manipulated or newly evaluated.
- Active or pending actions: none.
- Authority / control state: successful docking closed physical control for this invocation. Reset battery values did not authorize more work.
- Safety state: docked and unambiguous; backstop ahead. Future departure requires current rear sensing.
- Important uncertainty: next assignment; final settled sphere pose; exact kitchen drawer displacement/contact mechanism; generalization of throwing and recovery parameters.

## Durable artifacts created or materially changed

- Artifacts/session-006-trials.md — new curated seven-trial evidence, fresh acquisition geometry, parameter comparison, validation and scope. Distinguishes visible results from occluded final poses.
- Artifacts/session-006-trial-1.jsonl through session-006-trial-7.jsonl — new raw public output from every actual learned-program throw, including fresh feedback and final retraction.
- Artifacts/session-006-navigation.md — new departure failure/recovery evidence, constrained and later achieved lift encoders, actually traveled route and charger approach. Recovery is episode evidence, not a blind replay procedure.
- Artifacts/session-006-final-status.json — new raw docking and final landing snapshot.
- Programs/Learned/throw_orange.py — default durations changed from .27/.13 to .28/.137 after two actual successful explicit-argument runs. Syntax/defaults checked; no safety or trajectory logic change.
- Playbooks/Learned/ThrowOrange.md and Playbooks/Index.md — version/evidence/default updated, retaining narrow geometry and limited repetition scope. No new capability entry or learned executable was needed.
- Maps/kitchen-route.md and Maps/living-room.md — departure hazard/recovery, reobserved practice scene, repeated charging route and latest dock pose.
- LongTermMemory.md — one provisional learned interaction lesson about delayed arm motion after clearance changes; provenance and uncertainty retained.
- SummaryOfOnlyNecessaryContext.md and README.md — current completed practice/dock state and accurate discovery of new artifacts/report.
- This report — new immutable record following the supplied template. Earlier reports were not edited.

## Learned constraints, procedures, or reusable knowledge

The repeated .28/.137 pair gave the closest observed landings and became the learned default. .28/.135 now has three successful examples across two sessions; .28/.137 has two in this session. These small samples do not establish a reliability guarantee or universal timing law. The acceleration-only result was similar to the .28/.135 repetitions; increasing release duration moved the observed landing toward the near side. Further causal claims are not justified.

A completed high arm request at the drawer left lift encoder .13564 at sim 3720.000. With no intervening arm command, a later base turn was followed by lift encoder .81948, consistent with the prior requested z=1.25. The delayed movement is directly observed; persistent target tracking is an interpretation. This scoped lesson is worth retaining beyond the episode because it affects clearance planning during contact recovery and is not adequately captured by the existing startup statement that contact may prevent target attainment. It was promoted provisionally with evidence, without changing the protected embodiment contract.

Other route details remain in Maps and manipulation evidence remains in the indexed playbook/artifacts. Existing orange lift-feedback memory remained unchanged because the new trials supported its existing scope. Inline orchestration helpers did not warrant promotion as reusable programs. Default positioning capability files were unchanged.

## Failures and negative results

- rg was unavailable; used find and direct reads.
- Initial image-rendering attempts did not display pixels; subsequently extracted the tool's data URL and rendered it correctly before visual decisions.
- Kitchen westward turn f76a24712e774d15b08da3e9b4ab200f was blocked at sim 3692.868. Attempted arm disengagement did not reach its target; forward request c2867cbf2ffc46b2897dd133c7808413 was blocked at sim 3711.048. Exact contact bodies were not isolated. Recovery changed direction and clearance rather than replaying the failed segments.
- A high arm request reported completion while remaining physically low. The later rise was only recognized from measured state after base rotation; requested coordinates were never treated as proof of attainment.
- Side lidar clearance was close while passing the bin. Successful travel does not establish a generous-clearance route.
- One filesystem patch was rejected because it tried to delete and add the same summary path in one patch. Corrected with valid sequential updates; this did not affect physical control or earlier reports.
- No throwing miss, acquisition drop, failed dock request or physical command after docking occurred.

## Unresolved work

No required work remains for this practice assignment, warning response, docking or filesystem closeout. Optional future research includes repetition under fresh geometry, sensitivity to release timing and robust kitchen departure planning. Exact drawer contact geometry and displacement remain uncertain. Next assignment must be read from fresh public status; no future invocation is assumed guaranteed.

## Corrections / supersessions of earlier reports

The prior summary's unknown next assignment was resolved by current throwing status. Session-001's successful local throw calibration was reconfirmed and its default refined; its prior trial results and failure evidence remain valid. The old kitchen dock exit is superseded by the new living-room dock. Previous cup/toy completion was not newly assessed or contradicted by the practice assignment's task_success=false. No earlier report was rewritten.

## Summary update

The summary now marks practice complete, cites seven inside-bin landings and refined defaults, records verified living-room docking and closed control, preserves kitchen departure/contact caveats, links the new evidence and states that the next assignment is unknown. Prior cup recovery is not listed as active work.

## Session ending

- Task status: complete — practice window used, seven successful throws, ordinary warning respected, living-room docking and closeout complete.
- Reason for ending: successful docking after the ordinary warning, followed by required filesystem maintenance.
- Robot left in safe unambiguous state: yes.
- Anything a future session must verify immediately: current assignment/status, actual charger and departure scene, current object positions, and clearance for measured and commanded arm poses before recovering from any obstruction.
