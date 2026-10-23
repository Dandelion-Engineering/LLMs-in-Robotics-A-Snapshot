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
├── Maps/
│   ├── ApartmentRoutes.md
│   └── Kitchen.md
├── SessionReports/
│   ├── SessionReportTemplate.md
│   ├── 2026-10-07-session-001.md
│   ├── 2026-10-07-session-002.md
│   ├── 2026-10-07-session-003.md
│   ├── 2026-10-07-session-004.md
│   ├── 2026-10-07-session-005.md
│   ├── 2026-10-07-session-006.md
│   ├── 2026-10-07-session-007.md
│   ├── 2026-10-07-session-008.md
│   ├── 2026-10-07-session-009.md
│   ├── 2026-10-07-session-010.md
│   ├── 2026-10-07-session-011.md
│   ├── 2026-10-07-session-012.md
│   ├── 2026-10-07-session-013.md
│   ├── 2026-10-07-session-014.md
│   ├── 2026-10-07-session-015.md
│   └── 2026-10-07-session-016.md
├── Playbooks/
│   ├── Index.md
│   ├── PlaybookTemplate.md
│   ├── Default/
│   │   ├── README.md
│   │   └── PositionGrasp.md
│   └── Learned/
│       ├── README.md
│       └── ThrowOrange.md
└── Programs/
    ├── Default/
    │   ├── README.md
    │   └── position_grasp.py
    └── Learned/
        ├── README.md
        └── throw_orange.py
```

This tree represents the persistent runtime filesystem. Source-only preparation files such as `Setup.md` and generated Python caches are intentionally excluded.

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

### Observed environment notes

- `Maps/ApartmentRoutes.md` — sensor-grounded living-room/bedroom routes, kitchen-to-living-room traversals including a blocked corner turn and repeated clear earlier turns, measured toy grasps and confirmed four-toy containment across two assignments, a limited overhead chest inspection, and repeated charging contact from the bedroom and practice area. Coordinates are uncertain dead reckoning; fresh sensing is required. This is not an executable navigation or manipulation capability.
- `Maps/Kitchen.md` — observed kitchen routes and eight charging contacts, three B openings, head/wrist search coverage, tabletop and floor-cup grasps, and confirmed containment in open A and B across separate assignments. Pose-dependent evidence from eight sessions includes repeated deliberate B releases, wrist verification in both drawers, and a settled living-room entry route; general repeatability and the orange fitting's mechanism remain unresolved. This is not an executable capability.

### Reusable procedures

- `Playbooks/Index.md` — compact startup catalog of all reusable higher-level capabilities.
- `Playbooks/PlaybookTemplate.md` — standard structure for individual playbooks.
- `Playbooks/Default/` — semantic playbooks for reusable higher-level capabilities supplied with the robot or prepared before deployment.
- `Playbooks/Learned/` — semantic playbooks for reusable higher-level capabilities developed and promoted by the robot reasoning agent during operation.
  - `ThrowOrange.md` — measured grasp prerequisites, alignment scope, release motion, fifteen successful throws across three sessions at five timing settings, a small aiming comparison with observed variation, and limitations for the orange practice sphere.

A playbook explains what a capability does, when to use it, its preconditions, how to invoke it, its scope, evidence, and limitations. Full playbooks are opened only when relevant.

### Executable reusable programs

- `Programs/Default/` — filesystem-resident reusable higher-level programs supplied with the robot or prepared before deployment when such code belongs in this filesystem.
- `Programs/Learned/` — filesystem-resident reusable programs created or materially developed during operation and promoted for future reuse.
  - `throw_orange.py` — tested release sequence for an already grasped sphere and externally aligned base; no navigation or object reset.

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

The supplied PositionGrasp default playbook and position_grasp.py program implement only perception-directed open-gripper positioning. Primitive client code is mounted at /robot_client.py by the robot stack and is outside this persistent filesystem.
