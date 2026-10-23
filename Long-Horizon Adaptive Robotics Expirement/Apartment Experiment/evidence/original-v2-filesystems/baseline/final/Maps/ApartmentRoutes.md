# Observed apartment routes

These are sensor-grounded notes, not a surveyed map or executable route. Coordinates are approximate, session-independent dead reckoning. Reconcile current pose, RGB-D, and lidar before motion; inspect each segment and allow settling. Clearance applies to the retracted arm used in session 002.

## Session 036: yellow completes the resumed four-toy assignment

Evidence: [session 036](../SessionReports/2026-10-08-session-036.md), fresh yellow views **982–985**, contact/lift feedback, over-chest **988**, and wrist **989**. **Task_success=true at 27276.032** confirms all four contained, completing the work from sessions 033–035. These are sensing-dependent examples, not an executable procedure.

From living-room contact **(-1.879,-0.859)**, heading **3.5933**, settled rear **978** preceded reverse **1.08 m** to **(-0.906,-0.386)** in **979**. Inspected reverse **1.49 m**, settling, turn **-2.020**, head restoration, and settling reached **(0.435,0.264)**, heading **1.5733**, in **980**. Two separately inspected **1.50 m** advances, with **981**, reached **(0.427,3.264)**. Empty-arm lowering to z=0.25 exposed yellow near the bed in **982**, **27160.500**, with **220.58** work seconds left. Pixel **(141,194)** projected surface **(2.0969,0.9710,0.0455)**.

Turn **+0.434**, settling, and **983** inspected the clear approach. Advance **1.48 m** and settling reached **(-0.199,4.607)**, heading **2.0073**, in **984**, **27186.892**. Pixel **(240,305)** projected surface **(0.8632,-0.0027,0.0532)**. These are noisy visible surfaces, not exact centers or future grasp targets. Default open positioning at **(0.872,-0.003,0.037)** was inspected in **985** before closure **0.018**. Contact status **27222.468**: width **0.0995**, effort **24.464**. Lift to z=0.75 independently confirmed secure lift at **27223.484**, width **0.0892**, effort **21.218**. Retracted to **(0.30,0,0.85)**. Width later settled near **0.070** with both flags retained; no dimension or cause was inferred.

Settled side **986**, head pan **-1.865**, exposed the clear chest diagonal. Turn **-1.865**, head restoration, advance **1.334 m**, turn **+1.088**, and settling reached **(1.124,4.795)**, heading **1.2303**, in **987**. Image **988** showed yellow above the opening at **(1.02,-0.10,0.75)**. Deliberate opening **0.15**, request `d667c5b914d74817a406bb29f2869ebf`, completed **27275.364**. Success was still false at release-end status **27275.392**, then true after settling at **27276.032**. Raised the empty arm vertically to z=1.10; wrist **989**, **27276.892**, directly showed yellow with blue/green-colored edges near the chest front. Red was not individually distinguished and exact stacking was unresolved. Aggregate physical success confirms all-four containment. No placed toy was subsequently touched.

With **104.19** work seconds remaining at wrist verification, withdrew the empty arm high and restored **(0.22,0,0.70)**. Stationary side **990**, pan **+1.57**, covered the bed/floor; rear **991**, pan **3.10**, exposed the doorway and the living-room charger beyond. These views did not locate a bedroom charger. Existing full-sequence budgeting and overhead inspection memories already cover the relevant lessons.

After route-note maintenance, turn **-0.087**, settling, and rear **992** prepared the return. Inspected reverse **1.50 m**, settling, and **993** left **3.20** work seconds. Reverse **0.18 m** completion status **27386.092** first explicitly retained warning=true. Only charging-return work followed. Turn **+0.430**, settling, and **994** reached **(0.427,3.264)**, heading **1.5733**. Two separately inspected reverse **1.50 m** segments, views **995–996**, reached **(0.434,0.262)**. Turn **+2.020**, head restoration, settling, and **997** identified the green pad, yellow mark, and backstop. Inspected advances **1.50 m**, **0.85 m**, and **0.22 m**, with settling and views **998–1000**, established charging contact. No base request was blocked.

First dock call `47c4a83959094e0fa71254e6c7313e30` completed **27476.984**. Final status **27476.984** confirmed docked=true, battery 100%, no active action, empty gripper, and task_success=true, at **(-1.878,-0.858)**, unwrapped yaw **16.1597**, equivalent **3.5933**. Physical authority ended. All **23 observations 978–1000** were viewed, including wrist **989**. No toy work remains for this assignment; a fresh invocation must read the newly selected live assignment.

## Session 035: blue joins red and green; yellow remains outside

Evidence: [session 035](../SessionReports/2026-10-08-session-035.md), all **23 viewed observations 955–977**, including wrist **967**. Blue was independently acquired, deliberately released, and visually confirmed inside the chest. Previous red/green placements were preserved; the wrist did not separately enumerate all three. **Task_success remained false; yellow remains uncollected.** These are sensing-dependent examples, not an executable procedure.

From living-room contact **(-1.878,-0.860)**, heading **3.5932**, settled rear **955** preceded reverse **1.08 m** to **(-0.904,-0.388)** in **956**. Inspected reverse **1.49 m**, turn **-2.020**, head restoration, and settling reached **(0.436,0.263)**, heading **1.5732**, in **957**. Two separately inspected **1.50 m** advances, with **958**, reached **(0.429,3.263)**. Empty-arm lowering to z=0.25 exposed blue/yellow in **959**, **26444.312**, with **196.61** work seconds left.

Blue pixel **(49,331)** projected surface **(0.7228,0.9244,0.0517)**; yellow pixel **(141,194)** projected **(2.0990,0.9719,0.0444)**. These are noisy visible surfaces, not exact centers or future grasp targets. Turn **+0.907**, settling, and viewed **960** preceded advance **0.36 m**. Close **961** at approximately **(0.144,3.485)**, heading **2.4802**, pixel **(240,312)**, projected blue **(0.8234,-0.0026,0.0516)**.

Default open positioning at **(0.833,-0.003,0.038)** was inspected in **962** before closure **0.018**. Contact status **26511.248**: width **0.0903**, effort **21.756**. Lift to z=0.75 independently confirmed secure lift at **26512.296**, width **0.0816**, effort **19.239**. Retracted to **(0.30,0,0.85)**. Holding width later settled near **0.050** with both acquisition flags retained; no dimension or cause was inferred.

Side **963**, settled head pan **-1.55**, exposed the clear chest diagonal. Turn **-1.551**, head restoration, advance **1.50 m**, settling, and **964** reached **(1.043,4.687)**. Viewed advance **0.133 m**, turn **+0.301**, and settling reached **(1.123,4.794)**, heading **1.2303**, in **965**. Image **966** showed blue above the opening at **(1.02,-0.10,0.75)**. Deliberate opening **0.15**, request `55545ea0e236454291c5d6a25f9097ad`, completed **26583.116**. After settling and vertical empty-arm raising to z=1.10, wrist **967**, **26584.656**, directly showed blue with a green-colored edge near the chest front. Red was not individually distinguished; exact stacking remained unresolved. No placed toy was subsequently touched.

With **56.27** work seconds remaining at wrist 967, another complete handling sequence was not begun. Withdrew the empty arm high, lowered it retracted to z=0.25, and inspected yellow with settled head pan **+1.584**. View **968**, **26608.624**, pixel **(258,222)**, projected yellow **(-0.0020,1.7603,0.0457)** relative to chest base **(1.123,4.794)**, heading **1.2303**. Yellow was still outside near the bed and never manipulated. This is a historical search hint.

Restored empty arm **(0.22,0,0.70)**, turned **-0.087**, and viewed settled rear **969**. Reverse **1.50 m**, settling, and **970** left **1.88** work seconds. Reverse **0.18 m** completion status **26648.392** first explicitly retained warning=true. Only charging-return work followed. Turn **+0.430**, settling, and **971** reached **(0.426,3.263)**. Two separately inspected reverse **1.50 m** passage segments, views **972–973**, reached **(0.433,0.262)**. Turn **+2.020**, head restoration, and **974** identified the green pad, yellow mark, and backstop. Inspected advances **1.50 m**, **0.85 m**, and **0.22 m**, with settling and views **975–977**, established contact without blockage.

