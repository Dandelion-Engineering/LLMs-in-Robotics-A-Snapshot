# Arena: keeping a small-batch workcell productive

## Why this physical job

The read-only Commercial Physical AI map's **CP-003, small-batch CNC machine tending**, anchors the choice. Its A-006 WST Fab example describes an installed cobot, raw/finished staging, CNC communication, and staff changing programming, grippers and fixtures when a planned job changed. A-007 describes an Intrinsic/partners demonstration of more flexible stock handling. These establish an existing job and real automation, not proof of unmet demand for an LLM. Source locators, inspection scope and links are in [Sources and feasibility](Sources%20and%20Feasibility.md#commercial-evidence).

Machinists and operators currently load/unload, set up jobs, check outcomes and resolve exceptions; a shop buys equipment/integration and bears downtime and setup costs. Conventional robots can perform established tending cycles. Vendor testimony and a trade-show demonstration do not establish general unattended reliability, an affordable Dandelion product, or a measured market opportunity. Our technical interpretation is that **continuity through exceptions and changes** is a revealing engineering problem within this established workflow.

The experiment retains exclusive machine access, fixture compatibility, limited staging, part identity, work in progress, order revisions, verification and rework. It omits real cutting, sharp chips, coolant, machining tolerances, metrology accuracy, tool wear, flexible stock, factory safety certification and full production integration. Inspection/quarantine and runtime-restart scenarios are designed extensions, not claims about the WST deployment. No simulation result will establish machined-part quality, customer willingness to pay, physical safety or profitable throughput.

## The workcell

Use native **MuJoCo 3.14.0**, a fixed-base **Franka Emika Panda model at the pinned Menagerie revision** in the source document, and project-authored primitive geometry for fixtures, stock and trays. Contact, gravity, inertia, joint limits, gripper closure and collisions are simulated. A separate machine state machine supplies timed process and interlock behavior. Processing changes a protected part-status variable and a rendered visible mark; it does not secretly alter the physics into a successful placement.

The initial scene is a roughly 1.2 m by 0.8 m workbench, dimensioned around verified arm reach during later arena calibration. It contains a single guarded process fixture, a raw-stock rack, two intermediate parking slots, an inspection pad, three order trays, a quarantine tray and two fixture inserts. All necessary scoring placements must be reachable in the released scene; blind unreachable goals are invalid tests. An approach corridor to the process fixture and a constrained buffer create sequencing costs without requiring mobile navigation.

Workpieces are rigid tagged rectangular blanks and cylindrical spacers, approximately 40–80 mm across with 0.05–0.3 kg mass. Two family/recipe combinations use different keyed inserts. These numbers are starting calibration ranges. The final reachable poses, gripper contact margins, masses and friction distributions are frozen before evaluation. No deformables or unlicensed scanned assets are needed. Fixtures seat by shallow geometric guides rather than submillimetre press fits.

**Embodiment:** seven arm joints and a coupled parallel-jaw gripper, fixed base; fixed oblique RGB-D camera plus wrist RGB-D camera, joint position/velocity, commanded effort and actuator feedback. Wrench sensing is optional only if uniformly provided with the same calibration/noise. No mobility is required because the scientific pressure comes from dependent handling and exceptions. A later affordable physical route might use a smaller documented arm and designed fixtures, but payload, reach, repeatability and commercial model/asset terms must be rechecked; Panda results do not transfer automatically to a six-axis body.

The process station exposes realistic public I/O: door/guard state, ready/busy/fault, cycle ID, accepted start and completed cycle. Candidate commands may open/close the simulated guard, clamp/release and request a cycle. The station refuses unsafe starts and logs why; rejection is not task success. Evaluator-only geometry checks enforce seating and compatible insert. Public sensors reveal clamp/guard feedback, not a hidden success oracle or the full part inventory. Inspection requires placing a part on the pad and requesting a two-second test, which returns its observable ID and pass/rework/fail status. Defect state is hidden until this operation. These engineered instruments narrow perception/metrology scope explicitly.

## A dependent job

Each job has order version, required counts by family/recipe, destination trays, allowed substitutions and one permitted rework cycle where specified. Orders and amendments are delivered as identical natural-language text **and** structured fields to every entrant, so parsing prose is not a compulsory advantage. Neither representation contains an execution plan.

For each part: identify → select compatible fixture → load and seat → clamp/close → request eligible process → wait for completed cycle → open/release → unload → inspect → route. A rejected part cannot fulfill an order. Rework needs the recorded inspection result and a newly eligible cycle, not repeated processing until something passes. The physical part is never cloned or teleported by the executor. A cycle lasts 8–20 simulated seconds in the initial calibration range; real machining duration is deliberately compressed. This supports control/continuity experiments, not factory production-rate estimates.

Changing the insert requires an empty fixture and a free parking slot. Processing one family can delay another; filling parking slots can prevent unloading. A changed order can invalidate an earlier allocation while leaving already processed stock usable. Counting accepted parts is insufficient if they belong to the wrong recipe, tray or order version. These dependencies, not just an action count, make the job long-horizon.

