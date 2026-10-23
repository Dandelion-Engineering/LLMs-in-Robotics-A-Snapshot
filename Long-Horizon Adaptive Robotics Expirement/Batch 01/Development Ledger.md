# Batch 01 development ledger

Initial record cut: 2026-09-23 UTC after `B01-dev-A1-002`; the later five-pilot extension below supersedes its episode counts and model-readiness status. This ledger records development evidence. It does not select a winner, freeze a candidate, or declare scored readiness. Later attempts extend this ledger without replacing earlier attempts.

**Assessment correction, 2026-09-23:** C0-002's complete-task claim is withdrawn. Its protected final event 2213 places both inserts at the fixture, and its frozen `cell.py:376-391` outcome function omitted insert-state predicates. The [correction evidence](Corrections/B01-dev-C0-002-insert-state.json) and appended result `B01-dev-C0-002-result-correction-1` preserve the original. The three accepted parts remain a historical evaluator measurement; no full re-score with the later strict evaluator is claimed. This attempt establishes neither complete physical feasibility nor a valid completion time.

## Equal opportunity and accounting boundaries

The [original development allocation](../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Evaluation.md) gives **each entrant, including C0, two working sessions or 12 active engineering hours and up to 60 development episodes**. These are equal initial opportunity ceilings, not minimum work requirements. No entrant must consume all 60 episodes. Any extension must be recorded and offered symmetrically before the freeze. Equal access does not establish equal engineering effort or maturity.

Actual person/agent active engineering hours were not instrumented. They are **unmeasured**, not zero; elapsed session time, model latency and overlapping agent work must not be substituted for active engineering hours. Development assistant tokens and manual diagnostic human time are also unmeasured. The measured robot-policy calls and tokens below are a different quantity.

Shared work covers the arena, Panda execution, perception, machine interlocks, independent evaluator, observation/action contract, model gateway, isolation, resource instrumentation, queue integration and evidence/release tooling. It benefits all entrants and is reported separately from entrant-specific policy development. A baseline episode used for shared calibration still counts as a C0 development episode. Primitive contact probes and model smoke calls are shared prerequisite work, not complete entrant episodes; their compute is not implied to be free or absent from development effort.

| Entrant | Registered complete episode attempts at this cut | Initial episode ceiling | Active engineering hours used | Current selection status |
|---|---:|---:|---|---|
| C0 conventional baseline | 2 | 60 | Unmeasured | Development only; full readiness not established |
| A1 Durable Task Dispatcher | 2 | 60 | Unmeasured | Development only; both retained attempts failed the task |
| A2 Guarded Procedure Composer | 0 | 60 | Unmeasured | Implemented policy work/tests; no registered physical pilot yet |
| A3 Grounded Objective Composer | 0 | 60 | Unmeasured | Implemented policy work/tests; no registered physical pilot yet |

Zero registered episodes does not mean zero implementation work. No extension is recorded by this ledger. Opportunity remains available to all four entrants; these counts do not authorize skipping their readiness pilots.

## Registered attempts and measured use

The [run registry](../Architecture%20Map/runs.jsonl), [revision registry](../Architecture%20Map/revisions.jsonl) and [result registry](../Architecture%20Map/results.jsonl) are the structured record. Each attempt has its own source ZIP and environment/configuration manifest registered before launch. All four attempts used the nominal three-part job, persistent condition, world seed 0 and a 300-second cap. The A1 attempts additionally record the then-combined policy/noise seed 11; this is not the later four-role seed specification. Baseline manifests do not contain that combined seed field. Exact snapshots govern each historical run.

| Attempt and protected result | Physical result | Recorded validity | Task wall / simulation seconds | Model calls / total tokens | Timing windows outside tolerance |
|---|---|---|---:|---:|---:|
| [B01-dev-C0-001](../Evidence/raw/B01-dev-C0-001/result.json) | 0/3 accepted; time cap | Unknown: readiness incomplete | 300.000131 / 300.000000 | 0 / 0 | 0/300; timing gate passed |
| [B01-dev-C0-002](../Evidence/raw/B01-dev-C0-002/result.json) | Historical 3/3 accepted; completion withdrawn because inserts remained stacked | Invalid: timing gate and historical completion predicate defect | 142.906349 / 142.904000 | 0 / 0 | 4/142; timing gate failed |
| [B01-dev-A1-001](../Evidence/raw/B01-dev-A1-001/result.json) | 0/3 accepted; time cap | Invalid: timing gate failed | 300.000629 / 300.000000 | 54 / 182,753 | 8/300; timing gate failed |
| [B01-dev-A1-002](../Evidence/raw/B01-dev-A1-002/result.json) | 0/3 accepted; time cap | Unknown: readiness incomplete | 300.000445 / 300.000000 | 88 / 247,872 | 0/300; timing gate passed |

