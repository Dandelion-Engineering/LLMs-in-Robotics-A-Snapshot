# Home 03: both lag measurements fail despite observed task success

**Slot 6 remains an ordinary infrastructure-invalid attempt, with observed
evaluator success and scored task outcome unknown.** Its original per-tick lag
reaches approximately 0.327 seconds and its protected-journal lag approximately
0.334 seconds. Both exceed the strict 0.1-second limit. Unlike
[Home 02](home02-timing-investigation.md), this failure cannot be explained away
by the journal-versus-loop clock-origin limitation.

Official queue job `20260927T194109991699Z-f4d25fd1` was independently queried and
confirmed `succeeded` with integer exit status `0` before inspecting outcomes.
The [assessment](../execution/RCI001-C01-home-03/assessment.json) reports only one
failed check: `current_episode_frozen_one_second_rtf_and_strict_per_tick_lag`.
All other source, evidence, evaluator, lifecycle and storage checks pass.

## Exact recorded excursion

The [protected journal](../../local-evidence/campaign001/RCI001-C01-home-03/host/public-history.jsonl)
directly records the maximum at **event 648, observation sequence 633**, UTC
19:42:28.518428 on September 27, 2026. It is an input-sample maximum, not a value
introduced by one-second interpolation. Relative to the episode-start event:

| Event | Observation sequence | Wall elapsed (s) | Simulation elapsed (s) | Lag (s) |
|---|---:|---:|---:|---:|
| 647 | 632 | 63.765 | 63.738 | 0.027 |
| **648** | **633** | **64.140** | **63.806** | **0.334** |
| 649 | 634 | 64.250 | 64.096 | 0.154 |
| 650 | 635 | 64.312 | 64.288 | 0.024 |
| 660 | 642 | 65.156 | 65.040 | 0.116 |

Between events 647 and 648, wall time advances **0.375 seconds** while simulation
advances **0.068 seconds**. The resulting approximately 0.307-second lag increase
is followed by catch-up: the next two intervals advance simulation by 0.290 and
0.192 seconds while wall time advances 0.110 and 0.062 seconds respectively.
Events 648, 649 and 660 are the three journal samples at or above 0.1 seconds.
The maximum journal gap is the same 0.375-second interval. The samples establish
a transient lag excursion but not its exact continuous duration or any larger
unobserved peak between samples.

The [host result](../../local-evidence/campaign001/RCI001-C01-home-03/host/result.json)
independently retains 161,406 per-tick timing samples and maximum lag
**0.3269999999729123 seconds**. The reconstructed maximum is
**0.33399999998360386 seconds**. The original scalar has no maximum timestamp or
full retained per-tick series, so exact alignment of these two maxima remains
unavailable. Nevertheless, the original scalar itself exceeds its own limit by
approximately 0.227 seconds. The approximately 7 ms difference between the two
maxima is not a measured origin correction and is not needed to establish failure.

## One-second rates

Three of 322 reconstructed windows are outside 0.95–1.05 real-time factor:

| Wall interval relative to episode start | RTF | Observation |
|---|---:|---|
| 58–59 s | 1.058832000014732 | Above upper tolerance before the largest excursion |
| 63–64 s | 0.8117928205076907 | Below lower tolerance near the delay |
| 64–65 s | 1.1773866666664574 | Above upper tolerance during catch-up |

The fraction is **3/322 = 0.009316770186335404**, still strictly below 1%, so the
predeclared fraction criterion passes. Both maximum-lag criteria fail. These
criteria are conjunctive; passing the window fraction cannot rescue the result.
No samples or windows were excluded and no permissive alternative score was
computed.

## Nearby model and gateway activity

The complete retained journal and client event files were read for the timing
neighborhood. The [client trace](../../local-evidence/campaign001/RCI001-C01-home-03/orchestrator/pilot/client/events.jsonl)
and [broker receipts](../../local-evidence/campaign001/RCI001-C01-home-03/orchestrator/pilot/broker-events.jsonl)
give this sequence:

- At 19:42:23.48–23.52 UTC, the broker records successful status/history reads
  and a denied status request associated with the boundary canary. Client lines
  187–190 report the canary and focused history commands completed successfully.
  This is several seconds before the largest lag sample.