First dock call `69227c5a63d14c7aaa3c14cd47b3c85a` completed **26756.092**. Final **26756.108** confirmed docked=true, battery 100%, no active action, empty gripper, and task_success=false, at **(-1.879,-0.859)**, unwrapped yaw **16.1597**, equivalent **3.5933**. Physical authority ended. Preserve red/green/blue and freshly locate yellow in a subsequent authorized invocation. Bedroom charger location remains unconfirmed.

## Session 034: resumed assignment, red and green contained

Evidence: [session 034](../SessionReports/2026-10-08-session-034.md), all **28 viewed observations 927–954**, including wrists **938/945**. Red and green were independently acquired, deliberately released, and visually confirmed inside the chest. **Task_success remained false; blue and yellow remain uncollected.** These are measured examples requiring fresh sensing, not an executable procedure.

From living-room contact **(-1.877,-0.860)**, heading **3.5927**, settled rear **927** preceded reverse **1.08 m** to **(-0.903,-0.388)** in **928**. Reverse **1.49 m**, settling, turn **-2.020**, settling, and head restoration reached **(0.438,0.261)**, heading **1.5727**, in **929**. That image's head pan was still **0.2834**; its pixels and current body-relative lidar supported the next straight segment. Two separately inspected **1.50 m** advances, with **930**, reached **(0.432,3.261)**. Lowering the empty retracted arm to z=0.25 exposed all four toys in **931**, **25653.144**, with **220.56** work seconds remaining.

| Toy | Pixel in 931 | Base-relative visible surface x,y,z m | Outcome |
|---|---|---|---|
| Blue | 49,331 | (0.7243,0.9262,0.0493) | Untouched; still outside in return view 946 |
| Red | 368,204 | (1.9048,-1.1764,0.0480) | Acquired and contained |
| Green | 206,191 | (2.1619,0.3382,0.0439) | Acquired and contained |
| Yellow | 141,194 | (2.0991,0.9719,0.0443) | Untouched; also visible in 939–941 |

These are historical surface measurements, not centers or future grasp targets. Red was visibly on the floor near session 033's intended release region, resolving that session's final-pose uncertainty for this observation.

Turn **-0.5535**, settled view **932**, and advance **1.40 m** reached **(1.166,4.455)**, heading **1.0192**, in **933**. Pixel **(239,307)** projected red surface **(0.8455,0.0026,0.0609)**. Documented PositionGrasp at **(0.854,0.003,0.045)** and alignment **934** preceded closure **0.018**. Contact at **25720.504**: width **0.0596**, effort **12.530**. Lift to z=0.75 confirmed secure lift at **25721.532**, width **0.0601**. Retracted to **(0.30,0,0.85)**. View **935**, head pan **+0.21**, supported the short clear transport: turn **+0.675**, advance **0.34 m**, turn **-0.464**, with settling, to **(1.123,4.793)**, heading **1.2302**, in **936**.

Image **937** showed red held over the chest at **(1.02,-0.10,0.75)**. Deliberate opening **0.15**, request `dc6dfc74586f4421adfdaa63c7076731`, completed **25758.040**. After settling and vertical empty-arm raising to **(1.02,-0.10,1.10)**, wrist **938**, **25759.488**, showed red on the interior floor. No placed toy was subsequently touched by the arm.

Withdrew the empty arm high, lowered it retracted to z=0.25, turned **+1.364**, and settled. Head **939**, pixel **(243,258)**, projected green **(1.2046,-0.0231,0.0611)**. Viewed advance **0.37 m** and settling reached **(0.806,4.987)**, heading **2.5942**. Fresh close **940**, pixel **(244,308)**, projected **(0.8356,-0.0236,0.0662)**. Ordinary open arm approach through **(0.845,-0.024,0.20)** to z=0.045 was inspected in **941**. Closure **0.018** confirmed contact at **25815.268**, width **0.0904**, effort **21.511**. Lift to z=0.75 confirmed secure acquisition at **25816.332**, width **0.0888**, effort **21.464**. Retracted to **(0.30,0,0.85)**. Width later settled near **0.073** with both acquisition flags retained; its cause was not isolated.

Settled rear **942** preceded reverse **0.37 m**, settling, turn **-1.364**, settling, and forward-head restoration/settling. Chest **943** recorded **(1.125,4.793)**, heading **1.2302**. Image **944** showed green above the opening at **(1.02,-0.10,0.75)**. Opening **0.15**, request `12282fbb26d241e7b3dddc7ee9ee42c2`, completed **25850.368**, with **23.33** work seconds left. After settling and vertical empty-arm raising, wrist **945**, **25851.800**, showed green and a thin red edge inside the front region. Exact stacking was not resolved. Aggregate success remained false, consistent with blue/yellow outstanding.

Retracted empty arm to **(0.22,0,0.70)**, turned **-0.087**, and viewed settled rear **946**. Reverse **1.50 m** first retained **low_warning=true** at **25877.876**. Only charging-return work followed. Inspected reverse **0.18 m**, turn **+0.430**, and two separately inspected reverse **1.50 m** passage segments, views **947–950**, reached **(0.435,0.260)**. Turn **+2.020**, settling, forward-head restoration/settling, and **951** identified the green pad/yellow mark/backstop. Inspected advances **1.50 m**, **0.85 m**, **0.22 m**, with settling and views **952–954**, established contact.

First dock call `d363a36cbbb34196aa352861abcd1ed2` completed **25973.692**. Final **25973.704** confirmed docked=true, battery 100%, no active action, empty gripper, and task_success=false, at **(-1.878,-0.860)**, unwrapped yaw **16.1596**, equivalent **3.5932**. Physical authority ended. Preserve red/green; freshly locate and collect blue/yellow in a subsequent authorized invocation. The bedroom charger remains unlocated.

## Session 033: new arrangement, red pickup and floor release, no containment

Evidence: [session 033](../SessionReports/2026-10-08-session-033.md), all **20 viewed head observations 907–926**. This is a new four-toy assignment. **No containment was completed; task_success remained false.** Red was independently acquired but deliberately released toward its original floor location at warning. Its final resting pose was occluded. Blue/green/yellow were not manipulated. These are sensing-dependent examples, not an executable procedure.

From kitchen contact **(4.110,-0.849)**, heading **3.8915**, settled rear **907** preceded reverse **1.10 m** to **(4.915,-0.099)**. Raised the empty retracted arm to **(0.22,0,1.10)**, turned **-0.75**, and restored the head. Views **908–911** supported advance **0.90 m**, turn **-0.45**, advance **1.20 m**, turn **+0.45**, advance **1.10 m**, turn **+0.114**, and advance **1.40 m**, with settling. Side **912** at **(0.437,0.264)** preceded turn **-1.6828**. Two separately inspected **1.50 m** advances, with **913** between them, reached **(0.431,3.264)**, heading **1.5727**. Empty-arm lowering to z=0.25 exposed all four toys in **914**.

| Toy | Pixel in 914 | Base-relative visible surface x,y,z m |
|---|---|---|
| Blue, left foreground | 48,331 | (0.7233,0.9299,0.0508) |
| Red, right beside chest | 369,205 | (1.8962,-1.1827,0.0426) |
| Green, farther central | 206,191 | (2.1590,0.3378,0.0455) |
| Yellow, farther left near bed | 141,195 | (2.0926,0.9710,0.0367) |

These are historical visible surfaces, not centers or future targets. Turn **-0.557**, viewed **915**, and advance **1.40 m** reached **(1.169–1.170,4.454–4.456)**, heading **1.0157**. Close **916**, pixel **(238,308)**, projected red **(0.8395,0.0079,0.0610)**. PositionGrasp at **(0.848,0.008,0.045)** and viewed alignment **917** preceded closure **0.018**. Contact at **24886.740**: width **0.0812**, effort **19.070**. Lift to z=0.75 confirmed secure lift at **24887.772**, width **0.0790**, effort **18.167**. Retracted to **(0.30,0,0.85)**. No subsequent base transport occurred while holding red.