The four-attempt subtotal is **1,042.907553 task wall seconds, 1,042.904000 simulation seconds, 142 policy calls and 430,625 measured tokens**. This excludes setup, model loading, teardown, diagnostic probes, downloads and other engineering compute. It is not total project cost. The final A1 attempt includes one late model response in its 88 responses and token total; post-episode accounting took another 0.633921 seconds and did not extend the task deadline. Both A1 results report complete token accounting and no failed model calls. Invalid or unhelpful model outputs still consume their recorded budget.

`A1-001` requested scripted help 15 times, received 14 answers and ended with one pending answer. `A1-002` requested and received four answers. These are simulated assistance, not measured human work. Baseline results predate the structured assistance summary, so that field is missing rather than imputed zero. No registered attempt at this cut exercised a restart or order amendment; none supplies a continuity-effect result.

| Attempt | Official queue job recorded with final result | Immutable source/configuration |
|---|---|---|
| C0-001 | `20260923T024045678684Z-e3ac498a` | [snapshot manifest](../Architecture%20Map/releases/B01-dev-C0-001/manifest.json) |
| C0-002 | `20260923T024714729962Z-a45656d6` | [snapshot manifest](../Architecture%20Map/releases/B01-dev-C0-002/manifest.json) |
| A1-001 | `20260923T030659178447Z-ecff5cda` | [snapshot manifest](../Architecture%20Map/releases/B01-dev-A1-001/manifest.json) |
| A1-002 | `20260923T032635191754Z-0974bd42` | [snapshot manifest](../Architecture%20Map/releases/B01-dev-A1-002/manifest.json) |

Result hashes and source ZIP hashes are retained in the corresponding map records. A successful queue exit establishes job execution, not task success or experimental validity. The [queue limitation](Queue%20Limitation.md) and the requirement to verify official final queue status still apply.

## Feedback, source changes and common calibration

The [calibration record](Calibration%20Changes.md) gives the physical and implementation details. This table identifies what feedback motivated development; it is not a controlled estimate of any individual change's effect.

| Development boundary | Observed feedback | Resulting work and scope |
|---|---|---|
| C0-001 to C0-002 | Placement evidence remained occluded by the arm; no accepted parts | Shared executor returned to the calibrated home posture after release. C0-002 reported three accepted parts but failed timing; its complete-task claim was later withdrawn for stacked inserts. Source manifests also record unrelated shared model/resource/protocol changes; the baseline made no model calls. |
| Before A1-001 | Baseline exposed timing bursts and incomplete independent completion semantics | Shared asynchronous planning, independent outcome checking, lease/restart handling, exact candidate delivery evidence, resource sampling, seeded perception and scripted help were integrated. These prerequisite changes were not an A1-only controller advantage. |
| A1-001 to A1-002 | A1-001 had 0.442184-second maximum lag, eight failing timing windows and no accepted parts | Rendering, image-derived detection and frame writing moved off the physics owner into a private sensor worker. Candidate reconciliation/prompt/schema development also occurred. A1-002 timing passed with 0.0009752-second maximum lag; task outcome still failed. Multiple changes prevent attributing task behavior to one component. |
| After A1-002, before another registered pilot | Repeated occupied-destination proposals and omitted operation/guard arguments; source audit found authority, sensor and resource gaps | Per-operation/predicate argument schemas and common public feasibility information were strengthened. A1 still chooses its next action; its menu is unranked and contains unproductive legal alternatives. A2 receives the same current feasibility information for its procedure composition. Shared inspection ownership, held-part recovery, sensor access, quotas, scenario/exposure evidence and release safeguards remain under calibration. Synthetic checks are not physical readiness evidence. |

