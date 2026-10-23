# Maps + Attention

This subsystem provides persistent semantic-spatial memory for **fixed structure** learned by the robot from its own runtime perception.

It intentionally does not attempt to preserve the full world state. The map answers: what fixed places and landmarks have I learned, how do rooms connect, and what fixed structure should help me navigate the room I am currently in?

## Two-level structure

1. `Apartment.md` — top-level topology: discovered rooms, room identities, and room-to-room connections / doorways.
2. `Rooms/<Room>.md` — detailed fixed spatial structure for one identified room.

There is no required deeper hierarchy in this edition.

## What belongs in maps

Examples:

- rooms and room identities inferred from perception;
- doorways and room-to-room connections;
- fixed furniture and fixtures;
- counters, sinks, beds, couches, built-in or fixed drawers;
- toy chests or target bins when the deployment treats them as fixed landmarks;
- charging stations;
- stable navigation-relevant landmarks.

## What does not belong in maps

Do not map:

- movable task objects such as cups or toys;
- the current position of movable objects;
- temporary clutter or transient obstacles;
- people or agents;
- task progress;
- procedures for using an object;
- speculative landmarks that have not been observed well enough to treat as fixed.

Changing-object regularities may be retained elsewhere, such as `LongTermMemory.md`, when evidence justifies them.

## Map acquisition

Maps must be learned from the robot's normal sensors and runtime interfaces.

- Do not use hidden simulator room labels, semantic object IDs, exact ground-truth object poses, scenario source code, or operator-provided apartment coordinates to populate maps.
- Infer room identity from visible/observable cues plus known task semantics.
- When a fixed landmark is observed and missing from the current room map, add it promptly.
- When a newly identified room or room-to-room connection is discovered, update `Apartment.md`.
- If a fixed map fact is contradicted by reliable current perception, current perception wins; correct the map and record the correction in the session report.
- If permanence is uncertain, wait for stronger evidence rather than treating the item as fixed.

## Location representation

Store enough spatial relation to be useful for navigation without inventing precision.

At minimum, describe a fixed landmark relative to stable room features, entrances, or other fixed landmarks. When the robot's available localization interfaces support a meaningful local coordinate estimate, record that estimate and its frame. Coordinates are optional; false precision is prohibited.

## Attention and room transitions

- `Apartment.md` is read every startup and remains the global spatial orientation.
- At startup, explicitly identify the current room from current sensing, then load that room's detailed map.
- Whenever a doorway is crossed or a room change is suspected, explicitly identify the new room.
- Immediately load the identified room's detailed map before continuing navigation or task work through that room.
- If no room map exists yet, create it from `RoomMapTemplate.md`.
- The current room map is mandatory detailed context even when the robot is only passing through that room.
- A destination-room map may be opened early when useful for planning.
- Do not preload all room maps simply because they exist.

## Map-file maintenance

Room maps may be created, corrected, and extended during ordinary operation. This is expected content growth inside the established `Maps/Rooms/` collection and does not require changing the root README tree unless the subsystem's structure itself changes.