Work time fell from **58.27 s** at close view 916 to **29.99 s** at alignment 917, **12.82 s** after closure, and **10.00 s** at held-object side view **918**. Status **24901.696** first retained warning=true. Immediate safe wrap-up returned red through **(0.848,0.008,0.25)** to **z=0.065**, then opened **0.15**; request `7b04ac92c5624f0d9f8b907dd507040f` completed **24913.716**. The empty arm rose to z=0.30 and retracted to **(0.22,0,0.70)**. Head **919** occluded the release area. Intended floor location near **(1.61,5.18)** is inferred from the commanded release, **not a verified final object pose**. No chest placement was attempted after warning.

Settled rear **920** preceded reverse **1.40 m**, settling, and turn **+0.557** to entry **(0.431,3.262)** in **921**. Two separately inspected reverse **1.50 m** segments, with **922**, reached **(0.436,0.261)**. Turn **+2.020**, head restoration, and **923** identified the pad/yellow mark/backstop. Inspected advances **1.50 m**, **0.85 m**, **0.22 m**, settling, and views **924–926** established contact. First dock request `ac7f3cd6898f4683b25c9ff50e11b6ad` completed **25053.368**. Final **25053.380** confirmed docked=true, battery 100%, no active action, empty gripper, and task_success=false at **(-1.877,-0.860)**, heading **3.5927**. Physical authority ended. All four toys remain outstanding; obtain fresh observations before continuation.

## Session 031: blue and green complete the resumed assignment

Evidence: [session 031](../SessionReports/2026-10-08-session-031.md), all **27 viewed observations 858–884**, including wrists **868/875**. Blue and green were independently acquired and deliberately released. **Task_success=true at 23441.716** confirms all four toys contained and resolves the unfinished work from sessions 029–030. These are measured examples requiring current sensing, not an executable procedure.

Settled rear **858** preceded reverse **1.08 m** from living-room contact **(-1.879,-0.859)**, heading **3.5927**, to **(-0.906,-0.388)**. Rear **859** preceded reverse **1.49 m** and turn **-2.020**; no separate settling wait intervened between that drive and turn. After head restoration/settling, **860** recorded **(0.406,0.248)**, heading **1.5728**. Views **860/861** supported two separately inspected **1.50 m** advances to **(0.400,3.248)**. The route endpoint differed slightly from earlier sessions; current measurements guided subsequent movement. Empty arm z=0.25 exposed blue and green in **862**.

Blue surface **862**, pixel **(228,189)**, projected **(2.2311,0.1193,0.0300)**. Inspected advance **1.40 m** and settling reached **(0.397,4.649)**, heading **1.5728**. Close **863**, pixel **(217,311)**, projected **(0.8320,0.1183,0.0477)**. Documented PositionGrasp control at **(0.841,0.118,0.035)** and viewed alignment **864** preceded closure **0.018**. Contact at **23289.872**: width **0.0853**, effort **20.307**. Lift to z=0.72 confirmed secure acquisition at **23290.936**, width **0.0848**, effort **20.307**. Retracted to **(0.30,0,0.85)**.

Side **865**, pan **-1.379**, inspected a short clear diagonal. Turn **-1.379**, settling, head restoration, advance **0.741 m**, settling, turn **+1.036**, and settling reached **(1.126,4.791)**, heading **1.2298**, in **866**. Image **867** showed blue held above the chest at **(1.02,-0.10,0.75)**. Release **0.15**, request `257a7c813dc243fa81d32f3aee00b7a3`, completed **23336.908**. After settling and vertical empty-arm raising to **(1.02,-0.10,1.10)**, wrist **868**, **23338.544**, showed blue with a yellow border inside the front region. Red was not individually visible. Aggregate success remained false with green outstanding.

After empty-arm withdrawal/lowering, turn **+1.558** and settling produced green-search **869**. Pixel **(230,205)** projected **(1.8822,0.0861,0.0512)**. The viewed floor supported advance **1.05 m** to **(0.139,5.155)**, heading **2.7878**. Close **870**, pixel **(223,308)**, projected **(0.8352,0.0864,0.0668)**. Open arm approach through **(0.844,0.086,0.20)** to **z=0.045** was inspected in **871** before closure **0.018**. Contact at **23398.404**: width **0.0867**, effort **20.488**. Lift to z=0.72 independently confirmed secure lift at **23399.480**, width **0.0833**, effort **19.552**. Retracted to **(0.30,0,0.85)**. Holding width subsequently settled near **0.074** while both flags remained true; this does not establish an object dimension or the mechanism of the change.

Rear **872** preceded reverse **1.05 m**, settling, turn **-1.558**, head restoration/settling, and chest view **873** at **(1.128,4.790)**, heading **1.2298**. Image **874** showed green above the opening at **(1.02,-0.10,0.75)**. Release **0.15**, request `5ce52a8fb08a4f659d21bf8d1708b73e`, completed **23441.644**. Status **23441.716** first confirmed all-four success. After settling and vertical empty-arm raising, wrist **875**, **23443.292**, showed green, a yellow border, and a thin colored edge in the interior front region. It did not individually enumerate four toys or resolve stacking; physical task_success supplies aggregate containment evidence. No placed toy was subsequently touched.

Restored empty arm **(0.22,0,0.70)**, turned **-0.087**, and viewed settled rear **876**. Reverse **1.50 m** first retained **low_warning=true** at **23472.248**, after command completion **23472.240**. Only charging-return work followed. Views **877–880**, reverse **0.18 m**, turn **+0.430**, and two separately inspected reverse **1.50 m** segments reached **(0.435,0.259)**. Turn **+2.020** and head restoration identified the pad/yellow mark/backstop in **881**. Inspected advances **1.50 m**, **0.85 m**, **0.22 m**, settling, and views **882–884** established contact without blockage.

First dock call `286d319c83ac42a5a8fd80cff5827828` completed **23580.356**. Final status **23580.372** confirmed **docked=true**, **battery 100%**, **task_success=true**, and **no active action**, approximate pose **(-1.877,-0.860)**, unwrapped yaw **16.1591**, equivalent **3.5927**. Physical authority ended. No toy work remains for this assignment. The bedroom charger remains unlocated.

## Session 030: red joins yellow; blue and green remain outside

Evidence: [session 030](../SessionReports/2026-10-08-session-030.md), all **23 viewed observations 835–857**, including wrist **846**. The session-029 assignment resumed. Red was acquired, deliberately released, and directly seen inside the chest with yellow visible beneath or around it. Exact stacking was not resolved. **Task_success remained false; blue and green were not grasped.** These are sensing-dependent examples, not an executable procedure.

From living-room contact **(-1.879,-0.858)**, heading **3.5928**, settled rear **835** preceded reverse **1.08 m** to **(-0.905,-0.386)**. Rear **836** preceded reverse **1.49 m**, turn **-2.020**, and head restoration. Views **837–838** supported two separately inspected **1.50 m** advances. Lowered the empty retracted arm to z=0.25; view **839** at **(0.429,3.263)**, heading **1.5728**, showed red at the right foreground, blue farther centrally, and green farther left near the bed.

Red pixel **(417,323)** in 839 projected surface **(0.7592,-0.8828,0.0578)**. Turn **-0.861**, viewed **840**, advance **0.36 m**, and settling reached **(0.702,3.499)**, heading **0.7118**. Close **841**, pixel **(239,312)**, projected **(0.8151,0.0026,0.0630)**. Default open positioning at **(0.824,0.003,0.045)** was viewed in **842** before separate closure **0.018**. Contact status **22580.940**: width **0.0835**, effort **19.788**. Lift to z=0.72 independently confirmed secure lift at **22582.032**, width **0.0827**, effort **19.704**. Retracted to **(0.30,0,0.85)** before transport. These noisy surface and gripper measurements are not exact centers or object dimensions.

