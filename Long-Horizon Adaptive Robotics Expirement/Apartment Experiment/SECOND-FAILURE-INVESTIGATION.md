# Second apartment baseline stop: diagnosis and repair choices

**Session 32 — October 7, 2026. Investigation only.** Randy's 10:32 PDT correction controls this session: propose repairs for review; do not implement them, commission repairs, reset the pair, launch, or resume. Those boundaries were observed.

The baseline **terminated after the model service rejected the sixth native turn for capacity**. Queue `20261007T152810664605Z-1b6c57b1` ended at **10:12:09.831 PDT**, state `failed`, integer exit **1**. It is no longer running or stalled. Five Robot Codex sessions had completed normal model/filesystem/physical boundaries. The sixth produced no assistant output or robot tool call before its failed terminal response.

The decisive retained notification says:

> Selected model is at capacity. Please try a different model.

Its structured code is `serverOverloaded`, `willRetry: false`; native turn duration is **2,920 ms**. The local launcher then raised `RuntimeError('Model did not complete normally: Bootstrap turn did not complete')`. Native shutdown, transport drain and journal retirement completed normally. **No storage or transport repair is indicated as the remedy for this particular stop.** The remote service's internal cause and duration of its capacity shortage are unavailable locally.

**Recommendation:** improve error reporting and make every clean boundary durably recoverable, while retaining the same model and a visible stop for service failures. Approve a precise recovery/attempt-accounting rule before adding automatic retries. This handles service interruptions without silently changing the experiment. The existing interrupted history should remain intact while Randy decides whether a future authorized revision starts a fresh pair or uses a separately identified continuation.

## Evidence and preservation

The compact [evidence receipt](operations/session-32/evidence.json) binds the detailed audit at `D:/Dandelion-Apartment-Experiment/investigations/restart001-session32-audit002/result.json`. [Queue receipts](operations/session-32/queue-statuses.json) and two [runtime inspections](operations/session-32/runtime-inspection.json) ([second](operations/session-32/runtime-inspection-secondary.json)) give terminal and current-state evidence. All findings below are from retained observable records, source inspection and readback; private model reasoning was not used.

The sustained read-only audit ran through the shared queue: `20261007T174758541852Z-b6a03c0c`, succeeded, integer exit 0. It independently reconstructed all six journals, checked final exports, paired transport commitments, event hashes, 134 sensor images, and all replay chunks. All **254 frozen files** match their preparation manifest; all **244 executable/template identity entries** match the run. These counts describe different inventories.

Full SHA256/size/mtime inventories bracketed the investigation's bulk reads. **20,101 files are unchanged**: 16,522 in restart001, 3,565 in the original failed pair, and 14 in its preservation package. The retained byte totals are respectively 366,208,438; 3,302,050,897; and 894,768. Initial inventories from the first audit also equal the final inventories. No official artifact, frozen source, robot file, lock, process or mount was modified by this investigation.

The first audit (`20261007T174453199890Z-0efd7ee3`) exited 1 on an overly strong wall-clock-monotonicity assertion. Its source, partial findings and error remain preserved. The replacement separately reports the real clock regression instead of accepting that assertion. This was an analysis-tool failure, not another official attempt or a repair test.

## What happened

Recorded local times below are UTC minus seven hours; monotonic and simulation time are the duration authorities because wall time has the discontinuity described later.

| Event | Retained evidence |
|---|---|
| 08:28:10.996 PDT | The single queue worker begins the frozen baseline. |
| Sessions 1–5 | Native turns complete; five substantive reports, continuity updates, journal final records, retirement receipts and physical `session_closed` events are present. |
| 10:11:50.132 | Session 5 closes, event 1508, simulation time 6,194.532 s, docked, assignment position 1. |
| 10:11:56.964 | Controller emits `session_started` for session 6, event 1509; its ordinary 240 s bedroom window starts. |
| 10:12:04.217 | Native `turn/started`; the sole bootstrap instruction is accepted. Acceptance does not guarantee inference availability. |
| 10:12:07.139 | `error` and failed `turn/completed` notifications carry `serverOverloaded`. See session 6 `native/client/events.jsonl`, physical lines 64–65. |
| 10:12:07.190 | Native app-server exits 0 after a qualified unsubscribe/close handshake. The model turn failed despite this successful process retirement. |
| 10:12:09.445 | Last replay sample: simulation time 6,207.012 s. |
| 10:12:09.831 | Queue records exit 1. The launcher has written its failure result and removed its own running lock. |

The sixth session has only the completed user-message item: **zero completed agent messages, command executions, dynamic tools or file changes**. Its two successful journal writes total **50 bytes**, both to the framework's temporary `/.boundary-probe`; they are not Robot Codex learning. Its final exported regular files equal the persistent files left by session 5. The full inode state changes during preflight, so byte equality of regular files must not be mistaken for an unchanged namespace.

