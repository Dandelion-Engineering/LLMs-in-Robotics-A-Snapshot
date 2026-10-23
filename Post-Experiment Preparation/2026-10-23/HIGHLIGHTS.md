# Potential video highlights

Post-experiment selection, October 23, 2026. **No video has been made.** This is an editorial shortlist from the completed apartment-v4 Baseline and accepted Maps history through Development Session 74, not a controlled comparison of their performance. Ranking favors a clear visual sequence and a verifiable connection to files, decisions and feedback.

Times below are **run simulation seconds**, not video timecodes or continuous wall time. Filesystem times are measured brackets, not exact instants. Original robot RGB captures are sparse views; the ~50 Hz state recordings can support a separately labeled observer reconstruction. Any future clip should disclose that distinction and the [arm/model limitation](DIAGNOSIS.md).

## Ranked shortlist

### 1. A program is written, tested, carried forward and improved — Baseline sessions 1 → 6 → 9

**Why first:** this is the most complete compact chain from experimentation to a durable executable, later execution, parameter revision and further reuse.

Session 1's initial miss lands at **158.940**, followed by successful trials at **236.168, 303.880, 378.516, 448.792 and 525.332**. The learned `Programs/Learned/throw_orange.py` is written during **[410.724, 414.896]**; actual program runs produce the last two successful results. In session 6 it is read again during **[3634.576, 3638.764]**, then invoked seven times, with landings **3859.860–4154.464**. Two trials explicitly use `.28/.137` and land near center. The program's defaults are revised during **[4183.716, 4187.888]**. Session 9 reads those exact revised bytes during **[6120.364, 6124.568]** and invokes the program again.

**What viewers could see:** original sphere/bin views, the learned file being created, the same file opened in a later fresh session, shell commands with duration arguments, landing feedback, and the small default-value edit. [Original bin frame 11, 304.708 s](evidence/baseline-observation-0011.png) and [frame 147, 3869.172 s](evidence/baseline-observation-0147.png) provide actual sensor pixels; do not describe the former as a view of trial 5.

**Connecting evidence:** [write/checkpoint/read links 1 and 2](reuse-links.json), hashes `09a25635…` and `b28a34f0…`; [public program requests](selected-program-executions.json), Baseline session 6 request IDs 109–173 and session 9 IDs 107–169; [session-1 trial record](evidence/baseline-session-001-trials.md), [session-6 trial record](evidence/baseline-session-006-trials.md), [session-1 program output](evidence/baseline-session-001-trial-5.jsonl), [session-6 explicit-parameter output](evidence/baseline-session-006-trial-6.jsonl), and [session-9 default invocation output](evidence/baseline-session-009-trial-1.jsonl). Exact source paths/hashes are in [selected-exports.json](selected-exports.json).

**Caveat:** local repeated successes support useful reuse and tuning in this setup, not general throwing mastery or a causal memory advantage. Session 6 did not physically rerun the no-argument program after editing its defaults; the identical explicit parameters were exercised beforehand. The first miss changed several factors, so its cause was not isolated.

### 2. The next session finishes the remaining work — Baseline sessions 2 → 3

**Why:** the task boundary is easy to understand: two toys are left inside; a fresh session reads the saved state and completes the other two.

At **1198.488**, [original observation 34](evidence/baseline-observation-0034.png) shows green and blue in the chest. Session 2 saves its route map during **[1470.944, 1475.116]** and continuity summary during **[1561.052, 1565.240]**. Session 3 reads those exact files during **[1698.724, 1702.912]** and **[1690.536, 1694.708]**, respectively. It then acquires red and yellow. The protected success latch is **1956.584**; [original observation 66 at 1958.144](evidence/baseline-observation-0066.png) shows the completed chest view.

**What viewers could see:** two placements, docking/end of session, the saved “two remain” summary and route, a fresh-session read, new sensing, then red/yellow placement. A visible “new session” label would make the continuity comprehensible.

**Connecting evidence:** [reuse links 3–4](reuse-links.json), summary hash `e2822018…`, route hash `dbea8818…`; [session 2](evidence/baseline-session-002.md), [session 3](evidence/baseline-session-003.md), and [authenticated session/latch events](history-catalog.json). The route also records session 2's blocked return at **1265.556** and session 3's changed centered crossing.

**Caveat:** files were demonstrably read, but success cannot be attributed to memory alone; the world also preserves the two placements. The copied map is an observation-based route record, not a perfect localization system. Session 3 still needed a small dock-position correction.

### 3. A dropped cup is recovered, saved as unfinished work and resumed after a real infrastructure failure — Maps sessions 5 → accepted 6

**Why:** clear physical work, a useful failure, honest unfinished state and a strong human-directed recovery story all connect.

Session 5's transport/staging attempt loses contact by **3173.924**. [Original observation 146 at 3182.032](evidence/maps-observation-0146.png) shows the cup on the floor. A new pickup and separate lift/extension stages recover it; [observation 150 at 3230.592](evidence/maps-observation-0150.png) shows it on B's cabinet. The task remains incomplete. The kitchen map and summary are saved during **[3417.828, 3422.016]**. Accepted session 6 reads their exact bytes during **[3479.544, 3483.716]** and **[3459.076, 3463.264]**, opens B, reacquires the staged cup and places it inside. The latch is **3648.276**; release completes **3648.392**.