Side **843**, head pan **+0.543**, inspected the clear chest diagonal. Turn **+0.543**, head restoration, advance **1.36 m**, and turn **-0.025**, with settling, reached **(1.124,4.792)**, heading **1.2298**, view **844**. Extension **(1.02,-0.10,0.75)** was viewed in **845** with retained acquisition flags. Deliberate opening **0.15**, request `17c102a31d5b4d0ba964e4a5b4ee9677`, completed **22638.884**. After settling, raised the empty arm vertically to **(1.02,-0.10,1.10)**. Wrist **846**, **22640.236**, directly showed red and yellow near the chest interior front. No placed toy was subsequently touched.

After empty-arm withdrawal and lowering, turn **+1.234** and advance **0.25 m**, with settling and preceding floor/wrist clearance evidence, reached **(0.928,4.950)**, heading **2.4637**. No intermediate head image separated that turn and advance. Head **847**, **22664.688**, showed blue and green. Pixels **(243,309)** and **(150,231)** projected surfaces **(0.8411,-0.0185,0.0511)** and **(1.4954,0.6847,0.0573)** respectively. These are historical search hints. Only **42.94** work seconds remained at the observation; another grasp was not initiated.

Restored the empty arm to **(0.22,0,0.70)** and viewed settled rear **848**. Reverse **0.25 m** first retained warning=true in completion status after **22708.140**. Only charging return followed. Turn **-1.321** and settling reached **(1.126,4.791)**, heading **1.1428**, rear **849**. Inspected reverse **1.50 m**, view **850**, reverse **0.18 m**, turn **+0.430**, and views **851–853** with two separately inspected reverse **1.50 m** passage segments reached **(0.434,0.261)**. Turn **+2.020** and head restoration identified the green pad/yellow mark/backstop in **854**. Inspected advances **1.50 m**, **0.85 m**, **0.22 m**, settling and views **855–857**, established contact without blockage.

First dock call `c183fc76f67c475d8188acb1aca89c9a` completed **22863.860**. Status confirmed **docked=true**, **battery 100%**, **no active action**, **task_success=false**, approximate pose **(-1.879,-0.859)**, unwrapped yaw **16.1591**, equivalent **3.5927**. Physical authority ended. Red/yellow contained; blue/green remain uncollected. The bedroom charger remains unlocated.

## Session 029: adapted bedroom departure and yellow-only containment

Evidence: [session 029](../SessionReports/2026-10-08-session-029.md), all **24 viewed observations 811–834**, including wrist **823**. A new toy assignment was active. Yellow was acquired, deliberately released, and directly seen inside the chest. **Task_success remained false; red, blue, and green were not grasped.** These are sensing-dependent examples, not an executable procedure.

From living-room contact **(-1.893,-0.848)**, heading **3.9741**, initial rear **811** preceded head settling. Settled rear **812** was viewed before reverse **1.18 m** and settling to **(-1.097,0.026)** in **813**. Turn **-0.6805**, settling, and rear **814** inspected a new diagonal. Reverse **1.50 m** then **0.046 m**, each settled, reached **(0.433,0.259)**; these segments shared prior clearance evidence. Turn **-1.7208**, head restoration, and settling produced **815**, heading **1.5728**. Two separately inspected **1.50 m** advances, view **816** between them, reached **(0.426,3.261)**. Empty-arm lowering to z=0.25 exposed all four toys in **817**: red right foreground, yellow central foreground, blue farther centrally, green farther left near the bed. No navigation request was blocked.

Yellow surface in **817**, pixel **(227,276)**, was **(1.0611,0.0760,0.0531)**. Advance **0.25 m** and settling reached **(0.426,3.511)**. Close **818**, pixel **(225,313)**, projected **(0.8159,0.0752,0.0541)**. Default open positioning at **(0.824,0.075,0.035)** and viewed alignment **819** preceded closure **0.018**. Contact status **21565.020**: width **0.0703**, effort **15.541**. Lift to z=0.72 independently confirmed secure lift at **21566.080**, width **0.0697**, effort **15.542**. Retracted to **(0.30,0,0.85)** before transport. Measurements are noisy surfaces and feedback, not object dimensions.

Side **820**, head pan **-0.500**, inspected the chest diagonal. Turn **-0.500**, head restoration, advance **1.460 m**, and turn **+0.157**, with settling, reached **(1.124,4.794)**, heading **1.2298**, view **821**. Extension **(1.02,-0.10,0.75)** was viewed in **822** before deliberate opening **0.15**, request `a590ca76180b4a2ab68d5039c34284e7`, completed **21621.304**. Settled, then raised the empty arm vertically to **(1.02,-0.10,1.10)**. Wrist **823**, **21622.816**, directly showed yellow on the interior floor and blue outside. This is individual yellow containment, not all-four success. No placed toy was touched again.

After empty-arm withdrawal/lowering, turn **+1.234** and advance **0.25 m**, with settling and prior floor/wrist clearance evidence, reached **(0.929,4.952)**, heading **2.4638**. Head **824** showed blue and green. Pixels **(243,311)** and **(150,232)** projected surfaces **(0.8273,-0.0183,0.0541)** and **(1.4956,0.6863,0.0477)** respectively. These are historical search hints. No second grasp was initiated with the work window nearly spent. Red remained uncollected and was visible in **817/820/825**, without a fresh metric projection.

Restored empty arm **(0.22,0,0.70)** and viewed settled rear **825**. Reverse **0.25 m**, turn **-1.321**, and settling returned to **(1.126,4.793)**, heading **1.1428**, rear **826**. Reverse **1.50 m** first retained warning=true at **21708.676**. Only charging return followed. Views **827–830**, reverse **0.18 m**, turn **+0.430**, and two separately inspected reverse **1.50 m** passage segments reached **(0.434,0.261)**. Turn **+2.020** and head restoration identified the green pad/yellow mark/backstop in **831**. Inspected advances **1.50 m**, **0.85 m**, **0.22 m**, with settling and views **832–834**, established contact.

First dock call `23ceb4768e7e4295beefcdfb79cd5c76` completed **21846.064**. Status confirmed **docked=true**, **battery 100%**, **no active action**, **task_success=false**, pose **(-1.879,-0.858)**, unwrapped yaw **16.1592**, equivalent **3.5928**. This exit heading differs from the initial 3.9741. Physical authority ended; yellow contained, three toys outstanding. Bedroom charger remains unlocated.

## Session 028: repeated practice departure, retreat, and charging return

Evidence: [session 028](../SessionReports/2026-10-08-session-028.md), viewed head observations **789–810**. These are sensing-dependent examples, not an executable route. Throwing evidence belongs in the canonical [ThrowOrange playbook](../Playbooks/Learned/ThrowOrange.md).

Current living-room contact was approximately **(-1.881,-0.859)**, heading **3.5928**. Settled rear **790** preceded reverse **1.08 m**, reaching **(-0.908,-0.387)** in **791**. That view supported empty-arm raising to **(0.22,0,1.10)**, turn **-0.0623**, reverse **1.094 m**, and turn **+1.1816**, with settling. Restored head pan 0/tilt 0.55 and empty arm z=0.70. Image **792** established the sphere on its pedestal from base **(0.105,0.027)**, heading **4.7122**. No navigation request was blocked.

After confirmed acquisition and high retraction, a settled **+1.2188** turn and rear view **794** supported reverse **0.10 m**, request `dadcdf953fd04916a4fe74bc54f7a9fe`. Forward **795** confirmed the flight path at **(0.011,0.062)**, heading **-0.3522**, measured displacement approximately **(-0.094,+0.035)**. Three throws remained at this translated base. The final landing stayed in the bin without another reset.

Return view **805** identified the green pad, yellow mark, backstop, sofa, and clear approach. Turn **-2.7557**, settling, and forward head restoration produced **806**, heading **3.1753**, with **2.86** work seconds left. Inspected advance **1.11 m** reached **(-1.098,0.025)**; its completion status **20854.912** first explicitly retained **low_warning=true**. Only charging return followed. Side **807** checked the pad before turn **+0.7988**, head restoration, and empty-arm lowering to **(0.22,0,0.70), pitch 0**. Views **808–810** supported advances **0.90 m** and **0.28 m**, with settling, to charging contact.