Entrant-specific work remains visible: C0 has its conventional scheduler and durable reconciliation; A1 selects one task action per decision, A2 builds guarded multi-step procedures, and A3 composes geometric objectives under a conventional scheduler. Their common wrapper, public task knowledge and execution services are shared. The ledger does not treat a change to A1's prompt or A2's procedure validation as equal work on every policy merely because they share a source file. There is no reliable retrospective count of active engineering hours or meaningful iterations beyond the immutable registered snapshots and documented changes.

The initial local model was official Qwen3-4B-GGUF Q4_K_M, thinking disabled. Shared model setup and narrow structured-output smokes are prerequisites: the 16,384-context smoke in job `20260923T025011969972Z-1b58afe9` used 67 prompt and 19 output tokens and officially succeeded. It established a small actual inference call, not competent robot reasoning. Earlier setup/smoke evidence and the failed overlapping-queue setup attempt remain distinct from the four robot episodes; this ledger does not assert a complete token/compute subtotal for all prerequisite probes.

The proposed common model is now **Qwen3-14B-GGUF Q4_K_M**, revision `530227a7d994db8eca5ab5ced2fb692b614357fd`, weight SHA-256 `500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0`, 9,001,752,960 bytes. [Pinned setup code](../Runtime/model_setup.py) and [model documentation](../Runtime/MODEL.md) retain provenance. The rationale is to calibrate a stronger common reasoning component after elementary 4B decision failures, before freezing any architecture. All three LLM entrants will use the same selected weights/configuration. This is neither an A1-specific model privilege nor evidence of a measured 14B improvement; the two 4B failures remain unchanged. The old weights, manifests and licenses are retained.

At this record cut, the 14B download/smoke and release indexes are **not verified ready**. The intended common 16,384-token context/1,024-token response ceiling, explicit overflow refusal and current resource limits require actual joint runtime validation. A proposed model pin, an index-preparation helper, a unit test or an unverified queue log cannot close that gate.

## Selection and later append policy

Select the **latest eligible development checkpoint after shared calibration and each entrant's pilots**, using public feasibility, contract compliance, evidence completeness and readiness checks. Record each selected revision ID, all hashes, current prompt/initial knowledge and an explanation of any departure from the latest checkpoint. Do not select using held-out evaluation outcomes. Freeze all entrants and common artifacts together only after the outstanding [readiness audit](Readiness%20Audit.md) is resolved and [readiness.json](readiness.json) truthfully permits it. This ledger selects no checkpoint yet.

Before each additional episode, register a new immutable snapshot and run. After official queue verification, append its actual outcome, validity, task time, calls/tokens, help, failure feedback and scope of subsequent changes. Do not relabel an invalid development attempt as valid because a later fix passes. Accounting corrections retain the original record and name their source.

The declared evaluation remains **264 runs**: 192 main runs (24 cases × two policy/noise replicates × four entrants) plus 72 no-persistence runs (12 cases × two replicates × three LLM entrants). That is 48 C0 runs and 72 per LLM entrant. This ledger creates no held-out seeds, reduces no matrix and authorizes no automatic retries.

## Five-pilot extension, 2026-09-23 04:44 UTC

The common 14B smoke succeeded in official queue job `20260923T033848008215Z-bcba886b`. The following five development episodes then ran from pre-registered immutable snapshots in queue job `20260923T040518789052Z-46cf6518`, officially verified `succeeded`, exit 0. Its [receipt](../Evidence/queue-receipts/20260923T040518789052Z-46cf6518.json) and [batch result](../Evidence/raw/development-batch-001/batch-result.json) are retained. Final results were appended only after that verification. All five passed their actual-host timing checks; development validity remains unknown because common readiness is incomplete.

| Run | Scene | Independent accepted count / outcome | Task wall seconds | Model calls / tokens | Maximum lag seconds |
|---|---|---|---:|---:|---:|
| B01-dev-A1-003 | 3 parts, seed 0 | 0 / failure | 300.000125 | 62 / 150,134 | 0.0015864 |
| B01-dev-A2-001 | 3 parts, seed 0 | 2 / partial | 300.000448 | 14 / 47,354 | 0.0019817 |
| B01-dev-A3-001 | 3 parts, seed 0 | 3 / partial | 300.000223 | 9 / 21,478 | 0.0014111 |
| B01-dev-C0-003 | 6 parts, seed 1 | 6 / partial | 600.000498 | 0 / 0 | 0.0070113 |
| B01-dev-C0-004 | 10 parts, seed 2 | 9 / partial, candidate runtime failed | 769.152872 | 0 / 0 | 0.0038648 |

