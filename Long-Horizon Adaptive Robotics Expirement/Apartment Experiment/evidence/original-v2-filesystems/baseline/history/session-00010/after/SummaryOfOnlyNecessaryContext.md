# Continuity after session 010

The **bounded throwing-practice assignment is complete**. Five throws landed inside the living-room bin: one at duration scale 0.92, two at 0.90, and two at 0.88. The final two landed about 1.3 cm from center. The ordinary warning, return, docking, and filesystem closeout are complete. Read the next assignment from live status only in a fresh invocation.

## Confirmed exit state

- Living-room dock request `4c84004fbaef423196da7f7873241436` completed at simulation time **7186.152**. Status **7186.276** confirmed docked=true, battery 100%, and no active action.
- Approximate dead reckoning **(-1.890,-0.849)**, unwrapped yaw **10.2577**, equivalent to **3.9745** radians. Coordinates are uncertain, not a surveyed map.
- Empty open gripper **0.1510 m**. Arm commanded **(0.22,0,0.70), pitch 0**; measured reach 0.13975, lift encoder 0.27034. Head pan 0/tilt 0.55. The charging backstop is ahead.
- Final landing at **7043.004**: inside_bin=true, displacement **forward -0.003 m, left -0.012 m**. No later reset or object manipulation occurred. Post-throw head views concealed the sphere behind the bin front; fresh landing feedback established containment.
- First observed warning: observation **297**, **7120.276**. Only return/docking work followed. Physical control closed on successful docking. Replenished battery/work time does not authorize more control in this invocation.
- Generic task_success remained false during practice; the separate fresh landing feedback and completed practice window are the relevant outcomes.

## Relevant continuation context

1. Establish the new live assignment, authority, battery, pose, and departure clearance. Do not assume the next assignment or continue this expired practice window.
2. This living-room docking heading differs from sessions 002–004. The latest approach passed **(-1.098,0.024)**, turned to heading **3.9745**, and advanced **0.90 m then 0.28 m** with fresh sensing. Any departure must be checked from the actual current pose; these are historical route measurements.
3. [ThrowOrange](Playbooks/Learned/ThrowOrange.md), version 2, now records nine inside-bin throws across sessions 001/010 and four tested timing scales. Explicit scale **0.88** gave the closest repeated recent landings. The unchanged program's default remains 1.0. Its scope is release only from a confirmed grasp and visually aligned base about 1.8 m from the bin; other geometry is untested.
4. [Apartment routes](Maps/ApartmentRoutes.md) now includes the kitchen-to-living-room traversal, a blocked corner turn near **(2.74,-0.14)**, recovery from the observed resulting pose, and the latest charger return. Do not replay that tight turn as an established clear route. Exact contact was not isolated.
5. Prior cup-to-B and four-toy assignments were complete in sessions 009 and 004. Their contents were not deliberately handled or reverified during this practice session. Relevant evidence remains in [kitchen notes](Maps/Kitchen.md) and [apartment routes](Maps/ApartmentRoutes.md).
6. [Session 010](SessionReports/2026-10-07-session-010.md) contains current trial measurements, grasp/projection evidence, the blocked turn, and docking. Long-term memory was reviewed without additions; new throwing knowledge belongs in the playbook and route geometry in the map.

No required work remains for the completed practice assignment. Wider throwing generalization and exact corner contact are documented limitations, not mandatory follow-up work.
