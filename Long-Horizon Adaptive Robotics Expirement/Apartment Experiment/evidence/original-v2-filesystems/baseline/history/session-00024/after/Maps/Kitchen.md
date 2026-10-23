# Observed kitchen route and cup handling

Sensor-grounded history from sessions 005–009, 011, 012, 014, 021, and [024](../SessionReports/2026-10-08-session-024.md), not a surveyed map or executable procedure. Coordinates are uncertain session-independent dead reckoning. Reconcile live assignment, images, range, and pose before using any geometry. **The latest cup-to-A assignment was completed in session 024**: the tabletop cup was securely acquired and deliberately released inside already-open A; a wrist image and task_success confirmed containment. A stayed open and B was seen closed; neither drawer was operated. Earlier assignments' cup positions are historical. Ten kitchen dockings and four observed B openings are recorded. The orange fitting's mechanism and the differing handle-contact feedback remain unresolved.

## Session 024: second deliberate A containment and tenth kitchen docking

A fresh cup-to-A assignment began at the living-room charger, approximate **(-1.893,-0.848)**, heading **3.9746**. All **24 observations 695–718** were rendered and viewed; **713** is wrist RGB. The cup was upright on the middle teal mat. A was open and B closed when inspected at placement; the intervening fixture/cup changes were not observed.

### Inspected departure and tabletop pickup

Rear view **696** preceded reverse **1.18 m**, with settling, to **(-1.099,0.025)**. Raised the empty retracted arm to **(0.22,0,1.10)** and turned **+2.3086** to heading zero. Viewed **698**, advanced **1.50 m**, then viewed **699** before turn **+0.265**, advance **1.50 m**, and turn **-0.265**, with settling between motions, reaching **(1.850,0.419)**. Current imagery/range supported the familiar passage through advance **1.08 m**, turn **-0.45**, advance **1.20 m**, and turn **+0.45** to **(4.012,-0.104)**. These are measured route examples, not a navigation macro.

Inspected advances **1.50 m**, **1.27 m**, and **0.105 m**, with empty-arm lowering for perception before the last segment, reached **(6.887–6.889,-0.104)**. Forward lidar was about **0.34 m**; no further approach. Observation **705**, pixel **(213,114)**, projected cup side **(0.8802,0.0999,0.9502)**, a noisy surface rather than a center.

Default PositionGrasp at **(0.911,0.102,0.95)**, request **`2061ac9c16c44297a383dab6f123a606`**, completed **17218.532**. Alignment **706** was inspected before separate closure **0.025** over **0.7 s**. Closure **`c16737b0f6ee4cbbacecef0af52e62a4`** completed **17230.200**; status **17230.280** confirmed bilateral contact, width **0.0635**, effort **11.579**. Lift **`039a8daf4d564700a00437e252aaf28e`** to **z=1.20** completed **17231.512**; status **17231.592** confirmed secure lift. Retracted to **(0.25,0,1.15)** before transport; contact/lift persisted.

### A placement adapted to the current base

Rear views **707–708** preceded reverse segments **1.50 m** and **1.17 m**. Settled northward turn reached **(4.216,-0.104)**, heading **1.5708**. Shifted held cup to **(0.25,0.30,1.25)** and viewed open A in **709**, head pan **-0.12**, tilt **0.55**. Front pixels **(220,149)** and **(220,125)** projected **(0.6815,-0.0352,0.8976)** and **(0.6817,-0.0385,0.9765)**. These are front surfaces, not drawer-floor centers.

Compared with session 011, this base was about **0.045 m farther south** in uncertain odometry. With current visual clearance, extended above A to **(0.965,-0.10,1.22)** and viewed **710**; lowered to **z=0.92** and viewed **711**. Bilateral contact persisted; the secure-lift flag became false at the lower posture. Deliberate opening **0.15**, request **`c62b20eb1c3144dd99f7e3b5c4e28867`**, completed **17302.200**. Status **17302.264** first confirmed **task_success=true**, with **65.91** work seconds remaining.

Raised vertically, retracted, and inspected head view **712**; A's front concealed the cup. Empty wrist view from **(0.895,-0.10,1.22)**, observation **713** at **17312.264**, directly showed the cup upright inside A. Retracted without touching it. This is a second deliberate A placement and another useful overhead view, not a general placement program or a precision geometry calibration.

### Warning and charging

Views **714–716** supported a settled turn east and advance **0.70 m** to **(4.916,-0.104)**, then inspected the green pad, yellow mark, and charging backstop. Turn **-2.3916** established heading **3.8916**; restored empty arm **(0.22,0,0.70)** and head pan 0/tilt 0.45. View **717** preceded final approach **1.10 m**. Its completion status **17370.920** first reported **low_warning=true**. Only settling, contact view **718**, and docking followed.

First-call dock request **`45fdd0f37f584bb98890c19e16696596`** completed **17379.608**. Status **17379.656** confirmed **docked=true**, **battery 100%**, **task_success=true**, and no active action. Exit pose **(4.111,-0.854)**, unwrapped yaw **16.4580**; empty open gripper **0.1506**, reach encoder **0.13982**, lift encoder **0.27067**. No physical control followed. No request was rejected or blocked, and no grasp/lift check failed.

## Session 021: fourth observed B opening and third deliberate B containment

A fresh cup-to-B assignment began at the living-room charger. All observations 586–610 were rendered and viewed; 606 is wrist RGB. Current images found the cup upright on the middle teal mat, A open, and B closed. Prior completed assignments were not treated as current state.

