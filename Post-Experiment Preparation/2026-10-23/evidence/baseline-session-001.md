# Session-001 — living-room throwing practice

## Session identity

- Session ID: session-001.
- Start time: 2026-10-10 UTC; first recorded robot status sim time 24.364. Exact invocation wall-clock start was not recorded.
- End time: 2026-10-10T04:08:39+00:00 (filesystem closeout); last physical action completed at sim time 653.896.
- Agent / model: Codex, GPT-6 family.
- Runtime / configuration: apartment simulated robot, public robot_client primitives and RGB image tool; first deployment session.
- Project revision: not exposed; startup ProjectDetails.md used without modification.
- Robot configuration revision: not exposed; startup RobotDetails.md used without modification.

## Startup context consulted

- RobotDetails.md: read in full, including sensing, primitive controls, feedback and docking semantics.
- ProjectDetails.md: read in full, including fixed practice window and prompt return at warning.
- SummaryOfOnlyNecessaryContext.md: initial continuity indicated first session and no previous reports.
- Additional files / reports / artifacts consulted: RobotAgentPrompt.md, README.md, Playbooks/Index.md, LongTermMemory.md, Playbooks/Default/PositionGrasp.md, Programs/Default/position_grasp.py, SessionReports/SessionReportTemplate.md, Playbooks/PlaybookTemplate.md.
- SessionReports initially contained only its template; there were no three earlier immutable reports to read.
- Current status and head RGB-D were acquired before physical action. Every RGB observation used for visual decisions was actually viewed via robot_image.

## Objective on entry

Use the assigned working window to learn to throw the orange object into the living-room bin using ordinary arm/gripper controls and landing feedback. Practice until the battery warning, return to a visually identified charging pad, dock, and preserve useful learned work.

## Starting state

Robot near dead-reckoned origin (0,0), yaw 0, empty gripper, undocked, no active action. First status showed 576.04 working seconds remaining and no warning. Assignment explicitly authorized bounded throwing practice and object reset. No learned geometry or skills had been supplied beyond open-gripper positioning.

## Work performed

1. Inspected head images forward and to both sides. Located the blue bin, orange sphere on a pedestal to the initial right, and the green/yellow charging pad behind and to the initial right. Projected selected pixels to obtain noisy base-relative surface points.
2. Retracted/raised the arm before in-place turning toward the pedestal. Estimated sphere center near (.60,0,.935) in that facing base frame. Used the supplied positioning capability; closed the gripper and verified bilateral contact, then an actual lift at z=1.20.
3. Retracted reach before each base turn; faced the bin at approximate initial-frame yaw -.3208. Tested six arm/gripper trajectories, using the permitted reset between attempts. Initial weak-grip/different-preparation candidate failed; the five following throws succeeded. Parameters and outcomes are in Artifacts/session-001-trials.md.
4. Compared .25/.12, .27/.13 and .28/.135 second throwing segments. Slower successful candidates landed nearer the center. The repeated .27/.13 pair became the learned program default; the .28/.135 pair remains a single successful experiment.
5. Created and actually exercised Programs/Learned/throw_orange.py on trials 5 and 6. It checks feedback and battery, performs the calibrated arm trajectory, waits for fresh landing feedback, and retracts. Registered its semantic playbook in the index.
6. Preserved the final in-bin result, recorded geometry and results during remaining working time, and prepared the empty arm for travel. Low-warning status was observed at sim time 601.724; no further practice occurred.
7. Returned promptly to the charger with arm target (.22,0,.70). At heading -2.677, drove 1.20, .70 and .20 m segments with intermediate RGB/lidar inspection. Dock request 253ae027a854403eb729ad0b6d16b0c4 completed at sim time 653.896.
8. Performed filesystem closeout after docking. Did not modify default capabilities, protected runtime files, simulator state outside authorized primitives, or prior reports.

## Results and evidence

- **Practice result: complete.** Six trials, five successful inside-bin landings, working window exhausted normally and robot docked. The general task_success field stayed false; this report uses assignment-specific landing feedback and the documented bounded-practice ending condition.
- **Trial 1:** inside=false, forward/left error -1.281/+.428 m, landing time 158.940. Cause uncertain because grip, preparation and trajectory differed from subsequent candidates.
- **Trials 2 and 3:** inside=true at +.135/-.043 and +.173/-.055 m, landing times 236.168 and 303.880. .025 desired closure, .25/.12 second throw segments.
- **Trials 4 and 5:** inside=true at +.055/-.015 m, landing times 378.516 and 448.792. .27/.13 second segments; trial 5 is preserved as raw program output.
- **Trial 6:** inside=true at +.037/-.009 m, landing time 525.332. .28/.135 second segments; raw program output retained. Confidence high for this single outcome, limited for reliability estimation.
- **Visual evidence:** images 3/4 and selected-pixel projections established grasp geometry; image 10 showed the held sphere in preparation; image 11 showed the orange sphere within the blue bin after trial 3; image 15 was inspected after the final throw. Images 8 and 16–18 established charger appearance and approach clearance. Image IDs are provenance and may not remain retrievable in a fresh session.
- **Acquisition:** .025 requested aperture repeatedly produced about .089 measured opening, bilateral contact, effort 19.17 and secure-lift confirmation at z=1.20.
- **Docking:** final status at sim 656.960 showed docked=true, action=null and the matching completed dock request. This proves docking beyond the initial acceptance receipt.
- **Program verification:** two real robot runs succeeded (one default, one parameter variation); Python AST parse passed during closeout. No generalization claim beyond the observed setup.

