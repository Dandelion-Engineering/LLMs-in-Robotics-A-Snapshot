# Robot Details — Embodiment Skeleton

This file describes **the robot the agent inhabits**. It should be populated or verified whenever the filesystem is deployed to a new robot, simulator embodiment, or materially changed hardware configuration.

It should contain relatively stable embodiment facts and the agent-facing contracts for the robot's primitive controls. Task- or environment-specific rules belong in `ProjectDetails.md`. Reusable higher-level capabilities belong in the playbook system, whose canonical catalog is `Playbooks/Index.md`.

## Identity and configuration

- Robot name / identifier:
- Manufacturer / platform:
- Hardware revision:
- Simulation or physical robot:
- Configuration revision:
- Description of embodiment:

## Kinematic structure

- Base type:
- Degrees of freedom:
- Joint names and order:
- Joint types:
- Joint limits:
- Important coordinate frames:
- Base frame:
- Tool / end-effector frame:
- Other named frames:
- Kinematic model / URDF / equivalent path:

## End effectors and manipulators

For each end effector:
- name;
- type;
- tool center point;
- opening / closing or actuation behavior;
- payload / force limits;
- interchangeable tools;
- known constraints.

## Sensors and perception

For each sensor:
- name and modality;
- location / frame;
- what information it provides;
- update characteristics;
- calibration reference;
- known blind spots, uncertainty, latency, or failure modes.

Include proprioceptive sensing separately when relevant.

## Low-level control primitives and agent interfaces

Document the robot's complete primitive action vocabulary that a reasoning agent may directly invoke.

Examples may include base motion, joint commands, Cartesian motion, gaze/camera orientation, gripper commands, observation requests, or other atomic robot actions appropriate to the platform.

For each primitive or interface, record:

- **Name**
- **Purpose / effect**
- **How the agent invokes it**
- **Inputs, units, and coordinate frames**
- **Returned observation, status, or success signal**
- **Preconditions and operational limits**
- **Failure / rejection behavior**
- **Important safety or authority constraints**

The agent should be able to understand what its body can directly do from these contracts at startup.

### Implementation boundary

Do **not** copy the implementation code for low-level controllers, device drivers, motor control, simulator internals, or equivalent primitive-control machinery into this filesystem merely so the agent can use it. That implementation belongs to the robot or simulator software stack.

This file documents the **agent-facing contract**. The underlying robot stack executes the primitive.

If the primitive action set later becomes too large for this startup file, keep a compact complete control index here and point to detailed interface specifications elsewhere.

## Playbooks and reusable programs

`Playbooks/Index.md` is the canonical compact catalog of the robot's reusable higher-level capabilities and is read at startup.

- `Playbooks/Default/` describes reusable capabilities supplied or prepared during deployment.
- `Playbooks/Learned/` describes reusable capabilities Robot-Codex develops during operation.
- `Programs/Default/` contains reusable higher-level programs supplied or prepared during deployment when their code belongs in this filesystem.
- `Programs/Learned/` contains reusable programs created or materially developed by Robot-Codex and promoted for future reuse.

The playbook is the semantic usage layer: what the capability does, when to use it, prerequisites, invocation, evidence, and limitations. The program is the executable artifact when filesystem-resident code is involved.

The index is loaded at startup; the full playbooks and programs are not. Open only the relevant playbook and program when the current task calls for them.

A default playbook may describe a higher-level capability whose implementation remains inside the robot software stack rather than in `Programs/Default/`. In that case, the playbook should identify the built-in robot-stack capability it invokes.

Low-level controller implementations are **not** default programs in this system; they remain part of the robot or simulator stack.

## Physical and safety limits

- Workspace limits:
- Joint / velocity / acceleration limits:
- Payload limits:
- Force / torque limits:
- Collision constraints:
- Forbidden configurations or regions:
- Thermal / power / battery constraints:
- Hardware emergency behavior:

## Calibration and geometry

- Calibration files / versions:
- Sensor extrinsics:
- Tool offsets:
- Base / world alignment:
- Calibration validity checks:
- Known calibration drift or uncertainty:

## Compute and runtime

- Onboard compute:
- External compute:
- Operating system / runtime:
- Network dependencies:
- Persistent storage location:
- Available model / agent runtime:
- Relevant performance constraints:

## Other interfaces available to the agent

List diagnostic, maintenance, configuration, or other robot-level interfaces that are not already documented as low-level control primitives.

For each:
- name;
- purpose;
- input / output contract;
- authority boundary;
- failure behavior;
- source of truth.

## Known quirks and reliability notes

Record stable robot-specific issues a new session should know before acting, such as backlash, sensor dropout, gripper asymmetry, controller behavior, or simulator discrepancies.

Do not record temporary task state here. Temporary state belongs in `SummaryOfOnlyNecessaryContext.md` and session history.

## Verification

- Last verified:
- Verified against:
- Known stale / unverified sections:
