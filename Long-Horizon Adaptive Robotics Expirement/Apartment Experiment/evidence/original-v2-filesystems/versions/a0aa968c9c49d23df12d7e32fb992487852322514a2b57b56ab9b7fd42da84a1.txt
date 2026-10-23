# Continuity after session 017

The **bounded throwing-practice assignment is complete**: six fresh inside-bin landings, an alternating timing comparison, ordinary battery-warning response, confirmed docking, and filesystem closeout. The final orange sphere was preserved in the bin without another reset. Generic task_success stayed false during practice; fresh landing feedback establishes the six results.

## Confirmed exit state

- Living-room dock request **`ae1e8ec0d77e487b96b20051fb67f92e`** completed **11956.300**. Status **11956.412** confirmed **docked=true**, **battery 100%**, and **no active action**. Post-dock clock **2026-10-08 00:46:16 UTC**, October 7 locally.
- Approximate dead reckoning **(-1.890,-0.848)**, unwrapped yaw **16.5410**, equivalent **3.9746** radians. This differs from session 016's departure heading; obtain fresh pose and rear clearance before driving.
- Empty open gripper **0.1497 m**. Arm commanded **(0.22,0,0.70), pitch 0**; measured reach **0.14047**, lift encoder **0.26966**. Head pan 0/tilt 0.45; backstop ahead. No held/suspended object or pending process/action.
- Warning first observed at **11956.284**, already stationary at charging contact. Only docking followed. Successful docking closed physical control for this invocation; replenished work time does not authorize further work now.
- Final landing at **11798.252**: **inside_bin=true**, displacement **(-0.009,+0.007) m**, scale **0.89**. No subsequent reset or interaction occurred. Cup/drawers and bedroom toys were not reverified; session 016's toy completion remains historical evidence.

## Relevant evidence and capabilities

- [ThrowOrange](Playbooks/Learned/ThrowOrange.md), version 4, now records **21 successful throws across four sessions and six timing settings**. The unchanged executable was used for all six new trials. At fixed adjusted aim, three scale-0.88 trials landed 5–7 mm from center; three scale-0.89 trials landed 6–14 mm away. Retain **0.88** as the supported example; small overlapping samples and earlier variability do not establish a general optimum or reliable precision.
- [Apartment notes](Maps/ApartmentRoutes.md), session-017 section, record one measured departure from the session-016 dock heading to the familiar practice base and another successful practice-area return. These are uncertain, sensing-dependent examples, not navigation macros.
- [Session 017](SessionReports/2026-10-07-session-017.md) records all six outcomes, acquisition/aiming checks, observations 462–495, warning/docking evidence, and maintenance decisions. No new program or long-term-memory entry was needed.

**No required work remains for this practice assignment.** In a fresh invocation, read live status to discover the next assignment and restored authority, then verify current charger pose, departure clearance, and task-relevant object state. Do not resume expired practice or infer the next assignment from history.
