# Apartment Map

This is the always-read top-level map of fixed apartment topology learned from runtime perception.

Do not prepopulate it from simulator ground truth. Add only rooms and connections that Robot Codex has actually identified from its available observations.

## Discovered rooms

| Room | Identity evidence | Room map | Notes |
|---|---|---|---|
| _No rooms discovered yet_ |  |  |  |

## Room connections and doorways

| From room | To room | Doorway / transition description | Spatial relation / navigation note | Last verified |
|---|---|---|---|---|
| _No connections discovered yet_ |  |  |  |  |

## Global topology notes

- None yet.

## Maintenance rules

- Add a room only after there is enough perceptual evidence to identify it.
- Add a connection when the robot actually observes or traverses the transition.
- Keep this file compact; detailed room contents belong in `Rooms/`.
- Current reliable perception outranks remembered topology.
- Never put movable-object positions in this file.