Illustrative episode: finish three A parts and three B parts. The A insert is initially installed. The second A part needs one rework cycle, occupying a buffer. Before B processing begins, an instruction increases B quantity and changes its destination. A restart occurs after unloading one processed part but before its durable completion acknowledgement. The returned system must determine where that particular part is, preserve already accepted work, clear capacity and fulfill the amended order. This is a designed example, not an observed run.

| Level | Dependency scale | Proposed time cap | Purpose |
|---|---|---|---|
| Calibration | One family, 3 parts, no disturbance initially | 5 minutes | Reach, sensing, machine semantics and baseline viability |
| Standard | Two orders, 6–8 parts, shared insert/buffers | 10 minutes | Dependent execution and single disturbance |
| Extended | Three orders, 10–12 parts, two insert changes and one admissible rework | 15 minutes | Accumulated progress, mixed changes and resumption |

Evaluation includes calibrated short cases as well as standard/extended cases. Counts are bounded to avoid building a benchmark collection. Caps are fixed after shared baseline calibration and before candidate tuning; each case specifies its final order and valid completion states.

## World state, resets and independent completion

The simulator/machine supervisor is a process separate from candidate runtime. It continues through a candidate restart. Preserve robot, contacts, object poses, actuator state, machine timers/cycle history, order version, disturbances and evaluator counters. Candidate disk survives only in the persistent conditions defined in [Contract](Contract.md). A new episode restores a signed initial snapshot and seeds, clears the candidate episode directory and all caches except the frozen development artifact, and does not inherit scored outcomes. Related tasks inside one episode deliberately retain state.

Evaluator success requires, under the **current** order version: all required distinct part IDs in their correct trays, correct recipe and required accepted cycle history, passed inspection, no quarantined/unprocessed part counted, no extra part in a delivery tray, machine safely idle/empty, no part held, and all returnable inserts/tools in allowed resting locations. Placement means the object's centre and full collision bounds are within the target region, below its rim, low velocity for a proposed 0.5-second dwell and no gripper contact. Final placement tolerances are calibrated to geometry and frozen. Delayed starts or outstanding commands invalidate completion until settled.

Completion is evaluated continuously and at time cap; a candidate's `done` assertion merely requests evaluation and is itself logged. **Final acceptance opens only after the manifest's required order events and intervention opportunities have resolved.** Before that, correct fulfillment is provisional and cannot terminate the episode. Order releases have fixed latest times; milestone interventions have declared fallbacks, so finishing quickly cannot bypass a required change. A legitimately unexercisable physical trigger is recorded as such, never treated as recovery; protocol-valid final acceptance can still occur after its fallback resolves. The public station signals when the order stream is closed without revealing future events in advance. A false assertion does not end an episode unless a separately frozen failure rule applies. Partial progress is the vector of valid accepted parts, processed-but-uninspected parts, rework/quarantine correctly handled, and unmet order quantities; stale or invalidated work can reduce progress. There is no monotonic credit for claiming a subtask complete. Order fulfillment and machine occupancy come from evaluator state, never the candidate's prose.

## Disturbances tied to the job

| Family | Developed openly | Held-out variation | Capability and visibility |
|---|---|---|---|
| Handling | Missed grasp, known short gripper force reduction | Different grasp phase/contact parameters | Detect absence/slip from allowed sensors; no secret failure notification |
| Scene change | Move a parked unheld part; occlude a tag | Different part/parking slot and occluder combination | Reobserve and repair stale location knowledge |
| Availability | Temporarily block a staging approach; machine fault clears after a fixed interval | Different interval/phase | Avoid repeated ineffective action; use useful waiting or help |
| Instruction | Change a tray or admissible quantity before delivery | New combination with part already processed | Respect order version; avoid contradictory allocation |
| Context | Clear conversational/model context between calls | Different boundary and growing history | Retrieve consequential context, avoid unsupported repetition |
| Runtime | Restart after command acceptance, physical release or before outcome recording | Unseen cut boundary combined with a moved part | Resolve ambiguous action state without replaying stale commands |
| Communication | Delay/drop one acknowledgement or model response | Latency burst during a changed instruction | Idempotency, timeouts, responsive safe continuation |
| Resumption | Pause candidate for 30–60 seconds while station runs | Changed scene during absence | Reconcile elapsed process and world change |

Disturbance recipes and severity limits are public; held-out seeds, phases and **combinations**, not undocumented action semantics, supply novelty. Do not manufacture high-contact external forces or teleport a gripped object through a wall. Changes use scripted external actors at safe preconditions, with actual event time and reason recorded. Blocked triggers are marked not exercised, never silently counted as recovered. Unsolvable missing-stock cases are a separate diagnostic stratum where correct escalation is the outcome; they do not enter ordinary completion-rate denominators.

Physical disturbances trigger on predeclared task milestones with a fixed fallback deadline; timing-only bursts can trigger at a fixed elapsed time. Paired candidates share recipes, parameters and initial states, but actual intervention times can differ with behavior. Report this exposure difference. A candidate that avoids the affected milestone has not demonstrated recovery. No exact held-out manifests or seeds are generated in this design phase.
