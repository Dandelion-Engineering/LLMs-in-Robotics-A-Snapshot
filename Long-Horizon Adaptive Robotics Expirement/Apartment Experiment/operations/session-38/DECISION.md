# Session 38 engineering result

**Workspace startup and cleanup are repaired and independently qualified in isolated engineering environments.** Final `qualification008` and `audit002` both finished with queue state `succeeded`, integer exit 0. This is an engineering result; the working source is not an officially commissioned experimental release. No model call, official recovery, Baseline launch/resume, Maps launch, condition comparison or monitoring restart occurred.

Recommend a **fresh pristine matched pair after later explicit authority and full commissioning**. A checkpoint-14 recovery is technically plausible but requires a new, separately qualified source-migration/recovery policy and a scientific lineage decision. The original frozen guard correctly rejects its immutable `all_retired=false` execution. See [recovery options](RECOVERY-OPTIONS.md).

## What failed and what changed

The original checkpoint-size restoration crossed the old 20-second mount gate in isolated profiling. It contained 362 regular inodes / 358 unique objects / 51,034,996 bytes. Content publication consumed 20.03 of 21.19 Linux restore seconds; repeated file publication across the Windows filesystem bridge dominated, while compression used about 0.70 seconds. The profile supports a scaling-related restoration bottleneck. It does not establish the exact cache, device or host conditions that caused Session 37's 22.45-second observation.

The original constructor orphan and the closed-journal follow-up were separately reproduced with explicit test-only timing injection. The caller now owns a workspace before startup; constructor failures also retain ownership and invoke bounded cleanup. An owner record precedes service initialization and binds the process to the run, mount, PID/start ticks and Linux boot. Admission-record write failures and late helper setup are covered too.

Startup tracks completed files/bytes and ordered phases. Heartbeats alone do not extend it. Default admission limits are 20 seconds without progress and 120 seconds total, with bounded cleanup afterward. The caller also rejects a late result in its own clock domain. A successful fence requires committed initial evidence, FUSE initialization, mount presence, a healthy identified control response and a working filesystem operation.

Restoration prepares the unchanged content format through native Windows I/O, then Linux flushes adopted directories and verifies every reconstructed content hash before admission. Normal retirement no longer requires a post-unmount journal request. Closed journals reject checkpoints; compatible retirement requests observe finalization without appending. A failed startup/abnormal retirement remains failed even when resources are later proven retired. [Source review](SOURCE-REVIEW.md) explains the boundaries and fixes.

## Measured startup and scaling

End-to-end times below use the Windows performance clock, in seconds. Original and repaired startup use the same throwaway input states; the repaired fence also verifies responsiveness. Original profiles include instrumentation. The Linux profile's subphase times are a separate clock domain and are not added to Windows phases.

| State | Cache treatment | Regular inodes | Logical MB | Original startup s | Repaired startup s |
|---|---|---:|---:|---:|---:|
| small | advised-cold | 90 | 9.16 | 5.11 | 4.34 |
| small | warm | 90 | 9.16 | 4.44 | 4.28 |
| checkpoint14 | advised-cold | 362 | 51.03 | 21.46 | 18.63 |
| checkpoint14 | warm | 362 | 51.03 | 19.91 | 18.80 |
| large | advised-cold | 724 | 102.08 | 34.61 | 34.00 |
| large | warm | 724 | 102.08 | 32.92 | 33.44 |

Checkpoint-sized repaired startup was 18.63–18.80 seconds. The larger state still takes roughly half a minute: this is a modest performance change, not a broad speedup claim. The important reliability result is accepting slow verified progress within a hard admission budget while rejecting stalls, child exits and expired budgets.

Cold treatment is only Linux `DONTNEED` advice on the isolated input copies; physical device/Windows caches were not reset. File count and byte volume co-vary, and the doubled state retains some content-chunk sharing. This is not a factorial attribution, statistical performance study or worst-case bound. [Timings](timings.json) retain both clock domains, exact definitions and source references.

## Qualification and independent verification

