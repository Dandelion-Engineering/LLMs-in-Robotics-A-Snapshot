# Project Details — Deployment Skeleton

This file is populated for a specific deployment, experiment, environment, or task family. It should contain information about **what the robot is doing and under what rules**, not the robot's embodiment itself.

## Project identity

- Project / deployment name:
- Revision:
- Date prepared:
- Prepared by:
- Purpose:

## Operating setting

Describe the environment in which the robot operates.

- Physical or simulated setting:
- Work areas / regions:
- Relevant objects, stations, fixtures, or infrastructure:
- Humans or other agents that may be present:
- Environmental assumptions:
- Known environmental hazards or constraints:

## Mission and task family

- High-level mission:
- Types of tasks the robot may receive:
- Current task source:
- Success criteria:
- Failure criteria:
- Completion / handback conditions:

## Authority

- What the agent is authorized to control:
- What requires external approval:
- What is prohibited:
- What must remain under conventional or external control:
- Emergency / stop behavior:
- Authority handoff rules:

## Task-specific safety constraints

List constraints that arise from this project or environment rather than from the robot's intrinsic hardware limits.

## Available project interfaces

List project-specific tools, services, APIs, files, simulators, controllers, databases, or other systems that may be used.

For each important interface, include:
- name;
- purpose;
- authoritative source of truth;
- access method;
- important limitations.

## Evaluation and evidence

- What counts as evidence that an action or task succeeded:
- What must be recorded:
- Required provenance:
- Required logs / artifacts:
- Evaluation procedure:

## Persistent project resources

Point to durable project-specific resources that may be relevant across sessions.

In this Maps Edition, learned fixed spatial structure belongs canonically in `Maps/`. Do not duplicate apartment topology, room geometry, or fixed-landmark locations here. Project-specific resources may point to maps, task state, procedures, evidence stores, or other durable artifacts when relevant.

## Startup additions

List any additional files or resources, beyond the invariant Robot Agent Prompt startup set, that every session for this deployment must inspect.

- `Maps/Apartment.md` is already part of the invariant Maps Edition startup sequence; do not list it here merely to duplicate that requirement.

## Notes for the active deployment

Populate only information that is stable or operationally relevant. Do not turn this file into a chronological log; session-specific history belongs in `SessionReports/`.
