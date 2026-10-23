# Robot Agent Filesystem — First Draft

**Version:** 0.1 · **Prepared:** 2026-09-26 · **Status:** proposed, unconfigured, simulator-first

## The idea

A conventional robot performs its ordinary work. When a deterministic monitor detects a problem or an operator requests assistance, a filesystem-native agent investigates, uses available robot skills or lower-level controls, optionally writes executable recovery code, and helps return the robot to productive operation.

The agent can genuinely read, write, create, and edit its working files. It is not just a model receiving a checkpoint assembled by someone else. Its reasoning need not fit in one uninterrupted conversation.

Start with one framework and test it repeatedly. Do not build an architecture-search platform, hierarchical maps, attention agents, or a new company-management system yet.

**This package contains instructions, fill-in templates, an integration specification, and a pilot test plan. It contains no working robot adapter, launcher, controller, sandbox, or safety implementation. No robot behavior or crash recovery has been tested by creating these files.**

## Read first

1. [RobotAgentPrompt.md](workspace/RobotAgentPrompt.md): what the robot agent is being asked to do.
2. [Continuity.md](workspace/Continuity.md): its short, continuously maintained re-entry note.
3. [Tools.md](workspace/Tools.md): how skills, manual control, and generated programs relate.
4. [Implementation Guide](Implementation%20Guide.md): what development Codex must fill in and enforce outside the agent.
5. [Pilot Tests](Pilot%20Tests.md): how to inspect whether the first implementation behaves as intended.

[Tasks.md](workspace/Tasks.md) and [Robot.md](workspace/Robot.md) deliberately contain placeholders. The development agent fills them from the chosen experiment and actual robot interfaces, not from guesses.

## Structure

```text
Robot_Agent_Filesystem_v0.1/
    README.md                    Human/developer overview; not runtime instructions
    Implementation Guide.md      Builder-only integration requirements
    Pilot Tests.md               Builder/operator tests; keep outside runtime view
    workspace/                   Template for a separate runtime working directory
        AGENTS.md                Small Codex instruction-loading pointer
        RobotAgentPrompt.md           General role, filesystem use, recovery behavior
        Tasks.md                 Trusted task requirements, filled for the experiment
        Robot.md                 Body, sensing, frames, limits, normal operation
        Tools.md                 Actual tool bindings and code API, filled by builder
        Continuity.md            Agent-owned rolling recovery note
        live/
            README.md            Meaning and ownership of public live records
            activation.json      Supervisor-authored reason for this activation
            state.json           Supervisor-authored timestamped public snapshot
            events.jsonl         Public action/observation history, initially empty
            observations/        Permitted images and other observation artifacts
        notes/                   Agent-created lessons, plans, and supporting files
        programs/                Agent-created or revised recovery code
```

The layout is a logical contract; the builder can realize read-only surfaces through mounts or a projection service. Merely putting files in these folders does not enforce permissions.

## Three kinds of authority

| Surface | Writer during operation | What it means |
|---|---|---|
| AgentPrompt, AGENTS, Robot, Tools | Builder/operator only | Configuration and allowed capabilities; fixed during a trial |
| Tasks | Trusted task/operator service | Current authorized goal and task revision, not agent-generated progress |
| `live/` | Supervisor and public robot services | What triggered assistance, observable state, commands and feedback |
| Continuity, `notes/`, `programs/` | Robot agent | Working understanding, plans, lessons, and proposed/executable procedures |
| Simulator internals, evaluator, permissions, actuator gateway | Protected host only; not exposed to the runtime agent | Physical execution and enforcement, independent scoring and isolation |

The agent may improve its working material. It may not edit its task to declare success, rewrite the history of a failure, or grant itself more control permissions.

## The essential continuity decision

**Do not wait until the end of a session to preserve the only copy of important information.**

`Continuity.md` preserves the agent's interpretation and next step. The supervisor independently records public robot actions and feedback while the agent is both awake and asleep. After interruption, the next activation reconciles the note, records newer than its event cursor, unresolved requests, and fresh observations.

The note may be stale or absent. A command receipt is not proof of physical completion. Neither conversation history nor an orderly shutdown is required for the intended recovery protocol.

## Deliberate starting choices

- Error-triggered assistance; no continuously thinking model or multiple standing robot agents.
- Existing conventional skills remain available, but the agent also gets bounded manual primitives and a real programming interface.
- All physical requests pass through one externally enforced gateway. The agent cannot override it through custom code.
- The agent decides how to investigate and recover; the supervisor manages triggering, recording, ownership, and mechanical limits, not a hidden solution script.
- Maps + Attention comes later, once this simpler filesystem agent is a meaningful host for it.

Safety here means an explicitly tested set of simulated constraints, not a universal guarantee. Real hardware deployment requires a separate engineering assessment and authorization.

## Supporting context, not implementation claims

The repository's [Task and Architecture Explorer README](https://github.com/randycrespo/LLMs-in-Robotics/blob/main/Long-Horizon%20Adaptive%20Robotics%20Expirement/Task%20and%20Architecture%20Explorer/README.md) describes the earlier model interfaces and runtime-written checkpoint. This draft deliberately adds genuine filesystem agency. The existing [experimental contract](https://github.com/randycrespo/LLMs-in-Robotics/blob/main/Long-Horizon%20Adaptive%20Robotics%20Expirement/Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Contract.md) distinguishes public observations, command feedback, physical outcome, and protected execution. It is design context, not proof the current runtime implements every proposed interface.

Official Codex documentation describes [instruction discovery](https://developers.openai.com/codex/guides/agents-md) and [app-server integration](https://developers.openai.com/codex/app-server). Use current documentation when integrating; this package chooses no model, authentication route, runtime SDK, or new paid service. [MoveIt Servo documentation](https://moveit.picknik.ai/main/doc/examples/realtime_servo/realtime_servo_tutorial.html) illustrates specific configurable motion checks; it is not a claim that this project uses MoveIt or that those checks guarantee all safety.

These are reference points checked during drafting. The proposed design and defaults in this package are recommendations, not measured results or source-prescribed architecture.
