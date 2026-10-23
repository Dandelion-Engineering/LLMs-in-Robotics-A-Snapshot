# Observed apartment routes

These are sensor-grounded notes, not a surveyed map or executable route. Coordinates are approximate, session-independent dead reckoning. Reconcile current pose, RGB-D, and lidar before motion; inspect each segment and allow settling. Clearance applies to the retracted arm used in session 002.

## Living-room charger and bedroom

Evidence: [session 002](../SessionReports/2026-10-07-session-002.md), observations 39–40 and 49–55; [session 003](../SessionReports/2026-10-07-session-003.md), observations 56–62 and 79–87; and [session 004](../SessionReports/2026-10-07-session-004.md), observations 88–94 and 108–117. Sessions 003 and 004 traversed this route both outbound and returning, with fresh sensing at each segment.

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

These initial projected visible surfaces were transformed into approximate odometry coordinates. They are not object centers or grasp targets; objects may move. The initial floor locations below are historical: session 004 confirmed all four toys contained through the physical task-success signal.

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
- From the blue-acquisition base, red was released at commanded (1.02,-0.05,0.75) and blue at (1.02,-0.10,0.70). Both landings remained hidden by the front wall. Session 004's all-four task success after adding yellow subsequently confirmed the earlier containment; these remain pose-dependent examples, not a general placement procedure.
- At that base, observation 74 projected the front wall/rim region to (0.8561,-0.0999,0.4207), pixel (260,184), and visible low interior to (1.5179,-0.2735,0.1186), pixel (275,157). This supports substantial front-wall occlusion of objects near the front of the interior.
- A 0.32 m advance reached (1.233,5.102), heading 1.230. Observation 75 showed a small green patch just inside the front rim; it did not expose the full toy or red/blue. This was the closest inspection pose used; close forward lidar returns preclude assuming further advance is safe.
- The return from (1.232,5.100) turned -0.07 to heading 1.160, reversed 1.50 m then 0.50 m to (0.434,3.264), and turned +0.413 to the documented passage heading. This diagonal cleared in session 003 with an empty retracted arm.
- Yellow was still visible beside the bed in observation 76. Bedroom charger was still not identified.

### Yellow acquisition and completed containment

Evidence: session 004, observations 94–107 and public completion status. This resolves prior containment uncertainty without changing earlier reports.

- From bedroom entry (0.424,3.262), heading 1.573, observation 94 pixel (153,177) projected yellow's visible surface to (2.1906,0.8835,0.0414) in the base frame. Turn +0.386 and advance 1.50 m reached approximately (-0.144,4.648), heading 1.959. This diagonal cleared in this episode.
- After lowering the empty retracted arm to (0.22,0,0.25), observation 96 pixel (241,285) projected yellow's surface to (0.8903,-0.0084,0.0507). Default open positioning at (0.898,-0.008,0.035), requested closure 0.018, and lift to z=0.72 confirmed bilateral contact and secure lift. Lifted opening was 0.0773 m, effort 17.601. One measured yellow acquisition, not an object-size specification.
- Retract with yellow to (0.30,0,0.85), turn -1.84 to heading 0.119, and advance 1.28 m reached (1.129,4.800). Turn +1.11 established heading 1.229, matching the prior chest placement base. Fresh observations confirmed clearance and held-object contact.
- Yellow was extended to (1.02,-0.10,0.75), seen hanging over the opening in observation 101, and released at simulation time 2814.660. Status at 2814.796 reported `task_success=true`, which persisted through docking. This establishes all-four containment, including the earlier red, blue, and green placements. Observation 102 still appeared empty because the front wall concealed the toys; the image alone was inconclusive.
- From placement base (1.127,4.800), a return turn -0.086 to heading 1.143 and reverse segments 1.50 m then 0.19 m reached entry (0.426,3.260). Turn +0.43 restored the passage heading. This is a different start pose and shorter diagonal than session 003's close-inspection return.
- Stationary head scans in observations 103–107 did not identify the bedroom charger. The living-room pad remained visible through the doorway. No additional bedroom route or local docking procedure was established.

## Charging contact

At (-1.681,-0.769), heading 3.593, the pad was visible beneath the robot's front but `dock` rejected for no charging contact. Another 0.22 m forward plus settling produced successful docking near (-1.878,-0.865). Confirm actual dock status; image overlap is insufficient.

Session 003 repeated the final approach: from (-0.911,-0.391), heading 3.593, advance 0.86 m, inspect, then 0.22 m and settle. Docking succeeded near (-1.881,-0.862) without a rejected attempt. This is repeated evidence for the observed geometry, not an unconditional docking macro.

Session 004 repeated the route and contact: from (-0.918,-0.394), heading 3.593, advance 0.85 m, inspect, then 0.22 m and settle. Docking succeeded near (-1.879,-0.860) on the first call. Fresh sensing and actual dock status remain required.