### Departure adapted to the current living-room heading

Empty retracted arm; current rear views preceded reverse segments **1.08 m** and **1.49 m** from approximate **(-1.879,-0.870)**, heading **3.5928**, to **(0.436,0.252)**. Turn **+2.8054**, settling, and raising the retracted arm to **z=1.10** established heading **0.1150**. View 589 preceded advance **1.42 m** and turn **-0.115**, reaching **(1.848,0.416)**, heading zero. This joins the previously measured kitchen passage from a different departure heading.

Inspected advance **1.08 m**, turn **-0.45**, inspected advance **1.20 m**, and turn **+0.45**, with settling, reached **(4.012,-0.108)**. Advance **1.165 m**, turn **+1.5708**, and lowering the empty arm to z=0.70 exposed closed B in 593. Advance **0.235 m** reached **(5.179,0.130)**, heading north. Every straight segment had current visual/range clearance; no request was blocked. These are exercised measurements, not a navigation program.

### Visible opening with different closure feedback

Observation **594** projected orange-face pixel **(204,152)** to **(0.8321,0.1317,0.9286)** and handle pixel **(310,184)** to **(0.8265,-0.2762,0.7984)**. Closed to 0.015, moved through **(0.45,0.132,0.925)** toward **(0.875,0.132,0.925)**, then retracted. Press request **`0d64ce6e08fa40c3944911ded629dd27`** completed **14523.024**, effort **4.963**.

Opened to 0.15, approached **(0.805,-0.28,0.91)**, lowered to **z=0.81**, and closed to **0.015**. Unlike sessions 012/014, closure measured only **0.0141** opening and **0.243** effort; both acquisition flags remained false. Pull toward **(0.38,-0.28,0.80)** over 2 s, request **`ae11b02c152d4cd0ac3d144f9e925c81`**, completed **14529.024**. Observation **595**, **14529.152**, visibly showed B open; effort was near zero and both flags were still false. There was no intermediate image isolating when the drawer opened. Thus this confirms the full sequence's outcome, not a secure handle grasp, a particular opening phase, or the orange fitting's mechanism. Released, raised vertically to z=1.20, and retracted before driving. No closing was attempted.

### Confirmed pickup and containment

Rear view 596 preceded reverse **0.24 m**, turn east, and forward view 597. Inspected advances **1.50 m** and **0.208 m**, with empty arm lowered for perception between them, reached **(6.888–6.890,-0.114)**, heading zero. Forward lidar was about **0.33 m**; no further advance was attempted. Cup-side pixel **(211,145)** in **599** projected **(0.8806,0.1102,0.9400)**.

Default PositionGrasp target **(0.911,0.112,0.95)** completed **14603.948**; viewed alignment 600. Separate closure **0.025**, request **`c27b8a7c6cd543209a9b1ed8bac514d8`**, completed **14613.204**, bilateral contact true, width **0.0632**, effort **11.579**. Lift to **(0.911,0.112,1.20)**, request **`eedb3db7b4c24e8ca5a525736bd00fc3`**, completed **14614.536**; status **14614.620** confirmed secure lift. Retracted cup to **(0.25,0,1.15)** before transport.

Rear view 601 preceded reverse **1.50 m** and a settled northward turn, reaching **(5.386,-0.114)**. Shifted the held cup to **(0.25,0.30,1.25)** to expose B in **602**. Pixel **(220,154)** projected front surface **(0.6701,0.0591,0.9794)**, not interior floor. This surface height differed from earlier samples and was not treated as a drawer dimension.

Extended above B at **(0.92,0.085,1.22)**, viewed **603**, lowered to **z=0.92**, and viewed **604**. Bilateral contact persisted until opening; the secure-lift flag became false at the low posture. Deliberate release **0.15**, request **`a39f9590218e461282687c9edfbca85d`**, completed **14661.360**. Settled, raised vertically to z=1.25, and retracted. Observation **605**, **14664.104**, confirmed **task_success=true** with **18.56** work seconds left. Empty wrist at **(0.85,0.085,1.22)**, image **606**, **14670.400**, directly showed the cup upright inside B. Retracted without touching it. Both drawers stayed open.

### Ninth kitchen docking

Viewed westward clearance in 607 with the empty arm retracted high. Status **14685.900** first reported warning=true; only return sensing/navigation and docking followed. Turn west, view 608, advance **0.470 m**, turn **+0.75**, and arm restoration to **(0.22,0,0.70)** reached **(4.914,-0.114)**, heading **3.8916**. Image **609** identified the green pad, yellow mark, and backstop. Advance **1.10 m**, settling, and image **610** established contact.

First dock request **`9b561eeb21c34ea995cb3d548677c578`** completed **14720.212**. Status **14720.320** confirmed **docked=true**, battery **100%**, **task_success=true**, and no active action. Exit pose **(4.109,-0.864)**, unwrapped yaw **16.4580**; empty open gripper **0.1498**, reach encoder **0.13955**, lift encoder **0.26973**, head pan 0/tilt 0.45. Physical control ended; no post-dock motion followed.

## Session 014: repeated B opening and deliberate cup containment

A fresh cup-to-B assignment began at the living-room charger. Viewed observations 383–408 cover the complete route and handling; 404 is the wrist camera. Current views found the cup on the middle teal mat, A open, and B closed. The intervening change from session 012 was unobserved.

