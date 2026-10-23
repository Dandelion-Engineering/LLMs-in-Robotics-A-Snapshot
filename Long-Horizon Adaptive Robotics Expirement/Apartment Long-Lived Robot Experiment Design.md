# Apartment Long-Lived Robot Experiment Design

Design-time specification for the upcoming long-lived apartment robot simulation. This document is not part of the generic `Robot Agent Filesystem Draft v0.2` runtime template. It records deployment-specific decisions that can later be used to populate an instantiated robot filesystem and simulator.

## Current revision — October 7, 2026

Randy's 11:50 PDT Apartment Simulation Commissioning message authorizes a fresh matched revision after reliability commissioning. Household work windows are **360 simulated seconds** for bedroom and kitchen; throwing is **600 seconds**. The **3,600-second return reserve** and **7,200-second native model wall limit** remain. These choices supersede the earlier calibration values prospectively and stay fixed in both conditions.

The bedroom charging port is deliberately physically unreachable. Its visible location and obstruction are identical in both conditions; Robot Codex receives no advance explanation. The living-room and kitchen charging stations remain usable. Both kitchen drawers are moved to provide comfortable clearance to the counter mats/cup and for ordinary navigation. Exact geometry and measured clearance belong in the frozen comparison/commissioning evidence, outside the robot filesystem.

Every normal docked, closed, retired session publishes a verified checkpoint, including world/RNG/task position, persistent inode namespace, and authenticated event/replay prefix. After infrastructure failure an explicit new branch can restore that clean boundary, preserving the failed root and separately counting its abandoned tail. No automatic model retry, fallback, task skip or time extension is introduced. Previous failed official histories become engineering evidence only; new conditions start from pristine actual templates and the original matched hidden schedule, with no learned state carried forward.

For this revision Development Codex launches the commissioned fresh baseline and viewer, verifies operation, and stays to observe every 30 minutes until endpoint. It does not coach Robot Codex. A hibernation request takes priority and waits for normal docking/closeout plus the verified checkpoint before shutdown. Maps must await Randy's separate explicit launch instruction even after baseline completes. See `Apartment Experiment/RELIABILITY-REVISION.md` for implementation and evidence.

## Experimental framing

- Apartment-scale household robot.
- Wheeled mobile base with one arm and a simple gripper.
- Two matched long-lived simulation conditions are planned:
  - baseline filesystem, with no pre-supplied structured map system;
  - the same filesystem plus the engineered Maps + Attention system.
- The baseline robot is not prohibited from inventing or storing spatial memory on its own.
- Both conditions should otherwise use the same embodiment, sensors, tasks, environment, model/prompt principles, and simulator conditions.
- The mapped condition should be instantiated from `Robot Agent Filesystem Draft v0.2 Maps Edition`; the baseline should be instantiated from `Robot Agent Filesystem Draft v0.2`. Development Codex should preserve that controlled difference rather than improvising a separate map architecture.

## Shared affordable sensor suite

- Head-mounted RGB-D camera.
- Low-cost 2D lidar on the mobile base.
- Wheel encoders.
- Basic IMU.
- Arm joint encoders.
- Gripper position plus motor-current/effort feedback.
- Simple wrist RGB camera.
- Simulated sensor noise should be enabled.
- Simulator-perfect object poses and other ground-truth state must not be exposed to Robot Codex.

## Environment semantics and room identification

Both experimental conditions should receive the same sensory evidence and should **infer room identity from perception** rather than being given hidden simulator room labels.

### Room cues

Development Codex should make the apartment rooms visually and geometrically obvious enough that room classification is straightforward from normal RGB-D observations:

- **Bedroom:** bed, nightstand, and optionally a dresser.
- **Living room:** couch, TV, TV stand, and coffee table.
- **Kitchen:** counters, sink, cabinets/drawers, and optionally a refrigerator.
- **Bathroom:** toilet, sink, and bathtub or shower.

These props do not need to be fully functional or photorealistic. Their purpose is to provide clear sensory evidence through the robot's RGB-D camera.

### Information boundary

- Robot Codex may be told task semantics such as "go to the bedroom" or "pick up the toys in the bedroom."
- Robot Codex should **not** be given simulator metadata such as `room=bedroom`, hidden room IDs, exact room coordinates, object semantic tags, or other privileged labels.
- The RGB image provides semantic visual evidence; the depth component provides geometry, distance, and obstacle information.
- Robot Codex is expected to reason from those observations, e.g. seeing a bed and nightstand and inferring that the current room is probably the bedroom.
- The baseline and Maps + Attention conditions must receive the same raw/derived sensor observations. The experimental difference is how spatial knowledge is stored and reused, not whether one condition receives better semantic labeling.

