# Observed apartment routes

These are sensor-grounded notes, not a surveyed map or executable route. Coordinates are approximate, session-independent dead reckoning. Reconcile current pose, RGB-D, and lidar before motion; inspect each segment and allow settling. Clearance applies to the retracted arm used in session 002.

## Living-room charger and bedroom

Evidence: [session 002](../SessionReports/2026-10-07-session-002.md), observations 39–40 and 49–55, and [session 003](../SessionReports/2026-10-07-session-003.md), observations 56–62 and 79–87. Session 003 traversed this route both outbound and returning, with fresh sensing at each segment.

| Landmark | Approximate odometry x, y (m) | Observed route information |
|---|---|---|
| Living-room charging pad | -1.88, -0.87 | Green pad, yellow mark, dark backstop, beside teal sofa. Docked at yaw 3.593 rad in session 002. |
| Clear approach floor | -0.91, -0.39 | Return heading 3.593; then 0.86 m and 0.22 m forward to dock contact. |
| Living-room passage approach | 0.44, 0.26 | A 1.50 m drive at heading 3.593 reached the preceding waypoint. Bedroom direction from here is approximately heading 1.573. |
| Passage beside coffee table and TV partition | 0.44, 1.76 | Cleared along north/south heading. Coffee table west; TV/partition east. |
| Bedroom entry floor | 0.44, 3.26 | Straight 1.50 m segment to preceding waypoint, traversed both directions. |

Return traveled bedroom entry → passage → living-room approach with two 1.50 m reverse segments at heading 1.573, then turned +2.02 and followed the pad approach. In session 003 the outbound traversal backed 1.08 m then 1.49 m from the dock at heading 3.593, turned -2.02, and advanced 1.50 m twice at heading 1.573. Do not assume the dock heading or clearance is unchanged.

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

### Additional measured bedroom interactions

Evidence: session 003, observations 66–76. These are pose-dependent trials, not fixed grasp targets or proof of task completion.

- Red acquisition: base about (0.012,3.535), heading 2.553; observed upper surface (0.7211,-0.0139,0.0629) from pixel (242,209) in observation 66. Open positioning (0.730,-0.014,0.045), requested closure 0.018, and lift to z=0.72 confirmed contact and secure lift. Measured lifted width 0.0808 m, effort 18.628.
- Blue acquisition: base about (1.125,4.798), heading 1.230; observed surface (0.4006,-0.4022,0.0458) from pixel (330,315) in observation 72. Open positioning (0.411,-0.405,0.035), requested closure 0.018, and lift to z=0.72 confirmed contact and secure lift. Measured lifted width 0.0967 m, effort 23.108.
- From the blue-acquisition base, red was released at commanded (1.02,-0.05,0.75) and blue at (1.02,-0.10,0.70). Both were released over the chest, but their landings remained hidden by its front wall. Do not treat these release coordinates as a validated containment procedure.
- At that base, observation 74 projected the front wall/rim region to (0.8561,-0.0999,0.4207), pixel (260,184), and visible low interior to (1.5179,-0.2735,0.1186), pixel (275,157). This supports substantial front-wall occlusion of objects near the front of the interior.
- A 0.32 m advance reached (1.233,5.102), heading 1.230. Observation 75 showed a small green patch just inside the front rim; it did not expose the full toy or red/blue. This was the closest inspection pose used; close forward lidar returns preclude assuming further advance is safe.
- The return from (1.232,5.100) turned -0.07 to heading 1.160, reversed 1.50 m then 0.50 m to (0.434,3.264), and turned +0.413 to the documented passage heading. This diagonal cleared in session 003 with an empty retracted arm.
- Yellow was still visible beside the bed in observation 76. Bedroom charger was still not identified.

## Charging contact

At (-1.681,-0.769), heading 3.593, the pad was visible beneath the robot's front but `dock` rejected for no charging contact. Another 0.22 m forward plus settling produced successful docking near (-1.878,-0.865). Confirm actual dock status; image overlap is insufficient.

Session 003 repeated the final approach: from (-0.911,-0.391), heading 3.593, advance 0.86 m, inspect, then 0.22 m and settle. Docking succeeded near (-1.881,-0.862) without a rejected attempt. This is repeated evidence for the observed geometry, not an unconditional docking macro.
