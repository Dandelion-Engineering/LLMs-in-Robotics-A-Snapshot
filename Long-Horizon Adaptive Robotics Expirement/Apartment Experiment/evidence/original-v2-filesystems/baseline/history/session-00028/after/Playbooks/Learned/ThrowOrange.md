# Calibrated orange-object throw

## Identity

- Type: learned; version 7; apartment Cartesian-arm robot.
- Sources: [session 001](../../SessionReports/2026-10-07-session-001.md), [session 010](../../SessionReports/2026-10-07-session-010.md), [session 013](../../SessionReports/2026-10-07-session-013.md), [session 017](../../SessionReports/2026-10-07-session-017.md), [session 022](../../SessionReports/2026-10-07-session-022.md), and [session 023](../../SessionReports/2026-10-07-session-023.md), 2026-10-07; [session 028](../../SessionReports/2026-10-08-session-028.md), 2026-10-08.
- Status: thirty-nine inside-bin throws across seven sessions: thirty at nearly the original stationary-base geometry and nine after a measured 0.10 m retreat along the throwing heading. Eight timing settings have succeeded. The farther setup supports 0.86 as a scoped candidate; one 0.85 trial did not show an improvement. Other distances and directions remain untested.

## Purpose and scope

Throw the orange practice sphere into the living-room blue bin using ordinary arm and gripper primitives. This provides the release motion only; acquisition, visual aiming, navigation, and reset remain the agent's responsibility.

## Preconditions

- Current assignment is throwing practice; no battery warning; at least ten seconds of work time remain.
- Current RGB-D observation shows an unobstructed release and flight path.
- Base stationary and visually aimed at the bin center. Original evidence is approximately 1.8 m from it; session 023 also tested a measured 0.10 m retreat along that throwing heading. In the original setup the bin center was approximately x=1.7, y=-0.65 m before a -0.36 rad base turn. These are perception estimates, not surveyed coordinates; the program does not measure or select a distance.
- Orange sphere has confirmed bilateral contact and secure lift. Measured opening was about 0.089 m. Requested holding width 0.025 m gave effort about 19.17.
- Hold the object at x=0.36, y=0, z=1.16 m, pitch=0 before invocation. Reconcile the current object, wrist, and surroundings visually. Allow base turns to settle before aiming.
- No person or unrelated object lies in the motion or flight path.

## Inputs and invocation

Run from the persistent workspace:

```sh
python3 Programs/Learned/throw_orange.py --duration-scale 0.88
```

The optional duration scale multiplies both swing durations. Scale 0.88 gave the closest repeated landings in session 010, about 1.3 cm from center. The default remains 1.0, which also succeeded twice. Tested values are 1.0, 0.92, 0.90, 0.89, 0.88, 0.875, 0.86, and 0.85; 0.85 has only one sample, at the farther setup. Other accepted values are experimental. Session 013 tested a +0.008 rad aiming adjustment at scale 0.88, with center distances about 0.5, 3.7, and 0.9 cm; it also tested 0.86 twice, both inside but farther from center (about 6.8 and 7.5 cm). Session 017 alternated 0.88 and 0.89 three times each at the adjusted aim: all six landed inside, with observed center-distance ranges of 5–7 mm and 6–14 mm respectively. Keep 0.88 as the supported example; the small overlapping comparison does not establish a reliable advantage. Session 022 alternated 0.88 and 0.875 four times each at the adjusted aim: all eight landed inside, with mean center distances about 4.8 mm and 11.9 mm respectively. Retain 0.88 for this setup; four samples per setting and earlier variation do not establish a general optimum. The aiming adjustment is a scoped candidate, not an established improvement. Small sample counts and nearly identical geometry do not establish a general optimum or reliability rate.

For a base verified to be **0.10 m farther back along the same throwing heading**, session 023 supports **0.86 as a provisional setting**: three alternating samples averaged 3.1 cm from center, versus 7.3 cm for three 0.88 samples, all inside. Retain 0.88 at the original geometry. This small distance extension does not define a general distance-to-timing rule; see the scoped evidence below.

