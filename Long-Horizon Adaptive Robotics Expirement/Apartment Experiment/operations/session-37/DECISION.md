# Session 37 terminal decision

The fresh apartment-v3 Baseline is **infrastructure-failed and incomplete: 9/21 assignments advanced in 14 normally closed sessions**. Queue job `20261009T010627656726Z-71e4ed51` ended `failed`, integer exit `1`, on October 8, 2026 at 21:21:58 PDT (`2026-10-09T04:21:58.522567Z`). Attempted workspace startup for session 15 raised `FUSE mount deadline` before any fifteenth native/model turn or `session_started` event. There is no `completed.json` and no successful scientific condition endpoint.

The independent audit passed all 11 groups and authenticated this failed history. Checkpoint 14 is intact; the separate final runtime inspection confirms retirement. Maps remains pristine and unlaunched. All three observation automations are paused, and the live viewer tab is closed. This is the blocker and normal Development Session 37 closeout required by [Randy's authority](authority-original.md), with no repair, retry, resume, Maps launch or condition comparison.

## What is established

| Quantity | Retained observation |
|---|---|
| Assignments advanced | 9 of the fixed 21: bedroom 2, kitchen 4, throwing 3 |
| Actual native turns / normal closures | 14 / 14; no failed native turn |
| Additional attempt | One failed workspace construction for session 15, before native execution |
| Task-success events | 6; the three throwing assignments advance on their timed boundaries, so 9 advancements are not nine task-success events or a throwing-mastery claim |
| Retained checkpoint | `baseline/checkpoints/session-00014`, 723 authenticated files |
| Checkpoint simulation time | `11477.972000503372` seconds |
| Authenticated history | 3,176 events, 410 image deliveries; native, ordered transport, clocks, sensor, replay and filesystem journals validated for all 14 completed sessions |
| After-checkpoint tail | 0 additional events; 0.0 additional simulation seconds in replay |
| Source preservation | Exact frozen v3 source/configuration; all 42,359 original v2 condition files (2,468,400,045 bytes) and both v2 checkpoint anchors unchanged |
| Final resources | No active pair queue work, native process, filesystem service, mounted workspace or viewer listener; D: 199.47 GiB free, C: 528.45 GiB free at terminal recording |

The checkpoint manifest SHA-256 is `5314dc656b39dd4254325a46c94bc56c028f5f526004f85ac983e1547ec44015`; checkpoint state SHA-256 is `43746085720e2582651d6a5d5ce3e2c66a6cac9504d97fd0dab98c10ed3963ba`. A verified checkpoint does not make this execution a clean hibernation or authorize recovery.

## Failure and retirement evidence

The immutable pair is `D:/Dandelion-Apartment-Experiment/official/apartment-v3`. The terminal operator evidence root is `operator/failure-audit-session37-001` beneath that pair.

1. The [official terminal queue receipt](official-terminal.json) and [failed execution](failed-execution.json) retain the original failure. Execution SHA-256 is `6a020d3f5fe97cc93d79ff7099b70d4d0227097ea02ae1d480498e8719b07b99`. Its retirement remains `all_retired=false`: controller, native and viewer true; filesystem false. That receipt was never repaired or overwritten.
2. [Preservation](failure-preservation-result.json), queue `20261009T044522840121Z-77ab5606`, succeeded with integer exit 0 before cleanup. It inventoried all 30,872 Baseline files (2,736,319,421 bytes) and copied all 1,385 partial-startup files (48,749,075 bytes) to `preservation/output/session-00015-before-cleanup`. The original inventory SHA is `6948df9994628463476f44d45d2ef729d8a313e3abb4505d6a67628c944adda4`; the partial-copy inventory SHA is `2a0c26400f8bb4a7acfc33daef669fb19e48d25735d02faf742f1ce4c8f7d505`.
3. The session-15 service was bound by exact run ID, Linux PID 367, start ticks `1269642`, mount path and command before a single operator retirement attempt. Its original journal had one `initial` record, the exact checkpoint-14 namespace, and no guest mutations. The preflight checkpoint found zero open handles. Normal `fusermount3 -u` succeeded with exit 0. A following retirement request raced the closed journal and returned `RuntimeError('I/O operation on closed file')`. The [operator command receipt](operator-retirement-failed.json) remains **failed, exit 1**; it was not retried or rewritten.
4. Independent readback nevertheless found the service's final journal and `native-exit.json`: `libfuse_main_return=0`, `requested_sigterm=false`, final sequence 3. The three records are `initial`, the labeled operator checkpoint, and `final`, all with unchanged namespace. Exact condition changes consist only of the appended journal records and added native-exit receipt; no prior files were removed or changed. The pre-cleanup bytes remain separately retained.
5. [Independent audit](failure-audit-result.json), queue `20261009T045015412900Z-efafe052`, succeeded with integer exit 0 at `2026-10-09T04:54:44.800478Z`. All 11 groups passed. The unchanged frozen reader checks completed sessions 1–14; a read-only path selector includes exactly those proven completed sessions, while the required extra session-15 directory is independently audited as a failed startup. No condition file or frozen module was changed to accommodate the reader. A second complete inventory confirms the audit itself was read-only.
6. [Final runtime inspection](runtime-final.json) confirms no matching Windows/Linux execution, recorded service identity or mount, active pair queue entry, running lock or responding viewer port. This later independent retirement finding does not change the failed official or operator receipts. [Terminal summary](terminal-summary.json) binds the copied evidence, final capacity, viewer close and all three paused monitor configurations. [Monitoring pause](monitoring-paused.json) is separate from the immutable startup monitoring receipt.

The queued audit also authenticates all 14 checkpoint manifests, complete successful native/transport histories, event-chain lifecycle accounting, four retained lifecycle fixtures, frozen source/environment identity, original v2 preservation, pristine Maps and the exact operator cleanup delta. An audit pass establishes evidence integrity; it does not establish experimental completion.

## Source-supported explanation and limits

The frozen `native_runtime.py:66` waits at most 20 seconds for the filesystem mount. The session-15 service's retained process-start and first-journal timestamps span approximately **22.450884 seconds**, using the verified 100 ticks/second process clock. This is consistent with filesystem restoration exceeding the fixed readiness gate. The timing is observational; no restore-performance reproduction or attribution to a particular disk, content item or code path was performed. Capacity was well above the 20 GiB admission floor.

There is a separately source-supported cleanup ownership problem. `run.py:131` assigns `workspace = Workspace(...)`; the constructor starts its service before the mount wait, then raises. Because construction never returns, the caller's `workspace` remains `None`, and its `finally` cleanup cannot reach that partial object. The original false filesystem-retirement record and observed orphan match this control flow. The normal-unmount/follow-up closed-journal race is also retained as a distinct operator-path limitation. No source was modified in response.

Recommended next work, only under later direction, is isolated engineering for progress-aware, bounded readiness and cleanup that owns partially constructed services; exercise restoration with checkpoint-sized throwaway filesystems and both normal/failing startup and retirement paths. Then make an explicit experimental decision between a separately qualified recovery lineage and a new pristine matched pair. The current frozen recovery guard rejects `all_retired=false` in the original execution receipt, so recovery is not presently a supported command to issue. Never rewrite that receipt to bypass the guard. Preserve the original v3 pair and all v2 histories regardless of the later choice.

## Earlier authorized work completed

Original v2 filesystem publication was pushed separately in commit `3752d1a5169828e77e05a56d3f5ebe5dfc9faca7`; see [PUBLICATION.md](PUBLICATION.md) and the [browsing index](../../evidence/original-v2-filesystems/README.md). All 6,122 corpus files, including 106 final regular files, 58 session histories, 22,090 journal records and 355 distinct content versions, passed Git byte readback. Protected large archives and private simulator/schedule content were excluded with exact evidence references; publication is outside guest inputs.

The newly authorized diagnostic recorder repair passed 14 recorder checks, 30 physics/integrated groups and all 10 independent commissioning groups. Both two-hour cases retained the actual `7199.99999985739`-second terminal state after 1,800,000 integration steps, within the unchanged 10-microsecond gate. Session 36's failed evidence remains failed. Only the two prescribed `scene.py` physics attributes differ from v2: `ccd_tolerance="1e-10"` and cup `condim="6"`; official runtime recording was unchanged. Inherited native qualification was authenticated, with no new native pilot claim. Exact internal engine cause and real-material calibration remain unresolved.

The fresh matched v3 pair then passed preparation and all 12 startup checks, launched once, and received six healthy periodic observations before terminal failure was found at the next scheduled observation. Those historical startup/progress receipts remain intact. No new model call, command to the robot, intervention in task behavior, schedule change or Maps launch occurred during monitoring or terminal handling.