### Settled living-room-to-kitchen route

The empty arm was retracted and raised to (0.22,0,1.10) after leaving the pad. Every straight segment had current image/range clearance; turns settled before driving. No motion was blocked. This is another observed route, not a navigation macro.

| Endpoint x,y m | Heading rad modulo 2pi | Inspected motion |
|---|---:|---|
| (-1.097,0.025) | 0 | Rear observation 384, reverse 1.18 m from the living-room dock, turn +2.3086, settle. |
| (0.405,0.025) | 0 | Advance 1.50 m, observation 387. |
| (1.854,0.411) | 0.26 | Turn +0.26, settle, advance 1.50 m, observation 388. |
| (2.934,0.411) | 0 | Turn -0.26, settle, advance 1.08 m, observation 389. |
| (4.015,-0.112) | 0 | Turn -0.45, settle, advance 1.20 m, settle, turn +0.45, observation 390. |
| (5.177,-0.111) | 1.5708 | Advance 1.16 m, settle, turn north; lower empty arm to z=0.70; observation 391 confirmed B closed. |
| (5.177,0.130) | 1.5708 | Advance 0.24 m, settle; drawer-operation view 392. |

### Third observed B opening

Observation 392 projected orange-face pixel (204,152) to **(0.8319,0.1317,0.9287)** and right-handle pixel (310,184) to **(0.8297,-0.2772,0.7968)**. These are visible surfaces. Geometry closely matched session 012.

Closed to width 0.015, moved through **(0.45,0.132,0.925)** toward **(0.875,0.132,0.925)**, and retracted. Press request `12306a781d1c4b859905e842d37bae71` completed **9666.312**, effort about **4.22**. Opened to 0.15, approached **(0.805,-0.28,0.91)**, lowered to **z=0.81**, and closed to **0.015**. Closure measured width **0.0359**, effort **6.30**; both grasp flags stayed false.

Pulled to **(0.38,-0.28,0.80)** over 2 s, request **`1aba69ba56784be197e90e0e72b145c3`**, completed **9676.888**. Observation **393**, **9676.920**, visibly confirmed B extended. Both flags remained false, effort about **6.28**. Released, raised vertically to z=1.20, and retracted high. This first press/pull attempt succeeded without the preliminary failed pulls used in session 012. It repeats a complete sequence; it does not independently establish the press's necessity or internal mechanism. No drawer closing was attempted.

### Fourth measured tabletop pickup and second deliberate B release

Rear observation 394 preceded reverse 0.24 m, a settled eastward turn, and forward inspection 395. Advance 1.50 m, lower empty retracted arm to z=0.70, inspect, then advance 0.21 m reached **(6.889,-0.113)**, heading zero. Forward lidar was **0.334 m**. Observation **397**, pixel **(211,145)**, projected cup side **(0.8798,0.1101,0.9402)**.

Default PositionGrasp target **(0.910,0.112,0.95)** completed **9739.160**; image 398 showed open alignment. Closure **0.025**, request `ba847c04252b4adfb1baa29fec2e9ff6`, completed **9747.192**, with bilateral contact, width **0.0643**, effort **11.578**. Lift to **(0.910,0.112,1.20)**, request `7296d85b15684b919e75fe7d1d6f75f0`, completed **9748.512**; status **9748.608** confirmed secure lift and bilateral contact. Retracted to **(0.25,0,1.15)** before driving.

Rear observation 399 preceded reverse 1.50 m and a settled northward turn, reaching **(5.385,-0.113)**. Shifted the held cup to **(0.25,0.30,1.25)**; image 400 exposed B. Front surface pixel (220,154) projected to **(0.6794,0.0629,0.8802)**, not the interior floor.

Extended at **(0.92,0.085,1.22)**, inspected 401, lowered at the same x/y to **z=0.92**, and inspected 402. Bilateral contact persisted until deliberate opening; secure-lift became false at the low posture. Release to **0.15**, request **`ac8ed9f94b5e43f78ac484cb2e83b787`**, completed **9796.864**. Settled, raised vertically to z=1.25, and retracted. Observation **403**, **9799.576**, reported **task_success=true** while the front concealed the cup. Empty wrist at **(0.85,0.085,1.22)**, observation **404**, **9805.312**, directly showed the cup upright inside B. Retracted without further cup contact. Both drawers remained open.

This repeats session 012's deliberate placement and overhead verification at nearly the same geometry. Coordinates remain perception-dependent examples, not general dimensions or an autonomous procedure.

### Eighth kitchen docking

Inspected westward clearance in 405, turned west, inspected 406, advanced **0.467 m** to **(4.916,-0.113)**, turned **+0.75**, and restored empty arm **(0.22,0,0.70)**. Observation 407 showed green pad, yellow mark, and backstop at heading **3.8916**. Reviewed kitchen history and updated existing memory evidence while stationary.

First observed warning: status **9859.012**, task_success=true. Only final return/docking followed. Advance **1.10 m**, settling, and observation **408** reached the contact pose. Dock request **`3849243d9b9b4ee5a1ca5425ba3c53b0`** completed **9872.452**. Status **9872.560** confirmed **docked=true**, **task_success=true**, battery **100%**, and **no active action**. Final odometry **(4.111,-0.863)**, unwrapped yaw **16.4580** (heading **3.8916**). Empty open gripper **0.1503**, measured reach **0.14013**, lift encoder **0.27032**, head pan 0/tilt 0.45. First dock call succeeded; physical control ended.