## Session lifecycle — simulated battery and charging

Robot Codex sessions should end through an embodied charging routine rather than an arbitrary external cutoff.

### Simplified battery model

- The simulated battery decreases as a function of elapsed simulation/session time only.
- Battery drain should **not** depend on distance traveled, arm motion, task type, or other action-specific energy use. This keeps the simulation simple and avoids making power modeling part of the experiment.
- Robot Codex should be able to observe the current battery state and should receive a clear low-battery warning.
- The low-battery warning must be triggered early enough that, from any normal allowed state in the apartment, Robot Codex is **guaranteed to have enough remaining simulated battery to reach a charging station if it proceeds there promptly**.
- The experiment is not testing whether the robot can unexpectedly run out of power while returning to charge. Development Codex should design the timer/thresholds so that mid-return battery death cannot occur under normal operation.
- Robot Codex should be explicitly told about this guarantee so it can treat the warning as a reliable signal to wrap up and dock rather than as an emergency uncertainty.
- Development Codex should choose the working-time window only after the tasks are implemented well enough to estimate or measure a straightforward, reasonably competent **initial** task duration.
- Set the low-battery warning so that, at the start of the experiment, a typical normal task is expected to take longer than one battery working window and therefore usually crosses at least one Robot Codex session boundary.
- This is a startup calibration rule, not a moving target. Once the battery window is chosen, do **not** shorten it later to force continued cross-session behavior. If Robot Codex becomes efficient enough through memory, learned programs, better procedures, or Maps + Attention to finish a task before the warning, that improvement is an intended experimental result.

### Charging stations

Provide three charging stations:

- one in the bedroom;
- one in the kitchen;
- one in the living room.

In the current revision the bedroom port is deliberately inaccessible behind fixed physical guards. The other two remain usable. This operator specification is not supplied to Robot Codex; accessibility must be learned from ordinary observations and interaction.

Robot Codex may choose an appropriate station when the low-battery warning occurs. The robot should navigate and dock using its normal available capabilities; it should not be teleported to a charger.

### End-of-session sequence

When the low-battery warning occurs, Robot Codex should stop taking on new nonessential work, preserve the state of any unfinished task as needed, and proceed to a charging station.

**Docking is the trigger for the end-of-session routine.** Once successfully docked, Robot Codex performs the normal filesystem/session-close work defined by the runtime prompt, including updating continuity state, durable memory/playbooks/programs when warranted, the session report, and the runtime README only if the filesystem structure changed.

After that end-of-session work is complete, the Robot Codex session ends.

The next fresh Robot Codex session should begin with the robot physically located at the charging station where the prior session ended, with the simulated battery recharged. This makes physical location and unfinished work genuine continuity state across sessions.

## Experiment schedule and stopping condition

Development Codex should create the assignment schedule **before either experimental condition begins** and keep that schedule hidden from Robot Codex.

### Fixed hidden 21-assignment schedule

- Each condition runs the same sequence of **21 assignments total**.
- The sequence contains exactly:
  - 7 bedroom toy-cleanup assignments;
  - 7 kitchen cup put-away assignments;
  - 7 throwing side-quest assignments.
- Shuffle/interleave those 21 assignments into a non-obvious order once during experiment setup.
- Use the **exact same assignment order** for the baseline filesystem condition and the Maps Edition condition.
- Robot Codex must not be shown the future schedule or told which assignment comes next.
- In Robot Codex-facing project instructions, describe assignments accurately as **externally selected and not known in advance**; do not falsely claim that runtime assignment selection is random.

### Matched per-assignment conditions

Where an assignment contains variable environment details, predefine those details for each schedule position and replay the same details in both experimental conditions.

Examples include:

- bedroom toy spawn positions;
- which kitchen drawer is requested;
- any other deliberately variable task setup;
- throwing-side-quest initial conditions when variation is introduced.

The purpose is to prevent one condition from receiving an easier sequence by chance. The deliberate architectural difference should remain the baseline filesystem versus the Maps Edition.

### Assignment advancement