Native `model_started: true` records that `turn/start` was accepted; it does not establish that the model produced an inference. Recorded account telemetry reported **16% used** for the available weekly bucket, with no rate-limit-reached or spend-control flag. This supports the explicit capacity classification; it is not proof about every possible service limit. No raw HTTP status, `Retry-After`, server-side trace or capacity recovery time is retained. Do not relabel the event as an observed HTTP 503 or exhausted personal quota.

The generic error loses detail at `campaign-005/bootstrap_client.py:399–400`, which checks failed/completed status but does not copy the terminal error into its result. Apartment `run.py:127` propagates that generic string. The original structured cause remains in the event log. Its absence from the top-level result made a service failure look like a nonspecific bootstrap crash.

### Session and task accounting

| Session | Assignment | Active simulation interval, seconds | Native terminal | Clean boundary / advancement |
|---|---|---:|---|---|
| 1 | Throwing practice | 2,081.796 | completed | closed; advanced to position 1 |
| 2 | First bedroom assignment | 1,222.076 | completed | closed; incomplete, same assignment |
| 3 | Same bedroom assignment | 826.796 | completed | closed; incomplete, same assignment |
| 4 | Same bedroom assignment | 1,095.824 | completed | closed; incomplete, same assignment |
| 5 | Same bedroom assignment | 967.640 | completed | closed; incomplete, same assignment |
| 6 | Same bedroom assignment | at least 12.480 through last replay sample | failed in startup | no normal session close |

Intervals include work, return and closeout; they are not the nominal work windows. The source's `finish` gate requires physical docking, no outstanding motion, ordinary model completion, filesystem closeout and runtime retirement. Both the receipts and subsequent accepted `session_closed` events support the first five boundaries.

There are **six started sessions, five normally closed sessions, one advanced assignment out of 21, and no household success event**. Throwing advancement means a completed practice window, not learned throwing mastery. The final endpoint is missing; six is not a completed-endpoint session count. Maps is still byte-identical to its initial inventory, unlaunched, with no session directory. No Baseline-versus-Maps effect can be estimated from this interrupted history.

## Comparison with the first failure and Session 30

The first launch's evidence was recounted directly, including its failed write, rather than inferred from its queue exit. [REPAIR.md](REPAIR.md) retains the earlier diagnosis, mechanisms and all fifteen repair attempts.

| Quantity | Original launch, session 1 | Restart001, session 1 | Restart001, failed session 6 |
|---|---:|---:|---:|
| Successful write input | 2,900,579 B | 3,893,783 B | 50 B, framework probe |
| Stored content | 3,211,381,062 B | 3,779,435 B | 755,173 B, including restored content |
| Journal metadata | 7,411,973 B | 12,824,518 B | 158,890 B |
| Rejected mutations | 1, ENOSPC | 0 | 0 |
| Parent transport metadata | 1,048,283 B | 36,728 B | 12,337 B |
| Native terminal / retirement | completed / unqualified cleanup | completed / qualified | failed / qualified |
| Final filesystem journal | missing | verified | verified |

Originally, 2,270 appends to one 2,798,415-byte log retained **3,210,792,618 bytes of full versions**, exhausting the 3 GiB journal despite ample disk space. A separate per-frame transport ledger then approached its 1 MiB ceiling; cleanup reported a 25-second drain failure. Session 30 replaced full-prefix copies with immutable compressed chunks/deltas, replaced growing frame rows with ordered commitments, and repaired backpressure, native stream accounting, cancellation races and abnormal retirement.

The restarted throwing session exercised **2,506 writes to its largest log**, ending at 3,051,334 bytes. Total content/input ratio was **0.971**, compared with **1,107.15** originally. Including metadata, its total journal was **16,603,953 bytes**, about **0.515%** of the unchanged 3 GiB cap. Summing resulting full-file sizes after each successful write gives **4,006,989,823 bytes of hypothetical full-copy write traffic** for this session. That is a counterfactual traffic calculation, not measured deduplicated disk storage.

Across all six journals, retained content is **9,834,651 bytes** and metadata **37,495,602 bytes**, for **7,228,361 bytes** of successful write input. These totals include per-session restored initial content. All **17,385 journal records** passed reconstruction; none is a rejected mutation. The five completed sessions survived the paths exercised by the repair, including eight reconciled ordinary H2 cancellations across twelve codehost channels. This supports the repair's behavior over this history, not unlimited-duration reliability.

### Remaining headroom and transport state