Session 028 repeated the measured retreat and tested **0.86, 0.85, 0.86**. All three landed inside, at center distances **3.49, 4.34, and 4.25 cm**. One 0.85 sample supplies no evidence of improvement over 0.86; retain the farther-setting candidate at 0.86. The first sphere was acquired before retreat, while later acquisitions occurred at the translated base, limiting comparison across those trials.

## Procedure

The program checks task, work time, active action, and grasp feedback. It sets holding width 0.025 m, moves to (0.32, 0, 0.85) in one second, waits 0.5 seconds, and checks bilateral contact. It then executes:

| End x | End y | End z | End width | Duration before scaling |
|---|---|---|---|---|
| 0.63 | 0 | 1.08 | 0.025 | 0.22 s |
| 1.00 | 0 | 1.35 | 0.15 | 0.24 s |

It waits for fresh landing feedback, prints it, and retracts the empty arm to (0.36, 0, 1.16). Completion means a released, observed landing; success requires `throw_feedback.inside_bin=true`, not program exit status or request acceptance. Inspect a fresh image after execution.

## Acquisition notes

Use the default PositionGrasp procedure and current depth, correcting visible surface points to the estimated sphere center. In session 001, after settling at an approximately southward heading, center (0.628, -0.084, 0.919) was repeatable after reset. Approach above at z=1.16 with width 0.15, descend, close to requested width 0.025, then lift to z=1.16. Confirm both contacts and secure lift before retracting or turning. These coordinates are tied to that base pose and must not be reused blindly.

Session 010 reapproached from the kitchen and reconciled the setup at odometry about (0.103, 0.024), heading 3pi/2 for acquisition. Five fresh sphere projections at pixel (275,204) gave visible surfaces x=0.583–0.585, y about -0.098, z=0.947. Estimated center (0.623,-0.103,0.919) supported five confirmed acquisitions. The first used default positioning; subsequent trials used inspected arm approaches, with the final three raising the retracted arm before extending above the pedestal and descending. Each closure/lift was checked separately. Retract to (0.36,0,1.16) before turning +1.2108 to heading about -0.360 for the visually checked throw. These are pose-specific examples, not autonomous acquisition or navigation.

## Evidence

Session 001 recorded four inside-bin throws:

- Scale 1.0: forward/left displacement (-0.149, +0.039) m and (-0.145, +0.037) m.
- Scale 0.92: (-0.033, -0.005) m and (-0.035, -0.004) m.
- The executable was used successfully for the latter three throws.

Session 010 used the unchanged executable for five more fresh, confirmed inside-bin landings:

| Duration scale | Forward displacement m | Left displacement m | Landing simulation time |
|---|---:|---:|---:|
| 0.92 | -0.026 | -0.005 | 6795.460 |
| 0.90 | -0.017 | -0.008 | 6862.044 |
| 0.90 | -0.010 | -0.010 | 6926.816 |
| 0.88 | -0.004 | -0.012 | 6985.092 |
| 0.88 | -0.003 | -0.012 | 7043.004 |

Signed displacement uses the public target-bin frame. All trials started with confirmed bilateral contact and secure lift, then fresh visual alignment. The final object was preserved without another reset. The bin front concealed the landed sphere in post-throw head images; fresh landing feedback established containment. Generic `task_success` remained false for practice and was not used to judge these throws.

### Session 013: aiming and faster-timing comparison

Base remained approximately (0.101–0.102,0.023–0.024). Six fresh head projections at pixel (275,148), head tilt 0.55, measured sphere surface x=0.5826–0.5847, y=-0.0982–-0.0978, z=0.9440–0.9449. Estimated center (0.623,-0.102,0.919) supported six confirmed grasps/lifts. The first used default positioning; subsequent approaches raised the empty retracted arm before extension above the pedestal and descent. Acquisition heading was about 4.7124–4.7129 radians, with fresh sensing before each grasp.

The baseline turn +1.2108 gave throwing heading about -0.3599. Subsequent turns +1.2188 gave heading about -0.3518 to -0.3514, a +0.008 rad adjustment. Every release used the unchanged program, preceded by confirmed high lift, retraction, settling, and inspected flight clearance.