## Session 012: B opening, tabletop pickup, and controlled containment

Fresh status issued a new cup-to-B assignment at the kitchen charger. Observation 326 showed the cup upright on the teal mat; observation 327 showed A open and B closed. No intervening world transition from session 011 was observed.

### Handle attempts and opening

After rear inspection, reverse 1.45 m and turn -2.3207, with settling, reached approximately **(5.176,0.130)**, heading north (unwrapped yaw **7.8539**). Head pan 0/tilt 0.45. Observation 327 projected a right-handle surface at pixel (310,184) to **(0.8359,-0.2756,0.7941)** and orange face at (204,152) to **(0.8293,0.1346,0.9294)**. These are visible surfaces, not supplied centers.

Two pulls before the orange press failed:

- Approach **(0.805,-0.28,0.90)**, lower to z=0.81, close to 0.015, then retract to x=0.42. Closure measured only about 0.0182 opening and 0.43 effort. Contact constrained the arm and briefly displaced the base to (5.174,0.074), yaw 7.8313; retraction restored the earlier pose. Observation 328 showed B still closed.
- Observation 328, pixel (317,194), projected a nearer handle surface to **(0.7384,-0.2783,0.8027)**. Approach at **(0.75,-0.28,0.91)**, lower to z=0.80, close to 0.015, and pull to x=0.38 also failed. Closure measured width 0.015 and effort 0.103. Observation 329 again showed B closed.

With the gripper still commanded closed, moved via **(0.45,0.135,0.925)** toward **(0.875,0.135,0.925)** and retracted to x=0.45. The press generated effort about 4.806. Opened to 0.15, approached **(0.805,-0.28,0.91)**, lowered to **z=0.81**, then closed to **0.015**. This time measured opening was about **0.035–0.037** and effort **6.28**, while both grasp flags stayed false.

Pull to **(0.38,-0.28,0.80)** over 2 s, request **`3bd7a967e0ae459cbd8c5262f213a29b`**, completed at **8176.696**. Observation **330**, **8176.756**, clearly showed B open. Opened the gripper, raised vertically to z=1.20, and retracted clear. This is a second successful B opening after an orange press, with two preceding failed unpressed pulls in this session. It strengthens the association but does not isolate the fitting's mechanism or prove necessity/sufficiency; the approach also changed slightly. No automatic drawer capability was promoted.

### Tabletop pickup and deliberate B placement

With the empty arm retracted high and rear clearance inspected, reversed 0.24 m to y=-0.112, turned east, advanced 1.50 m, lowered the empty arm to z=0.70, then advanced an inspected 0.21 m. Acquisition base **(6.888,-0.112)**, heading zero; forward lidar about **0.334 m**. Observation **334**, pixel **(211,145)**, projected cup side **(0.8821,0.1104,0.9395)**.

Default open positioning at **(0.912,0.112,0.95)** completed at **8253.920**; observation 335 showed alignment. Closure 0.025 gave bilateral contact, width **0.0647**, effort **11.574**. Lift to **(0.912,0.112,1.20)** confirmed secure lift at **8264.612**, width **0.0636**. Retracted cup to **(0.25,0,1.15)** before driving.

Rear observation 336 preceded reverse **1.50 m**, then turn **+1.5708** and settling. Base **(5.384,-0.112)**, heading north. Shifting the held cup to **(0.25,0.30,1.25)** exposed open B in observation 337. Its front surface at pixel (220,154) projected to **(0.6792,0.0651,0.8803)**; this was not interpreted as interior floor.

Extended the held cup above B at **(0.92,0.084,1.22), pitch 0**, then lowered at the same x/y to **z=0.92**. Observations 338–339 inspected these postures. Bilateral contact persisted; the high-lift flag became false at the lower height. Deliberately opened to **0.15**, request **`fcff49253474412ab6dcf01fd3c3c172`**, completed **8316.480**. Raised vertically to z=1.25, then retracted. Observation **340**, **8319.628**, reported **task_success=true** but concealed the cup. Empty wrist at **(0.85,0.084,1.22), pitch 0**, observation **341**, **8326.912**, directly showed the cup upright inside B. Retracted without further cup interaction. Both drawers stayed open.

This adds a third measured tabletop pickup and the first deliberate B release to the historical examples. Pose-dependent performance and current perception remain necessary; no autonomous handling program is established.

### Return and seventh kitchen docking

Observed the westward aisle, turned west with the empty arm retracted high, and advanced **0.466 m** to **(4.916,-0.112)**. Turn **+0.75** established heading **3.8916**; restored arm **(0.22,0,0.70), pitch 0**. Observation 344 identified the green pad, yellow mark, and backstop. Used the remaining work time for memory maintenance while stationary.

Live status **8390.708** first reported warning=true. Only final approach and docking followed. Advance **1.10 m**, settling, and observation **345** reached the station. Dock request **`5d48945711ba47e08eafc1bb29d76c62`** completed **8405.412**. Status **8405.536** confirmed **docked=true**, **task_success=true**, battery 100%, and no active action. Final odometry **(4.111,-0.861)**, unwrapped yaw **10.1748**; empty open gripper **0.1494**, arm commanded (0.22,0,0.70), head pan 0/tilt 0.45. Physical control closed for the invocation.

## Session 011: tabletop pickup and completed containment in A