## Robot / world state at exit

- Robot state: stationary at living-room charger, approximate dead-reckoned pose (-1.880,-.939), yaw -2.677. Empty open gripper; arm target (.22,0,.70), pitch 0; head pan 0, tilt .55. Encoder reach about .140 and lift .269 are raw joint values, not the commanded endpoint coordinates.
- Environment / object state: final orange object left in the bin; no reset after trial 6. Pedestal empty as a result. No household objects manipulated.
- Active or pending actions: none.
- Authority / control state: successful docking closed physical control for this invocation. Only filesystem closeout followed. Next assignment not yet known.
- Safety state: safe and unambiguous; dock confirmed. Last status displayed reset battery 100%, but that does not authorize resuming physical work in this invocation.
- Important uncertainty: map coordinates are noisy estimates; first throw failure mechanism unresolved; flag behavior and throwing performance on other objects untested.

## Durable artifacts created or materially changed

- Programs/Learned/throw_orange.py — new calibrated throw implementation using public primitives only. Runs validated on trials 5/6, default on trial 5; scene clearance remains caller responsibility.
- Playbooks/Learned/ThrowOrange.md — new semantic contract, exact scope, prerequisites, execution, evidence and limits.
- Playbooks/Index.md — registered learned throwing capability; default row preserved.
- Artifacts/session-001-trials.md — six-trial parameter/outcome record and observations; useful for avoiding rediscovery and ungrounded causal claims.
- Artifacts/session-001-trial-5.jsonl and session-001-trial-6.jsonl — raw public status, request IDs, landing feedback and retraction output from learned-program runs.
- Maps/living-room.md — selected-pixel-derived geometry and successful charger approach; navigation actually used, broader room routes not tested.
- LongTermMemory.md — added narrowly scoped, evidence-backed lesson on secure-lift feedback becoming false during lowering while grip persists.
- SummaryOfOnlyNecessaryContext.md — replaced initial continuity with completed objective, confirmed dock state, required fresh sensing and relevant pointers.
- README.md — updated durable tree/map for learned capability, evidence, map and this report; transient Python caches are explicitly omitted.
- This report — first immutable episode report; no older reports rewritten.

## Learned constraints, procedures, or reusable knowledge

- A verified grasp at high pose can remain held at z=.90 with secure_lift_confirmed=false. Bilateral contact, measured opening and visual state are needed to interpret the flag. This repeated observation was promoted to long-term memory with narrow scope; its internal mechanism is not known.
- The orange sphere can be thrown accurately with the documented learned routine when the current geometry matches the practice setup. This was promoted through program, playbook and index rather than copied into long-term memory.
- Smaller desired closure than measured width can produce stable bilateral grasp. The tested sphere values are documented in the playbook, not generalized to other objects.
- Status may show small residual encoder/odometry settling immediately after a completed motion; practice scripts allowed .3–.4 s before subsequent measurements. No universal settling bound was established.
- Observed charger geometry and actual approach were preserved in Maps; current sensing remains necessary.

## Failures and negative results

- rg was unavailable; filesystem searches used find thereafter.
- Robot image tool initially returned a text string containing a data URL. First attempts did not display pixels; the URL was then extracted and displayed. All subsequent image inspections used that method. No visual effect was inferred from the failed display attempts.
- Trial 1 missed substantially. Its feedback landing time preceded trajectory completion; the reason was not isolated. Do not assert the grip strength alone caused the miss.
- No failed docking, rejected physical command, or confirmed collision was observed.

## Unresolved work

No required work remains for this bounded practice assignment. Research uncertainties are optional future work: isolate trial 1 failure, assess variability over more trials, retest the .28/.135 candidate, and calibrate other geometries if future assignments authorize them. Next household/practice assignment must be read from fresh status. No guaranteed future invocation is assumed.

## Corrections / supersessions of earlier reports

None; this is the first immutable report.

## Summary update

Replaced operator-supplied first-session text with the completed practice outcome, confirmed dock/arm/gripper state, approximate pose, fresh-observation requirement, unknown next assignment, and learned artifact pointers.

## Session ending

- Task status: complete — bounded throwing practice, return and docking all completed.
- Reason for ending: ordinary battery warning, successful physical docking and finished filesystem closeout.
- Robot left in safe unambiguous state: yes.
- Anything a future session must verify immediately: current assignment, actual dock-area pose and clearance using fresh status/RGB-D; backstop is ahead of the parked robot.