All used persistent state, nominal scenarios and policy/noise seed 11. A1 repeatedly requested the already installed setup. A2 omitted necessary setup and inspection prerequisites. A3 and C0 exposed insert exchange failures: requested insert motion receipts did not prove the previous insert reached home, and inserts remained stacked. The strict evaluator correctly refused full completion. C0-004 ended with `candidate_transport_failure`; its terminal runtime evidence is being diagnosed, and a successful queue exit does not erase this failure.

Current episode totals are **C0 4, A1 3, A2 1, A3 1**, each against the same initial 60-episode ceiling. Actual active engineering hours remain unmeasured. No scored run or continuity comparison has occurred. Corrected common insert geometry/witnesses, bounded recent resolution context, operation prerequisite guidance, measured carry-height selection and matched opaque public episode IDs are development changes to be tested in new attempts; prior evidence is unchanged.

## Eight-pilot extension, 2026-09-23 07:26 UTC

[Development plan002](development-plan-002.json) completed all eight declared attempts under job `20260923T064028897100Z-56d90aa6`, officially verified succeeded/exit0 at07:23:11 UTC. The [receipt](../Evidence/queue-receipts/20260923T064028897100Z-56d90aa6.json) and [batch result](../Evidence/raw/development-batch-002/batch-result.json) retain exact identities and no unstarted rows. All eight results were then appended to the canonical map. Every initial-world check and actual-host timing gate passed; there were no recorded resource-watchdog stops. Development validity remains unknown because readiness and the scored release are still incomplete.

| Run | Scene and cut | Accepted / outcome | Task wall seconds | Model calls / tokens | Maximum lag seconds |
|---|---|---|---:|---:|---:|
| B01-dev-C0-005 | nominal n3, seed0 | 3 / success | 166.923170 | 0 / 0 | 0.0044782 |
| B01-dev-A1-004 | nominal n3, seed0 | 1 / partial | 300.000436 | 30 / 112,896 | 0.0070286 |
| B01-dev-A2-002 | nominal n3, seed0 | 2 / partial | 300.000397 | 14 / 67,318 | 0.0180469 |
| B01-dev-A3-002 | nominal n3, seed0 | 3 / success | 185.307333 | 10 / 37,512 | 0.0064987 |
| B01-dev-C0-006 | nominal n6, seed1 | 6 / success | 305.223322 | 0 / 0 | 0.0061015 |
| B01-dev-C0-007 | nominal n10, seed2 | 9 / partial | 900.000538 | 0 / 0 | 0.0097639 |
| B01-dev-C0-008 | restart n3, seed2, first closed-grip transfer | 3 / success | 183.579116 | 0 / 0 | 0.0328442 |
| B01-dev-C0-009 | restart n3, seed3, second transport after acceptance | 3 / success | 171.959736 | 0 / 0 | 0.0364590 |

All used persistent state and policy/noise seed11, with the common pinned14B configuration for LLM entrants. This batch totals **2,512.994048 task wall seconds, 2,512.996000 simulation seconds, 54 model calls and217,726 tokens**, excluding setup, model loading, teardown and engineering probes. Successful completion timestamps precede finalization: C0-005166.922437s, A3-002185.306561s, C0-006305.222385s, C0-008183.578415s and C0-009171.958700s. Non-successful attempts have no completion time.

The two restart opportunities reached their configured cuts without fallback. C0-008's at-cut admissibility remains **unknown**, because prior measured grip/route envelopes were absent; its later success cannot repair that missing qualification. C0-009's empty-state after-acceptance exposure was classified admissible by the unchanged instantaneous predicates. Neither is a matched persistence comparison or a qualified duration result: the subsequent loader/absence instrumentation was not in these immutable snapshots.

A2 requested and received two scripted assistance replies. C0-007 requested24, received23 and had one pending at the cap. The other six requested none. These are scripted events, not measured human labor. C0-007 retained B6 as last known raw stock while the other nine had passing records; its exact visibility/physical failure mechanism is under separate evidence diagnosis. A source-only repeated-frame observation counterexample is documented, but it is not yet assigned as this run's cause. Early public done assertions before independent settling remain recorded (C0-005/006/008/009:4each; A3-002:5); the evaluator alone authorized final success.

