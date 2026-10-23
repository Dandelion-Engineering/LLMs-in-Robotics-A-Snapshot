# Robot Agent Filesystem

This is the persistent filesystem used by the robot reasoning agent across fresh invocations.

The filesystem separates current state, episodic history, durable learned knowledge, embodiment information, project rules, reusable procedures, and executable programs so that later sessions can continue work without loading the robot's entire history.

## Runtime filesystem tree

```text
/
├── README.md
├── RobotAgentPrompt.md
├── RobotDetails.md
├── ProjectDetails.md
├── SummaryOfOnlyNecessaryContext.md
├── LongTermMemory.md
├── SessionReports/
│   └── SessionReportTemplate.md
├── Playbooks/
│   ├── Index.md
│   ├── PlaybookTemplate.md
│   ├── Default/
│   │   └── README.md
│   └── Learned/
│       └── README.md
└── Programs/
    ├── Default/
    │   └── README.md
    └── Learned/
        └── README.md
```

This tree represents the persistent runtime filesystem. Source-only preparation files such as `Setup.md` are intentionally excluded.

## Filesystem map

### Core startup files

- `RobotAgentPrompt.md` — the invariant operating contract for the robot reasoning agent, including startup, memory use, playbook use, and end-of-session responsibilities.
- `RobotDetails.md` — stable facts about the robot embodiment, sensors, limits, and the complete agent-facing primitive control vocabulary. Low-level controller implementation code remains in the robot or simulator software stack.
- `Playbooks/Index.md` — the compact canonical catalog of reusable higher-level capabilities currently available to the robot. This index is read at every startup.
- `ProjectDetails.md` — the current deployment, setting, task family, authority boundaries, safety constraints, interfaces, and evaluation rules.
- `SummaryOfOnlyNecessaryContext.md` — the compact rewriteable statement of the current objective, state, unresolved work, important constraints, and immediately relevant artifact pointers.
- `LongTermMemory.md` — selective durable learned knowledge that should remain available after individual session reports age out of the recent startup window.

### Episodic memory

- `SessionReports/` — immutable per-session reports describing what each invocation actually did, observed, changed, learned, and left unresolved.
  - `SessionReports/SessionReportTemplate.md` — required structure for new session reports.

The three most recent session reports are read at startup. Older reports are retrieved when the summary, long-term memory, playbook index, or current task makes them relevant.

### Reusable procedures

- `Playbooks/Index.md` — compact startup catalog of all reusable higher-level capabilities.
- `Playbooks/PlaybookTemplate.md` — standard structure for individual playbooks.
- `Playbooks/Default/` — semantic playbooks for reusable higher-level capabilities supplied with the robot or prepared before deployment.
- `Playbooks/Learned/` — semantic playbooks for reusable higher-level capabilities developed and promoted by the robot reasoning agent during operation.

A playbook explains what a capability does, when to use it, its preconditions, how to invoke it, its scope, evidence, and limitations. Full playbooks are opened only when relevant.

### Executable reusable programs

- `Programs/Default/` — filesystem-resident reusable higher-level programs supplied with the robot or prepared before deployment when such code belongs in this filesystem.
- `Programs/Learned/` — filesystem-resident reusable programs created or materially developed during operation and promoted for future reuse.

Programs are executable artifacts. Playbooks are their semantic usage layer. A playbook may instead point to a built-in higher-level capability implemented inside the robot software stack, in which case no filesystem-resident program is required.

Low-level controller implementations, device drivers, motor-control code, and simulator internals are not copied here merely for agent use; their agent-facing contracts belong in `RobotDetails.md`.

## Startup path

Each fresh robot-agent invocation begins by reading, in order:

1. `README.md`
2. `RobotDetails.md`
3. `Playbooks/Index.md`
4. `ProjectDetails.md`
5. `SummaryOfOnlyNecessaryContext.md`
6. `LongTermMemory.md`
7. the three most recent immutable reports in `SessionReports/`

The agent then follows relevant pointers and obtains current observations before relying on remembered world state.

## Maintenance

- Keep this README compact and accurate as a map of the persistent runtime filesystem.
- Keep both the runtime filesystem tree and the descriptions below it current.
- If persistent files or folders are added, removed, renamed, or reorganized, update the tree and any affected descriptions before ending the session.
- Do not use this README as a chronological log or current-state summary.
- Current perception and current authority outrank historical memory.
