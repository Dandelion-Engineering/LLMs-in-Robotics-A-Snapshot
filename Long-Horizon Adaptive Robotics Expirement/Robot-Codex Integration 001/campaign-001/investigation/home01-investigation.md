# First blocked-home recovery: clearing the obstruction was insufficient for handback

`RCI001-C01-home-01` is the prospectively selected first blocked-insert-home example. Its admitted result is **valid, scorable task success**, with a meaningful failed intermediate decision. The model moved obstructing A1 to parking1 and requested handback, but the supervisor rejected that handback because conventional automation still lacked a supported next action. The model retained recovery ownership, completed the insert exchange itself, verified the new state, and successfully returned control. Conventional automation then completed the B2 order.

This was one fresh invocation of exact `RCI001-wsl-010d`, Astra Max, with world seed 173 and sensor seed 22002. Official job `20260927T191409572767Z-6038d425` completed `succeeded`, integer exit 0, at 2026-09-27 19:20:36.629043 UTC. Outcome inspection began only after that gate and the root's admitted assessment existed. No restart, rerun, framework edit or tuning was performed for this investigation.

[Admitted assessment](../execution/RCI001-C01-home-01/assessment.json) · [official queue receipt](../execution/RCI001-C01-home-01/storage/queue-receipt.json) · [protected event history](../../local-evidence/campaign001/RCI001-C01-home-01/host/public-history.jsonl) · [model/tool trace](../../local-evidence/campaign001/RCI001-C01-home-01/orchestrator/pilot/client/events.jsonl) · [retained runtime files](../../local-evidence/campaign001/RCI001-C01-home-01/orchestrator/pilot/runtime-after-close.json).

## Diagnosis and the first repair

The order required one family-B part, recipe B, delivered to tray2, with no rework. Before activation, the conventional worker made three setup-B requests. All three native admissions rejected them as `destination occupied` (protected events 5, 10 and 15). At event 18 it requested assistance because its bounded attempt limit was reached; event 19 transferred ownership, and event 23 started the single recovery invocation at epoch 3.

The model read the configured instructions, task, robot description, tools, activation, state and initially empty continuity. It inspected startup history and fresh status. Structured detections showed raw A1 at `insert_home_A`, insert A still installed in the fixture, insert B at its home, raw B2 available, and no observed parking1 occupant. Its interpretation was that A1 blocked the return pad needed for the insert exchange. It announced a plan to move A1 to parking1, verify the move, and hand back for conventional setup and production (trace line 206).

The first protected note named the planned request ID before dispatch. `pilot-9cebcb9b8e73-clear-A1-v1` was then requested, dispatched once and admitted at simulation 97.238 s. The model committed the unresolved accepted action to continuity and queried its status instead of sending another physical command. At 116.842 s the native transport became terminal; subsequent observation 1145 and a separate public-effect record supported A1 at parking1. The model requested one explicit fresh capture, then checked current status: observation 1475 at 150.050 s showed A1 at parking1, both insert locations unchanged, idle station/arm and approximately 0.080 m open jaws with no visibly held object. See trace lines 229, 239, 241, 248, 255, 257, 320 and 321.

This established useful physical progress. It did **not** establish that the conventional worker could resume.

## Why the first handback failed

The model's first handback request, `pilot-9cebcb9b8e73-handback-v1`, proposed normal setup B as the next step. Protected event 1799 rejected it at simulation 179.548 s with `unsupported_resumption`: the frozen conventional controller lacked a currently supported next action. Ownership remained robot at epoch 3. The rejection was a real intermediate failure, preserved in the command registry and assessment; it was not an infrastructure failure and did not invalidate the eventual task success.

The source and retained controller state support a specific explanation. The [final baseline checkpoint](../../local-evidence/campaign001/RCI001-C01-home-01/host/baseline-workspace/candidate-state.json) still records a failure count of **3** for the setup-B action signature. The frozen [candidate controller](../../../Runtime%20004/candidates.py), lines 25 and 499–500, sets `MAX_FAILURES=3` and rejects an action at that count. The protected [handback implementation](../../host/supervisor.py), lines 451–489, previews the reconciled conventional controller and validates its next proposal before committing an ownership change. Clearing A1 changed the physical scene but did not reset the exhausted setup signature.