| Limit or mechanism | Observed maximum across six sessions | Interpretation |
|---|---:|---|
| Journal, 3 GiB per session | 16,603,953 B content + metadata | Far below cap. |
| Individual file, 16 MiB | 3,051,334 B | 18.2% of cap. |
| Live namespace, 256 MiB | 7,101,561 B | 2.65% of cap. |
| Parent metadata, 1 MiB | 81,715 B | 7.79% of cap. Namespace ledger maximum: 53,658 B, measured as canonical serialized records. |
| Channel queue + fixed headroom, 1 MiB | **1,032,314 B in session 2** | **98.45%; 16,262 B spare.** It drained successfully. Retain a near-capacity case for future regression testing; this did not trigger session 6. |
| Native session input, 256 MiB | 18,461,323 B | 6.88% of cap. Session 6 consumed only 66,077 B. |
| Retained native events, 512 MiB | 18,621,713 B | 3.47% of cap. |
| Native notification queue, 8 MiB / 256 items | 428,432 B / 23 items | Bounded queue stayed small; not a measurement of total process RAM. |
| Executor capture, 64 MiB | 1,553,669 B | 2.32% of cap. |
| Runtime CANCEL proof, 64 per channel | 3 | No exhausted protocol record bound. The 1,024 H2 stream limit is not a lifetime request quota. |
| Transport shutdown, 25 s | 0.610 s | Session 6: 0.391 s, sealed, no failure. |
| Native turn wall limit, 7,200 s per session | 2,065.066 s reported native duration | Session 6: 2.920 s; no two-hour timeout. |

All native-stream receipts report no reader errors and retired readers. Session 6 had **zero authenticated codehost channels**, zero charged payload queue bytes, and empty transport failures. These codehost channels carry isolated execution traffic; they are not a captured transcript of the model provider connection. Its native quiescence took approximately **47 ms**, exit 0, without forced job closure. All six guest cleanup and workspace retirement receipts passed. FUSE returned 0 in sessions 2, 4, 5 and 6; sessions 1 and 3 record `libfuse_main_return: 8` with `requested_sigterm: true`. This is the existing qualified retirement path after unmount and final journal closure (`journal_service.py:78–96`), not a failed service process exit. Preserve that distinction instead of rewriting those values to zero.

Live inspection found none of the six recorded native Windows PIDs, none of the six identified FUSE services or mounts, no queue child PID, and no observer listener on port 55582. No intervention was required. D: had **425,970,368,512 bytes free at the audit snapshot**, well above the 20 GiB new-session admission threshold; current free capacity is not historical peak telemetry. No historical peak-RAM trace exists, so a numerical memory-exhaustion assessment is unavailable. The explicit service rejection and clean local teardown are the positive causal evidence.

Persistent storage remains finite. Later sessions restore accumulated files, and repeated household sessions are unbounded by the frozen design. These observations cannot guarantee space for eventual completion. Raising quotas or shortening/limiting sessions would not address the observed service rejection.

## Checkpoints and replay

**There is no `latest-checkpoint.json`, checkpoint directory, or `completed.json`.** No hibernation was requested. This follows the existing code: `controller.py:46–61,106–114` creates a resume package only at hibernation or the 21-assignment endpoint. Ordinary boundaries write `boundary-state.json` and flush replay, but do not invoke checkpoint verification.

The retained boundary is session 5 at 6,194.532 simulation seconds. The event log then contains the sixth start, and replay continues another 12.480 seconds. The boundary record alone is not a validated checkpoint; pointing `--resume` at it would also encounter the exact log-tail checks at `controller.py:139–151`. Session 6's FUSE final record establishes filesystem retirement, not physical session completion. No checkpoint was manufactured and no tail was truncated.

All **1,500 indexed replay chunks**, **191,834 samples**, **88,780,454 bytes** and 134 sensor-image hashes passed readback. There are no extra unindexed replay files. Physics values are finite; simulation and Windows monotonic timestamps remain ordered. The 1,509-event chain is intact. This is retained-state verification, not a new simulator run or cinematic replay.

One wall-clock regression occurs in `states-000887.npz`, sample 40, simulation time **3,622.612 s**: wall time decreases **7.7461822 s**, while Windows monotonic time advances **31.6662 ms**. This precedes the service stop by roughly 43 minutes of simulation time. A system wall-clock adjustment is plausible, but its operating-system cause is not recorded. Preserve the original timestamps and align detailed replay through monotonic clocks and retained clock bridges; do not silently sort or correct the original wall times. Alignment behavior itself was not browser-tested in this investigation.

## Ranked repair options

### 1. Same-model recoverable stop at every clean boundary — recommended first

**Change:** propagate structured native error code/message, retry disposition, thread/turn identity and lifecycle phase into the top-level result; commit a verified world/RNG/task/filesystem/replay checkpoint at every normal docked boundary; preserve an immutable failed-attempt tail with an explicit service-interruption status. Define a prospective, operator-authorized continuation branch that references the failed tail and its parent checkpoint. The current resume path cannot accept an older checkpoint plus a later tail without such a change.

**Why:** a cloud availability rejection remains possible, but one no-work startup failure need not destroy a long-lived experiment's recovery path. Accurate status prevents another storage investigation when the actual cause is already known.