Final qualification passed 14 real startup/retirement cases: six size/cache starts, slow progress beyond 20 seconds, an actual hang, false heartbeat, early child exit, partial initialization failure, adopted-directory flush failure, absolute expiry, and the unmount/journal-close race. Four additional failures cover corrupt source content, process creation, admission-receipt writing after mount, and a forced helper-setup overrun. The original failure reproductions, deadline state checks and all six existing isolation-canary gates also passed.

The separately implemented audit passed all seven groups: source/environment; queue and failed-attempt accounting; old-reader matrix replay; namespace/open handles; adversarial failures; actual resource retirement; and official preservation/checkpoint/recovery guard. It additionally tested hard links, symlinks, mode bits, empty directories, writes after restoration, sparse writes/truncation, open-handle refusal, corruption after preparation, a pre-owner bootstrap hang and a poisoned journal. It used the unchanged pre-repair journal reader. This is independent computational readback, not an external human or second-model review.

All **75,407 official v2/v3 files, 5,284,557,531 bytes**, matched the pre-work inventory exactly. Checkpoint 14 and its completed prefix passed readback; its manifest remains `5314dc656b39dd4254325a46c94bc56c028f5f526004f85ac983e1547ec44015`. The original false retirement and failed operator receipt remain unchanged, v3 Maps is unlaunched, and neither original v2 history was modified. The final audit found no matching service processes or mounts and opened 754 retained logs exclusively on Windows, confirming their handles were closed. Empty native metadata directories remain as diagnostic evidence.

## Retained attempts

Every attempt has its own frozen source/test manifest, queue receipt and result. No failed attempt was overwritten or reclassified as passed.

| Attempt | Terminal state / exit | Queue ID |
|---|---|---|
| profile001 | succeeded / 0 | `20261009T185746013876Z-c3b4512e` |
| qualification001 | failed / 1 | `20261009T190825436455Z-8d0f4c12` |
| qualification002 | failed / 1 | `20261009T191018964423Z-13a80c20` |
| qualification003 | failed / 1 | `20261009T191215559301Z-0d85aeb2` |
| qualification004 | failed / 1 | `20261009T191526741871Z-2e3d347b` |
| qualification005 | failed / 1 | `20261009T191733586478Z-92a0d755` |
| qualification006 | succeeded / 0 | `20261009T192233631281Z-28c98dba` |
| qualification007 | succeeded / 0 | `20261009T193143835442Z-6e274070` |
| qualification008 | succeeded / 0 | `20261009T193917117931Z-3e9a5116` |
| audit001 | succeeded / 0 | `20261009T192756811095Z-d23eadfc` |
| audit002 | succeeded / 0 | `20261009T194437635586Z-aac9a4cd` |

Qualifications 001–005 remain failed. Their blockers were, respectively: a fault-injector syntax error; a `/proc` stat/cmdline exit race in cleanup inspection; Windows progress-file replacement failure; recurrence of that replacement failure despite delete sharing; and omitted binary bind arguments in the test-only isolation call. Qualification005's 13 startup/retirement cases passed before its canary call failed. Qualification006 and audit001 passed; subsequent source review added explicit directory flushes in qualification007 and caller budget guards in qualification008. These revisions were separately tested, not retrofitted into prior evidence. The exact owner of the Windows rename conflict was not established; append-only progress avoids that operation.

## Remaining limits and stop

No live Robot Codex invocation, complete official experiment, recovery branch, physical deployment, hardware power-loss test or verified device-cold test was performed. Kernel failure, forced termination of the supervising Windows process and arbitrary storage hangs are outside the exercised failure set. Simulator physics, task scoring, robot, sensors, memory templates, control contract, checkpoint/recovery code and content/journal readers are unchanged. Five prospective production files implement this repair; [evidence index](evidence-index.json) binds their hashes.

The original v3 Baseline remains failed and incomplete at 9/21 assignments and 14 normal sessions. Current working-source commissioning certificates are stale for the repaired source. Preserve every original root and frozen receipt. Later explicit direction is required for any recovery policy/lineage, new matched pair, model-based commissioning or launch. This Development session ends with normal repository closeout.
