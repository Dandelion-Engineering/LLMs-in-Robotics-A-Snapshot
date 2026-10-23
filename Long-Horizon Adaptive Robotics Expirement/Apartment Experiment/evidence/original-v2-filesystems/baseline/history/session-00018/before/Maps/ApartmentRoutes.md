# Observed apartment routes

These are sensor-grounded notes, not a surveyed map or executable route. Coordinates are approximate, session-independent dead reckoning. Reconcile current pose, RGB-D, and lidar before motion; inspect each segment and allow settling. Clearance applies to the retracted arm used in session 002.

## Session 017: living-room dock to the practice base

Evidence: [session 017](../SessionReports/2026-10-07-session-017.md), viewed head observations 462–465. From the freshly observed living-room contact pose (-1.882,-0.863), heading 3.5931, rear view 463 supported reverse 1.08 m to (-0.909,-0.391). View 464 showed clear floor toward the practice area, with the pedestal and bin off to the side. Raised the empty retracted arm to (0.22,0,1.10), turned -0.0623 and settled, reversed 1.094 m, then turned +1.1816 and settled. Restored head pan 0/tilt 0.55 and lowered the empty retracted arm to z=0.70. Observation 465 established the sphere on the pedestal from base (0.103,0.024), heading 4.7124. No motion was blocked. This is one measured departure from this dock heading, not an unconditional route.

Six confirmed grasp/throw trials and the alternating 0.88/0.89 results are in the canonical [ThrowOrange playbook](../Playbooks/Learned/ThrowOrange.md). The final landing was preserved without another reset. Charger views 489–490 identified the green pad, yellow mark, backstop, sofa, and westward floor. View 489 was obtained before the commanded head pan had fully settled; 490 confirmed the settled view. Return preparation used turn -2.7904 to heading pi, restored the head, and inspected 491. Advance 1.20 m and settling reached (-1.099,0.025), view 492; turn +0.833 and arm restoration to (0.22,0,0.70) gave view 493 from approximately (-1.096,0.025), heading 3.9746, with 54.71 work seconds remaining and no warning. No held object or pending action remained.

After stationary artifact maintenance, inspected advances 0.90 m and 0.28 m repeated the practice-return contact. Observation 494 showed the pad from (-1.703,-0.643); 495 showed the final approach at approximately (-1.892,-0.850), still with 4.85 work seconds. Status 11956.284 first reported the warning, already stationary on the pad. Only docking followed. Request `ae1e8ec0d77e487b96b20051fb67f92e` completed **11956.300**; status **11956.412** confirmed docked=true, battery 100%, and no active action. Final settled odometry **(-1.890,-0.848)**, unwrapped yaw **16.5410**, equivalent **3.9746**. Empty open gripper, arm commanded (0.22,0,0.70), pitch 0; head pan 0/tilt 0.45. First dock call succeeded. This repeats sessions 010/013's practice-return geometry and differs from session 016's departure heading; fresh sensing remains necessary.

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

## Kitchen to living-room practice area

Evidence: [session 010](../SessionReports/2026-10-07-session-010.md), viewed head observations 265–275. This is one sensor-guided traversal with a blocked turn, not an executable route. The kitchen aisle and earlier eastbound entry are described in [Kitchen.md](Kitchen.md).

- Started at the kitchen charger near (4.113,-0.862), heading 3.8916. After rear clearance inspection, reverse 1.10 m and turn -0.75 settled at (4.889,-0.139), heading pi. This endpoint differs slightly from the earlier kitchen departures; actual odometry was used.
- Advanced west 1.50 m to (3.387,-0.139), then raised the empty retracted arm to (0.22,0,1.10) and advanced 0.65 m to (2.737,-0.139). The blue bin was ahead-left and the partition/TV area was on the right. A rim surface projected in observation 268 to (1.0316,0.0306,0.29), showing that simply continuing along the centerline would approach the bin edge.
- Head pan -1.15 inspected the right-front floor. A requested turn -0.65 was **blocked**, request `c83e1d79586649a4a10284bf6dacf771`, at simulation time 6658.268. Settled pose was about (2.825,-0.054), heading 2.628. Exact contacting surface was not isolated. Do not treat this corner turn as cleared merely because the floor ahead looks open.
- Reobserved with the head forward. Advance 0.90 m along the actual heading cleared to (2.039,0.390). Turn +0.70 reached heading 3.328. Freshly inspected drives of 1.50 m and 0.47 m reached the practice base near (0.103,0.023). Retracted high arm posture was retained during navigation.
- Turn +1.3845 established the southward sphere-acquisition view. Fresh grasp/throw details belong in [ThrowOrange](../Playbooks/Learned/ThrowOrange.md), not in this navigation record.