Live status issued a new cup-to-A assignment from the living-room charger. Current images identified the upright cup on the middle teal countertop mat, A open, and B closed. No drawer was deliberately operated. The transition from the earlier cup/drawer state was not observed.

### Living-room departure and kitchen aisle

Head observations 302–310 established departure and segment clearance with a retracted arm. The arm was raised to (0.22,0,1.10) before traveling east past the bin and partition. The following are measured route examples, not a navigation macro:

| Observed endpoint | Approximate odometry x, y, heading | Motion and limitations |
|---|---|---|
| Clear living-room floor | (-1.110,0.009), 0 | Rear inspection, reverse 1.18 m from the session-010 dock, then turn +2.3087. |
| Before bin/partition passage | (0.392,0.009), 0 | Inspected eastward advance 1.50 m. |
| Kitchen entrance | (1.837,0.411), 0.2703 | Requested turn +0.30 followed immediately by advance 1.50 m. Actual heading differed from requested heading; do not replay nominal coordinates. |
| Inside entrance | (2.936,0.464), 0.0496 | Requested turn -0.2703 followed immediately by advance 1.10 m. Fresh sensing established the actual endpoint. |
| Clear aisle | (4.016,-0.059), approximately 0 | Turn -0.50, settle, advance 1.20 m, settle, turn +0.45, settle. Elevated retracted arm cleared in this episode. |
| Counter approach | (5.518,-0.060), approximately 0 | Inspected advance 1.50 m. |
| Initial cup view | (6.786,-0.060), approximately 0 | Advance 1.27 m; lower empty retracted arm to z=0.70 for perception. Forward lidar about 0.446 m. |
| Grasp base | (6.886,-0.060), approximately 0 | Advance 0.10 m with fresh sensing; forward lidar about 0.34 m. No further forward approach. |

No base request was blocked. Small heading differences were observed during the first two turn/drive pairs; their exact causes were not isolated. Later turns were allowed to settle before driving.

### Measured tabletop acquisition

- Observation 310, pixel (225,138), measured cup side (0.9844,0.0616,0.9375). After the 0.10 m approach, observation **311**, pixel **(224,148)**, measured **(0.8819,0.0603,0.9274)**. These are visible surface samples, not cup centers.
- Default open positioning at **(0.912,0.060,0.95)**, request `1ca7c84522154c1eaae12664ccb714a2`, completed at **7618.128**. Observation 312 showed the open fingers aligned around the cup.
- Requested closure **0.025**, request `cec1d541911340efaefa70181780f637`, established bilateral contact at measured opening **0.0637**, effort **11.578**. Lift to **z=1.20**, request `0b195e802dae47f589bb1577483b4481`, confirmed secure lift at **7629.744**.
- Retracted with cup to **(0.25,0,1.15)**. Both acquisition flags remained true through transport. Rear observations 313–314 preceded reverse segments **1.50 m** and **1.17 m**, reaching **(4.214,-0.059)**. Turn +1.5711, with settling, faced A at heading **1.5707** (unwrapped yaw about 14.1371).

This repeats a successful tabletop grasp pattern from session 005 with new projections and a different base pose. It does not establish a perception-free grasp macro or general dimensions.

### Deliberate placement and inspection

From base **(4.214,-0.059)**, heading north, observation 315 showed the held cup and open A. Moving the retracted held cup to **(0.25,0.30,1.25)** exposed the drawer in observation 316, head pan -0.12/tilt 0.55. Pixel (225,119) returned a far visible surface **(1.4789,-0.0841,0.7560)**, while (218,129) returned the near front **(0.6571,-0.0223,0.9818)**. Neither was treated as a drawer-floor center.

Extended the cup above the opening at **(0.92,-0.10,1.22), pitch 0**, request `58b4910a65084669a892e2e32de1d22d`. Observation 317 showed the held cup above the opening with both acquisition flags true. Lowered at the same x/y to **z=0.92**, request `e9ba77af9a14427488deaa9e143ab487`, completed at **7713.052**. Observation 318 showed the lowered fingers; bilateral contact persisted at width about 0.0636 and effort 11.578, while secure-lift became false at the lower posture.

Deliberately opened to **0.15**, request **`d85a0b395ff3405f85ddb05832b8a372`**, completed at **7722.940**. Raised the empty gripper vertically to z=1.25, then retracted. Observation **319**, **7726.416**, reported **task_success=true**; the head image still concealed the cup behind the front. An empty wrist view from arm **(0.85,-0.10,1.22), pitch 0**, observation **320**, **7737.712**, directly showed the cup upright inside A with success still true. Retracted without touching the cup. A remained open; closing was unnecessary for the accepted result.

This is one controlled release into A with visual containment verification, not an established autonomous placement program. The wrist view repeats the usefulness of session-007 overhead inspection at slightly different geometry.

### Return and sixth kitchen docking

With empty arm retracted high, observed the eastward aisle, turned -1.642 from north, and advanced 0.704 m at heading about -0.0712 to **(4.919,-0.109)**. Turn -2.3205 established heading **3.8914**; lowered empty arm to **(0.22,0,0.70)**. Observation 323 showed the green pad, yellow mark, and backstop. Live status **7781.900** first reported warning=true. Only the final charging approach and docking followed.

Advance **1.10 m** and settling reached approximately (4.112,-0.860), observation 324. Dock request **`a31c445b41ea449685d437c46a5e7dcb`** completed at **7799.384**. Status **7799.508** confirmed docked=true, inactive, battery 100%, **task_success=true**, final odometry **(4.114,-0.859)**, unwrapped yaw **10.1746** (heading **3.8914**). Empty open gripper **0.1501**, commanded arm (0.22,0,0.70), pitch 0, head pan 0/tilt 0.45. Physical control closed for that invocation.

