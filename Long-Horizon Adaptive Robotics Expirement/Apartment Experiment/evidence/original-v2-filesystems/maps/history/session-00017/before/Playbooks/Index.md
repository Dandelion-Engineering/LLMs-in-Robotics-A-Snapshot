# Playbook index

| Capability | Scope | Playbook | Implementation |
|---|---|---|---|
| Position open gripper | Perceived reachable target; stops before closure | [PositionGrasp](Default/PositionGrasp.md) | Programs/Default/position_grasp.py |
| Throw orange practice sphere | Verified grasp and bin 1.8–1.9 m forward; four successes in session 001, narrow geometry | [ThrowForward](Learned/ThrowForward.md) | Programs/Learned/throw_forward.py |
| Open kitchen drawer B | Empty open gripper near freshly perceived left handle attachment; visible openings in sessions 008/015; provisional, mechanism and insertion clearance unresolved | [OpenDrawerB](Learned/OpenDrawerB.md) | Default positioning plus reviewed arm primitives; no dedicated executable |

Learned capabilities have narrow empirical scope; load their preconditions before use.