### Return from the practice base

Session 010 reconciled the session-001 charger approach using current images. Observation 296 showed the green pad, yellow mark, backstop, adjacent sofa, and clear westward floor from practice base about (0.104,0.024), heading -0.360. Empty arm was retracted to x=0.36, z=1.16.

Turn -2.782 established heading pi. Observation 297 first reported the low warning, at simulation time 7120.276. Only return work followed: advance 1.20 m to (-1.098,0.024), turn +0.833 toward the pad, lower the empty retracted arm to (0.22,0,0.70), and inspect observation 299. Advance 0.90 m reached (-1.703,-0.643); a fresh view preceded a final 0.28 m approach and settling. Observation 301 showed the contact pose.

Dock request `4c84004fbaef423196da7f7873241436` completed at **7186.152**. Status **7186.276** confirmed docked=true, inactive, battery 100%, final odometry **(-1.890,-0.849)**, yaw **10.2577** (equivalent to **3.9745** radians). The first dock call succeeded. This heading differs from sessions 002–004, so their departure distances and headings must not be reused without fresh sensing.

## Session 013: earlier kitchen exit turn

Evidence: [session 013](../SessionReports/2026-10-07-session-013.md), viewed head observations 346–353. A fresh reverse view preceded kitchen-pad departure. With the empty arm retracted and then raised to (0.22,0,1.10), this route cleared without a blocked request. Coordinates are uncertain dead reckoning, not an autonomous navigation macro.

| Endpoint x,y m | Heading rad, modulo 2pi | Inspected motion |
|---|---:|---|
| (4.917,-0.111) | 3.1416 | Reverse 1.10 m from the kitchen dock, then turn -0.75 and settle. |
| (4.017,-0.111) | 3.1416 | Advance 0.90 m, then inspect the diagonal with head pan -0.45. |
| (2.937,0.411) | 2.6917 | Turn -0.45, settle, advance 1.20 m. |
| (1.835,0.411) | 3.1416 | Turn +0.45, settle, advance 1.10 m. |
| (0.371,0.084) | 3.3616 | Turn +0.22, settle, advance 1.50 m. |
| (0.101,0.023) | 4.7124 after turn | Advance 0.276 m, settle, turn +1.3508 to inspect the pedestal. |

The earlier diagonal turn avoided repeating session 010's tight turn near (2.737,-0.139). This is one successful traversal, not proof that the old obstruction moved or that either route always clears. Fresh sensing preceded every straight segment; no task object was carried during navigation.

### Session 013: repeated living-room charging contact

After six throws, observation 377 showed the green pad, yellow mark, backstop, sofa, and westward floor. From about (0.102,0.024), throwing heading -0.3514, turn -2.7902 and settling established heading pi. Observation 378 inspected the forward route. Advance 1.20 m reached (-1.100,0.024); the first observed warning was the completed-drive status at simulation time **9220.768**. Only return work followed.

Turn +0.833, settling, and empty-arm restoration to (0.22,0,0.70), pitch 0, preceded observation 380. Advance 0.90 m reached (-1.705,-0.643); observation 381 preceded a final 0.28 m approach and settling. Observation 382 showed the contact pose. Dock request `a9e8ff46cbe84792b08136030b04ba78` completed **9265.484**. Status **9265.596** confirmed docked=true, no active action, and battery 100%, at approximately **(-1.892,-0.849)**, yaw **10.2578** (equivalent to **3.9746**). The first dock call succeeded. This repeats session 010's contact geometry with current sensing; departure still requires a new observation.

## Session 015: new toy arrangement and three releases

Evidence: [session 015](../SessionReports/2026-10-07-session-015.md), viewed head observations **409–438**. This was a new four-toy assignment, not a continuation of session 004's completed assignment. All four toys were on the floor at different locations. Three were securely lifted and deliberately released over the chest opening; individual settled containment was not directly verified, and aggregate task success stayed false. Blue was untouched. These are perception-dependent examples, not navigation or manipulation programs.

### Kitchen to bedroom

The session-013 earlier kitchen-exit route cleared again with the empty arm retracted high. Reverse 1.10 m from the kitchen dock, turn -0.75, advance 0.90 m, turn -0.45, advance 1.20 m, turn +0.45, and advance 1.10 m reached about **(1.833,0.410)** facing west. Turns were settled before precise travel.