Current episode totals are **C0 9, A1 4, A2 2, A3 2** against the same60-episode initial ceilings. Active engineering hours remain unmeasured; there is no claim of equal realized effort. The shared physical repairs before this batch are in [Calibration Changes](Calibration%20Changes.md). Subsequent protected loader and analysis changes do not rewrite these results. No scored seeds, selected winner or completed264-run comparison is claimed.


## Raw-layout feasibility attempt, 2026-09-23 08:05 UTC

Fresh predeclared C0-012 (development-plan004) repeated the nominal ten-part seed2/noise11/persistent/cap900 setting after the shared95mm raw-row repair and visibility-reacquisition implementation. Official job `20260923T075457882738Z-ba7ff50d` succeeded/exit0, and its result was appended only after verification. Independent full completion:10/10 in569.6893982s; actual wall569.6910115s/simulation569.6900000003s; all host timing checks passed, maximumlag0.0074465992s. No help, model calls or tokens. The required late A order and A9 rework completed, and strict insert/empty-cell/settling requirements passed. Three premature candidate done assertions are retained.

[Manifest](../Architecture%20Map/releases/B01-dev-C0-012/manifest.json), [result](../Evidence/raw/B01-dev-C0-012/result.json), [receipt](../Evidence/queue-receipts/20260923T075457882738Z-ba7ff50d.json). Development validity remains unknown; no scored benefit is inferred. Earlier C0-0079/10 and B6 tip remain unchanged. This is a whole-checkpoint check, not a causal spacing-only ablation.

Current completed episode totals:C0=10,A1=4,A2=2,A3=2 (18total), all within the common60 ceiling. Active engineering hours remain unmeasured. Remaining development003 and broader restart qualification are still pending.

## Symmetric closeout opportunity, 2026-09-23

Root adopted [development-opportunity-extension-001.json](development-opportunity-extension-001.json), SHA-256 `350827d8691e275d81ff30b15084e2d84115bbadfd6470fe08c19639969f29a7`, before development003 or final checkpoint selection. It offers all four entrants the same task-bounded closeout opportunity: the original two remaining episodes each and necessary common implementation/qualification repairs, with the cumulative 60-episode ceiling unchanged. Further entrant-specific score tuning requires a separately declared symmetric opportunity. Close this extension after the named prerequisites have terminal evidence and the common implementation is eligible for freeze.

Historical active engineering hours and compliance with the initial time ceiling remain unknown. This amendment does not repair or infer that history. Equal opportunity is distinct from realized effort and implementation maturity. All four entrants remain in the comparison; the final selection will use the latest supported implementation without requiring every development episode to succeed. No checkpoint, qualification or readiness decision is made by this record.


## Development003 closeout and C0-013 milestone repeat, 2026-09-23

All eight original [development003 attempts](development-plan-003.json) completed under official succeeded/0 execution `20260923T104637848546Z-10f91c9b` and [derivation receipt](../Evidence/queue-receipts/20260923T120012011674Z-75d4a1dc.json). The [results report](Development%20003%20Results.md) and [derived index](../Evidence/derived/development-batch003-001/index.json) retain all eight, with zero derivation integrity findings. C0-010/011 and A3-003/004 each completed 3/3; A1-005/006 each ended at the cap with 0/6, and A2-003/004 each ended at the cap with 1/10. All eight actual-host timing gates passed. Their canonical validity remains unknown; capped failures, premature completion claims and unknown physical-class/qualification scope remain recorded. Different tasks and this small development sample establish neither a winner nor a persistence benefit.

The original C0-010 after-release cut was inadmissible despite eventual completion. The new, prospectively declared C0-013 repeated seed0/noise11, n3, persistent restart and cap300 after the common public milestone acquired a fixed 0.10 simulation-second open-jaw dwell. It completed 3/3 in 168.1155432 wall seconds, with zero model calls and maximum lag 0.0169045 s. The configured cut fired without fallback after an observed 0.1000000000000334 s open interval; every required instantaneous predicate passed. [Physical validation](After%20Release%20Milestone%20Patch/physical-validation-001.json), [execution receipt](../Evidence/queue-receipts/20260923T121521761878Z-5a73938e.json), [completed derivative](../Evidence/derived/development-C0-013-001/index.json) and [derivation receipt](../Evidence/queue-receipts/20260923T121917353957Z-9c6d09f6.json) retain this additional attempt. Canonical validity remains unknown. This one admissible empty-state cut establishes no universal settling guarantee, carry-duration coverage or retroactive repair of C0-010.