First dock call **`c527936afae34527b1c0ccc286ef1a80`** completed **20918.800**. Status **20918.912** confirmed docked=true, battery 100%, no active action, empty gripper, pose approximately **(-1.893,-0.848)**, unwrapped yaw **16.5405**, equivalent **3.9741**. The exit heading differs from this session's initial 3.5928; future departures require fresh sensing. No physical control followed docking.

## Session 027: yellow and green complete the resumed four-toy assignment

Evidence: [session 027](../SessionReports/2026-10-08-session-027.md), all **23 viewed observations 766–788**, including wrist **779**. Yellow and green were independently acquired and deliberately released; **task_success=true at 19808.004** confirms all four toys contained, resolving the outstanding work from sessions 025–026. Success persisted through docking. These are pose-specific, sensing-dependent examples, not an executable procedure.

### Departure and yellow acquisition

From living-room contact **(-1.882,-0.860)**, heading **3.5929**, settled rear **766** preceded reverse **1.08 m**. Rear **767** supported reverse **1.49 m**, turn **-2.020**, and forward head restoration. Views **768–769** supported two separately inspected **1.50 m** advances to **(0.426,3.262)**, heading **1.5729**. Empty-arm lowering to **(0.22,0,0.25)** exposed yellow near the bed and green near the chest in **770**. Yellow pixel **(219,193)** projected visible surface **(2.1303,0.2048,0.0384)**.

The inspected floor supported turn **+0.096** and advance **1.32 m**, reaching approximately **(0.298,4.575)**, heading **1.6689**. Fresh image **771**, pixel **(240,307)**, projected yellow surface **(0.8519,-0.0027,0.0523)**. Default PositionGrasp at **(0.860,-0.003,0.035)** completed **19680.668**; alignment **772** was viewed before closure **0.018**. Status **19695.240** confirmed bilateral contact, width **0.0720**, effort **16.209**. Lift to **z=0.72** confirmed secure lift at **19696.316**, width **0.0697**, effort **15.542**. Retracted to **(0.30,0,0.85)** before transport. These noisy projections and measured openings are not supplied object centers or dimension specifications.

### Two deliberate releases from one chest base

Side image **773**, head pan **-1.412**, inspected the short chest approach. Turn **-1.412**, forward head restoration, advance **0.852 m**, and turn **+0.973**, with settling, reached **(1.124,4.792)**, heading **1.2299**, image **774**. Extension to **(1.02,-0.10,0.75), pitch 0**, was viewed in **775** with yellow held over the opening and both acquisition flags true. Deliberate release **0.15**, request `dc677759ecb94c3a9fc8c31f713612d9`, was followed by empty-arm withdrawal, lowering to z=0.25, and head tilt **0.80**. Containment was initially hidden; later aggregate success confirmed it.

Image **776** exposed green beside the retracted arm. Pixel **(302,274)** projected **(0.4317,-0.2921,0.0711)**. Without base movement, default PositionGrasp at **(0.440,-0.292,0.045)** completed **19779.116**. Viewed alignment **777** preceded closure **0.018**. Status **19791.472** confirmed bilateral contact, width **0.0666**, effort **14.260**; lift to **z=0.72** independently confirmed secure lift at **19792.536**, width **0.0534**, effort **10.158**. Holding width subsequently settled near **0.052** with both flags true; its change was not isolated as a size measurement.

Extended green to **(1.02,-0.10,0.75)** and restored head tilt **0.45**. Image **778** showed it above the opening. Release **0.15**, request `119bcc382324417dbbee132197077599`, completed **19807.932**. Status **19808.004** confirmed **task_success=true**, with **54.97** work seconds remaining. After settling, raised the empty arm vertically to **(1.02,-0.10,1.10)**. Wrist **779**, **19810.144**, showed green/yellow surfaces and thin colored strips near the chest front. It did not separately expose all four whole toys or resolve their stacking; the physical success signal establishes aggregate containment. No placed toy was touched again.

### Warning and living-room docking

Retracted empty arm to **(0.22,0,0.70)**, turned **-0.087**, and obtained settled rear **780**, with **34.30** work seconds remaining. Inspected reverse **1.50 m**, view **781**, reverse **0.18 m**, and turn **+0.430** reached entry **(0.426,3.262)**, view **782**. Two inspected reverse **1.50 m** passage segments, views **783–784**, reached **(0.432,0.259)**. First explicitly retained warning was **783**, **19873.772**, after the first passage segment; only charging-return work followed.

Turn **+2.020**, settling, and forward head restoration identified the green pad, yellow mark, and backstop in **785**. Inspected advances **1.50 m**, **0.85 m**, and **0.22 m**, with settling and views **786–788**, established contact. First dock call `73401c9d6d1f43108e693b902ffb31fe` completed **19959.460**. Status **19959.488** confirmed **docked=true**, **battery 100%**, **task_success=true**, and **no active action**, pose **(-1.881,-0.859)**, unwrapped yaw **16.1592**, equivalent **3.5928**. Physical control ended. The bedroom charger remains unlocated; no toy work remains for this assignment.

## Session 026: resumed assignment, red contained, green and yellow outstanding

Evidence: [session 026](../SessionReports/2026-10-08-session-026.md), viewed observations **745–765**, including wrist **756**. Live status resumed the incomplete assignment from session 025. Red was securely lifted, deliberately released, and seen inside the chest with a small blue surface also visible. **Task_success remained false. Green and yellow were untouched and still outside the chest.** These are sensing-dependent measurements, not executable procedures.

From living-room contact **(-1.882,-0.860)**, heading **3.5929**, settled rear **745** preceded reverse **1.08 m**. Rear **746** preceded reverse **1.49 m**, turn **-2.020**, and head restoration. Views **747–748** supported two separately observed **1.50 m** advances, reaching **(0.426,3.262)**, heading **1.5729**. The empty arm was lowered to **(0.22,0,0.25)**. Image **749** showed red at the left foreground, yellow near the bed, and green near the chest; no blue toy was visible on the floor. Session-025 green/yellow surface coordinates remain search hints, not new measurements or current grasp targets.

Red pixel **(52,322)** in **749** projected **(0.7627,0.9342,0.0603)**. Turn **+0.886**, observation **750**, and advance **0.42 m** reached **(0.099,3.528)**, heading **2.4589**. Image 750 was rendered in the same orchestration call as the advance, so it was not model-reviewed before that motion; preceding image 749 and current lidar provided clearance evidence. Fresh close image **751**, pixel **(241,317)**, projected **(0.7886,-0.0076,0.0613)**. Default open positioning at **(0.797,-0.008,0.045)** and separately viewed alignment **752** preceded closure **0.018**. Status **18864.052** confirmed bilateral contact, width **0.0842**, effort **19.702**. Lift to z=0.72 confirmed secure lift at **18865.068**, width **0.0835**, effort **19.524**. Retracted to **(0.30,0,0.85)** before transport.

Side view **753**, pan **-1.568**, inspected the chest diagonal. Turn **-1.568**, head restoration, advance **1.50 m**, view **754**, advance **0.125 m**, and turn **+0.339** reached chest base **(1.123,4.792)**, heading **1.2299**. Extension to **(1.02,-0.10,0.75), pitch 0**, was inspected in **755** with red held above the opening and both acquisition flags true. Deliberate opening **0.15**, request `61388e145a794454a38854bf7c43d95f`, was followed by settling and vertical empty-arm raising to **(1.02,-0.10,1.10)**. Wrist **756**, **18931.444**, showed red and a small blue strip inside the front region; their exact contact/stacking was not resolved. Green and yellow were visible outside. The arm did not subsequently touch either placed toy.

Return preparation retracted the empty arm to **(0.22,0,0.70)**, turned **-0.087**, and obtained rear **757** with **6.22** work seconds remaining. The first retained warning observation was **758**, **18975.132**, after reverse **1.50 m**; only charging-return work followed. Inspected reverse **0.18 m**, turn **+0.430**, and two inspected reverse **1.50 m** passage segments reached **(0.431,0.259)**. Turn **+2.020** and forward head restoration identified the green pad, yellow mark, and backstop in **762**. Inspected advances **1.50 m**, **0.85 m**, and **0.22 m**, with settling and views **763–765**, established contact.