This is a source-supported interpretation of the observed rejection, not a separately retained dump of the first handback's internal preview. It also explains why simply retrying the same handback without changing state would not establish progress. The model instead recognized the rejection, rechecked current ownership/status and announced a different repair: perform the insert exchange so the conventional worker could resume with B2 transport (trace lines 379 and 381). It did not alter the conventional checkpoint or failure counts.

## Second repair and actual completion

The model committed the changed plan, then issued `pilot-9cebcb9b8e73-setup-B-v1` at simulation 210.156 s. The native setup skill first returned insert A. It paused internally awaiting a fresh capture at event 2277, recorded observed return to `insert_home_A` with open jaws at event 2279, and only then dispatched the next trajectory to install B. That intermediate record explicitly says `independent_physical_success=false`: it supplies public transition evidence, not task grading authority.

Setup reached terminal completion at 243.008 s; observation 2405 supported its physical effect. A subsequent status response, observation 2490 captured at 251.550 s, positively detected insert A at its home and insert B in the fixture, A1 parked, B2 still raw, idle arm/station and open jaws with no visibly held object. The model then committed a pre-handback note and submitted `pilot-9cebcb9b8e73-handback-v2`. Event 3188 accepted it at 317.016 s, moved ownership to conventional epoch 4, and identified **transport B2 into the fixture** as the supported next action. Trace lines 391, 401, 403, 415, 417, 475, 479 and 481 record this sequence.

The agent used two physical action requests and one explicit observation request. No robot-authored control program was admitted or run; it used native gateway skills, status/history/query calls and filesystem notes. All its observation claims here concern structured detections/telemetry. Its retained notes explicitly say no PNG content was viewed.

## Protected event timeline

Times are simulation-clock values, starting at 1.000 s, not model inference durations. Protected event IDs equal one-based lines in `public-history.jsonl` for this episode.

| Simulation time | Event IDs | Observed chain |
|---:|---|---|
| 1.002–1.402 s | 3–5, 8–10, 13–15 | Three conventional setup-B requests dispatched to the service and rejected at admission: destination occupied. |
| 1.602–1.810 s | 18–19, 22–23 | Assistance after bounded limit; robot authority and single invocation begin. |
| 97.238 s | 969–971 | A1-to-parking1 request, one command dispatch and accepted admission. |
| 97.492–116.916 s | 974, 1166–1168 | Native trajectory, terminal completion, observation 1145 and separate effect verification. |
| 138.648–138.710 s | 1384–1388 | Explicit capture requested and completed, sequence 1361. |
| 179.548 s | 1798–1799 | First handback rejected; robot retains epoch 3. |
| 210.156 s | 2107–2109 | Setup-B request, one command dispatch and accepted admission. |
| 226.730–226.848 s | 2277, 2279–2280 | Native setup waits for capture, observes returned insert A, then dispatches installation trajectory. |
| 243.008–243.088 s | 2444–2446 | Setup terminal; observation 2405 supports installed B and returned A. |
| 317.016 s | 3187–3188 | Second handback accepted; conventional epoch 4, next action B2 transport. |
| 317.054–329.086 s | 3189–3193, 3313, 3318–3319 | Conventional loads B2; terminal and public placement support follow. |
| 329.054–338.408 s | 3314–3317, 3413 | Recipe-B cycle accepted, then actual native cycle completion. |
| 338.454–349.492 s | 3414–3419, 3528, 3533–3534 | Conventional transfer to inspection and observed effect. |
| 349.454–351.454 s | 3530–3532, 3554 | Linked inspection completes with pass. |
| 351.454–362.690 s | 3555–3559, 3671, 3677–3678 | Conventional tray2 delivery and observed effect. |
| 363.196 s | 3691; evaluator in assessment | B2 independently accepted in tray2 after 0.5 s settled dwell; host task-success stop. |

The independent first-success snapshot is `93a3e7454680bdbe1bbbe1985db57df1198d90bf5e3fc34addb41ea79b106f32`. The evaluator records no violations, no unmet quantity, and A1 remaining at parking1. The model's final message claimed recovery and handback, while leaving overall order completion unverified (trace line 591). The final task-success claim comes from protected evaluation after conventional follow-through.

## Continuity preserves the changed plan, but the final transfer outpaces its authority