Turn **+0.107** and advance **1.40 m** reached **(0.443,0.261)**. Head pan -1.675 exposed the bedroom passage. Turn **-1.6756** established heading **1.5730** modulo 2pi. Two inspected **1.50 m** advances reached **(0.436,3.261)**. Lowering the empty retracted arm to **(0.22,0,0.25)** exposed all four toys in observation **417**. No base request was blocked.

### Fresh toy surfaces and acquisitions

At entry, observation 417 projected these visible surfaces. Odometry transformations are approximate and do not define object centers. Red, green, and yellow subsequently moved during pickup/release; blue remained on the floor when last viewed.

| Toy | Pixel u,v | Base-relative surface x,y,z m | Approximate odometry surface x,y m |
|---|---|---|---|
| Red | 230,277 | (1.0460,0.0571,0.0611) | (0.377,4.307) |
| Blue | 414,314 | (0.8161,-0.9076,0.0461) | (1.342,4.079) |
| Green | 380,212 | (1.7814,-1.2247,0.0421) | (1.657,5.045) |
| Yellow | 208,193 | (2.1214,0.3134,0.0433) | (0.118,5.382) |

- **Red:** advance 0.25 m reached base **(0.435,3.513)**, heading 1.5730. Observation **418**, pixel (228,314), projected **(0.8045,0.0590,0.0622)**. Default open positioning at **(0.812,0.059,0.045)**, inspected alignment 419, closure **0.018**, and lift to **z=0.72** confirmed bilateral contact and secure lift. Lifted width about **0.0602**, effort **12.53**. Retracted to (0.30,0,0.85), turned -0.493, advanced 1.45 m on inspected floor, then turned +0.150 to placement base **(1.120,4.791)**, heading **1.2300**.
- **Green:** at the placement base, empty arm retracted low and head tilt 0.80, observation **423**, pixel (327,272), projected **(0.4398,-0.4112,0.0705)**. Open approach via **(0.45,-0.415,0.20)** to **z=0.045**, inspected alignment 424, closure **0.018**, and lift to **z=0.72** confirmed contact/lift. Width changed from **0.0703** on closure to **0.0519** after lift; effort changed from **15.49** to **10.16**. The cause was not isolated; these are not object dimensions.
- **Yellow:** head pan 1.38 exposed yellow and the floor. Turn **+1.38**, advance **0.35 m**, and empty-arm lowering reached **(0.819,4.969)**, heading **2.6099**. Observation **427**, pixel (246,251), projected **(0.8201,-0.0362,0.0500)**. Open approach via **(0.83,-0.036,0.20)** to **z=0.035**, inspected alignment 428, closure **0.018**, and lift to **z=0.72** confirmed contact/lift. Width was **0.1116** on closure and **0.1104** after lift, then settled near **0.090** during retracted transport with both flags true. Rear observation 429 preceded reverse **0.35 m** and turn **-1.38** back to the placement base. The width change was not assigned a mechanism.

All three toys were extended to commanded **(1.02,-0.10,0.75)**. Images **422, 425, and 430** showed the respective held toy over the opening before deliberate opening to **0.15**. Release requests: red **`1a3b35379a214744afac43d35221813b`** at **10332.952**; green **`92adfdc4db9144439fec7a8aedbd4968`** at **10375.812**; yellow **`5c50d6f307de4e43833f55baab7f6a53`** at **10444.384**. Each release left empty fingers. Subsequent red/green head views concealed the landing area behind the front; yellow had no dedicated post-landing inspection because the warning was first observed in its release status. No wrist containment verification was performed. Do not substitute these releases for confirmed all-four completion.

### Warning, return, and living-room contact

First observed warning: yellow-release status **10444.432**. Only empty-arm retraction and return/docking followed. From placement base, turn **-0.087**, rear inspection, reverse **1.50 m**, inspect, reverse **0.18 m**, and turn **+0.43** reached **(0.424,3.260)** at heading 1.5730. Two inspected reverse **1.50 m** segments reached **(0.430,0.259)**. Turn **+2.020** established heading **3.5930**; observation 435 identified the green pad, yellow mark, and backstop.

Inspected advances **1.50 m**, **0.85 m**, and **0.22 m**, with settling, repeated the older bedroom-return charging approach. Dock request **`8c1fdc66ebd94c10af8841bba6d46da3`** completed **10556.980**. Status **10557.088** confirmed docked=true, battery 100%, no active action, task_success=false, approximate odometry **(-1.882,-0.863)**, unwrapped yaw **16.1594**, equivalent **3.5930**. First dock call succeeded. This heading differs from sessions 010/013's practice returns; fresh departure sensing is required. Bedroom charging was not discovered or attempted.