First dock call `de0e7444e4fe4de88ba57ee59231ead4` completed **19143.772**. Status confirmed **docked=true**, **battery 100%**, **no active action**, **task_success=false**, pose **(-1.882,-0.860)**, unwrapped yaw **16.1593**, equivalent **3.5929**. No physical control followed. The bedroom charger remains unlocated. Red and blue are contained; green and yellow still require fresh acquisition and placement.

## Session 025: kitchen-to-bedroom traversal and one confirmed blue placement

Evidence: [session 025](../SessionReports/2026-10-08-session-025.md), all viewed observations **719–744**, including wrist **736**. A new four-toy assignment was active. Blue was acquired, deliberately released, and directly seen inside the chest. **Task_success remained false; red, green, and yellow were not manipulated.** These are sensing-dependent examples, not an executable procedure.

### Departure and fresh search evidence

From kitchen contact **(4.111,-0.854)**, heading **3.8916**, rear image **720** was captured before the head fully settled; settled **721** preceded reverse **1.10 m**. Settling reached **(4.916,-0.104)**. Raised the empty retracted arm to **(0.22,0,1.10)**, turned **-0.75**, and restored the head forward. Views **722–725** supported advance **0.90 m**, turn **-0.45**, advance **1.20 m**, turn **+0.45**, advance **1.10 m**, turn **+0.114**, and advance **1.40 m**, with settling between motions, reaching **(0.439,0.259)**. Side view **726** preceded turn **-1.6828**. Two inspected **1.50 m** advances reached bedroom entry **(0.433,3.259)**, heading **1.5729**. Lowering the empty retracted arm to z=0.25 exposed all four toys in **728**.

| Toy | Pixel in 728 | Base-relative visible surface x,y,z m | Approximate odometry surface x,y m |
|---|---|---|---|
| Red | 52,321 | (0.7678,0.9376,0.0605) | (-0.506,4.025) |
| Blue, subsequently placed | 435,350 | (0.6357,-0.8869,0.0511) | (1.319,3.897) |
| Green | 366,209 | (1.8077,-1.1117,0.0561) | (1.541,5.069) |
| Yellow | 219,193 | (2.1300,0.2048,0.0385) | (0.224,5.389) |

These are noisy visible surfaces and historical search locations, not centers or grasp targets. Green and yellow were again visible on the floor in wrist **736**; red was visible during departure in **737**. Fresh sensing is required before any remaining pickup.

### Blue acquisition and direct containment verification

Turn **-0.949**, view **729**, advance **0.32 m**, and settling reached **(0.694,3.447)**, heading **0.6238**. Image **730**, pixel **(239,323)**, projected blue surface **(0.7642,0.0025,0.0505)**. Default PositionGrasp target **(0.773,0.0025,0.035)** and alignment image **731** preceded separate closure **0.018**, request `946ceadd00674d188846d2b74d99c94e`. Status **17984.712** confirmed bilateral contact, width **0.0892**, effort **21.223**. Lift to z=0.72, request `1a3fb659033b4474af241805567c162c`, confirmed secure lift at **17985.744**, width **0.0740**, effort **16.621**. Retracted to **(0.30,0,0.85)**; holding width settled near **0.050** with both acquisition flags true.

Side image **732** inspected the diagonal. Turn **+0.638**, head restoration, advance **1.412 m**, and turn **-0.032**, with settling, reached chest base **(1.122,4.793)**, heading **1.2299**. Image **733** checked the approach. Extension to **(1.02,-0.10,0.75), pitch 0**, was viewed in **734** with blue held over the opening. Deliberate release **0.15**, request `ed1e00c72419437286acb08960a113f9`, completed **18033.724**. Head **735** concealed the landing behind the front. The empty arm was raised retracted before extending to **(1.02,-0.10,1.10)**. Wrist **736**, **18049.416**, directly showed blue on the interior floor and green/yellow outside. This is confirmed individual blue containment, not all-four success. No placed toy was touched again.

### Warning and repeated living-room docking

First observed warning **18061.136**, during empty-arm withdrawal for return. Only retraction, charging navigation/sensing, and docking followed. Restored arm **(0.22,0,0.70)**, turned **-0.087**, and inspected the rear in **737**. Inspected reverse **1.50 m**, then **0.18 m**, and turn **+0.430** reached entry **(0.424,3.263)**. Two inspected reverse **1.50 m** segments reached **(0.430,0.261)**. Turn **+2.020**, settling, and head restoration identified the green pad, yellow mark, and backstop in **741**. Inspected advances **1.50 m**, **0.85 m**, and **0.22 m**, with settling and views **742–744**, established contact.

First dock call `1da545f2a3284c9c935165d1efccda88` completed **18199.292**. Status **18199.308** confirmed **docked=true**, **battery 100%**, **no active action**, **task_success=false**, approximate pose **(-1.882,-0.860)**, unwrapped yaw **16.1593**, equivalent **3.5929**. No physical request was rejected or blocked. The bedroom charger remains unlocated. No physical control followed docking.

## Session 023: departure from the practice-return heading and a translated return

Evidence: [session 023](../SessionReports/2026-10-07-session-023.md), viewed head observations **656–660**, rear clearance **666**, and charging return **689–694**. These are sensing-dependent route examples, not an executable procedure. Coordinates remain uncertain dead reckoning.

Fresh living-room contact was **(-1.891,-0.846)**, heading **3.9746**. Settled rear view **657** preceded reverse **1.18 m** to **(-1.096,0.029)**. View **658**, empty-arm raising to **(0.22,0,1.10)**, turn **-0.833**, and settling established heading pi. Rear image **659** inspected the next segment. Reverse **1.20 m**, settling, turn **+1.5708**, settling, head restoration to pan 0/tilt 0.55 and empty-arm lowering to z=0.70 reached **(0.104,0.027)**, heading **4.7124**. Observation **660** showed the sphere on its pedestal. This is a measured departure from the 3.9746 dock heading; the older 3.593 route was not reused unchanged.

After one baseline throw and a second confirmed acquisition, image **666** inspected rear clearance with the sphere retracted at **(0.36,0,1.16)**. A settled reverse **0.10 m** along throwing heading **-0.3517** reached **(0.010,0.062)**. Contact/lift persisted, and forward image **667** verified the new flight path. Six throws at this farther position are documented in the canonical [ThrowOrange playbook](../Playbooks/Learned/ThrowOrange.md).

From the translated base **(0.010,0.063)**, image **689** identified the green pad, yellow mark, backstop, sofa, and return floor. Turn **-2.7557**, settling and forward head restoration gave view **690**, heading **3.1758**. Inspected advance **1.11 m** reached **(-1.099,0.025)**; side view **691** preceded turn **+0.7988** to heading **3.9746**. Restored empty arm **(0.22,0,0.70), pitch 0**. View **692** preceded advance **0.90 m**. Its completion status **16675.328** first reported the warning, already on the charging return. Only final approach sensing, advance **0.28 m**, settling, and docking followed.

Dock request **`484b00a2126a4c329db36955f5e99fe0`** completed **16693.408**. Status **16693.516** confirmed docked=true, battery 100%, no active action, approximate pose **(-1.893,-0.848)**, unwrapped yaw **16.5410**, equivalent **3.9746**. All navigation requests completed; no blockage or docking retry occurred. Final sphere stayed in the bin without a reset. Fresh sensing remains necessary for departure and future geometry changes.

## Session 022: repeated kitchen-to-practice route and living-room contact

Evidence: [session 022](../SessionReports/2026-10-07-session-022.md), viewed head observations **611–617** for departure/travel, **650–655** for return. These are sensing-dependent examples, not an executable route. No task object was carried during navigation.

From kitchen contact **(4.109,-0.864)**, heading **3.8916**, a settled rear view preceded reverse **1.10 m**, then turn **-0.75**. The settled result **(4.888,-0.139)** differed slightly from session 013's endpoint; current odometry and images supplied the continuation. The reverse drive was not separately settled before that turn. The empty retracted arm was raised to **(0.22,0,1.10)**.

