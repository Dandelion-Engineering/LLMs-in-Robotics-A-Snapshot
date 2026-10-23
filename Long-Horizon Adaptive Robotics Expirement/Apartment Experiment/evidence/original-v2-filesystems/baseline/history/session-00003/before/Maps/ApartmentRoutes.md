# Observed apartment routes

These are sensor-grounded notes, not a surveyed map or executable route. Coordinates are approximate, session-independent dead reckoning. Reconcile current pose, RGB-D, and lidar before motion; inspect each segment and allow settling. Clearance applies to the retracted arm used in session 002.

## Living-room charger and bedroom

Evidence: [session 002](../SessionReports/2026-10-07-session-002.md), observations 39–40 and 49–55. This table reverses the successfully traversed return path; the full outbound route in this form has not been tested.

| Landmark | Approximate odometry x, y (m) | Observed route information |
|---|---|---|
| Living-room charging pad | -1.88, -0.87 | Green pad, yellow mark, dark backstop, beside teal sofa. Docked at yaw 3.593 rad in session 002. |
| Clear approach floor | -0.91, -0.39 | Return heading 3.593; then 0.86 m and 0.22 m forward to dock contact. |
| Living-room passage approach | 0.44, 0.26 | A 1.50 m drive at heading 3.593 reached the preceding waypoint. Bedroom direction from here is approximately heading 1.573. |
| Passage beside coffee table and TV partition | 0.44, 1.76 | Cleared along north/south heading. Coffee table west; TV/partition east. |
| Bedroom entry floor | 0.44, 3.26 | Straight 1.50 m segment to preceding waypoint, traversed both directions. |

Return traveled bedroom entry → passage → living-room approach with two 1.50 m reverse segments at heading 1.573, then turned +2.02 and followed the pad approach. The reverse suggests a useful outbound path after fresh clearance sensing; do not assume the dock heading is unchanged.

### Coffee-table obstruction

Near (0.07,1.32), heading 1.555, the bedroom opening looked clear but the table occupied left-side clearance. A requested 1.50 m advance was blocked after about 0.15 m, ending near (0.09,1.47). The later passage near x=0.44 was traversable. These findings apply to the observed furniture arrangement.

## Bedroom landmarks

Looking from the living room, the blue-covered bed is left and an open brown chest is right. A dark container is behind the brown chest. The bedroom charger was not identified.

These projected visible surfaces were transformed into approximate odometry coordinates. They are not object centers or grasp targets; objects may move.

| Initial feature | Approximate x, y, surface z (m) | Evidence / limitation |
|---|---|---|
| Red toy | -0.57, 3.93, 0.058 | Observation 41, pixel (54,214); untouched in session 002. |
| Yellow toy | -0.47, 5.45, 0.034 | Observation 40, pixel (149,230); untouched. |
| Blue toy | 1.64, 5.02, 0.039 | Observation 40, pixel (384,255); untouched. |
| Green toy, former location | 1.19, 4.04, 0.066 | Observation 41, pixel (371,198); subsequently picked up. |
| Brown chest rim | 1.63, 5.57, 0.469 | Observation 40, pixel (360,185); does not define the interior. |

Green acquisition base was near (0.734,3.575), heading 0.813. Open positioning at base-relative (0.650,-0.008,0.045), closure request 0.018 m, and lift to z=0.72 produced confirmed contact/lift. Chest approach base was near (1.207,4.700), heading 1.173. Release at commanded arm (1.02,0,0.85) was followed by an empty gripper, but containment was not visible. These are single-episode particulars, not a reusable manipulation program.

## Charging contact

At (-1.681,-0.769), heading 3.593, the pad was visible beneath the robot's front but `dock` rejected for no charging contact. Another 0.22 m forward plus settling produced successful docking near (-1.878,-0.865). Confirm actual dock status; image overlap is insufficient.