Both original A3 carry cuts remain outside their supplied joint-position/velocity route support; later task completion does not repair them. A separate common carry-profile qualification now has [explicit limited root acceptance](Recovery%20Profile%20Assembly%20Tools/acceptance-profile-001.json) for the unchanged predeclared local **part:A-only** high-profile cell: first raw A1-to-fixture cut, recovery to parking1, at most five wall seconds from before cancellation through accepted recovery admission. Three predeclared fresh high-profile validations passed; the full six-row assessment remains **3 pass / 3 fail**, retaining the three baseline-profile rows outside joint-position/velocity support. Acceptance does not widen the cell or turn those failures into passes. Other payloads, pickup/profile states, unmeasured coupled interiors, longer absence and continuous between-step trajectories remain unsupported. The same numerical cell is available to every entrant; architecture identity does not select support.

The completed accounting cut is **27 episodes: C0=13, A1=6, A2=4, A3=4**, with **28 canonical result records** including the C0-002 correction. All remain below the common 60-episode ceiling. The two prospectively declared [A3-005/006 attempts](Recovery%20Profile%20Qualification/A3-profile-validation-development-plan.json) launched under job `77877d08` at 12:48 UTC are **not counted as completed here**; pre-registration may already increase the map's run count. Their pending raw outputs were not read for this entry.

Historical and later active engineering hours remain unmeasured; no equal realized effort, original hour-limit compliance, scored readiness or selected winner is claimed. Original evidence and all failures remain unchanged. The actual A3 pair's terminal evidence and interpretation, then final checkpoint selection and source-bound freeze/readiness, remain pending.

## Online A3 profile pair closeout, 2026-09-23 12:57 UTC

The two prospectively declared [A3 profile attempts](Recovery%20Profile%20Qualification/A3-profile-validation-development-plan.json) completed under official succeeded/exit-0 execution [77877d08](../Evidence/queue-receipts/20260923T124804450282Z-77877d08.json), ending at 12:55:27.900438 UTC. Both repeated the original n3, world-seed2, policy/noise-seed11 restart setting with cap300 and the accepted common A-only qualification. A3-005 used persistent state; A3-006 used no persistence. The preceding entry's pending status was correct at its earlier accounting cut and is superseded by this completed record.

| Run | Independent accepted count / outcome | Task wall seconds | Model calls / tokens | Maximum lag seconds | Before-cancel to recover_held_admitted wall seconds |
|---|---|---:|---:|---:|---:|
| B01-dev-A3-005 | 3/3 / success | 201.5759562 | 10 / 36,724 | 0.0390572 | 0.2957894 |
| B01-dev-A3-006 | 3/3 / success | 200.2711454 | 10 / 35,545 | 0.0365645 | 0.2927943 |

Both actual configured closed-grip-transfer cuts occurred without fallback and were admissible, with all17 required at-cut predicates passing. Their measured before-cancel through accepted recover_held admission coverage passed under the frozen five-wall-second bound. Earlier restart_ready coverage remains recorded as unknown because the required endpoint had not yet occurred. The absence field physical_recovery_success remains not_assessed; admissibility, duration coverage and later independent task completion are separate facts. This pair establishes no persistence benefit or general recovery guarantee.

Canonical finish [b537850e](../Evidence/queue-receipts/20260923T125616352142Z-b537850e.json) officially succeeded. Current accounting is **29 episodes: C0=13, A1=6, A2=4, A3=6**, with **30 canonical result records and32 revisions**. The additional result record is correction history, not an extra episode. All entrants remain below the common60-episode ceiling, and canonical development validity remains unknown. Original A3-003/004 results and inadmissible route-start classifications are unchanged; the new attempts do not repair them retrospectively.