| Trial | Duration scale | Approximate aim change rad | Forward displacement m | Left displacement m | Landing simulation time |
|---|---:|---:|---:|---:|---:|
| 1 | 0.88 | 0 | -0.004 | -0.014 | 8858.448 |
| 2 | 0.88 | +0.008 | -0.005 | +0.002 | 8911.416 |
| 3 | 0.88 | +0.008 | +0.035 | -0.012 | 8971.164 |
| 4 | 0.88 | +0.008 | -0.008 | +0.004 | 9030.428 |
| 5 | 0.86 | +0.008 | +0.064 | -0.022 | 9087.536 |
| 6 | 0.86 | +0.008 | +0.071 | -0.024 | 9143.576 |

All six had fresh inside-bin feedback. Post-throw images 364, 372, and 376 exposed a small orange patch inside the bin; other head images concealed the sphere behind the front. Feedback remains the primary containment evidence. No reset followed trial 6.

Two of three adjusted 0.88 results were within 1 cm, but the third was 3.7 cm away. The unexplained variation prevents a claim of repeatable millimeter accuracy or reliable improvement from the aiming change. Both 0.86 trials went farther forward and right than all three adjusted 0.88 trials; this supports retaining 0.88 for the observed geometry, not a universal optimum. These observations add evidence, not an autonomous aiming or acquisition procedure.

### Session 017: alternating 0.88 and 0.89

The stationary base was approximately (0.103–0.104,0.023–0.025). Six fresh head projections at pixel (275,148), tilt 0.55, measured sphere surface x=0.5838–0.5855, y=-0.0983 to -0.0980, z=0.9436–0.9444. Estimated center (0.623,-0.102,0.919) supported six separately confirmed grasps/lifts. The first used default open positioning; later approaches raised the empty retracted arm before extending above the pedestal and descending. Open alignment, high lift, retraction, and flight clearance were checked each time.

All trials used acquisition heading about 4.7124–4.7131 and a settled +1.2188 rad turn to throwing heading about -0.3519 to -0.3512. This reproduces the adjusted aim in session 013, rather than comparing aiming directions. The unchanged executable alternated the two timing settings:

| Trial | Scale | Forward displacement m | Left displacement m | Landing simulation time |
|---|---:|---:|---:|---:|
| 1 | 0.88 | -0.006 | +0.003 | 11518.072 |
| 2 | 0.89 | -0.005 | +0.004 | 11564.684 |
| 3 | 0.88 | +0.007 | -0.001 | 11618.164 |
| 4 | 0.89 | -0.012 | +0.007 | 11682.736 |
| 5 | 0.88 | +0.005 | +0.001 | 11743.628 |
| 6 | 0.89 | -0.009 | +0.007 | 11798.252 |

All six had fresh inside-bin feedback. Observed mean center distance was about 6 mm at 0.88 and 11 mm at 0.89, with overlapping ranges and only three samples per setting. These results add 0.89 as a successful tested setting and support retaining 0.88 without claiming an optimum or dependable millimeter accuracy. The larger session-013 variation remains relevant. Head images 476 and 484 exposed a tiny orange patch near the bin front; the other post-throw views concealed the sphere. No reset followed trial 6.

### Session 022: alternating 0.88 and 0.875

From the kitchen charger, current sensing supported a return to base approximately (0.101–0.102,0.025–0.027). Eight fresh sphere projections at pixel (275,148), head tilt 0.55, measured visible surfaces x=0.5857–0.5892, y=-0.0989 to -0.0983, z=0.9419–0.9435. Estimated center (0.625,-0.102,0.919) supported eight separately confirmed grasps and lifts. The first used default open positioning; later approaches raised the empty retracted arm before extending above the pedestal and descending. Each open alignment was viewed, and closure/contact and high secure lift were checked separately.

Acquisition heading was about 4.7124–4.7132 radians. A settled +1.2188 turn gave throwing heading about -0.3519 to -0.3511. Every flight path was viewed with the object held at (0.36,0,1.16), pitch 0. The unchanged executable alternated the two scales:

| Trial | Scale | Forward displacement m | Left displacement m | Landing simulation time |
|---|---:|---:|---:|---:|
| 1 | 0.88 | -0.001 | +0.003 | 15264.324 |
| 2 | 0.875 | +0.013 | -0.002 | 15319.760 |
| 3 | 0.88 | +0.005 | +0.001 | 15369.084 |
| 4 | 0.875 | +0.013 | -0.001 | 15414.636 |
| 5 | 0.88 | +0.001 | +0.004 | 15468.280 |
| 6 | 0.875 | +0.008 | +0.002 | 15516.900 |
| 7 | 0.88 | +0.006 | +0.003 | 15564.568 |
| 8 | 0.875 | +0.013 | +0.001 | 15613.640 |

All eight had fresh inside-bin feedback. Mean center distance was 4.8 mm at 0.88 (range 3.2–6.7 mm) and 11.9 mm at 0.875 (range 8.2–13.2 mm), calculated from the rounded public displacements. The 0.875 landings were consistently farther forward in this small comparison. Keep 0.88 as the supported example; this does not establish dependable millimeter accuracy, a general optimum, or performance outside the tested geometry. Session 013's larger variation remains relevant.

All 32 trial images 618–649 were rendered and viewed. Tiny orange patches were visible near the bin front in several post-throw views; others concealed the sphere. Fresh landing feedback establishes containment. No reset followed trial 8, and no new trial began near or after the warning. Ordinary warning response, first-call living-room docking, and session closeout completed. No executable change was needed.

### Session 023: measured 0.10 m retreat and timing comparison

Fresh sensing from the living-room dock established acquisition base approximately (0.104,0.027), heading 4.7124. Sphere surface projections in observations 660 and 664 at pixel (275,148), head tilt 0.55, were (0.5874,-0.0986,0.9428) and (0.5864,-0.0984,0.9432). Estimated center (0.627,-0.103,0.919) supported the first two separately confirmed acquisitions. The first used default open positioning; later approaches raised the empty retracted arm before extension and descent. All seven open alignments were viewed, closures confirmed bilateral contact, and separate high lifts confirmed acquisition before retraction.

Trial 1 used the original base and a settled +1.2188 turn, heading about -0.3519. Before trial 2, a viewed rear clearance check and a settled reverse 0.10 m moved the held, retracted sphere and base to approximately (0.010,0.062), retaining heading about -0.3517. The measured displacement was approximately (-0.094,+0.034) in uncertain odometry. The program and aiming direction were unchanged; a new forward image confirmed the flight path. Trials 2–7 remained at this translated base, approximately y=0.062–0.063.

Later southward acquisition views 669/673/677/681/685 at pixel (243,143) projected surfaces x=0.6219–0.6233, y=-0.0102 to -0.0101, z=0.9424–0.9429. Perceived center (0.662,-0.010,0.919) supported five more confirmed grasps/lifts. These coordinates are pose-specific examples, not autonomous acquisition. Each sphere was retracted to (0.36,0,1.16), pitch 0, before a settled +1.2188 turn and viewed flight clearance.

| Trial | Retreat m | Scale | Forward displacement m | Left displacement m | Landing simulation time |
|---|---:|---:|---:|---:|---:|
| 1 | 0 | 0.88 | -0.005 | +0.007 | 16232.656 |
| 2 | 0.10 | 0.88 | -0.056 | +0.026 | 16309.400 |
| 3 | 0.10 | 0.86 | -0.033 | +0.018 | 16372.712 |
| 4 | 0.10 | 0.88 | -0.094 | +0.041 | 16423.972 |
| 5 | 0.10 | 0.86 | -0.022 | +0.014 | 16490.912 |
| 6 | 0.10 | 0.88 | -0.050 | +0.025 | 16548.548 |
| 7 | 0.10 | 0.86 | -0.024 | +0.016 | 16604.492 |

All seven had fresh **inside_bin=true** feedback from the unchanged executable. At the farther base, 0.88 mean center distance was **7.34 cm**, range **5.59–10.26 cm**; 0.86 mean was **3.08 cm**, range **2.61–3.76 cm**, calculated from rounded signed feedback. All three faster samples were closer to center than all three slower samples in this session. This supports 0.86 as a provisional setting for this measured extension, while retaining 0.88 for the original geometry. Three samples per setting, one session at the new distance, variable 0.88 results, and changes in acquisition geometry limit causal attribution and generalization. No optimum, reliability rate, or continuous distance correction was established.