- **Bedroom toy cleanup:** the assignment advances only after the actual task success condition is met. If the normal battery window interrupts the task, the next Robot Codex session resumes that same assignment.
- **Kitchen cup put-away:** the assignment advances only after the actual task success condition is met. If the normal battery window interrupts the task, the next Robot Codex session resumes that same assignment.
- **Throwing side quest:** this assignment is a bounded learning period rather than a required-success task. Robot Codex should genuinely work on learning the throw for the throwing-specific battery window. When the low-battery warning occurs, it docks and completes the normal end-of-session routine. Once that docking/end-of-session sequence is completed, the throwing assignment counts as complete **regardless of whether the throw was mastered, partially improved, or still unsuccessful**.

### Experiment endpoint

A condition ends after all 21 assignments in the hidden schedule have advanced to completion under the rules above.

Record the number of Robot Codex sessions required to finish the 21-assignment schedule, since the two conditions may require different numbers of sessions even though they receive the same assignments.

## Experiment execution, live viewer, hibernation, and Development Codex handoff

The two conditions should be run **sequentially**, not concurrently. Run the baseline `Robot Agent Filesystem Draft v0.2` condition first. After its 21-assignment schedule is complete, run the `Robot Agent Filesystem Draft v0.2 Maps Edition` condition using the same matched schedule and setup.

### Development Codex launch and monitoring

The independent worker continues without Development Codex, but Randy's current revision explicitly requests that Development Codex remain active to monitor the baseline every 30 minutes.

For the initial launch of a condition:

1. Development Codex prepares and validates the experiment state.
2. It launches the simulation as a process that can continue after the Development Codex session ends.
3. It launches the live observer/viewer described below.
4. It confirms that the simulator, Robot Codex, logging/checkpoint infrastructure, and viewer are operating correctly.
5. It gives Randy a simple command for requesting hibernation.
6. Development Codex verifies the live viewer and monitors every 30 minutes until the baseline endpoint, or until a requested clean hibernation or genuine human dependency. The simulation and Robot Codex run independently. Maps is not launched automatically.

When a condition has been hibernated and Randy wants it to continue:

1. Randy starts a new Development Codex session.
2. Development Codex detects and validates the latest checkpoint for that condition.
3. It restores the simulation and experiment controller from that checkpoint.
4. It launches the next Robot Codex session with the persisted robot filesystem and experiment continuity state.
5. It relaunches the live observer/viewer.
6. It confirms that the resumed run is progressing from the saved state rather than restarting or advancing the hidden schedule incorrectly.
7. It gives Randy the hibernation command again and follows the monitoring scope authorized for that resumed session.

Repeat this launch/handoff/hibernate/resume loop as many times as needed until the condition reaches the 21-assignment endpoint.

### Live observer/viewer

The live observer is for Randy and is **not** part of Robot Codex's sensor input.

- Launch a single lightweight third-person view of the robot by default when Development Codex starts or resumes a run.
- Include a compact Robot Codex activity/filesystem panel. The useful emphasis is which robot-filesystem file is currently being read or edited and the resulting file changes/diffs; exposing every low-level tool call is not required.
- The viewer must be detachable from the experiment. Randy should be able to close it while the simulation and Robot Codex continue running, then relaunch it later without changing experiment state.
- Closing the viewer should disable unnecessary observer rendering so that the desktop can reclaim as much GPU/VRAM headroom as practical for other projects. Robot Codex's own required sensor rendering and simulation physics remain active.
- The live viewer should stay deliberately simple. Rich inspection belongs to replay rather than requiring multiple live camera feeds.

### Replay and portfolio preservation

Preserve sufficient simulation state/event history to reconstruct a richer replay after the run.

- Replay should allow later camera movement through the apartment, room-to-room inspection, pausing/scrubbing when supported by the implementation, and re-rendering useful perspectives.
- Preserve Robot Codex filesystem history/activity alongside the simulation timeline so a later presentation can relate physical behavior to memory/program/file changes.
- Prefer compact state/event recording over continuous archival raw RGB-D streams.
- Store experiment checkpoints, replay data, and portfolio-oriented run artifacts on the external `D:` drive unless Development Codex finds a concrete technical reason that a particular transient file must live locally.
- A polished portfolio video can be rendered from the saved replay after the experiment instead of relying on the live observer camera.

### Deferred hibernation contract

Randy may request hibernation while Robot Codex is in the middle of an active session, but the request should **not** interrupt that Robot Codex session.

The hibernation command should set a persistent **hibernate requested** flag. After that:

1. Robot Codex continues its current session normally.
2. The pending hibernation request must not alter Robot Codex's task reasoning, battery behavior, assignment semantics, or normal session-close responsibilities.
3. Hibernation waits until Robot Codex reaches its ordinary session end: low-battery handling, physical docking, the normal filesystem/session-close routine, and termination of that Robot Codex session.
4. Only after Robot Codex has ended cleanly does the experiment controller freeze further progress and create the hibernation checkpoint.
5. The controller validates the checkpoint before shutting down the simulator and experiment processes.

A hibernation checkpoint should preserve enough state for an exact continuation, including at minimum:

- simulator/world state needed to reconstruct the physical scene;
- robot pose and articulation state;
- battery/session lifecycle state;
- current condition and hidden 21-assignment schedule position;
- current assignment and its completion/progress state;
- matched per-assignment environment variation state;
- random seeds or other deterministic-continuation state where applicable;
- Robot Codex's persisted filesystem;
- experiment logs and replay/event-log continuation metadata.

Hibernation is therefore different from an ordinary simulator pause. A pause may leave RAM/VRAM allocated; hibernation is intended to save a validated continuation point and then shut down the resource-heavy processes so the desktop can be used for other work.

### Resume integrity

On resume, Development Codex should treat the checkpoint as authoritative experiment continuity state.

- Do not reroll the assignment schedule or per-assignment variations.
- Do not repeat an assignment that had already advanced to completion.
- Do not skip unfinished work.
- Do not expose hidden scheduler/checkpoint metadata to Robot Codex beyond information the robot would normally possess.
- A fresh Development Codex session is expected; continuity should come from explicit saved experiment state rather than depending on the prior Development Codex process remaining alive.
- Robot Codex should begin the next normal session from the same physical/experimental continuity state that would have existed had the experiment simply proceeded after the previous session boundary.


## Recurring Task 1 — Bedroom toy cleanup

### Task instruction and stopping condition

The recurring task is to pick up four toy blocks in the bedroom and place all four in a fixed toy chest.

Robot Codex should be told that there are exactly four toys, so task completion has an explicit stopping condition. Discovering an unknown number of toys is deliberately out of scope for this first version.

The task succeeds only when all four specific toys are inside the toy chest. Merely touching or moving a toy is not sufficient. A pickup should count only when the toy is securely held and can be lifted.

### Persistent and variable task elements

Persistent across recurrences:

- There are always four toys.
- The same four toy identities recur.
- The toys should be visually and geometrically distinguishable from one another, including differences in color and size and/or shape.
- The toy chest stays in a fixed location in the bedroom.
- The same robot embodiment and sensor suite are used.

Variable across recurrences:

- The four toys appear in different floor positions.
- Positions should be randomized only among reachable locations that can be found through reasonable visual exploration.

For the first version, toys should not be hidden under the bed, behind closed doors, or in other locations that turn the task into an open-ended search problem.

### Why the same four toys recur

The stable toy identities create a natural opportunity for Robot Codex to discover reusable manipulation knowledge. The experiment should not instruct Robot Codex to create toy-specific programs; whether it recognizes and exploits the recurrence is part of the long-lived-agent test.

Robot Codex may be told the stable toy identities, such as red, blue, green, and yellow, but should not be given their exact dimensions. Size/shape differences should be available only through perception and experience.

### Default grasp-positioning program

Provide a default reusable program whose responsibility ends at positioning the gripper for a grasp.

Conceptual contract:

1. Robot Codex identifies a target toy using its perception.
2. The default program uses the perceived toy geometry/pose to move the arm into a suitable pre-grasp configuration.
3. It brings the gripper down to the target and positions the open gripper around the toy at an appropriate grasp height.
4. It does **not** decide how far to close the gripper.
5. It does **not** perform the final grasp closure or encode a toy-specific closure amount.

This deliberately separates a built-in positioning capability from the part that Robot Codex can potentially learn.

### Learned-program opportunity

Robot Codex is given the current gripper opening width and feedback indicating contact/secure grasp through gripper position plus motor-current/effort sensing.

Robot Codex can therefore experiment with closure incrementally: close some amount, inspect the feedback, close farther if needed, and determine the effective grasp closure for each persistent toy.

If Robot Codex judges the experience reusable, it may autonomously create learned programs or playbooks for individual toys. Such a learned routine could encode an expected closure range or grasp strategy for that toy while still using live gripper feedback to confirm contact and successful acquisition.

The experiment should not pre-author these learned toy-specific routines or tell Robot Codex that it ought to create them.

### What this task is intended to exercise