## Session 009: floor pickup and completed containment in B

Current sensing found the cup again beside the far counter, approximately (7.50,1.89). Its motion from session 008's last exposed-floor sighting was not observed; no reset or path is inferred.

### Approach and failed attempts

After observing rear clearance, reversed 1.10 m from the kitchen pad to (4.918,-0.113). Turned to heading zero, advanced 1.50 m to (6.420,-0.113), turned +1.255, and advanced 1.20 m to (6.791,1.028). Lowered the empty retracted arm to (0.22,0,0.25). Observation 240 pixel (304,235) projected the cup upper surface to (1.0366,-0.4038,0.0609). A further 0.25 m approach reached (6.869,1.267), heading 1.255. Observation 241 pixel (312,270) gave (0.7890,-0.3954,0.0533).

Two pitch-1.35 approaches from this oblique, laterally offset geometry failed: (0.785,-0.395,0.13), width 0.12 then closure 0.02; and (0.765,-0.40,0.075), width 0.105 then closure 0.02. Both encountered constrained arm coordinates and small base displacement. Lifts left the cup on the floor; neither closure established bilateral contact. Retraction cleared contact. These are failed pose-specific attempts, not reusable instructions.

### One successful grasp

Retracted before turning -0.45 to heading **0.8052** (reported unwrapped yaw 7.0884), base approximately **(6.868,1.266)**. Observation **248**, pixel **(234,260)**, measured the cup surface at **(0.8517,0.0311,0.0569)**. This brought the cup almost directly forward. The successful attempt used:

1. Open width 0.14; approach (0.865,0.018,0.25), pitch 1.35; lower to z=0.055. Observation 249 inspected alignment. Contact initially kept measured height above target and perturbed the base slightly.
2. Close to requested width **0.015**, request `8beee5bdb5ca47b987e1e086436c333d`, completed at 6082.620. Bilateral contact=true, measured width 0.0730, effort 17.18; secure-lift=false.
3. Lift to (0.82,0.025,0.40), pitch 1.35; retract/lift to (0.30,0,0.75), pitch 1.35. Bilateral contact persisted at opening about 0.063–0.064 and effort 14.55, but secure-lift remained false. Do not infer the flag's cause from these correlated changes.
4. Raise to **(0.30,0,1.15), pitch 0**, request `386bf444687e432f936685260226aae9`, completed at **6103.032**. Both bilateral-contact and secure-lift flags were true. Subsequent transport/extension retained them. Observation 253 clearly showed the cup hanging upright between the fingers.

This establishes one successful acquisition with current sensing, not a robust floor-grasp macro. Changing heading, centering, height, and orientation all differed from the failures; their individual causal contributions were not isolated. Default PositionGrasp was consulted but not invoked for this pitched approach.

### Side approach and placement

With the cup retracted high, observed behind and reversed **0.80 m** at heading 0.8052, reaching **(6.313,0.687)**. Turned +2.3364 to face west (heading pi). Observation **253** showed the open right drawer B and held cup. Pixel (279,183) projected exposed drawer interior to **(0.8904,-0.1753,0.6362)**. Other samples on the nearer side/front were about x=0.60, z=0.65; they were not treated as the placement center.

Extended to **(0.88,-0.16,1.14), pitch 0**, keeping both grasp flags true. Then lowered at the same x/y to **z=0.85**, request `83c506fb6b4546f6a8bfc76f89e0b94e`, completed **6152.860**. The cup separated from the fingers during lowering, before any open command. Observation **255** at **6152.920** showed the cup lying inside B, empty closed fingers, and **task_success=true**. The exact contact/slip mechanism was not isolated; this was not a clean deliberate release sequence.

Raised the empty arm vertically to z=1.22, retracted to (0.22,0,1.10), and opened width 0.15. Observation **256** at **6162.780** again showed the cup inside B and task_success=true. Both drawers remained open. Closing B was unnecessary for this accepted completion; its operation remains untested. No further task manipulation occurred.

### Return and charging

Observed southward clearance, turned to heading 3pi/2, and lowered the empty retracted arm to z=0.70. First observed warning was observation **258**, **6188.264**. Only return/docking work followed. Advanced 0.80 m south to (6.313,-0.115), turned west, advanced 1.395 m to (4.916,-0.113), turned +0.75, and approached the observed station 1.10 m. Each segment was checked with current sensing.

Dock request **`0d590e6c31dd4ec4963ef64625cda1ed`** completed at **6249.060**. Status **6249.076** confirmed docked=true, no active action, battery 100%, and task_success=true. Final approximate odometry **(4.113,-0.862)**, unwrapped yaw **10.1747** (equivalent to **3.8915**). Arm commanded (0.22,0,0.70), pitch 0; empty open gripper 0.1507; head pan 0/tilt 0.45. Successful docking closed physical control for the invocation.

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

This establishes one opening sequence, not the necessity or sufficiency of the orange press or repeatability of the support grasp. The grasp feedback flags did not certify fixture contact; visible drawer motion established the result. Closing remains untested; cup placement was subsequently completed in session 009 above. No reusable drawer program is established.

## Failed cup reacquisition and last sighting

