# Continuity after session 013

The **bounded throwing-practice assignment is complete**: six fresh inside-bin throws, comparison of a small aiming adjustment and faster timing, ordinary warning response, confirmed living-room docking, and filesystem closeout. Read the next assignment from live status in a fresh invocation. Generic task_success remained false during practice; the separate fresh landing feedback established each throw result.

## Confirmed exit state

- Living-room dock request **`a9e8ff46cbe84792b08136030b04ba78`** completed at simulation time **9265.484**. Status **9265.596** confirmed **docked=true**, **battery 100%**, and **no active action**. Post-dock clock: **2026-10-08 00:00:54 UTC** (October 7 locally).
- Approximate dead reckoning **(-1.892,-0.849)**, unwrapped yaw **10.2578**, equivalent to **3.9746** radians. These are uncertain coordinates, not a surveyed map.
- Empty open gripper **0.1503 m**. Arm commanded **(0.22,0,0.70), pitch 0**; measured reach **0.14004**, lift encoder **0.26995**. Head pan 0/tilt 0.55. The charging backstop is ahead.
- Orange sphere last confirmed inside the bin by trial-6 feedback at **9143.576**, displacement **(+0.071,-0.024) m** in the target-bin forward/left frame. Head observation **376** exposed a small orange patch inside. No subsequent reset or object manipulation occurred; feedback persisted through docking.
- First observed warning: completed return-drive status **9220.768**. Only final return and docking followed. Successful docking closed physical control for this invocation; replenished work time does not authorize further control now.
- Prior cup/toy containment was not reverified. The old kitchen pose and completed cup-to-B assignment are historical, not current authority.

## Relevant continuation context

1. Establish the next live assignment, restored authority/battery, actual station pose, and departure clearance. Do not resume this expired practice period or completed cup tasks.
2. [ThrowOrange](Playbooks/Learned/ThrowOrange.md), version 3, now records **15 successful throws across sessions 001/010/013 at five timing settings**. The executable is unchanged; acquisition, aiming, navigation, and reset remain external responsibilities.
3. Current comparison: baseline scale 0.88 landed about 1.5 cm from center. With a +0.008 rad aiming adjustment, three 0.88 throws landed about **0.5, 3.7, and 0.9 cm** from center. Two 0.86 throws landed about **6.8 and 7.5 cm** away. Keep 0.88 as the supported example; the small aim change is not a proven repeatable improvement. Do not infer millimeter accuracy from one result.
4. [Apartment routes](Maps/ApartmentRoutes.md) adds an earlier kitchen-exit diagonal turn that cleared without a blocked request, and a second observed practice-base return using the session-010 dock geometry. These are sensor-grounded examples, not route macros.
5. [Session 013](SessionReports/2026-10-07-session-013.md) records all six acquisition/release outcomes, current geometry, variability, route observations, and docking evidence. Long-term memory was reviewed and unchanged: throwing evidence belongs in its playbook, route evidence in the map. No new program was promoted.

No required work remains for this bounded practice assignment. The cause of the observed landing variation and performance at wider distances, headings, or objects remain background uncertainties.