All trial images 660–688 were rendered and viewed. Post-throw head images concealed the sphere behind the bin front; fresh landing feedback establishes containment. No reset followed trial 7. Warning response, first-call living-room docking, and normal closeout completed. No executable change was needed.

### Session 028: repeated retreat and one 0.85 comparison

Freshly reconciled living-room departure reached acquisition base approximately **(0.105,0.027)**, heading **4.7122**. Head image **792**, tilt 0.55, pixel **(275,148)** projected sphere surface **(0.5889,-0.0988,0.9421)**. Estimated center **(0.629,-0.103,0.919)** supported default open positioning, viewed alignment **793**, separately confirmed closure, and high secure lift. Retracted to **(0.36,0,1.16)** before a settled **+1.2188** turn.

Rear image **794** established clearance before reverse **0.10 m**. After settling, pose was approximately **(0.011,0.062)**, throwing heading **-0.3522**; measured translation was approximately **(-0.094,+0.035)**. Viewed image **795** checked the flight path. All three throws used this translated base and the unchanged executable. Later acquisitions used southward views **797/801**, pixel **(243,143)**, surfaces **(0.6227,-0.0101,0.9426)** and **(0.6230,-0.0101,0.9425)**. Estimated center **(0.663,-0.010,0.919)** supported two more confirmed grasps/lifts after raising the empty retracted arm, extending above the pedestal, and descending. Open alignments **798/802** and flight paths **799/803** were individually viewed before closure or release.

| Trial | Retreat m | Scale | Forward displacement m | Left displacement m | Landing simulation time |
|---|---:|---:|---:|---:|---:|
| 1 | 0.10 | 0.86 | -0.031 | +0.016 | 20514.732 |
| 2 | 0.10 | 0.85 | -0.039 | +0.019 | 20718.352 |
| 3 | 0.10 | 0.86 | -0.038 | +0.019 | 20797.728 |

All had fresh **inside_bin=true** feedback. Center distances from rounded public feedback were **3.49, 4.34, and 4.25 cm**; the two 0.86 samples averaged **3.87 cm**. The single 0.85 result was nearly identical to the following 0.86 result, and does not establish a timing advantage or a monotonic relation between speed and range. Trial 1 was acquired before retreat, unlike trials 2–3; grasp geometry and unexplained prior variation further limit attribution. Retain **0.88** at the original geometry and **0.86 provisionally** after the measured retreat. No general optimum or reliability rate is established.

Post-throw head views **796/800/804** concealed the sphere behind the bin front; fresh landing feedback establishes containment. No reset followed trial 3. The ordinary warning, inspected charging return, first-call docking, and filesystem closeout completed. No executable modification was needed.

## Limitations and failure modes

- Only this sphere, bin, pitch, robot configuration, original geometry and one 0.10 m retreat along the same aim were tested. Other distances and directions remain untested. The program cannot perceive its own alignment or choose timing from distance.
- A faster horizontal candidate using width 0.055 was associated with far-short landing feedback. The landing timestamp preceded the command's completion; freshness relative to command start was not established. Release timing and loss mechanism were not isolated.
- During a separate preparation the object was lost after a prolonged low hold and a subsequent lift. Do not linger at the low swing start; loss timing/cause remains uncertain.
- `secure_lift_confirmed` became false when the held sphere was lowered below its initial support height, despite bilateral contact. A prior high confirmed lift plus current contact is used for the low swing start; do not infer a secure grasp from closure alone.
- Same commanded release timing and nearly unchanged pose produced about 4 cm of landing variation in session 013. Session 023's farther-base 0.88 samples also varied by about 4 cm. Causes were not isolated; do not tune or claim precision from a single result.
- A completed request can precede settled motion. Fresh observation and feedback remain necessary.
- On a warning, stop new trials and follow the deployment docking rule. On an error, inspect live status before further physical actions; an exception does not stop an already active primitive.

## Implementation

[Programs/Learned/throw_orange.py](../../Programs/Learned/throw_orange.py); uses only public robot-client primitives. It does not navigate, acquire, reset, or dock.