From base (5.313,0.175), heading 1.5716, observation 160 pixel (246,138) projected the upright cup side to (1.0585,-0.0285,1.1031). This was beyond the 1.03 m commanded arm reach. The attempted near-limit grasp at (1.03,-0.03,1.11), after an approach at z=1.25, only partly engaged the cup. Closure 0.025 briefly reported bilateral contact and secure lift, opening 0.0488, effort 7.13. Lifting to z=1.29 lost contact and the opening returned to about 0.025. Observation 162 showed the cup lying on its side on the cabinet, not held.

The cup then rolled left across the top. Observation 164, from base (5.312,0.274), heading 1.5716, projected its visible circular end at (116,145) to (0.9763,0.5058,1.0855). This corresponds approximately to odometry (4.81,1.25), z=1.09. Observation 165 was the last clear sighting, still lying near the left part of the cabinet top. The cup was no longer identified in subsequent frontal and leftward views 167–172. No fall or final resting place was directly observed.

Those observations motivated session 007's cabinet search. Session 008's positive floor sightings below supersede that search priority; the intervening path from cabinet to floor was never observed. The task stayed `task_success=false`. A near-limit partial grasp is not a substitute for positioning the base so the measured object center is comfortably reachable.

## Kitchen charging contact

Observations 124, 126, and 146–148 identified the green pad, yellow mark, and dark backstop near the entrance. From (5.311,-0.175), heading pi, observation 147 projected the yellow mark to (1.3053,0.8077,0.0070), pixel (123,268), and a backstop surface to (1.6125,0.8835,0.1926), pixel (126,221).

Turn +0.55 to heading 3.6916, then advance 1.25 m reached (4.245,-0.829). `dock` rejected for no charging contact. Another 0.20 m with settling reached (4.075,-0.934); docking then succeeded. Final status at simulation time 3648.248: docked=true, inactive, battery 100%, odometry (4.077,-0.933), heading 3.6916, empty open gripper, arm commanded (0.22,0,0.70), head pan 0/tilt 0.40.

Session 006 returned from approximately (4.954,-0.171), heading 2.4491, after the warning. Turn +1.40 to 3.8491 and a fresh forward view (173) aligned with the visible station. Advance 1.10 m with settling reached (4.116,-0.887). Docking succeeded on the first call, request `4a8710ee6c07442980a75485de16bccb`, at simulation time 4207.196. Status at 4207.320 confirmed docked=true, inactive, battery 100%, task_success=false, odometry (4.118,-0.885), heading 3.8491. Empty open gripper; commanded arm (0.22,0,0.70), pitch 0; head pan 0/tilt 0.45.

Session 007 departed the session-006 pose after observing rear clearance: reverse 1.10 m reached (4.955,-0.170), then turn -2.278 reached heading 1.5711. No close approach between the open drawers was repeated. On return, from (4.916,-0.131), heading 3.1414, turn +0.75 reached 3.8914; observation 204 showed the station. Advance 1.10 m and settling reached (4.110,-0.883). Dock request `1e964ad9dcbc4a1fa9a43d8bc5601fad` completed at simulation time 4905.316. Status 4905.332 confirmed docked=true, inactive, battery 100%, task_success=false, final odometry (4.112,-0.881), yaw 3.8914. Arm commanded (0.22,0,0.70), pitch 0, empty open gripper, head pan 0/tilt 0.45.

Session 008 departed the session-007 dock after rear observation 207: reverse 1.10 m settled at (4.916,-0.131), heading 3.8914. Turn -2.32 established heading 1.5714 and confirmed both drawers open in observation 208. Return from the floor-cup area reversed 1.20 m at heading 1.5504 to (7.048,-0.115), then turned +1.5912 and advanced 1.50 m and 0.63 m west along the observed aisle. From (4.916,-0.113), heading pi, turn +0.75 and advance 1.10 m reached the pad. Dock request `f06aba534eae46e0997a5c4f3c010c3e` completed at simulation time 5530.752. Status 5530.768 confirmed docked=true, inactive, battery 100%, task_success=false, final odometry (4.113,-0.863), yaw 3.8916. Empty open gripper; commanded arm (0.22,0,0.70), pitch 0, head pan 0/tilt 0.45.

Including session 009 above, five successful kitchen dockings and four departures are observed, with differing final poses. These are examples, not unconditional macros. Inspect current rear clearance and reconcile pose before leaving; visual pad overlap alone does not establish contact.

## Session 007 search coverage and remaining occlusions

No cup was positively identified in observations 175–205. No cup grasp or placement was attempted, and no deliberate drawer operation occurred. Both drawers remained visibly open. This narrows the observed search area but does not establish a new cup location or prove that entire compartments are empty.

