# Room Map — Living Room

## Room identity

- Room name / working label: Living room.
- Evidence used to identify the room: Sofa, television on stand, low coffee table (head RGB-D observation 3); blue practice bin (observation 1).
- Apartment-map entry: `../Apartment.md`, Living room.
- First mapped session: 001.
- Last verified session: 002; observations 33–37 and 48–53.

## Entrances and connections

| Entrance / doorway | Connects to | Location / relation in this room | Navigation notes |
|---|---|---|---|
| Opening between sofa and television sides | Bedroom, bed visible | Left of initial forward heading | Traversed both ways in session 002; furniture narrows approach |
| Opening beyond practice bin | Unidentified cabinetry room | Along initial forward heading | Not traversed |

## Fixed landmarks

| Landmark | What it is | Location / relation | Optional local coordinates / frame | Navigation or task relevance | Last verified |
|---|---|---|---|---|---|
| Sofa | Teal seating | Left side when looking toward bedroom | Not measured | Room identity, obstacle | 001, observation 3 |
| Television and stand | Screen on dark cabinet | Right side when looking toward bedroom | Not measured | Room identity, obstacle | 001, observation 3 |
| Coffee table | Low brown table | In front of sofa, toward bedroom opening | Not measured | Navigation obstacle | 001, observation 3 |
| Practice bin | Open blue target container | Forward and right of initial robot heading | Position not yet measured | Throwing target | 001, observation 1 |
| Practice pedestal | Gray raised block | Right of initial heading, opposite bedroom direction | Near initial robot position | Fixed starting support for practice | 001, observation 4 |
| Charger | Green floor pad with yellow stripe and dark backstop | Behind initial heading, beside sofa | Yellow stripe approximately (-1.98, -1.01) m in initial odometry frame; observations 5, 27 and session 002 observation 51 are consistent | Charging station; docking confirmed in sessions 001 and 002 | 002, observations 50–53 and successful docking |

## Stable navigation notes

- Furniture narrows the approach toward the bedroom opening; clearance must be checked live.
- Open floor was traversed from near the practice area toward the charger on an approximately southwest diagonal in the initial frame; pedestal stays on the left, sofa on the right when approaching the charger. Recheck clearance; this is not an automatic route.

## Exclusions

Movable practice objects and transient state are excluded.

## Maintenance

Use current perception; coordinates, when added, are estimates in the dead-reckoned initial frame, not surveyed truth.