**What viewers could see:** slip/floor image → recovery/top staging → saved unfinished summary → fresh-session read → [open drawer at 3579.136](evidence/maps-observation-0165.png) → [held cup above the opening at 3642.856](evidence/maps-observation-0170.png) → success feedback. [Post-release view 171](evidence/maps-observation-0171.png) is useful precisely because the cup is occluded; keep the feedback beside it.

**Connecting evidence:** [reuse links 6–7](reuse-links.json), summary hash `820e8abf…`, kitchen map hash `4990c029…`; [session 5](evidence/maps-session-005.md), [accepted session 6](evidence/maps-session-006.md). The successful drawer procedure becomes a playbook in session 6 and is read, byte-identically, in session 9 during **[5362.988, 5367.172]** ([link 9](reuse-links.json)); reading a procedure and subsequently acting is stronger than merely retaining its filename.

**Caveat:** there are **two distinct native invocations numbered 6**. The original parent failed the one-report closeout rule after creating a report plus addendum. Its later learning and physical progress were discarded from the accepted branch. This candidate uses only checkpoint-5 material and the accepted continuation. There is an 87-minute wall-time interruption; do not edit it as uninterrupted operation. The settled cup is not visible in the post-release frame, and the orange-button interaction's necessity was not isolated by the robot.

### 4. The human makes a constrained decision, and Codex implements and qualifies it — Development sessions 62 → 63, then Robot Maps session 6

**Why:** a concise view of Randy's role and the engineering/testing behind an apparently seamless continuation.

