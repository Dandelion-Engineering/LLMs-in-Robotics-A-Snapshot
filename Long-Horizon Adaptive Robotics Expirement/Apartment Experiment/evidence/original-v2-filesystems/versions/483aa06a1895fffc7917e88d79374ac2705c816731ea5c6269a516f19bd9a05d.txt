# Apartment Map

This is the always-read top-level map of fixed apartment topology learned from runtime perception.

Do not prepopulate it from simulator ground truth. Add only rooms and connections that Robot Codex has actually identified from its available observations.

## Discovered rooms

| Room | Identity evidence | Room map | Notes |
|---|---|---|---|
| Living room | Sofa, television on stand, coffee table; practice bin | Rooms/LivingRoom.md | Identified from observations 1 and 3 in session 001 |
| Bedroom | Bed visible through doorway from living room | Rooms/Bedroom.md | Entered and confirmed by bed in sessions 002–004, observations 38, 60 and 86 |

## Room connections and doorways

| From room | To room | Doorway / transition description | Spatial relation / navigation note | Last verified |
|---|---|---|---|---|
| Living room | Bedroom | Wide opening between television side and sofa side | Left of initial forward heading, approximately +90 degrees | Session 004, observations 85–86 and 97–98; traversed both ways |

## Global topology notes

- Another opening ahead of the initial living-room heading shows cabinetry; destination identity unconfirmed.
- A bedroom opening to the right of the toy chest is visible in session 002 observations 39 and 41; destination unconfirmed and not traversed.

## Maintenance rules

- Add a room only after there is enough perceptual evidence to identify it.
- Add a connection when the robot actually observes or traverses the transition.
- Keep this file compact; detailed room contents belong in `Rooms/`.
- Current reliable perception outranks remembered topology.
- Never put movable-object positions in this file.
