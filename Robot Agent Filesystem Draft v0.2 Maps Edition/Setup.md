# Setup — Maps Edition

This file is for the agent or operator preparing a new Robot Agent Filesystem deployment before the first robot-agent invocation.

## Source-only file

**Read `README.md` first.** It defines the runtime filesystem structure and the role of each component.

This `Setup.md` file is **not part of the robot's runtime filesystem**. Use it while preparing an execution, simulation, campaign, or deployment, then exclude it from the instantiated runtime copy before Robot-Codex or any other robot reasoning agent is launched.

The deployed robot filesystem should begin with `README.md` already present and accurate. The first robot-agent session should not need to reconstruct its filesystem map.

## Preparation procedure

Before launching any robot-agent execution or simulation:

### 1. Instantiate the runtime filesystem

Create an execution-specific copy of the runtime template.

Include the runtime files and folders described in `README.md`.

Do **not** include this `Setup.md` file in the instantiated runtime filesystem.

Do not carry unrelated template-development notes, campaign-development chats, or source-only instructions into the robot's runtime context.

### 2. Populate `RobotDetails.md`

Replace the embodiment skeleton with verified information for the actual robot or simulator configuration.

At minimum, establish:

- robot/platform identity and configuration revision;
- kinematic structure and important coordinate frames;
- end effectors;
- sensors and perception interfaces;
- the complete primitive action vocabulary available to the reasoning agent;
- for every primitive: invocation contract, inputs, units/frames, returned status or observations, limits, rejection/failure behavior, and important safety or authority constraints;
- physical and safety limits;
- calibration/geometry information needed for operation;
- relevant compute/runtime facts;
- stable robot-specific quirks.

Do not copy low-level controller, driver, motor-control, or simulator implementation code into the agent filesystem merely to expose a primitive. The implementation remains in the robot/simulator stack; `RobotDetails.md` documents the agent-facing contract.

### 3. Populate `ProjectDetails.md`

Replace the project skeleton with the actual deployment and task context.

At minimum, establish:

- project/deployment identity;
- operating setting;
- mission and task family;
- source of current tasks;
- success, failure, completion, and handback conditions;
- authority boundaries and prohibited actions;
- project-specific safety constraints;
- project interfaces and authoritative sources of truth;
- required evaluation and evidence;
- any additional startup resources required for this deployment.

Keep robot embodiment facts out of `ProjectDetails.md`; those belong in `RobotDetails.md`.

### 4. Populate default reusable capabilities

Inspect the actual robot/simulator stack and any reusable higher-level routines supplied for the deployment.

For every reusable higher-level capability that should be available from the beginning:

- create an appropriate semantic playbook in `Playbooks/Default/`;
- register it in `Playbooks/Index.md`;
- if its executable implementation belongs in the agent filesystem, place that program in `Programs/Default/` and point the playbook to it;
- if the implementation remains inside the robot software stack, point the playbook to that built-in capability instead.

Do not turn primitive low-level controls into playbooks. Primitive controls belong in `RobotDetails.md`.

Do not invent capabilities that have not actually been supplied, implemented, or verified.

If there are no default higher-level playbooks or programs, leave the corresponding libraries empty and keep the index truthful.

### 5. Initialize the Maps + Attention subsystem

Keep the map architecture present but the learned apartment map unpopulated before the first robot-agent session.

- Retain `Maps/README.md`, `Maps/Apartment.md`, `Maps/RoomMapTemplate.md`, and `Maps/Rooms/README.md`.
- Do **not** seed discovered rooms, room connections, doorways, furniture locations, fixtures, charging-station locations, or other spatial knowledge from simulator metadata, scenario source code, operator knowledge, hidden labels, or ground-truth coordinates.
- Leave `Maps/Apartment.md` in its undiscovered initial state.
- Do not create deployment-specific room maps in `Maps/Rooms/` before the first Robot-Codex session.
- Robot Codex must build the map from the same perception available during runtime.
- The map condition may know the map structure and map-maintenance rules from launch; it must not receive privileged knowledge of the environment.

This initialization boundary is important for controlled comparisons against a non-map filesystem: the intervention is the supplied Maps + Attention architecture, not preloaded knowledge of the apartment.

### 6. Initialize current continuity state

Populate `SummaryOfOnlyNecessaryContext.md` with the minimum context required for the first robot-agent session to begin correctly.

The initial summary must explicitly state:

- that the upcoming invocation is the **first robot-agent session** for this deployment;
- that there are no prior robot-agent session reports for this deployment;
- that this initial summary was populated before launch by the **deployment operator**, not by a prior robot-agent session.

Use **deployment operator** as the source label whether the setup work was performed directly by a person or by an authorized setup/development agent acting on the operator's behalf.

Include the initial objective, known current state, unresolved setup-relevant work, important constraints, and immediately relevant artifact pointers.

The first robot-agent session should treat operator-populated continuity as setup-provided context and reconcile any world-state claims against current observations before relying on them.

Do not turn the summary into project documentation or historical narrative.

### 7. Initialize long-term and episodic memory

For a genuinely fresh deployment:

- leave `LongTermMemory.md` with no learned memories unless there is legitimate pre-existing learned knowledge that belongs there and is not already represented by another startup file;
- begin `SessionReports/` with no historical session reports;
- retain `SessionReports/SessionReportTemplate.md` so the robot agent can create its first report;
- leave `Playbooks/Learned/` and `Programs/Learned/` empty.

Do not preload robot details, project rules, or current state into long-term memory; those already have canonical startup files.

### 8. Verify the runtime README

Confirm that the instantiated `README.md` accurately describes the filesystem the robot will actually receive, including both its runtime filesystem tree and its component descriptions.

If deployment preparation added, removed, renamed, or reorganized persistent runtime components, update both the runtime tree and the affected descriptions in `README.md` before launch.

Do not add this `Setup.md` file to that map because it must not be present in the deployed runtime filesystem.

### 9. Pre-launch consistency check

Before the first robot-agent invocation, verify that:

- `Setup.md` is absent from the instantiated runtime filesystem;
- `README.md` accurately maps the runtime filesystem in both its tree and descriptions;
- `Maps/Apartment.md` contains no pre-seeded apartment knowledge;
- `Maps/Rooms/` contains no deployment-specific room maps before the first session;
- the runtime agent has access to the sensor observations needed to infer room identity and fixed landmarks without hidden semantic labels;
- `RobotDetails.md` describes the actual robot and its primitive control contracts;
- `Playbooks/Index.md` matches the actual default playbooks/capabilities available at launch;
- every indexed default playbook points to a real implementation or real built-in capability;
- `ProjectDetails.md` describes the actual setting, task, authority, safety, and evaluation contract;
- `SummaryOfOnlyNecessaryContext.md` reflects the real initial state;
- `LongTermMemory.md` contains only legitimate durable learned knowledge;
- learned playbook/program libraries do not contain fabricated history;
- the first session can follow the startup sequence in `RobotAgentPrompt.md` without needing template-development context.

Only after this consistency check should the robot reasoning agent be launched.