| Search view | Approximate base and camera posture | Evidence and limits |
|---|---|---|
| Frontal cabinet | (4.954,-0.171), heading 1.5711, head pan 0/tilt 0.40 | Observation 178: A/B open; visible top empty; tall fronts conceal much of the drawers and floor. |
| Left end and gap beside partition | Along aisle y about -0.17 at x 4.054 and 3.504; then (3.503,0.230), heading 1.5711 | Observations 181, 183–186: no cup on the exposed top/side floor. Lowering the empty retracted arm exposed more floor. Partition, cabinet sides and legs still occlude regions. |
| A interior from above | (4.213,-0.131), heading 1.5712; wrist at arm (0.85,0,1.22), pitch 0 | Observation 190 clearly exposed the accessible drawer floor that was mostly hidden in head observation 188; no cup visible. The cabinet top still conceals the rear. |
| A top, closer wrist view | Same base; arm (1.00,0,1.35), pitch -0.70 | Observation 191: no cup on the visible A top. No view behind the cabinet was obtained. |
| Under A | Same base; arm (1.00,0,0.22), pitch -1.30 | Observation 192: no cup in the visible floor cavity between side panels and rear panel. Panels block surrounding space. |
| Between drawers | (4.817,-0.131), heading 1.5711; arm (0.72,0,0.22), pitch -1.30 | Observation 195 showed the two central supports and exposed floor, without a cup. No probe into the narrow seam was attempted. |
| Under B | Same base; arm (1.00,-0.40,0.22), pitch -1.30 | Observation 196: no cup in the visible under-B cavity; rear and side panels still conceal exterior regions. |
| Entrance side of partition | (3.317,-0.131) and (2.766,-0.131), heading 3.1414; head pan -1.40/tilt 0.55 | Observations 198 and 200: no cup on visible nearby floor. The partition still blocks a direct view behind the cabinet. |

Wrist inspection motions were approached by retracting before changing height and extending in the observed clear region. All coordinates depend on the listed base pose. They are evidence of individual viewing postures, not a collision-free inspection macro. The wrist views improved coverage but did not locate the cup.

At the end of session 007 the last positive sighting was still session 006 observation 165. Rear/exterior cabinet floor, hidden drawer regions, and space beyond the partition were unresolved candidates. Session 008's floor sightings supersede those candidates as the immediate cup-search priority, without proving those older regions fully inspected.

## Session 008: floor localization and unsuccessful retrieval

Head observations 207, 209, and 210 showed a small white cylinder near the far counter's base. A closer view in 212 and subsequent observations identified it as the cup lying on its side. Its path from the earlier cabinet sighting was not observed.

From (4.916,-0.131), turned to heading 0.0004 and advanced 1.15 m to (6.066,-0.131). Observation 212, head pan 0.65/tilt 0.60, pixel (178,145), projected the cup surface to base-relative (1.4241,1.9965,0.048), approximately odometry (7.49,1.87). Turn +0.88, head pan 0/tilt 0.65, and advance 1.30 m reached (6.894,0.871). Lowering the empty retracted arm exposed the cup. Observation 215, pixel (212,209), gave (1.1539,0.1846,0.0552). A further 0.28 m approach reached (7.074,1.089), heading 0.8804; forward lidar was about 0.423 m, with much shorter right-side ranges. Observation 216, pixel (209,244), gave (0.8650,0.1765,0.0548). No further drive toward the counter was attempted.

Retrieval attempts did not establish bilateral contact or secure lift:

- Default PositionGrasp target (0.89,0.177,0.05) encountered surrounding contact: the measured lift encoder was -0.30496 (arm height about 0.125), reach 0.7574, and base shifted to (7.002,1.070), heading 0.9465. Observation 217 did not establish alignment or acquisition. Retraction cleared the contact and returned the base near the earlier pose.
- A low approach through (0.65,0.177,0.08) toward (0.83,0.177,0.055), pitch 0, also deviated from its target and displaced the base. Closure 0.025 produced no bilateral contact. This was unsuccessful; do not replay it as a grasp macro.
- After retraction, opening, and a +0.67 turn, base was (7.073,1.087), heading 1.5504, approximately parallel to the counter. Observation 220, pixel (314,253), measured cup surface (0.7966,-0.4131,0.0636). An approach (0.79,-0.40,0.12), narrowing to width 0.09, then (0.81,-0.418,0.047) remained constrained. Closure 0.02 showed asymmetric finger encoders and effort 5.99, but no bilateral contact; lifting to z=0.30 lost the effort and left the cup on the floor in observation 222.
- An angled approach at pitch 1.0, via (0.65,-0.35,0.30) toward (0.78,-0.428,0.15), width 0.10, displaced the cup away from the counter. Observation 223 showed it left of its prior position. Closure 0.02 and lifting again failed to acquire it.
- Observation 224, pixel (257,262), measured the moving cup at (0.7404,-0.0939,0.0619), from base (7.071,1.087), heading 1.5509. A subsequent pitch-1.0 approach at (0.74,-0.10,0.15), width 0.12, then closure 0.02 and lift, also failed. Observation 226 showed the cup still on the floor and farther left. A different projection at pixel (280,258) sampled floor, not cup, and was not used as the grasp target.

Exact contact surfaces were not isolated. Arm request completion did not mean requested coordinates were attained, and effort was not proof of a cup grasp. No successful floor-cup grasp or new reusable manipulation procedure was established.

### Session 008 last floor sighting (superseded by session 009)

After retracting empty and opening, observation **227** at simulation time **5443.020** showed the cup lying on exposed floor. Base was (7.073,1.086), heading 1.5505, head pan 0/tilt 0.65. Pixel **(231,268)** projected to **(0.7027,0.0446,0.0642)** in that base frame, approximately odometry **(7.043,1.789)**, z=0.064. This is a visible upper surface, not the object's center.

The cup changed position between observations 223–227. Its final resting pose was **not** established, and it was not reobserved during that return/docking. At the end of session 008, fresh floor localization was still required. Session 009 above completed that work and contained the cup in B; these old coordinates are not a current grasp target. Both drawers remained open in session-008 cabinet/return views, and task_success was still false then. No deliberate drawer operation occurred in session 008.