**Tradeoffs and comparison effects:** more checkpoint I/O, manifests and recovery complexity; storage sharing must retain exact versions and full inode semantics. Snapshotting while `between_sessions` uses an existing physics pause and can preserve nominal task windows, but changes calendar time and provider exposure. A continuation must keep the abnormal sixth start visible and must specify whether it continues the remaining physical window or returns to a prior boundary. Returning to the earlier boundary is a rollback, not a semantics-neutral resume. No such rollback is authorized for the current pair. Freeze the same recovery rule for both conditions before use; never insert evaluator knowledge into Robot Codex.

**Validation before launch:** offline fault injection around every checkpoint commit/publish boundary; hash-exact world/RNG/inode recovery and append-only branch lineage; one recorded failure cannot create two successful continuations; service failure, crash and interruption after side effects must remain distinguishable. Then separate throwaway native runs for both actual templates through warning, docking, retirement, recovery and a fresh session. Validate replay tails, attempt counts, template/model identity and storage growth. Preserve all failed cases.

### 2. Bounded automatic recovery for an explicitly rejected startup — optional extension

**Change:** after option 1, permit a finite same-model backoff policy only for positively classified capacity rejection with no assistant output, tool/action activity or uncertain side effects. Record every native request and underlying retry if observable; stop after a fixed attempt/time budget. Never apply a catch-all retry or fallback model.

**Why:** transient capacity shortages may clear without requiring an operator at every boundary. General [OpenAI overload guidance](https://developers.openai.com/api/docs/guides/rate-limits) recommends delays and finite retry budgets and cautions against replay after output. It does not establish that this ChatGPT-authenticated failure is safe to retry under the existing experiment rules.

**Tradeoffs and comparison effects:** `turn/start` acceptance is not an availability guarantee. The current harness starts physics and increments the session count first. Retrying during that window consumes battery; resetting it gifts time; moving activation until useful inference changes session timing and potentially which bootstrap work is counted. A recovery design must choose and document these semantics, preserve failed-attempt accounting, and use a recovery RNG separate from the world/schedule RNG if jitter is used. Repeated requests may incur unmeasured compute/use and alter provider timing. A new amendment and prospective paired revision are required.

**Validation:** inject explicit capacity errors before output, repeated exhaustion, malformed/unknown failures, stream breaks after output, timeouts after a possible command and process crashes during waiting. Prove only the declared empty-start case retries, no action executes twice, all attempts remain visible, total bounds hold, and physical clocks/battery obey the approved rule. Follow with separate native end-to-end validation in both conditions. A successful probe cannot guarantee the next request's capacity.

### 3. Wait for availability and authorize a new clean attempt with the current apparatus

**Change:** no runtime repair; retain this failed history and obtain an explicit future launch decision and fresh lineage. Waiting here is an operational choice, not a scheduled monitor created by this session.

**Why:** the immediate capacity rejection may disappear; the local apparatus completed five sessions successfully.

**Tradeoffs and comparison effects:** the same interruption can recur at any later native turn, and ordinary boundaries still lack resumable checkpoints. A fresh pair discards accumulated learning from the comparison and consumes additional compute/time; it must not silently replace the failed record. Repeatedly restarting until a favorable history completes would condition the evidence on survival. The current history cannot simply be launched again as pristine.

**Validation:** authenticate the frozen source/environment and an explicitly authorized pristine pair; an authorized non-scored availability check may reduce uncertainty but cannot ensure a 21-assignment history will finish. No new availability probe was made here.

### 4. Change the model, provider route or native runtime

**Change:** choose another inference configuration, or investigate a documented client change only if evidence identifies relevant behavior.

**Why:** another service/model could have different availability, but local evidence provides no reliability estimate or proof that updating the client would cure this rejection.

**Tradeoffs and comparison effects:** model/reasoning changes directly affect behavior and the scientific question; API/auth changes may require new credentials or spending and different isolation/observability. Switching only after one condition starts breaks the frozen matching. No spending or new credential authority exists. This ranks last.

**Validation:** new explicit configuration choice, both-condition requalification, capability/isolation and observable-evidence checks, fresh comparative lineage and preserved failed histories. Never silently substitute another model in this pair.

Error surfacing and clock-aware replay are useful across options. Storage-cap increases, timeout extensions, automatic recharging, skipping the bedroom task, and retrospective deletion of session 6 have no causal support as remedies here.

## Decision left to Randy

Authorize the scope of the next repair, particularly **checkpoint-and-stop only** versus **a bounded, explicitly defined startup-recovery policy**. Decide the future comparison lineage separately from the technical repair. This session leaves the current pair, its six started sessions, Maps' pristine state, all failures and all original evidence intact. No implementation, repair commissioning, reset, official launch or resume occurred.
