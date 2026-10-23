# Home 05: startup lag and the predeclared campaign stop

**Slot 10 is timing-invalid, with observed evaluator success and scored task
outcome unknown. It is the second consecutive ordinary infrastructure-invalid
attempt, so the frozen protocol requires stopping further admission.** The final
24-slot accounting is 6 valid successes, 4 invalid attempts and 14 not run.

Official queue job `20260927T200444386051Z-269f55a5` was independently queried and
confirmed `succeeded`, integer exit status `0`, before outcome inspection. The
[assessment](../execution/RCI001-C01-home-05/assessment.json) reports only
`current_episode_frozen_one_second_rtf_and_strict_per_tick_lag` as failed. The
model turn completed; other evidence, source, evaluator, lifecycle and storage
checks passed. No scoring or sealed source was changed in this investigation.

## What failed and when

| Timing measure | Value | Result |
|---|---:|---|
| Original per-tick maximum lag | 0.10800000001411725 s; 167,213 samples | Fails strict 0.1 s limit |
| Journal maximum lag | 0.11500000004097766 s | Fails strict 0.1 s limit |
| Out-of-tolerance one-second windows | 1/334 = 0.0029940119760479044 | Passes fraction below 1% |
| Maximum journal sample gap | 0.15700000000651926 s | Retained measurement spacing |

The sole bad one-second window is **0–1 seconds after episode start**, RTF
0.9220512819940316. The overall fraction still passes. The maximum-lag checks
fail independently of that fraction.

The [protected journal](../../local-evidence/campaign001/RCI001-C01-home-05/host/public-history.jsonl)
records four samples at or above 0.1 seconds. All are early in the episode:

| Event | Recorded context | Relative wall (s) | Relative simulation (s) | Lag (s) |
|---|---|---:|---:|---:|
| 11 | Observation 3, conventional owner | 0.313 | 0.204 | 0.109 |
| 19 | Control transfers to robot after conventional assistance request | 0.672 | 0.602 | 0.070 |
| **20** | **Observation 7, robot owner** | **0.719** | **0.604** | **0.115** |
| 21 | Operator requests invocation start | 0.766 | 0.752 | 0.014 |
| 22 | Protected invocation-start event | 0.797 | 0.752 | 0.045 |
| 24 | Observation 9 | 0.969 | 0.868 | 0.101 |
| 100 | Observation 85 | 8.641 | 8.528 | 0.113 |

The primary peak is the directly recorded sample at **event 20**, not an artifact
created by one-second interpolation. Between events 19 and 20, wall time advances
approximately 0.047 seconds while simulation advances 0.002 seconds, raising lag
from 0.070 to 0.115 seconds. The following sample at event 21 shows catch-up:
0.047 seconds of wall advance and 0.148 seconds of simulation advance, reducing
lag to 0.014 seconds. The maximum sample gap occurs later, between observations
29 and 30; it is not the interval producing the maximum lag.

The largest sample is timestamped **20:04:46.701723 UTC**. Protected invocation
start follows at 20:04:46.784827. The
[client launch](../../local-evidence/campaign001/RCI001-C01-home-05/orchestrator/pilot/client/launch.json)
starts at 20:04:51.224937; the actual model `turn/started` notification in
[client trace line 71](../../local-evidence/campaign001/RCI001-C01-home-05/orchestrator/pilot/client/events.jsonl)
is at **20:04:58.283 UTC**. Even the later event-100 threshold sample at
20:04:54.627989 precedes that model-turn notification.

This timing location distinguishes Home 05 from
[Home 03's later 0.334-second excursion](home03-timing-investigation.md).
Home 05's largest journal lag occurs during startup/control transfer, before its
model turn starts. It cannot be attributed to a recovery decision or physical
command issued by that not-yet-started turn. These records do not isolate which
startup, sensor, filesystem, scheduler or other host activity produced the delay.
No causal assignment to a specific operation or competing process is established.

The journal and original host scalar retain the different clock origins described
in [Home 02](home02-timing-investigation.md). Their approximately 7 ms maximum
difference is not a measured correction. Here the original per-tick maximum also
fails its own limit. Its peak timestamp is unavailable, so this note does not
claim that the scalar's maximum necessarily occurred at event 20 or before the
model turn. Nothing was rebased, excluded or rescored.

## Later task and lifecycle evidence

The model turn eventually completes at 20:10:25.906 UTC. Protected handback/control
transfer event **2914** occurs at 20:09:34.171657, returning conventional ownership.
The independent task-success stop is event **3418**, 20:10:20.428479 UTC.
The predeclared natural terminal-host-closure branch is valid, including clean
host exit and observed namespace retirement. Late explicit retirement and HTTP403
receipts remain missing rather than being marked passed.

Storage coverage passes with 72 samples, no alerts and no stop latch. Minimum
native free space is 419,257,778,176 bytes; minimum WSL free space is
1,009,098,420,224 bytes. Capacity therefore does not trigger the stop; storage
measurements do not identify the cause of the timing excursion.

## Independent stop-rule and disposition audit

The current protocol bytes were hash-checked against the pre-outcome certificate
and match. The protocol explicitly requires stopping after **two consecutive
ordinary infrastructure-invalid attempts**, with no replacement and remaining
slots recorded `not_run`. It does not require both invalid attempts to have the
same failure type.

The sealed ten completed assessments and their disposition hashes agree. Their
ordinary-invalid counter sequence is:

```text
slot:      1  2  3  4  5  6  7  8  9 10
counter:   0  0  1  0  0  1  0  0  1  2
```

Slot 9's unrecognized client transport disposition and slot 10's timing failure
are consecutive ordinary infrastructure-invalid attempts. Stopping after slot 10
therefore follows the predeclared rule. It is not an outcome-driven stop for
observed robot success and is not based on an invented immediate-stop condition.

| Fixed fixture | Planned | Completed valid successes | Completed invalid | Not run |
|---|---:|---:|---:|---:|
| Misplaced stock | 12 | 4 | 1 | 7 |
| Blocked insert home | 12 | 2 | 3 | 7 |
| **Total** | **24** | **6** | **4** | **14** |

There are no scored task failures among the six valid attempts. All ten completed
episodes retain observed evaluator success, but the four invalid observations
remain diagnostic and are not added to the valid-success denominator. All
remaining slots 11–24 have explicit `not_run` dispositions, unknown outcomes,
`allow_next=false`, and the actual stop reason. At audit time none of those slots
has a launch intent, job file, assessment, designated host/orchestrator evidence
directory or runtime workspace. This is consistent with stopping before slot 11.

## Provenance and scope

- Assessment SHA256:
  `d5220287d7e7bb79a024970ac0ae7bab1afaba864a7913317acdb9384a59d0aa`.
- Protected journal SHA256:
  `24c3ba8086b0140455a49ce93ac99781852ba0c812b02c63648e5006e2d51dad`.
- Frozen protocol:
  [PROTOCOL-v2.md](../admission/PROTOCOL-v2.md), authenticated by the retained
  [sealed-v3 certificate](../admission/sealed-v3/certificate.json).

Only this investigation note was written. Sealed files, map records, dispositions
and assessment outcomes remain unchanged. No simulation, model run, qualification,
test suite or heavy profiling was performed.