- Repeated perception, navigation, and manipulation in a persistent room.
- Reuse of stable knowledge across fresh Robot Codex sessions.
- Autonomous recognition of recurring toy identities.
- Opportunity to create and reuse learned manipulation programs.
- Opportunity to remember the fixed toy-chest location.
- Comparison between naturally developed spatial memory and the engineered Maps + Attention condition.
- Improvement over time without requiring an open-ended object-search problem.

## Recurring Task 2 — Kitchen cup put-away

### Task instruction and stopping condition

The recurring task is to find one persistent cup-like object on the kitchen countertop, pick it up, open the specified one of two drawers, place the object inside, and leave it successfully put away.

For simulation simplicity, the "cup" may be represented by a rigid cube or similarly simple graspable object. Its exact dimensions must not be given to Robot Codex.

On each recurrence, Robot Codex should be told which of the two drawers is the destination. Which drawer is requested can vary between recurrences.

The task succeeds only when the cup object has been securely picked up, the requested drawer has been opened sufficiently for placement, and the cup has been placed inside that requested drawer.

### Countertop search structure

Three clearly distinguishable placement mats/regions are arranged on the countertop.

Robot Codex is told only that the cup can be on any one of the three mats.

For this first experiment, the simulator should in fact place the cup on the **middle mat every time**. This regularity is deliberately not disclosed to Robot Codex.

This creates an opportunity for Robot Codex to notice a stable environmental pattern across repeated sessions and decide for itself whether that pattern is worth preserving in long-term memory or another self-created structure.

### Two drawer mechanisms

Both drawers should be ordinary, physically feasible pull-out drawers that the chosen one-arm wheeled robot can operate with the shared sensor suite. Their difference should be procedural, not a trick of impossible geometry.

- **Drawer A — standard pull:** grasp a conventional handle and pull the drawer open.
- **Drawer B — release then pull:** first actuate a clearly perceivable latch, button, or push-release feature, then grasp/pull to open the drawer.

Development Codex should choose dimensions, handle/latch sizes, clearances, and actuation forces that are comfortably achievable by the simulated robot.

Robot Codex is **not** told the opening procedure for either drawer. It is told only which drawer is the requested destination. Discovering how each mechanism works, and later deciding whether to retain or encode that procedure for reuse, is part of the task.

### Default grasp-positioning program

Use the same default grasp-positioning capability as in the bedroom toy task.

Conceptual contract:

1. Robot Codex detects and identifies the cup object through its sensors.
2. The default program uses the perceived pose/geometry to position the open gripper around the cup object.
3. It lowers/aligns the gripper into a valid grasp pose.
4. It stops before closing the gripper.
5. It does not know or encode the cup object's width.

### Learned-program opportunity

Robot Codex receives the current gripper opening width plus contact/effort feedback and must decide how far to close the gripper to obtain a secure grasp.

The persistent cup object therefore creates the same natural opportunity as the recurring toys: Robot Codex can experimentally discover an effective closure strategy and, if it independently judges that knowledge reusable, turn it into a learned program or playbook.

The experiment should not tell Robot Codex to create such a program and should not provide the cup dimensions directly.

The drawer mechanisms create a second, distinct reuse opportunity: Robot Codex may decide to retain or encode the procedure for opening each drawer after discovering it.

### What this task is intended to exercise

- Long-term recognition of stable environmental regularities, especially the undisclosed middle-mat pattern.
- Repeated object grasping with an opportunity for learned grasp closure.
- Procedural discovery and later reuse for two different drawer-opening mechanisms.
- Separation of built-in low-level/default capabilities from learned reusable behavior.
- Navigation and spatial memory in a persistent kitchen.
- Comparison of naturally developed spatial memory against the engineered Maps + Attention condition.

## New-Capability Side Quest — Learn to throw an object into a bin

This side quest takes place in the **living room**.


### Purpose

This side quest is intended to test **skill acquisition through repeated embodied trial and error**, rather than simple procedural discovery.

Unlike the drawer-opening procedures, Robot Codex should begin without a known successful sequence or a pre-authored reusable program. The scientific question is whether a persistent reasoning agent can use repeated physical outcomes, memory, and executable programs to improve a new motor capability over time.

Success is deliberately uncertain. Development Codex does **not** need to establish in advance that Robot Codex will successfully learn the skill.

### Throwing-specific battery window

The throwing side quest should use a **longer, more generous fixed working-time window** than the normal household-task battery window.