## Session 016: blue placement completes the resumed toy assignment

Evidence: [session 016](../SessionReports/2026-10-07-session-016.md), viewed observations **439–461**, including wrist observation **453**. Live status resumed session 015's unfinished four-toy task. After blue was securely lifted and deliberately released, observation **452**, simulation time **11061.712**, reported **task_success=true**. This confirms all-four containment and resolves the earlier red/green/yellow landing uncertainty for this assignment without revising session 015. The separate session-004 completion remains historical.

### Fresh blue acquisition and completed containment

- Departed the living-room dock after a rear view: reverse **1.08 m**, inspect, reverse **1.49 m**, turn **-2.020**, settle, then two inspected **1.50 m** advances. Reached bedroom entry **(0.425,3.259)**, heading **1.5730** modulo 2pi. Empty arm lowered to (0.22,0,0.25). Observation **444**, pixel (416,313), projected blue's visible surface to **(0.8191,-0.9188,0.0497)**. This agrees with the prior search area but was a fresh measurement.
- Turn **-0.842**, settle, inspect, advance **0.48 m** reached **(0.784,3.581)**, heading **0.7310**. Observation **446**, pixel (239,326), projected **(0.7475,0.0025,0.0522)**. Default open positioning target **(0.756,0.0025,0.035)**, request `efc9561e3af245968ca3acdca1cabe2a`, completed **11010.160**. Alignment image **447** was viewed.
- Separate closure to **0.018**, request `994f66cddd5948868734dcbee6f107b4`, completed **11021.216** with bilateral contact, measured opening **0.0937**, effort **22.614**. Lift to z=0.72, request `f93342eabf1b416fa2511a3ebb791ce1`, completed **11022.272**; secure lift confirmed with width **0.0868**, effort **20.376**. During retraction to (0.30,0,0.85), opening narrowed, eventually settling near **0.049–0.050** with effort **9.555** while contact/lift remained true. The cause was not isolated; these are not stable object dimensions.
- With fresh clearance images **448–449**, turn **+0.567**, settle, advance **1.255 m**, then turn **-0.068** reached the familiar chest base **(1.121,4.790)**, heading **1.2300**. Image **450** established the current chest approach. Extended to **(1.02,-0.10,0.75)**; image **451** showed blue held above the opening. Release width **0.15**, request `2361c6274a2448cfb048818d85d7a874`, completed **11059.560**. After settling and empty-arm withdrawal, observation **452** confirmed success.
- The head view still concealed the toys. An empty wrist at **(1.02,-0.10,1.10), pitch 0**, approached by raising the retracted arm before extension, exposed the chest interior in **453** at **11071.616**. Blue and yellow patches were visible near the front floor. Red and green were not individually identifiable in that view; physical task success is the all-four containment evidence. No placed toy was touched again. Retracted to (0.22,0,0.70) before driving.

### Return preparation

With fresh rear observations **454–457**, turn **-0.087**, reverse **1.50 m** then **0.18 m**, and turn **+0.43** reached entry **(0.424,3.260)**. Two inspected reverse **1.50 m** segments returned to **(0.430,0.258)**. Turn **+2.020** and head restoration gave the charger view **458** at **11140.976**, with **63.30** work seconds remaining and success still true. These repeated measured routes remain sensing-dependent; coordinates are uncertain dead reckoning, not executable navigation commands.


### Warning and repeated living-room docking

After stationary evidence/memory maintenance, a checked **1.50 m** advance reached **(-0.921,-0.397)**; observation **459** at **11194.572** still reported warning=false and **9.70** work seconds. Advance **0.85 m** reached **(-1.686,-0.768)**. Its completed-action status **11206.040** first reported the warning; only final charging approach and docking followed. Image **460** was viewed, then advance **0.22 m**, settling, and image **461** established the contact pose. Dock request **`57a1752312c54138addddcd9092a6c25`** completed **11222.804**. Status **11222.916** confirmed **docked=true**, **task_success=true**, **100% battery**, and **no active action**, at approximate odometry **(-1.882,-0.863)**, unwrapped yaw **16.1595**, equivalent **3.5931** radians. First dock call succeeded. Empty open gripper, arm (0.22,0,0.70), pitch 0; no physical control followed docking. The bedroom charger remains unlocated; no new bedroom charging claim is supported.