The [pair's derived index](../Evidence/derived/development-A3-profile-001/index.json) is completed:2 selected,2 completed,0 failed/partial,0 with integrity findings. Official derivation [a3c8c319](../Evidence/queue-receipts/20260923T125651721797Z-a3c8c319.json) succeeded at12:57:17.815612 UTC. The [profile results report](Recovery%20Profile%20Results.md) retains the construction/validation scope, successful accepted assembly, all three failed baseline transfer checks and the actual online pair. Source and empirical-coverage limits remain unchanged.

No scored seed, scored validity, readiness, selected winner or equal realized engineering effort is inferred. Active engineering hours remain unmeasured. Final checkpoint selection and source-bound freeze/readiness remain separate pending decisions.


## Final development selection — 2026-09-23T13:06:51.173308+00:00

Root closed the symmetric extension and selected all four latest supported mechanisms under [development-selection-decision-001.json](development-selection-decision-001.json). The closed accounting retains 29 terminal attempts and 30 result records, including the C0-002 correction: C0=13, A1=6, A2=4, A3=6. All remain below60; remaining opportunity is unused. Historical and later active engineering hours remain unmeasured, and original12-hour compliance remains unknown. No winner or success-only filter was used.

Final source identity is the successful prepared batch01-eval-r1-final bundle. C0-013/A3-006 match all56 Runtime files. A1/A2 policy/model/prompt/physics/sensing/evaluator bytes are unchanged; their three later common files and supporting tests/probes are explicitly dispositioned in the decision. The original failures, cut classifications and source identities remain intact. This closes development; scored evidence will be registered separately.


## Infrastructure-only r2 selection — 2026-09-23T13:39:39.527537+00:00

The first r1 evaluation launch failed before physical or policy execution because direct-script and imported runner classes differed. Its failed/invalid result and all263 unlaunched dispositions remain in the retirement record. Root retained all four selected mechanisms and all264 planned r2 attempts; no development score tuning or changed scientific question. [The r2 selection](development-selection-decision-r2-001.json) binds the minimal entrypoint repair, versioned coordinator/readers and passed checks. The simulator remains at its original path to preserve exact physical calibration identity. Original r1 sources survive in the immutable prepared ZIP and selection snapshot; r1 is retired and cannot resume against changed working sources. Development counts and unmeasured-effort limitations are unchanged.

## Post-closure fixed-environment checks — 2026-09-23

The prospectively registered common environment pair A3-007/008 completed under official succeeded/0 job `20260923T144956839110Z-6185c4de`; canonical finalization `887f8b68` and 003 derivation `809878dd` also succeeded/0. The new project-owned Linux userland changes only the sandbox distribution default; the candidate, prompt, model, geometry and evaluator sources are unchanged from r2. These two infrastructure checks do not reopen policy tuning or replace prior attempts.

A3-007 persistent completed 3/3 in 201.459850300 task wall seconds, maximum lag 0.033420600s, 10 model calls and 36,819 tokens. A3-008 no-persistence completed 3/3 in 200.753731400s, maximum lag 0.037142500s, 10 calls and 35,734 tokens. Both timing checks and all 17 required cut predicates passed without fallback. The recorded before_cancel-to-recover_held_admitted wall intervals were 0.42197670000314247s and 0.42549419999704696s, within the unchanged five-second A-only profile qualification. [The scoped endpoint review](Release%20Environment%20Repair%20001/pair-validation-001.json) retains preliminary readiness coverage unknown, physical recovery success not_assessed and canonical development validity unknown. Derived continuity lacks an independently supplied frozen qualification context and remains unverified; no evaluation denominator is upgraded from this development review.

Full installed-userland verification passed before the pair (`979d83ae`) and afterward (`46a2502b`), including all recorded paths, native binary identities, /init and kernel. An intervening queue submission `f9928411` failed to establish a worker before any command or output existed; its receipt remains retained. No physical run was retried.

The [new closed accounting snapshot](selection-evidence-r3-001/accounting.json), official `b433ef3e`, records 31 development attempts and 32 result records, preserving the C0-002 correction: C0=13, A1=6, A2=4, A3=8. The two retired evaluation attempts are separately retained and excluded from development counts and r3 inference. All remain within the unchanged 60-episode ceilings. Active engineering hours remain unmeasured, initial 12-hour compliance remains unknown, and equal realized effort is not claimed.

Fresh retention audit `f361386e` inventories all 31 bundles. Its planning rate remains 3.189121856241325 MiB per task second, requiring 577,363,228,951 bytes for all 156,600 planned seconds plus the 50 GiB reserve. A current free-space check and the frozen coordinator must enforce this before the new release and each batch. Existing evidence is preserved. Selection, freeze and scored execution are separate subsequent records.