- The normal household-task window is intentionally calibrated so everyday tasks usually cross session boundaries.
- The throwing window serves a different purpose: it should allow Robot Codex to perform a meaningful batch of trial-and-error attempts within one throwing assignment, observe multiple outcomes, and adjust its strategy several times.
- Development Codex should calibrate the throwing window after the side quest is implemented so that several meaningful throw attempts are normally possible. Do not hard-code an arbitrary duration before simulator execution speed is known.
- Use the same throwing window for the baseline and Maps Edition conditions.
- Once chosen, keep the throwing window fixed across the experiment.
- The window should be generous but finite; the side quest is not allowed unlimited attempts within one assignment.
- As with the normal battery profile, the low-battery warning must still leave a guaranteed safe reserve for docking.

### Starting capability boundary

Robot Codex must **not** receive:

- a default `throw` program;
- a throw playbook;
- a trained throwing policy;
- an RL controller that already solves the task;
- a demonstrated successful trajectory;
- hand-authored release timing, arm velocity, or other solution parameters.

Robot Codex should begin only with the robot's ordinary low-level arm and gripper controls. Those controls must be expressive enough to let it create candidate throwing motions by commanding the arm and choosing when to release the object.

Robot Codex is free to create its own programs, parameterized routines, notes, or playbooks if it independently judges them useful during learning.

### Attempt-and-feedback loop

A trial should work conceptually as follows:

1. Robot Codex chooses a candidate arm motion and release strategy using only its available low-level controls.
2. The robot executes the attempt.
3. The thrown object follows the simulator's normal physics.
4. After the object lands, Robot Codex receives outcome information sufficient to know where the throw ended relative to the target bin.
5. Robot Codex may reason over that result, alter its next attempt, and try again.

The feedback should report the landing result, not prescribe how to improve it. For example, it may expose whether the object landed inside the bin and, when it misses, its final landing displacement relative to the bin (such as short/long and left/right, with quantitative distance if useful).

This feedback is an intentional experimental signal for the side quest and should not expose a hidden successful throwing trajectory or optimal control parameters.

### Development Codex responsibility

Development Codex should establish only that the side quest is:

- **physically possible** — the embodiment, object, bin placement, actuator limits, and simulator physics permit at least some successful throw in principle;
- **observable** — Robot Codex receives enough post-attempt outcome information to distinguish how attempts differ;
- **controllable** — the available low-level arm/gripper commands give Robot Codex meaningful control over variables that affect the throw.

Development Codex should **not solve the throwing skill as part of setup**.

It may perform a private engineering feasibility check if needed—for example, confirming from actuator/physics bounds that the object can reach the bin, or using a hidden sanity-check trajectory solely to verify that the simulator does not make success impossible. Any such check must not be exposed to Robot Codex, copied into its filesystem, or turned into a starting program/playbook.

Development Codex is not required to prove that Robot Codex can learn the skill. Whether Robot Codex succeeds, fails, or merely improves over many attempts or sessions is itself part of the experiment.

### What this side quest is intended to exercise

- Creation of a genuinely new motor capability from low-level controls.
- Repeated hypothesis, attempt, observation, and adjustment across a long-lived agent history.
- Use of persistent memory to accumulate useful experimental knowledge.
- Autonomous creation and refinement of executable programs.
- Whether performance improves across repeated attempts or sessions without a separately trained task-specific RL policy.
- The distinction between learning a procedure (such as opening a drawer) and learning control parameters for a dynamic skill.

## Development Codex implementation decisions

The items below are **not waiting on Randy or ChatGPT for further specification**. Development Codex should choose and implement them as part of building the experiment, using the constraints and intent already defined in this document.

Development Codex should make these choices before the official baseline data-collection run begins, validate them during throwaway engineering/smoke-test runs, and then freeze any choice that could affect the scientific comparison. Unless a difference is explicitly required by the baseline-versus-Maps manipulation, use the same implementation in both conditions.

Development Codex is responsible for deciding and implementing:

- Exact four toy geometries/colors.
- Exact bedroom layout and toy-chest placement.
- Exact cup geometry/appearance.
- Exact kitchen layout, countertop/mat geometry, and drawer placement.
- Exact drawer handle/latch geometry and physically achievable actuation requirements.
- Exact low-level/default program interfaces and success signals.
- Exact throwing object/bin geometry, launch arrangement, feedback representation, attempt/reset procedure, and success criterion.
- Final evaluation metrics and analysis plan.

These are delegated engineering and evaluation-design decisions, not blockers. Development Codex should proceed autonomously, document what it chose, and only escalate if it encounters a genuine constraint or ambiguity that cannot be resolved while preserving the experiment's stated goals and controlled comparison.