Inspected advance **0.90 m**, turn **-0.45**, advance **1.20 m**, turn **+0.45**, and advance **1.10 m** reached **(1.806,0.384)** facing west. Each subsequent drive and turn was settled. An inspected **+0.2075** turn followed by advances **1.50 m** and **0.240 m** reached **(0.102,0.025)**. Turn **+1.3633** established the southward acquisition view. No request was blocked. Eight confirmed throws and their current grasp measurements are documented in [ThrowOrange](../Playbooks/Learned/ThrowOrange.md).

After trial 8, rearward head image **650** identified the green charging pad, yellow mark, backstop, sofa, and clear westward floor. Turn **-2.7905**, forward head restoration, and inspected advance **1.20 m** reached **(-1.098,0.027)** at heading pi. Side view **652** inspected the pad. Status **15667.476** first reported the warning; only charging return followed. Turn **+0.833**, settling, empty-arm restoration to **(0.22,0,0.70)**, and inspected advances **0.90 m** and **0.28 m** established contact in **655**.

Dock request **`7d2bc8e43c0649339f1c40d7770c7f85`** completed **15704.240**; status **15704.348** confirmed docked=true, battery 100%, and no active action. Final odometry **(-1.891,-0.846)**, unwrapped yaw **16.5410**, equivalent **3.9746**. This repeats the earlier practice-return contact geometry. Fresh departure sensing remains necessary. The final sphere was left in the bin; no reset followed trial 8.

## Session 020: four pickups and confirmed containment in one work window

Evidence: [session 020](../SessionReports/2026-10-07-session-020.md), all viewed observations **550–585**, including wrist **577**. Live status established a new incomplete four-toy assignment after session 019's completed assignment. Current images showed a different floor arrangement. All four were acquired and deliberately released during this invocation; observation **576**, simulation time **14000.840**, confirmed **task_success=true**. These are pose-specific, sensing-dependent examples, not an executable route or grasp procedure.

### Departure and fresh arrangement

From living-room contact near **(-1.880,-0.863)**, heading **3.5937**, settled rear image **551** preceded reverse **1.08 m**. Image **552** preceded reverse **1.49 m**, turn **-2.020**, settling, and forward head restoration. Images **553–554** preceded two **1.50 m** advances. Entry was **(0.426,3.260)**, heading **1.5736**. Empty-arm lowering to **(0.22,0,0.25)** exposed all four toys in **555**.

| Toy | Pixel in 555 | Base-relative visible surface x,y,z m |
|---|---|---|
| Red | 44,326 | (0.7442,0.9620,0.0572) |
| Green | 132,190 | (2.1952,1.0996,0.0375) |
| Blue | 227,191 | (2.1965,0.1282,0.0252) |
| Yellow | 374,215 | (1.7254,-1.1435,0.0485) |

These noisy surfaces are historical search evidence after placement, not object centers or dimensions. Fresh close-range projections were used for acquisition.

### Acquisitions and placement

- **Red:** turn **+0.912**, image **556**, advance **0.42 m**, settle, and image **557** reached base **(0.091,3.518)**, heading **2.4857**. Pixel **(240,313)** projected **(0.8115,-0.0026,0.0602)**. Default open positioning at **(0.820,-0.003,0.045)** and alignment image **558** preceded closure **0.018**. Lift to **z=0.72** confirmed secure lift at **13807.136**, width **0.0829**, effort **19.341**. Retracted to **(0.30,0,0.85)**. Head pan **-1.596** exposed the chest diagonal in **559**; turn **-1.596**, advance **1.50 m**, image **560**, advance **0.134 m**, and turn **+0.340** reached chest base **(1.123,4.788)**, heading **1.2297**, image **561**.
- **Yellow:** after red's release and empty-arm withdrawal/lowering, head tilt **0.80** exposed yellow partially beside the arm in **563**. Pixels **(312,282)** and **(319,292)** projected **(0.3994,-0.3363,0.0526)** and **(0.3546,-0.3588,0.0523)**. Open approach through **(0.385,-0.350,0.20)** to **z=0.035** was viewed in **564**. Closure **0.018** and lift to **z=0.72** confirmed secure lift at **13872.996**, width **0.0743**, effort **16.624**. No base motion was needed.
- **Blue:** after yellow's release and empty-arm retraction, turn **+1.234**, image **566**, and advance **0.25 m** reached **(0.927,4.945)**, heading **2.4638**. Image **567**, pixel **(242,282)**, projected **(0.8107,-0.0136,0.0508)**. Open approach through **(0.820,-0.014,0.20)** to **z=0.035**, alignment **568**, closure **0.018**, and lift to **z=0.72** confirmed secure lift at **13918.264**, width **0.0834**, effort **19.623**. Retracted to **(0.30,0,0.85)**. Rear view **569** preceded reverse **0.25 m** and turn **-1.234** back to the chest base.
- **Green:** after blue's release and empty-arm retraction, turn **+1.558**, image **571**, and advance **1.05 m** reached **(0.137,5.149)**, heading **2.7878**. Image **572**, pixel **(244,268)**, projected **(0.8864,-0.0254,0.0709)**. Open approach through **(0.895,-0.025,0.20)** to **z=0.045**, alignment **573**, closure **0.018**, and lift to **z=0.72** confirmed secure lift at **13973.388**, width **0.0840**, effort **19.607**. Retracted to **(0.30,0,0.85)**. Rear view **574** preceded reverse **1.05 m** and turn **-1.558** back to the chest base.

All four releases used arm **(1.02,-0.10,0.75), pitch 0**, from approximately **(1.123–1.126,4.784–4.788)**, heading **1.2297**. Images **562, 565, 570, 575** showed the respective toy above the opening with acquisition flags true. Deliberate opening **0.15** completed at **13845.192** (red), **13884.052** (yellow), **13940.440** (blue), and **13999.208** (green). After the last release and empty-arm withdrawal, **576** confirmed all-four success. No placed toy was touched again.

Holding widths changed while contact/lift persisted. Red settled near **0.060**, yellow **0.070**, blue **0.050**, green **0.074** before release. Their causes remain unisolated; these are not object-size specifications.

The cleared empty-wrist viewpoint **(1.02,-0.10,1.10), pitch 0**, reached by raising the retracted arm first, exposed blue/green/yellow patches near the front in **577** at **14010.152**. Red was not individually distinguishable. Physical task success supplies aggregate containment evidence; the image does not establish exact stacking. Retracted to **(0.22,0,0.70)** before driving.

### Warning and charging contact

Return preparation used turn **-0.087** and settled rear view **578**. Status **14024.528** first reported **low_warning=true**. Only return navigation/sensing and docking followed. Inspected reverse **1.50 m** then **0.18 m**, turn **+0.430**, and two inspected reverse **1.50 m** passage segments reached **(0.434,0.251)**. Turn **+2.020** and head restoration gave charger view **582**, identifying the green pad, yellow mark, and backstop.

Inspected advances **1.50 m**, **0.85 m**, and **0.22 m**, with settling and images **583–585**, established contact. Dock request **`6706a12fa42345b99d66fca0ce6b42c5`** completed **14100.060**. Status **14100.168** confirmed **docked=true**, **task_success=true**, **battery 100%**, and **no active action**, near **(-1.879,-0.870)**, unwrapped yaw **9.8760**, equivalent **3.5928**. First dock call succeeded. No physical control followed. The bedroom charger remains unlocated.

## Session 019: green placement confirms all four toys contained

Evidence: [session 019](../SessionReports/2026-10-07-session-019.md), all viewed observations **527–549**, including wrist **541**. Live status resumed session 018's unfinished assignment. Green was securely lifted and deliberately released; observation **540**, simulation time **13206.548**, confirmed **task_success=true**. This resolves session 018's red/yellow/blue landing uncertainty for this assignment. These are sensing-dependent examples, not executable procedures.

### Current departure and green acquisition