Six protected commits distinguish planned actions, unresolved dispatches, completed repair and the revised response to rejected handback:

| Event / simulation time | Bytes | SHA-256 prefix | Note state |
|---|---:|---|---|
| 935 / 93.956 s | 1,555 | `7cceb8826c31` | Initial evidence and planned A1 transport. |
| 1141 / 114.372 s | 1,579 | `c90a604bb1ca` | Accepted transport explicitly unresolved. |
| 1795 / 179.380 s | 2,101 | `d7aca25b57b6` | Transport verified; first handback planned. |
| 2105 / 210.050 s | 2,747 | `0366cee89f30` | Rejection retained; planned setup-B repair. |
| 2302 / 228.948 s | 2,899 | `2cfe98cef5a3` | Accepted setup action explicitly unresolved. |
| 3184 / 316.858 s | 2,277 | `4bdfbb094eee` | Setup verified; second handback planned. |

Full notes are in the [protected continuity history](../../local-evidence/campaign001/RCI001-C01-home-01/host/continuity-history/). The final local continuity backing matches the last protected commit, and before/after-cleanup runtime exports agree. The notes limit their fully reviewed history to event 25 and label later evidence as direct command/status receipts; they do not claim a complete later history review.

After successful handback, a piped status read produced `ok:false` with null fields while the shell pipeline exited 0 (trace line 488). The model did not treat the process exit as success: it checked raw status next, exposing the explicit unauthorized response (line 495). Its attempted final continuity commit was also unauthorized (line 500). The old capability had lost authority. It made no further physical request, retained the uncommitted intended update in `notes/next-continuity.md`, and wrote `notes/recovery-result.md` with the actual accepted handback and the continuity gap (line 507; file bytes in the runtime export).

Thus protected continuity still says the second handback is planned, while protected event 3188 and the local recovery note say it completed. A later invocation must reconcile those sources rather than replay the planned request. This episode exercises writing and maintaining continuity, including a failed publication after authority transfer; it contains no restart and cannot establish a memory benefit.

## Infrastructure, timing and limitations

Missing `rg` and the `python` alias caused startup shell failures (trace lines 91, 124 and 125); the model used `find` and `python3` afterward. It ran the canary successfully at line 214. As in stock01, the assessment's `model_canary_repetition_observed=false` describes the absent optional saved canary artifact, not absence of an observed canary invocation. These tool-level issues and the rejected first handback remain visible without being mislabeled as infrastructure-invalid attempts.

All admitted checks passed. Lifecycle used the predeclared successful-terminal-host-closure branch: accepted handback, clean task-success host stop, observed namespace retirement, clean cleanup and durable export identity. The orchestrator's late retirement and token queries encountered connection refusal after natural host closure. Explicit operator-retirement and late HTTP403 receipts remain absent; they were not manufactured or marked passed.

Original per-tick maximum lag was 0.070 s over 181,097 samples. The separate journal reconstruction yielded 362 complete one-second windows, none outside 0.95–1.05 RTF, maximum lag 0.086 s and maximum sample gap 0.156 s. These are interpolated journal windows, not originally retained per-tick RTF. Queue occupancy was 386.780 s; host simulation elapsed was 362.196 s. Storage monitoring had 80 samples, maximum start gap 5.016 s, minimum native free space 418,220,335,104 bytes and no notice/stop. Its 97,532,575-byte sampled aggregate additional peak is measured from the campaign baseline and includes preceding campaign/shared-service growth; it is not home01's isolated file size or the exact between-sample peak.

The central observation is that physical obstruction removal and controller readiness were distinct. The agent responded to a protected rejection by producing a different admissible physical state, without resetting a control limit, and then returned work to conventional automation. This supports a concrete recovery chain on this known fixture. It does not establish repeatability, generalization, framework superiority or whether a simpler fixed recovery would perform equally well; those conclusions require the complete planned dispositions and separately authorized comparisons.

Evidence integrity anchors: protected history SHA-256 `8e469b24644b7f9c63c9e75056cf6dc4dc68256a29307721527e7096a5d371c8`; client trace SHA-256 `be905fffe76b2687dc1e0609d00cc838a8b4d80761ccc560ceaa445de329935b`. The admitted assessment retains the complete manifest, source, queue and evidence hash bindings.
