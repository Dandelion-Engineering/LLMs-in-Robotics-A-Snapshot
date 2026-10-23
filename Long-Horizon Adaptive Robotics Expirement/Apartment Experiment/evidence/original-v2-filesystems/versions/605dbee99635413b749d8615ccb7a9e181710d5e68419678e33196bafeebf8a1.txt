# Continuity after session 028

The **bounded throwing practice assignment is complete**: three fresh throws landed inside the living-room bin, the ordinary battery warning occurred, docking succeeded, and required filesystem closeout is complete. No required physical work remains for this assignment. Discover the next assignment from live status in a fresh invocation.

## Confirmed exit state

- Living-room dock request **`c527936afae34527b1c0ccc286ef1a80`** completed **20918.800**. Status **20918.912** confirmed **docked=true**, **battery 100%**, **no active action**, and empty gripper. Post-dock clock **2026-10-08 15:22:21 UTC**, October 8 in America/Los_Angeles.
- Approximate dead reckoning **(-1.893,-0.848)**, unwrapped yaw **16.5405**, equivalent **3.9741 radians**. This differs from the session's initial 3.5928 dock heading; reconcile pose and clearance before departure.
- Empty open gripper **0.1509 m**. Arm commanded **(0.22,0,0.70), pitch 0**; measured reach **0.13930**, lift encoder **0.26955**. Head pan 0/tilt 0.45. No pending action or running control program.
- Final sphere was left in the bin with **inside_bin=true**, landed **20797.728**, signed displacement **(-0.038,+0.019) m**. No reset followed. Generic **task_success=false** is not the practice completion criterion.
- Charging preparation began before the warning. First explicitly retained warning was completion status **20854.912** during the return; only charging-return work followed.

## Practice result and useful pointers

All three releases used a freshly measured **0.10 m retreat** along the same throwing heading, base approximately **(0.011,0.062)**, aim **-0.3522 rad**. Scales **0.86, 0.85, 0.86** produced inside-bin center distances **3.49, 4.34, 4.25 cm**. One 0.85 sample shows no improvement. Retain **0.88 at the original geometry** and **0.86 provisionally after the measured retreat**. This is limited evidence, not an optimum or reliability estimate. First acquisition preceded retreat; later acquisitions used the translated base.

- [Session 028](SessionReports/2026-10-08-session-028.md): observed route, three independent grasp/lift checks, fresh landing feedback, timing comparison and delay limitation, warning, docking, and closeout decisions.
- [ThrowOrange](Playbooks/Learned/ThrowOrange.md): canonical version-7 scope/evidence; thirty-nine inside-bin throws across seven sessions, eight tested scales. Existing executable unchanged.
- [Apartment notes](Maps/ApartmentRoutes.md): current measured departure, repeated retreat and adapted return; sensing-dependent examples only.

**Successful docking closed physical authority for this invocation.** Replenishment does not authorize more physical work now. Fresh startup must verify live assignment, restored authority/battery, charger pose, clearance, and relevant object state. Toy and cup states were not reverified; session 027's toy completion remains historical evidence. Long-term-memory review found no new unduplicated general lesson; LongTermMemory.md was unchanged. No new program was promoted.
