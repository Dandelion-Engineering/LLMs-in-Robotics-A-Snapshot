# Evidence that makes the robot's behavior investigable

Randy should begin with a job, a visible outcome and a specific discrepancy, then inspect the mechanism that could explain it. The future interface is an engineering investigation workspace, not a long report or an animation presented as measured performance. It is specified here; it is not built in this assignment.

## Minimum record for every run

A protected append-only event stream assigns `run_id`, monotonic `event_id`, `event_type`, `source`, simulator tick/time, monotonic wall time, parent/correlation IDs and payload hash. Cross-process events use timestamps from the gateway plus their original clock information; sequence numbers detect gaps. Wall clock date is metadata, not the ordering clock. Store explicit schema/version, units and missing-data reasons. Log failures to log; a missing consequential chain cannot support a causal claim.

| Evidence | Every run | Rich diagnostic addition |
|---|---|---|
| Identity/reproducibility | Candidate/config/model hashes, dependency manifest, simulator/model/assets hashes, seeds in evaluator-only record, initial world and resource budgets | Environment/export bundle suitable for exact-version replay |
| World and task | Initial/full end state, protected task/part/cycle predicates at changes, disturbances and actual exposure, periodic 1 Hz snapshots | Full integration checkpoints at 10 s and before/after consequential events |
| Sensors | Each delivered packet or loss record, image/depth content hashes and retained compressed frames actually delivered to candidate, calibration, capture/delivery times | Higher-rate raw frames around ambiguous contact/perception events |
| Actions | Requests, validation/rejection, receipt, dispatch, command authority, cancel/supersede acknowledgement, expiry, terminal feedback and safety interventions | High-rate control/force traces around contact transitions |
| Motion | Joint q/dq/effort and end-effector pose at 100 Hz, command targets, machine state; **500 Hz online accumulation of contact impulses, control peaks and saturation events**, saved as compact values with tick/interval, so short transients are not lost | Full native physics-rate samples around faults; external inspection views |
| Context | Candidate durable file manifests/hashes, versioned changed bytes, crash/restart snapshots, exposed file reads/retrieval payloads with offsets/version, model-visible prompt/context | Full relevant source trees and generated artifact lineage |
| Reasoning/tools | Model inputs/observable outputs, model/version/settings, request/response/timeout/token counters, tool arguments/results, declared decisions and generated code if any | Optional short candidate-provided rationale, explicitly self-report |
| Outcome/resources | Independent predicates, progress/error events, help, termination reason, timing/CPU/GPU/RAM/VRAM/storage sampling | Actual human annotation and investigation notes |

Do not require or invent hidden model chain-of-thought. Observable decisions, emitted explanations/programs, prompts, tools and actions provide the evidence; a self-reported reason is not proof of cause. File existence does not show retrieval, and retrieval does not show that a model acted on it. Log those distinctions. If a candidate uses a long-lived process cache or memory mapping, instrument the actual context supplied to decisions and label unobserved internal accesses unknown rather than pretending filesystem calls capture everything.

Deduplicate identical blobs by hash. Default retention target is at most 2 GiB per 15-minute ordinary run; measure real compression during calibration instead of assuming this cap is achievable. Preserve every candidate-visible frame needed to reconstruct consequential inputs. If budget conflicts with that requirement, reduce common sensor resolution/rate **before** the freeze or allocate more storage; do not silently omit failure evidence. Keep rich captures for the predeclared representative set and failures, with a proposed 5 GiB/run ceiling. Store logs under a dedicated local experiment-results root selected at implementation time, not in Git. The design package and compact manifests belong in Git.

At 48 main + 24 ablation runs, a conservative 2 GiB/run allowance is 144 GiB per entrant before rich captures. Do not multiply that blindly across candidates: preflight available space, compress/deduplicate, archive only to an approved drive with verified capacity, and stop before exhausting the host. No deletion of evidence to make a failed run disappear. Retention/export and storage limits must be frozen before scored runs; a user-approved later pruning policy may preserve all summaries plus selected full traces with explicit missingness.

## Replay and attribution

Distinguish three modes:

1. **Recorded playback:** render captured states and display actual delivered observations/actions. This is the authoritative way to see the episode, even when exact physics re-execution diverges.
2. **Deterministic re-execution attempt:** restore integration state plus full model/version, machine timers, RNG, pending commands, observation queues and disturbance scheduler, then replay recorded commands. Compare state/predicate hashes at checkpoints. MuJoCo state alone omits application state. Mark divergence and its first tick; do not call a divergent replay exact.
3. **Counterfactual diagnostic:** change one delay, controller or memory condition and rerun. Label it a new run; its later observations and model outputs need not match. It offers evidence about a proposed cause, not a replacement history.

Candidate restarts and simulator recovery are different operations. Candidate disk/world persist according to the test condition; an infrastructure restart restores a coordinated checkpoint and receives its own validity label. Do not roll the robot's world backward just to simplify a failed memory test.

Use parent IDs to walk: world change → available observation → delivered/retrieved context → decision/program/target → accepted execution → physical outcome → task-state record. An explanation should identify the earliest **supported** discrepancy and competing causes, not automatically blame the first LLM call near a failure. Where state was unavailable, label an observability limitation; where it was available but stale records prevailed, show both versions.

## Future investigation interface requirements

| View or interaction | Randy's question | Required evidence and acceptance condition |
|---|---|---|
| Workcell + current job | What was the robot trying to finish? | Episode order/version, independent progress, world playback; one-click return to system view |
| Synchronized timeline | What changed first? | Scrub across world, sensor, command, machine and restart events; linked panes agree on tick and show timing gaps |
| Robot-view/evaluator-view toggle | Could the robot know that? | Delivered images/age versus private truth; privileged view has persistent label, never looks like a robot observation |
| Available versus retrieved context | Did correct information survive and get used? | File versions, actual retrieval/prompt; distinguish not stored, stored-not-retrieved, retrieved-but-stale, and unknown |
| Action lifecycle | Was it planned, sent, executed, or verified? | Request/receipt/dispatch/outcome IDs; show unresolved gaps and duplicate suppression |
| Paired comparison | Why did two systems differ under this disturbance? | Same case/replicate; align both by elapsed time and intervention/milestone, with exposure differences shown |
| Motion/time overlays | Was the robot waiting, oscillating, or responding usefully? | Path, velocity, action updates, observation age, inference pending, machine waits; quantitative units and filters visible |
| Failure-to-mechanism link | What should I learn to investigate this? | Evidence-linked explanation, alternative cause, focused original source sections and one testable follow-up |
| Cross-run cases | Is this common, or an interesting exception? | Counts and denominators, common successes/failures, outliers, selection rule and access to omitted cases |

Every displayed claim carries one of these labels: **measured** (linked run/event/data), **source-reported** (original source and locator), **interpretation** (evidence chain), **hypothesis** (discriminating test), or **schematic**. Quantitative charts expose units, denominators, excluded runs and uncertainty. An automatically assigned failure label can be corrected with an append-only annotation; retain original data and label version.

Acceptance checks for the later interface: reconstruct one ambiguous restart without looking at a developer console; identify what was unseen; follow one false-completion claim to its physical mismatch; compare one paired recovery without losing actual delay; inspect a file version actually supplied to a call; export a compact evidence bundle; operate timeline/filter controls by keyboard; show missing evidence instead of fabricated interpolation. Test with real representative logs before polishing appearance. No controls should be decorative.

## Learning from the next runs

After the future comparison, return a small set of evidence-backed questions rather than a prerequisite robotics syllabus. Examples: a delayed correction can motivate observation age and feedback control; an unresolved crash can motivate idempotency and transactional state; a blocked buffer can motivate scheduling and deadlock; a slip can motivate contact/friction and grasp mechanics. These are contingent learning opportunities, not predictions of what will fail.

For each selected observation, provide the concrete episode, what the current evidence establishes, what it does not, the relevant mechanism/source, and a small next experiment Randy can help design. The loop is build → observe → identify a consequential mechanism → learn enough → discuss → iterate. Design review remains the stopping point of this assignment.
