# Apartment Map

This is the always-read top-level map of fixed apartment topology learned from runtime perception.

Do not prepopulate it from simulator ground truth. Add only rooms and connections that Robot Codex has actually identified from its available observations.

## Discovered rooms

| Room | Identity evidence | Room map | Notes |
|---|---|---|---|
| Living room | Sofa, television on stand, coffee table; practice bin | Rooms/LivingRoom.md | Identified from observations 1 and 3 in session 001 |
| Kitchen | Refrigerator, cabinetry and counter with three mats; entered in observation 109 | Rooms/Kitchen.md | Identified in session 005 |
| Bedroom | Bed visible through doorway from living room | Rooms/Bedroom.md | Entered and confirmed by bed in sessions 002–004, observations 38, 60 and 86 |
| Bathroom | White toilet with rectangular cistern and a rectangular blue-interior bathing fixture visible beyond the rear kitchen opening | Rooms/Bathroom.md | Identified from kitchen observation 317 in session 015; entered and confirmed in session 016, observation 331 |

## Room connections and doorways

| From room | To room | Doorway / transition description | Spatial relation / navigation note | Last verified |
|---|---|---|---|---|
| Living room | Bedroom | Wide opening between television side and sofa side | Left of initial forward heading, approximately +90 degrees | Session 004, observations 85–86 and 97–98; traversed both ways |
| Living room | Kitchen | Opening beyond practice bin, previously called cabinetry-side opening | Refrigerator/cabinet on left, charger on right when entering | Session 005, observations 108–109; entered |
| Kitchen | Bathroom | Rear opening beyond cabinet, beside counter | Directly traversed in sessions 016–017; toilet ahead-left and bathtub ahead-right on entry | Session 017, observations 355–356 and return 368–369 |

## Global topology notes

- The cabinetry-side opening ahead of the initial living-room heading leads to the kitchen, confirmed by entry in session 005.
- A bedroom opening to the right of the toy chest is visible in session 002 observations 39 and 41; destination unconfirmed and not traversed.
- A rear opening beyond the kitchen cabinet, beside the counter, exposes the bathroom fixtures in observation 317, session 015. Direct kitchen–bathroom passage was confirmed by traversal in session 016, observations 330–331. This does not establish a bedroom–bathroom connection.

## Maintenance rules

- Add a room only after there is enough perceptual evidence to identify it.
- Add a connection when the robot actually observes or traverses the transition.
- Keep this file compact; detailed room contents belong in `Rooms/`.
- Current reliable perception outranks remembered topology.
- Never put movable-object positions in this file.
