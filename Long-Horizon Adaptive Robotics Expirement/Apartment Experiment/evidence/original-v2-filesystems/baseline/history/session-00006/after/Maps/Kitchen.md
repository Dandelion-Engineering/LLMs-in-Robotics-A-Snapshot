# Observed kitchen route and cup handling

Sensor-grounded history from [session 005](../SessionReports/2026-10-07-session-005.md) and [session 006](../SessionReports/2026-10-07-session-006.md), not a surveyed map or executable procedure. Coordinates are uncertain session-independent dead reckoning. Reconcile live assignment, images, range, and pose before using any geometry. B was opened once after an orange-block press attempt and a handle-support pull; the press's role is unresolved. Cup containment remains incomplete and its current location is unknown.

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

Session 006 tested departure from the kitchen dock at (4.077,-0.933), heading 3.6916: after viewing rear clearance, reverse 1.45 m reached (5.314,-0.174). Turn -2.12 established heading 1.5716 and a direct frontal view of B. Advance 0.35 m reached (5.313,0.177), the drawer-operation base. B was closed during that approach and is now open, so its old clearance does not establish clearance for another approach.

Later, an additional 0.10 m advance reached (5.312,0.274) with the empty arm retracted high. A lateral viewing route reversed 0.35 m, turned +1.57, advanced 0.42 m, turned -1.57, and advanced 0.38 m to (4.893,0.329), heading 1.5718. Both drawers were open. Moving the retracted gripper from (0.22,-0.30,0.95) toward (0.22,0,1.10) there produced substantial contact, finger deflection, and base displacement; this tight posture is not a safe general viewing position. Retreating 0.50 m cleared the contact and reached approximately (4.954,-0.171), heading 1.5391.

## Measured cup acquisition and staging

Initially the white cylindrical cup stood on the middle teal mat. The purple mat was to its left and the orange mat to its right from the acquisition view. Cup dimensions are not specified by these measurements.

- Observation 134 from acquisition base (6.813,-0.175), heading -0.0007: pixel (198,178) projected the cup's visible side to (0.9536,0.1729,0.9513) in the base frame. The empty retracted arm was lowered to (0.20,0,0.70) to expose the cup.
- Default PositionGrasp at (0.98,0.174,0.95) completed; observation 135 showed alignment. Requested closure 0.025 m gave bilateral contact, measured opening 0.0634 m, effort 11.578. Lift to z=1.20 confirmed secure lift, opening 0.0635 m. One successful measured grasp; do not reuse coordinates without fresh perception.
- Carried at retracted (0.25,0,1.10). A later side viewing posture (0.22,-0.35,1.05) retained bilateral contact, but secure-lift feedback was false after the final approach. Raising again restored secure lift before staging. The cup was not observed to fall.
- Observation 139 from (6.274,0.272), heading 2.4486: cabinet top pixel (270,140) projected to (1.3211,-0.1664,1.0568). B handle pixel (229,203) projected to (1.2494,0.0587,0.7158). These are surface samples, not centers or operation instructions.
- At staging base (5.966,0.527), heading 2.4491, raised cup to z=1.25, extended to (0.94,-0.17,1.19), then lowered to z=1.12 and released to opening 0.15. Retracted empty and lowered arm to travel posture. Observation 143 clearly showed the cup upright on the cabinet top above drawer B. Approximate cup location is (5.35,1.26), supported by a top surface at z about 1.057.

This was the exit state of session 005. It was superseded by the failed reacquisition and roll in session 006 below. The original mat remained empty; do not assume the cup is still upright above B.

## Drawer observations and one successful opening

Observations 139–143 showed A already open and B closed, both with dark U-shaped handles, and an orange block near B's upper left front. Session 006 observations 154–155 confirmed the same initial states and the upright staged cup.

At base approximately (5.313,0.175), heading 1.5716:

- Observation 155 projected B's horizontal handle bar at pixel (235,248) to (0.6810,0.0149,0.7921), and the orange face at (164,201) to (0.7824,0.2678,0.9180), in the base frame.
- Default PositionGrasp at (0.71,0.01,0.79), closure 0.025, and retraction to x=0.45 did not open the drawer. Closure had no bilateral contact and only about 0.29 effort. Observation 157 showed B still closed.
- With width 0.025, moved to (0.45,0.268,0.918), advanced toward (0.83,0.268,0.918), then retracted to x=0.55. The press attempt generated contact/effort and temporary base displacement; B did not visibly open. Whether a latch was released is unknown.
- Observation 158 projected the right handle support at (278,235) to (0.7600,-0.1389,0.7952). Opened gripper to 0.15, approached (0.76,-0.145,0.90), lowered to z=0.81, and closed to requested width 0.015. Measured opening was about 0.036, effort 6.28; bilateral-contact and secure-lift flags remained false.
- Pulled to (0.38,-0.145,0.80), duration 2 s. Observation 160 showed B clearly extended/open. Pull request `ea3869a3cc494a789b4fcee33e0d2bbd` completed at simulation time 3977.796. Released the handle and lifted the empty gripper vertically clear. B remained open in later views through observation 172.

This establishes one opening sequence, not the necessity or sufficiency of the orange press or repeatability of the support grasp. The grasp feedback flags did not certify fixture contact; visible drawer motion established the result. Closing and cup placement have not been tested successfully. No reusable drawer program is established.

## Failed cup reacquisition and last sighting

From base (5.313,0.175), heading 1.5716, observation 160 pixel (246,138) projected the upright cup side to (1.0585,-0.0285,1.1031). This was beyond the 1.03 m commanded arm reach. The attempted near-limit grasp at (1.03,-0.03,1.11), after an approach at z=1.25, only partly engaged the cup. Closure 0.025 briefly reported bilateral contact and secure lift, opening 0.0488, effort 7.13. Lifting to z=1.29 lost contact and the opening returned to about 0.025. Observation 162 showed the cup lying on its side on the cabinet, not held.

The cup then rolled left across the top. Observation 164, from base (5.312,0.274), heading 1.5716, projected its visible circular end at (116,145) to (0.9763,0.5058,1.0855). This corresponds approximately to odometry (4.81,1.25), z=1.09. Observation 165 was the last clear sighting, still lying near the left part of the cabinet top. The cup was no longer identified in subsequent frontal and leftward views 167–172. No fall or final resting place was directly observed.

Search should begin by reobserving the left cabinet top, drawer A, and floor/occluded areas around the cabinet's left end, without assuming which contains the cup. These are candidate search regions, not confirmed locations. The task stayed `task_success=false`; the cup still needs to be located, acquired, placed inside B, and physically verified. A near-limit partial grasp is not a substitute for positioning the base so the measured object center is comfortably reachable.

## Kitchen charging contact

Observations 124, 126, and 146–148 identified the green pad, yellow mark, and dark backstop near the entrance. From (5.311,-0.175), heading pi, observation 147 projected the yellow mark to (1.3053,0.8077,0.0070), pixel (123,268), and a backstop surface to (1.6125,0.8835,0.1926), pixel (126,221).

Turn +0.55 to heading 3.6916, then advance 1.25 m reached (4.245,-0.829). `dock` rejected for no charging contact. Another 0.20 m with settling reached (4.075,-0.934); docking then succeeded. Final status at simulation time 3648.248: docked=true, inactive, battery 100%, odometry (4.077,-0.933), heading 3.6916, empty open gripper, arm commanded (0.22,0,0.70), head pan 0/tilt 0.40.

Session 006 returned from approximately (4.954,-0.171), heading 2.4491, after the warning. Turn +1.40 to 3.8491 and a fresh forward view (173) aligned with the visible station. Advance 1.10 m with settling reached (4.116,-0.887). Docking succeeded on the first call, request `4a8710ee6c07442980a75485de16bccb`, at simulation time 4207.196. Status at 4207.320 confirmed docked=true, inactive, battery 100%, task_success=false, odometry (4.118,-0.885), heading 3.8491. Empty open gripper; commanded arm (0.22,0,0.70), pitch 0; head pan 0/tilt 0.45.

Two successful kitchen dockings and one departure are observed, with different final headings. These are examples, not unconditional macros. The session-006 exit pose differs from the departure pose tested earlier that session. Inspect current rear clearance and reconcile pose before leaving; visual pad overlap alone does not establish contact.
