# Observed kitchen route and cup handling

Sensor-grounded history from [session 005](../SessionReports/2026-10-07-session-005.md), not a surveyed map or executable procedure. Coordinates are uncertain session-independent dead reckoning. Reconcile live assignment, images, range, and pose before using any geometry. Drawer operation is **not established**.

## Route and obstacles

The kitchen is reached through the opening to the right of the living-room TV partition. Three colored mats are on a far countertop. The drawer cabinet is on the left when entering, and the kitchen charging pad is on the right near the entrance.

| Observed waypoint | Approximate x, y, heading | Evidence and limits |
|---|---|---|
| Living-room passage approach | (0.434, 0.262), 3.593 | Reached by reversing 1.08 m and 1.49 m from the living-room charger. |
| Facing kitchen opening | (0.434, 0.262), 0.173 | Turned -3.14 then -0.28; observations 122–123 established clearance. |
| Kitchen entrance | (1.913, 0.521), 0.173 | Advanced 1.50 m; observation 124. |
| Inside entrance | (2.898, 0.693), 0.173 | Advanced 1.00 m; observation 125. Open drawer A protruded into the aisle. |
| Blocked drawer-side approach | (3.875, 0.374), -0.241 | A 1.50 m request at heading -0.277 stopped after about 1.03 m, with a blocked result. The nearby protruding drawer/handle is the likely obstacle; exact contact was not isolated. |
| Recovery waypoint | (3.680, 0.424), -0.841 | Backed 0.20 m, raised retracted arm from z=0.70 to 1.10, and turned -0.60. |
| Clear counter aisle | (4.213, -0.173), -0.001 | Advanced 0.80 m at heading -0.841, then turned +0.84. |
| Counter acquisition base | (6.813, -0.175), -0.001 | Advanced 1.50 m, 0.80 m, and 0.30 m with fresh observations. Final forward lidar about 0.42 m; do not assume further advance is safe. |
| Cabinet staging base | (5.966, 0.527), 2.449 | From acquisition base, turned +2.45, advanced 0.70 m then 0.40 m. A nearby protrusion produced short side ranges; this is not an unconditional approach. |

After staging, reverse 1.10 m at heading 2.449 returned to (6.814,-0.176). Turn +0.6925 established heading pi; forward 1.50 m reached (5.311,-0.175). This return used fresh clearance observations and an empty retracted arm.

## Measured cup acquisition and staging

Initially the white cylindrical cup stood on the middle teal mat. The purple mat was to its left and the orange mat to its right from the acquisition view. Cup dimensions are not specified by these measurements.

- Observation 134 from acquisition base (6.813,-0.175), heading -0.0007: pixel (198,178) projected the cup's visible side to (0.9536,0.1729,0.9513) in the base frame. The empty retracted arm was lowered to (0.20,0,0.70) to expose the cup.
- Default PositionGrasp at (0.98,0.174,0.95) completed; observation 135 showed alignment. Requested closure 0.025 m gave bilateral contact, measured opening 0.0634 m, effort 11.578. Lift to z=1.20 confirmed secure lift, opening 0.0635 m. One successful measured grasp; do not reuse coordinates without fresh perception.
- Carried at retracted (0.25,0,1.10). A later side viewing posture (0.22,-0.35,1.05) retained bilateral contact, but secure-lift feedback was false after the final approach. Raising again restored secure lift before staging. The cup was not observed to fall.
- Observation 139 from (6.274,0.272), heading 2.4486: cabinet top pixel (270,140) projected to (1.3211,-0.1664,1.0568). B handle pixel (229,203) projected to (1.2494,0.0587,0.7158). These are surface samples, not centers or operation instructions.
- At staging base (5.966,0.527), heading 2.4491, raised cup to z=1.25, extended to (0.94,-0.17,1.19), then lowered to z=1.12 and released to opening 0.15. Retracted empty and lowered arm to travel posture. Observation 143 clearly showed the cup upright on the cabinet top above drawer B. Approximate cup location is (5.35,1.26), supported by a top surface at z about 1.057.

The cup is now on the cabinet, **not on its original countertop mat and not inside B**. This is continuation state, not a permanent environment rule. Reobserve before reacquisition. All staging and retraction finished before the first observed warning.

## Drawer observations and unresolved operation

Observations 139–143 clearly showed the A and B markings. A was already extended/open before interaction; B remained closed. Both had dark horizontal handles. A bright orange block was visible near the upper left of B's front. It may be part of the mechanism, but its function was not tested. No handle pull, push, latch press, drawer motion, or containment procedure was attempted. Do not infer that A's initial state establishes B's operation.

The task remained `task_success=false`. Remaining work: discover and operate B, reacquire the staged cup, place it inside, and verify physical success.

## Kitchen charging contact

Observations 124, 126, and 146–148 identified the green pad, yellow mark, and dark backstop near the entrance. From (5.311,-0.175), heading pi, observation 147 projected the yellow mark to (1.3053,0.8077,0.0070), pixel (123,268), and a backstop surface to (1.6125,0.8835,0.1926), pixel (126,221).

Turn +0.55 to heading 3.6916, then advance 1.25 m reached (4.245,-0.829). `dock` rejected for no charging contact. Another 0.20 m with settling reached (4.075,-0.934); docking then succeeded. Final status at simulation time 3648.248: docked=true, inactive, battery 100%, odometry (4.077,-0.933), heading 3.6916, empty open gripper, arm commanded (0.22,0,0.70), head pan 0/tilt 0.40.

One successful kitchen docking, not a repeatable macro. Visual pad overlap alone did not establish contact. The reverse departure and route from this dock to the cabinet have not been traversed; inspect fresh clearance.