- From living-room contact near **(-1.884,-0.861)**, heading **3.5926**, rear observation 528 was obtained before head settling (measured pan 2.76013 against requested 3.10). Settled observation **529**, pan 3.09992, preceded any base motion. Inspected reverse **1.08 m** then **1.49 m**, turn **-2.020**, and two inspected forward **1.50 m** segments reached bedroom entry **(0.425,3.260)**, heading **1.5726**. No command was blocked.
- Empty-arm lowering to **(0.22,0,0.25)** exposed green at the right edge of image **533**. Pixel **(415,347)** projected **(0.6370,-0.7908,0.0713)**. Turn **-0.893**, view 534, and advance **0.26 m** reached **(0.629,3.424)**, heading **0.6796**. Image **535**, pixel **(242,324)**, projected **(0.7432,-0.0122,0.0738)**. These are noisy visible surfaces, not object centers or dimensions.
- Default open positioning target **(0.752,-0.0122,0.045)** completed at **13138.344**; alignment image **536** was inspected. Closure **0.018** confirmed contact at **13157.752**, width **0.0901**, effort **21.510**. Lift to **z=0.72** confirmed secure lift at **13158.844**, width **0.0896**, effort **21.457**. Retracted to **(0.30,0,0.85)** before transport. Holding width subsequently narrowed near **0.050–0.052**, effort **10.158**, with both acquisition flags true; the cause remains unisolated.
- Head pan **+0.545** exposed the chest diagonal in image **537**. Turn **+0.545**, settle, restore head forward, and advance **1.455 m** reached **(1.121,4.793)**, heading **1.2246**. Image **538** verified the chest approach. Green was extended to **(1.02,-0.10,0.75), pitch 0** and viewed above the opening in **539**. Release to **0.15**, request `78ed53ce6bc746ccbdcdf3c5f6fc407a`, completed **13204.600**. After settling and empty-arm withdrawal, **540** confirmed all-four success.
- An empty wrist view at **(1.02,-0.10,1.10), pitch 0**, reached by raising the retracted arm before extension, exposed colored toy surfaces near the chest front in **541**. Green/yellow were visible but the view did not individually distinguish all four toys. Physical task success is the aggregate containment evidence. No placed toy was touched. Retracted to **(0.22,0,0.70)** before driving.

### Warning and repeated charging contact

With inspected rear views **542–545**, turn **-0.081**, reverse **1.50 m** then **0.18 m**, and turn **+0.430** reached entry **(0.424,3.261)**. Two inspected reverse **1.50 m** passage segments returned to **(0.432,0.260)**. The first observed warning was status **13273.908**, after the first passage segment; only return sensing/navigation and docking followed. Turn **+2.020** and head restoration established the charger view **546**, identifying its green pad, yellow mark, and backstop.

Inspected advances **1.50 m**, **0.85 m**, and **0.22 m** with settling and images **547–549** established contact. Dock request **`fdb022d653cc4efc9244dde5d0be28eb`** completed **13345.644**. Status **13345.752** confirmed **docked=true**, **task_success=true**, **100% battery**, and **no active action**, near **(-1.880,-0.863)**, unwrapped yaw **9.8769**, equivalent **3.5937**. First dock call succeeded. Empty open gripper, retracted arm; no physical control followed docking. The bedroom charger remains unlocated.

## Session 018: changed toy arrangement, three releases, green outstanding

Evidence: [session 018](../SessionReports/2026-10-07-session-018.md), viewed head observations 496–499 and 501–526. This was a new four-toy assignment. Red, yellow, and blue had confirmed pickups and deliberate releases over the chest; settled containment remains unverified and task_success=false. Green was not touched. These examples require fresh sensing and do not form an autonomous procedure.

### Departure and new arrangement

From the living-room dock near (-1.890,-0.848), heading 3.9746, rear observation 497 supported reverse 1.18 m to (-1.095,0.026). After observation 498, turn -0.680 and observation 499 preceded reverse 1.50 m to (0.388,0.254). Turn -1.7216 established heading 1.5730. Fresh observation 501 preceded the first of two inspected 1.50 m advances. At bedroom entry (0.381,3.254), lowering the empty retracted arm to z=0.25 exposed all four toys in observation 503. This departure differs from the historical dock heading 3.593; no command was blocked.

| Toy | Observation 503 pixel | Base-relative surface x,y,z m | Approximate odometry surface x,y m |
|---|---|---|---|
| Red | 87,313 | (0.8114,0.7868,0.0604) | (-0.408,4.064) |
| Blue | 232,279 | (1.0463,0.0453,0.0442) | (0.333,4.300) |
| Green | 424,346 | (0.6414,-0.8344,0.0711) | (1.214,3.897) |
| Yellow | 382,209 | (1.8160,-1.2579,0.0508) | (1.635,5.073) |

Surfaces are noisy measurements, not centers or dimensions. Red/blue/yellow subsequently moved.

### Acquisitions and releases

- Red: turn +0.770, inspect, advance 0.32 m reached (0.157,3.485), heading 2.3430. Observation 505, pixel (240,311), projected (0.8222,-0.0026,0.0611). Default open positioning target (0.830,-0.0026,0.045), alignment image 506, closure 0.018, and lift to z=0.72 confirmed acquisition; lifted width 0.0838, effort 19.863. Retracted to (0.30,0,0.85). A checked turn -1.407 and advances 1.50 m then 0.122 m, followed by turn +0.294, reached the chest base (1.121,4.790), heading 1.2300. Holding width later settled near 0.060, effort 12.530, without lost contact/lift.
- Yellow: from the chest base with empty arm low and head tilt 0.80, observation 511, pixel (321,269), projected (0.4631,-0.3929,0.0513). Open approach through (0.474,-0.395,0.20) to z=0.035, alignment image 512, closure 0.018, and lift to z=0.72 confirmed acquisition. Lifted width 0.0745, effort 17.006; later held width near 0.069. No base translation was needed.
- Blue: from the same base, retracted the empty arm, turned +2.469, settled, and used head tilt 0.55. Observation 514, pixel (243,268), projected (0.9030,-0.0201,0.0492). Open approach through (0.913,-0.020,0.20) to z=0.035, alignment image 515, closure 0.018, and lift to z=0.72 confirmed acquisition; lifted width 0.0718, effort 15.886. Retracted to (0.30,0,0.85) before turn -2.469. Holding width settled near 0.050, effort 9.555, with both flags true. No translation was needed.

All three releases used arm (1.02,-0.10,0.75), pitch 0, at the chest base. Images 510, 513, and 517 showed red, yellow, and blue respectively above the opening before deliberate opening to 0.15. Release completions: red 12424.300, yellow 12469.724, blue 12526.520. Fingers were empty afterward. The head view concealed the landing region and no wrist inspection was made. Do not treat these releases as confirmed settled containment.

### Green search evidence and warning return

After blue's release, the empty retracted robot turned -2.699. Observation 518 at 12533.956 showed green on the floor with 12.80 work seconds remaining. Pixel (237,268) projected (0.8843,0.0141,0.0734) from base (1.122,4.791), heading 4.8143. Approximate odometry surface (1.226,3.913) is the latest search estimate. Green was seen again in return view 519 and left untouched; no grasp target was exercised.

First observed warning was status 12548.580, during empty-arm restoration to (0.22,0,0.70). Only return work followed. Turn -0.530 established heading 4.2842; observations 519–520 supported forward 1.50 m then 0.18 m to (0.423,3.261). Turn +0.430 established heading 4.7142. Two inspected forward 1.50 m segments reached (0.429,0.258); turn -1.1216 faced the living-room charger at heading 3.5926. This drove the familiar return corridor forward, where earlier sessions had reversed.

Observation 523 identified the green pad, yellow mark, and backstop. Inspected advances 1.50 m, 0.85 m, and 0.22 m established contact. Dock request `1ede6fcb0f4149bea5a36cca6259f61e` completed 12636.924. Status 12637.080 confirmed docked=true, battery 100%, no active action, and task_success=false. Settled odometry (-1.884,-0.861), unwrapped yaw 9.8758, equivalent 3.5926. First dock call succeeded; no physical control followed. This latest heading differs from session 017's exit.

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
