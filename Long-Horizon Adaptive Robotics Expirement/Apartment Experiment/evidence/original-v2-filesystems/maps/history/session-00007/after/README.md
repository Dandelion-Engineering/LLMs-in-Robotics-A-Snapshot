# Robot Agent Filesystem — Maps Edition

This is the persistent filesystem used by the robot reasoning agent across fresh invocations. This Maps Edition extends the v0.2 filesystem with a purpose-built persistent spatial map and selective room-map loading.

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
│   ├── README.md
│   ├── Apartment.md
│   ├── RoomMapTemplate.md
│   └── Rooms/
│       ├── README.md
│       ├── LivingRoom.md
│       ├── Bedroom.md
│       └── Kitchen.md
├── SessionReports/
│   ├── SessionReportTemplate.md
│   └── *-session-*.md (immutable runtime reports)
├── Playbooks/
│   ├── Index.md
│   ├── PlaybookTemplate.md
│   ├── Default/
│   │   ├── README.md
│   │   └── PositionGrasp.md
│   └── Learned/
│       ├── README.md
│       └── ThrowForward.md
└── Programs/
    ├── Default/
    │   ├── README.md
    │   └── position_grasp.py
    └── Learned/
        ├── README.md
        └── throw_forward.py
```

This tree represents the persistent runtime filesystem. Source-only preparation files such as `Setup.md` are intentionally excluded.

## Filesystem map

### Core startup files

- `RobotAgentPrompt.md` — the invariant operating contract for the robot reasoning agent, including startup, memory use, playbook use, and end-of-session responsibilities.
- `RobotDetails.md` — stable facts about the robot embodiment, sensors, limits, and the complete agent-facing primitive control vocabulary. Low-level controller implementation code remains in the robot or simulator software stack.
- `Playbooks/Index.md` — the compact canonical catalog of reusable higher-level capabilities currently available to the robot. This index is read at every startup.
- `ProjectDetails.md` — the current deployment, setting, task family, authority boundaries, safety constraints, interfaces, and evaluation rules.
- `SummaryOfOnlyNecessaryContext.md` — the compact rewriteable statement of the current objective, state, unresolved work, important constraints, and immediately relevant artifact pointers.
- `LongTermMemory.md` — selective durable learned knowledge that should remain available after individual session reports age out of the recent startup window, including scoped toy-grasp, containment-verification, and docking observations.
- `Maps/Apartment.md` — the compact top-level apartment topology. It is read at every startup and stores discovered rooms, doorways, and room-to-room relations.
- The current room's detailed map in `Maps/Rooms/` is loaded after the agent identifies which room it is physically in.

### Persistent spatial maps

- `Maps/README.md` — operating contract for the Maps + Attention subsystem: what belongs in the map, how maps are learned from perception, room-transition behavior, and selective loading.
- `Maps/Apartment.md` — always-read top-level map of discovered rooms and how they connect. It begins unpopulated and is learned from experience.
- `Maps/RoomMapTemplate.md` — standard structure for a newly discovered room map.
- `Maps/Rooms/` — detailed maps of individual rooms created during operation.
  - `LivingRoom.md`, `Bedroom.md` and `Kitchen.md` — observed fixed structure and connections for the three identified rooms; coverage remains partial. The kitchen map includes the marked drawer cabinet, counter and sink fixtures, and confirmed charger.

The map stores only persistent fixed spatial structure: rooms, doorways, fixtures, furniture, charging stations, fixed containers, and other landmarks expected to remain in place. Do not put movable task objects, transient obstacles, or their current positions into the map.

The attention rule is deliberately simple: keep the apartment map available globally; load the detailed map for the room the robot is currently in whenever that room is entered. A destination-room map may also be opened when useful for planning, but unrelated room maps are not preloaded.

### Episodic memory

- `SessionReports/` — immutable per-session reports describing what each invocation actually did, observed, changed, learned, and left unresolved.
  - `SessionReports/SessionReportTemplate.md` — required structure for new session reports.

The three most recent session reports are read at startup. Older reports are retrieved when the summary, long-term memory, playbook index, or current task makes them relevant.

### Reusable procedures

- `Playbooks/Index.md` — compact startup catalog of all reusable higher-level capabilities.
- `Playbooks/PlaybookTemplate.md` — standard structure for individual playbooks.
- `Playbooks/Default/` — semantic playbooks for reusable higher-level capabilities supplied with the robot or prepared before deployment.
- `Playbooks/Learned/` — semantic playbooks for reusable higher-level capabilities developed and promoted by the robot reasoning agent during operation.
  - `ThrowForward.md` — empirically tested orange-sphere throwing procedure with perception and grasp preconditions.

A playbook explains what a capability does, when to use it, its preconditions, how to invoke it, its scope, evidence, and limitations. Full playbooks are opened only when relevant.

### Executable reusable programs

- `Programs/Default/` — filesystem-resident reusable higher-level programs supplied with the robot or prepared before deployment when such code belongs in this filesystem.
- `Programs/Learned/` — filesystem-resident reusable programs created or materially developed during operation and promoted for future reuse.
  - `throw_forward.py` — checked replay of the learned throw using ordinary trajectory controls; no automatic pickup or navigation.

Programs are executable artifacts. Playbooks are their semantic usage layer. A playbook may instead point to a built-in higher-level capability implemented inside the robot software stack, in which case no filesystem-resident program is required.

Low-level controller implementations, device drivers, motor-control code, and simulator internals are not copied here merely for agent use; their agent-facing contracts belong in `RobotDetails.md`.

## Startup path

Each fresh robot-agent invocation begins by reading, in order:

1. `README.md`
2. `RobotDetails.md`
3. `Playbooks/Index.md`
4. `ProjectDetails.md`
5. `Maps/Apartment.md`
6. `SummaryOfOnlyNecessaryContext.md`
7. `LongTermMemory.md`
8. the three most recent immutable reports in `SessionReports/`
9. current sensor observations sufficient to identify the robot's present room
10. the detailed map for that current room in `Maps/Rooms/`, creating it from `Maps/RoomMapTemplate.md` if the room has been identified but has no room map yet

The agent then follows relevant pointers and obtains any further current observations needed before relying on remembered world state.

## Maintenance

- Keep this README compact and accurate as a map of the persistent runtime filesystem.
- Keep both the runtime filesystem tree and the descriptions below it current.
- If persistent files or folders are added, removed, renamed, or reorganized, update the tree and any affected descriptions before ending the session.
- Do not use this README as a chronological log or current-state summary.
- Current perception and current authority outrank historical memory.
- Fixed spatial structure belongs canonically in `Maps/`, not in `LongTermMemory.md` or the current-state summary.
- Adding or updating ordinary room-map files inside the already documented `Maps/Rooms/` collection does not by itself change the filesystem structure and does not require a root README edit.

The supplied PositionGrasp default playbook and position_grasp.py program implement only perception-directed open-gripper positioning. Primitive client code is mounted at /robot_client.py by the robot stack and is outside this persistent filesystem.