The preserved [human conversation](../../chats/Codex-Human/Apartment%20v4%20Maps%20Launch%20and%20Monitoring/Apartment%20v4%20Maps%20Launch%20and%20Monitoring%20-%20Active.md), lines 103–153, records the **October 10, 11:32 PDT** authorization: restore checkpoint 5 once, preserve the failed parent, transfer none of its abandoned session-6 learning, and leave the scientific runtime and reporting rule unchanged. [Session 63's handoff](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-63/human-reply.md) reports **11 qualification, 9 audit and 5 preparation gates**, followed by the continuation launch at **11:59:32 PDT**, queue `20261010T185932431096Z-5e6874a0`. Accepted checkpoint 6 was independently checked at **12:08 PDT**.

**What viewers could see:** Randy's actual message, the operator-side restoration/negative-test records, exact preserved checkpoint identity, and the accepted robot resuming the cup scene from candidate 3. There is no continuous camera footage of code testing; these are retained text/receipt views, with wall-clock labels.

**Sources:** [protocol](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-63/PROTOCOL.md), [source review](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-63/SOURCE-REVIEW.md), [independent audit](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-63/audit-result.json), [continuation route](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-63/continuation-route.json), [timing provenance](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-74/timing-provenance.json).

**Caveat:** operator recovery is separate from autonomous Robot Codex task recovery. Show the failed invocation and human authorization; do not imply the robot recovered its own infrastructure or retained the abandoned tail. This overlaps candidate 3, so one combined sequence may be preferable in a short video.

### 5. Maps and a learned tool return together — Maps sessions 1 → 7

**Why:** a compact second condition example showing a room record and executable being consulted after several unrelated sessions.

Session 1 writes `throw_horizontal.py` during **[345.056, 349.240]**, then runs it five times. Session 7 reads the same hash `6f6a63ed…` during **[3969.292, 3973.492]**, consults kitchen/living-room maps, travels back to the living room and performs ten actual program runs. Their landing times span **4143.176–4432.556**. The `.184/.10` repeats at **4338.860, 4365.780 and 4432.556** visibly vary in their recorded displacement; the lateral `.065` trial at **4402.228** does not improve centering.

**What viewers could see:** a learned file and semantic playbook created in session 1; later room-map reads, a room transition, executable invocation and new feedback. [Observation 210 at 4435.900](evidence/maps-observation-0210.png) supplies original post-throw pixels, with an occluded settled ball.

**Sources:** [reuse link 5](reuse-links.json), [session 1](evidence/maps-session-001.md), [session 7](evidence/maps-session-007.md), and [31 selected public program requests](selected-program-executions.json). Session-7 process IDs/arguments identify all ten executions; the journal read proves file access, while the process requests and recorded trajectories/feedback support actual use.

**Caveat:** retain the obstruction on the first low-to-high approach and the nonmonotonic timing outcomes. Defaults were retained. Maps surviving and being read is observed; a causal benefit of the Maps template is unproven. The same recovery interruption described above lies between these sessions.

### 6. Several failures are kept, and access changes eventually work — Baseline sessions 19–23

**Why:** an unusually honest example of adaptation with accumulated negative evidence, though longer than the top candidates.

Session 19 places the cup unsuccessfully at **14163.448**. Session 20 locates it with wrist view **590** and preserves a final view at **15015.624**, but three descents are constrained. Session 21's side views/attempts at **15638.572–15773.588** still fail. Session 22 pulls the already-open drawer farther at **16462.196**; view **635 at 16476.164** records the changed cup/panel geometry, followed by another constrained descent. It saves that negative result in continuity during **[16761.900, 16766.104]**. Session 23 reads the exact summary during **[16913.836, 16918.040]**, reobserves the changed geometry, adjusts high lateral access, eventually obtains bilateral contact at **17243.444**, and lifts at **17244.908**. A safe set-down/release then supports sustained success from **17256.336**.

**What viewers could see:** selected wrist images and short blocked-descent/feedback excerpts, the changed drawer opening, a summary explicitly saying “do not replay these as successful recovery motions,” its next-session read, then the successful approach. Original image IDs are recoverable from [history-catalog.json](history-catalog.json); this package does not export those wrist images or make a montage.

**Sources:** [reports 19](evidence/baseline-session-019.md), [20](evidence/baseline-session-020.md), [21](evidence/baseline-session-021.md), [22](evidence/baseline-session-022.md), [23](evidence/baseline-session-023.md); [reuse link 8](reuse-links.json), hash `4e517c10…`; [saved session-22 summary](evidence/baseline-s022-SummaryOfOnlyNecessaryContext.md.txt).

**Caveat:** the drawer/world also changed across sessions. Neither memory's causal contribution nor the exact obstructing bodies was isolated. The protected latch at **17243.212** is earlier than the sustained release success: do not label that transient closure-time signal as the final release. The warning occurs with a cup held at **17254.084**; the subsequent safe set-down belongs in the story. These maneuvers inherit the incomplete arm geometry.

## Additional worthwhile candidates

| Candidate | Exact locator / what viewers could see | Why useful and honest limit |
|---|---|---|
| Apparent floating arm, both runs session 1 | Baseline **524.288**, chunk `000130` sample 110; Maps **487.648**, chunk `000121` sample 85; [saved-state renders and diagnosis](DIAGNOSIS.md) | A transparent limitations insert. New reconstructions, with walls hidden, must be labeled; this is not a claim that these are Randy's exact watched frames. |
| A completed arm command did not mean arrival — Baseline 6 | Two blocked base terminals **3692.868 / 3711.048**; requested-high arm still low at **3720.000**, then rises after a base turn. [Navigation evidence](evidence/baseline-session-006-navigation.md), [report](evidence/baseline-session-006.md) | Connect requested action → measured feedback → changed approach. Delayed movement is observed; exact contact bodies were not isolated. |
| Success feedback later disappears — Maps 8 | Latch **5019.552**, first later observed false at **5041.272**, dock **5145.164**. [Report](evidence/maps-session-008.md), [endpoint audit](../../agents/Codex/Session%20Summaries/HumanReport74.md) | The robot calls the task incomplete, while the operator's unchanged rule advances on the earlier latch. Drawer opening passes at the exact latch but later falls below threshold. Do not silently reconcile these different claims or invent a cup fall. |
| The warning was missed — Maps 15 | Session begins **9566.728**; work deadline **9926.728**. [Independent readback](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-74/session15-window-readback.json) records release request **+3.812 s**, completion **+4.412 s** after deadline. [Report](evidence/maps-session-015.md) | A short instruction-following limitation. No advancement occurred; an endpoint pass is not perfect timing compliance. Use exact receipt clocks, not a report's retrospective impression. |
| Navigation recovery remains messy — Maps 29 | Blue release **18824.184**, partly occluded chest view **879 at 18830.016**; later return has four blocked actions. [Report](evidence/maps-session-029.md), source events under its run root | Useful negative behavior. The early recovery sequence was not fully guarded; do not describe it as an exemplary safe policy. Task remains incomplete. |
| Final accepted Maps endpoint | Session 34 yellow release **21830.984**, latch **21830.972**, dock **21956.568**; original views **1003/1004** and [report](evidence/maps-session-034.md) | An ending grounded in physical feedback and the [Session-74 audit](../../agents/Codex/Session%20Summaries/HumanReport74.md). No single image exposes all four toys; green remains occluded. 21 advancements include seven timed throwing windows, not 21 mastered tasks. |

## Asset and timestamp availability

Both run roots, their replay indexes, selected original state chunks, journals and RGB images are accessible. [verification.json](verification.json) inventories common movie/animation formats inside those two run roots; no external screen recorder location is established by this inspection. Missing continuous footage should be replaced only by clearly labeled reconstruction or text views, not claimed to exist. Exact supplied RGB pixels and their hashes/times are listed in [selected-images.json](selected-images.json).

For every cross-session claim above, [reuse-links.json](reuse-links.json) identifies both sessions, exact path, checkpoint bytes, write/read journal sequence and original record hash, and adjacent clock-bridge records. The bracket's upper bound governs when a file read can safely appear on a synchronized display. Process-request files lack a direct simulation timestamp; join to their journal brackets and physical request IDs rather than inventing one.

These are outcome-selected editorial moments, not a representative sample or comparative statistic. The ranked list is the requested handoff for choosing a later video; editing, narration, publication, licensing and other release work remain outside this session.