- At 19:42:28.518 UTC, the maximum appears in a routine protected observation.
  No robot physical command is dispatched in the peak neighborhood. Adjacent
  protected events 647–650 are observations, and control belongs to the robot.
- At 19:42:29.430 UTC, protected events 657–658 accept an explicit observation
  request, `pilot-b09ec96fbd7b-pre-move-01`; the broker records its receipt at
  19:42:29.435. Client lines 195–196 show the corresponding `robot.py observe`
  command. This request follows the maximum and its main catch-up interval.
- Event 659 records an available requested image at 19:42:29.479 UTC; event 660
  is the later 0.116-second lag observation. Event 662 records observation-request
  completion at 19:42:29.631. This temporal association does not isolate the
  operation responsible for that smaller later lag sample.
- The first robot physical dispatch, event 952, is the A1-to-parking1 transport
  at **19:42:58.883 UTC**, about 30 seconds after the largest lag sample. The
  later setup-B command is farther removed, at event 2131 / 19:44:55.826 UTC.

Client `emittedAtMs` values are notification timestamps, not a profiler's exact
process-start/stop measurements. Broker receipt timestamps also do not isolate
each operation's CPU, waiting or I/O duration. The records support ordering and
show that the primary spike precedes robot motion; they do not establish which
host activity caused it. Model processing, sensor work, filesystem activity,
host scheduling and external monitoring remain possible unisolated contributors,
not measured causes. No heavy profiling or new experiment was performed.

## Lifecycle, storage and comparison

This attempt establishes the **explicit-retirement** lifecycle branch. Protected
invocation-start event 23 is followed by retirement event **3171** at
19:46:35.904397 UTC. Control is already conventional, authority epoch 4, and
retirement preserves the active conventional command. The task-success stop is
event **3299** at 19:46:47.201587 UTC. Explicit retirement, late stale-token HTTP403
and all namespace retirements are observed; the missing-receipts list is empty.
This is a different observed shutdown branch from the earlier natural-closure
cases, and it introduces no retirement failure.

The storage monitor records 71 samples, complete coverage, maximum sample gap
approximately 5.016 seconds, no alerts and no stop latch. Minimum native free
space is 419,751,682,048 bytes and minimum WSL free space is 1,009,114,099,712
bytes. These capacity observations pass; they do not measure or exclude transient
performance contention.

| Retained measure | Home 02 | Home 03 |
|---|---:|---:|
| Original per-tick maximum lag | 0.099 s: pass | 0.327 s: fail |
| Journal maximum lag | 0.113 s: fail | 0.334 s: fail |
| Maximum journal sample gap | 0.188 s | 0.375 s |
| Bad reconstructed windows | 0/315: pass | 3/322: pass |
| Lifecycle branch | Successful terminal host closure | Explicit retirement |

The clock-origin difference documented for Home 02 remains a measurement caveat
for both episodes. Home 03 adds direct original-host evidence of a substantially
larger lag failure. Their shared infrastructure-invalid classification therefore
does not imply an identical failure magnitude or an established common cause.

At slot 6 close, the preceding valid slots 4 and 5 mean the consecutive ordinary
infrastructure-invalid count becomes **one**. The timing-only invalidity consumes
slot 6 without replacement. It is not a scored robot failure and does not itself
activate an immediate integrity, capacity or retirement stop. The original
two-consecutive-invalid rule governs subsequent admission.

## Retained identities

- Assessment SHA256:
  `dd6d94363a199f71b1894333efa73015a832970e05598e31551960d2621e0e43`.
- Protected journal SHA256:
  `11a3eab36ea40e2b19f72af019d20d66adae0d61a4eb088a6b77297207d68a2a`.
- Original host result SHA256:
  `cf98b1b20d82728014b4298d9b72b234f98eccda355b983d47bdf1da4fbf8431`.
- Client trace SHA256:
  `406b70300c55a9caa4b8682287f154e0afb7ac84951cc7298917c7a126eb9e26`.
- Broker trace SHA256:
  `a3f7ebb88217116496d852809c9908a904a1d0a3f92a12ce687a45205eafe498`.
- Official queue receipt SHA256:
  `1238c723dcf48853abae857691a84420bbf6a612c64385105262e89b55e9b5af`.

Only this investigation note was written. Framework sources, protocol, assessor,
retained outcomes and scoring remain unchanged; no qualification was rerun.
