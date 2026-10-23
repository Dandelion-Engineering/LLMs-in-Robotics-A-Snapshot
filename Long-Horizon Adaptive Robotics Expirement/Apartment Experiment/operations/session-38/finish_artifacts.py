"""Build the compact handoff only after final queue and independent-audit success."""
import json
from pathlib import Path
import subprocess
import sys
from attempts import HERE,APP,REPO,ROOT,read,sha,save,ref

def write(path,text):
    Path(path).write_text(text,encoding='utf-8',newline='\n')

def main():
    for name in ('qualification008','audit002'):
        q=read(HERE/(name+'-terminal.json'))
        assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
        assert read(ROOT/name/'output/result.json')['passed'] is True
    profile=read(ROOT/'profile001/output/result.json')
    qualification=read(ROOT/'qualification008/output/result.json')
    audit=read(ROOT/'audit002/output/result.json')
    protected=audit['checks']['official_preservation_checkpoint_and_guard']
    runtime=audit['checks']['all_runtime_retired']
    timings=[]
    for old in profile['cases']:
        name=old['size']+'-'+old['cache'];new=next(r for r in qualification['cases'] if r['name']==name)
        workspace=ROOT/'qualification008/output'/name/'workspace'
        prepared=read(workspace/'prepare-readiness.json');ready=read(workspace/'readiness.json')
        timings.append(dict(size=old['size'],cache=old['cache'],files=old['shape']['files'],logical_bytes=old['shape']['bytes'],
            before_windows_startup_s=old['preparation_s']+old['launch_to_ready_s'],before_linux_restore_s=old['profile']['restore_elapsed_ns']/1e9,
            after_windows_startup_s=new['startup_s'],after_windows_preparation_s=prepared['elapsed_s'],after_linux_readiness_s=ready['elapsed_s'],
            before_evidence=ref('Original profile measurement',ROOT/'profile001/output'/name/'measurement.json'),
            after_evidence=ref('Final qualification case',ROOT/'qualification008/output'/name/'result.json')))
    save(HERE/'timings.json',dict(measurements=timings,
        definitions='End-to-end columns use Windows perf_counter. Before adds disjoint preparation and launch-to-mount intervals; after includes constructor, native preparation and the stronger responsive-readiness fence. Subphase Linux times use Linux monotonic clocks; do not cross-add them to Windows subphases.',
        limitations='Two sequential cache variants per size; DONTNEED is advisory, not verified device cold. Counts and byte volumes co-vary. The doubled fixture clones content with a changed suffix, retaining some chunk sharing. No statistical or worst-case speedup claim.'))
    names=['profile001']+['qualification'+str(n).zfill(3) for n in range(1,9)]+['audit001','audit002']
    attempts=[]
    for name in names:
        q=read(HERE/(name+'-terminal.json'));manifest=ROOT/name/'manifest.json';result=ROOT/name/'output/result.json'
        attempts.append(dict(name=name,queue_id=q['id'],state=q['state'],exit_status=q['exit_status'],
            manifest=ref('Exact source/test manifest',manifest),result=ref('Retained result',result),
            terminal=ref('Queue terminal receipt',HERE/(name+'-terminal.json'))))
    sources={name:sha(APP/name) for name in ('native_runtime.py','journal_service.py','run.py','workspace_lifecycle.py','workspace_restore.py')}
    for name,key in sources.items():assert key==sha(ROOT/'qualification008/source'/name)
    save(HERE/'evidence-index.json',dict(authority=ref('Randy authority',HERE/'authority-original.md'),attempts=attempts,
        final_source=sources,final_qualification='qualification008',independent_audit='audit002',official_model_calls=0,model_calls=0,
        preserved_files=sum(protected[k]['files'] for k in ('apartment-v2','apartment-v3')),preserved_bytes=sum(protected[k]['bytes'] for k in ('apartment-v2','apartment-v3')),
        checkpoint14_manifest_sha256=protected['checkpoint14']['manifest_sha256'],runtime=runtime))
    table='\n'.join(f"| {r['size']} | {r['cache']} | {r['files']} | {r['logical_bytes']/1e6:.2f} | {r['before_windows_startup_s']:.2f} | {r['after_windows_startup_s']:.2f} |" for r in timings)
    ledger='\n'.join(f"| {r['name']} | {r['state']} / {r['exit_status']} | `{r['queue_id']}` |" for r in attempts)
    cp=[r['after_windows_startup_s'] for r in timings if r['size']=='checkpoint14']
    decision=f'''# Session 38 engineering result

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
{table}

Checkpoint-sized repaired startup was {min(cp):.2f}–{max(cp):.2f} seconds. The larger state still takes roughly half a minute: this is a modest performance change, not a broad speedup claim. The important reliability result is accepting slow verified progress within a hard admission budget while rejecting stalls, child exits and expired budgets.

Cold treatment is only Linux `DONTNEED` advice on the isolated input copies; physical device/Windows caches were not reset. File count and byte volume co-vary, and the doubled state retains some content-chunk sharing. This is not a factorial attribution, statistical performance study or worst-case bound. [Timings](timings.json) retain both clock domains, exact definitions and source references.

## Qualification and independent verification

Final qualification passed 14 real startup/retirement cases: six size/cache starts, slow progress beyond 20 seconds, an actual hang, false heartbeat, early child exit, partial initialization failure, adopted-directory flush failure, absolute expiry, and the unmount/journal-close race. Four additional failures cover corrupt source content, process creation, admission-receipt writing after mount, and a forced helper-setup overrun. The original failure reproductions, deadline state checks and all six existing isolation-canary gates also passed.

The separately implemented audit passed all seven groups: source/environment; queue and failed-attempt accounting; old-reader matrix replay; namespace/open handles; adversarial failures; actual resource retirement; and official preservation/checkpoint/recovery guard. It additionally tested hard links, symlinks, mode bits, empty directories, writes after restoration, sparse writes/truncation, open-handle refusal, corruption after preparation, a pre-owner bootstrap hang and a poisoned journal. It used the unchanged pre-repair journal reader. This is independent computational readback, not an external human or second-model review.

All **75,407 official v2/v3 files, 5,284,557,531 bytes**, matched the pre-work inventory exactly. Checkpoint 14 and its completed prefix passed readback; its manifest remains `5314dc656b39dd4254325a46c94bc56c028f5f526004f85ac983e1547ec44015`. The original false retirement and failed operator receipt remain unchanged, v3 Maps is unlaunched, and neither original v2 history was modified. The final audit found no matching service processes or mounts and opened {runtime['exclusive_log_opens']} retained logs exclusively on Windows, confirming their handles were closed. Empty native metadata directories remain as diagnostic evidence.

## Retained attempts

Every attempt has its own frozen source/test manifest, queue receipt and result. No failed attempt was overwritten or reclassified as passed.

| Attempt | Terminal state / exit | Queue ID |
|---|---|---|
{ledger}

Qualifications 001–005 remain failed. Their blockers were, respectively: a fault-injector syntax error; a `/proc` stat/cmdline exit race in cleanup inspection; Windows progress-file replacement failure; recurrence of that replacement failure despite delete sharing; and omitted binary bind arguments in the test-only isolation call. Qualification005's 13 startup/retirement cases passed before its canary call failed. Qualification006 and audit001 passed; subsequent source review added explicit directory flushes in qualification007 and caller budget guards in qualification008. These revisions were separately tested, not retrofitted into prior evidence. The exact owner of the Windows rename conflict was not established; append-only progress avoids that operation.

## Remaining limits and stop

No live Robot Codex invocation, complete official experiment, recovery branch, physical deployment, hardware power-loss test or verified device-cold test was performed. Kernel failure, forced termination of the supervising Windows process and arbitrary storage hangs are outside the exercised failure set. Simulator physics, task scoring, robot, sensors, memory templates, control contract, checkpoint/recovery code and content/journal readers are unchanged. Five prospective production files implement this repair; [evidence index](evidence-index.json) binds their hashes.

The original v3 Baseline remains failed and incomplete at 9/21 assignments and 14 normal sessions. Current working-source commissioning certificates are stale for the repaired source. Preserve every original root and frozen receipt. Later explicit direction is required for any recovery policy/lineage, new matched pair, model-based commissioning or launch. This Development session ends with normal repository closeout.
'''
    write(HERE/'DECISION.md',decision)
    write(HERE/'STATUS.md',f'''# Session 38 handoff

Workspace infrastructure repair passed final qualification008 and independent audit002. Start with [the decision](DECISION.md), [recovery options](RECOVERY-OPTIONS.md), [source review](SOURCE-REVIEW.md) and [evidence index](evidence-index.json).

No experiment or monitor was started. Original v3 Baseline remains failed at checkpoint 14, 9/21 assignments and 14 normal sessions; its false retirement receipt and the failed operator follow-up are immutable. All 75,407 official v2/v3 files were rehashed unchanged. Maps v3 remains pristine. Earlier failed engineering attempts remain failed.

Evidence root: `D:/Dandelion-Apartment-Experiment/engineering/workspace-session38`. Final qualification: `{read(HERE/'qualification008-terminal.json')['id']}`. Final independent audit: `{read(HERE/'audit002-terminal.json')['id']}`. Both succeeded with integer exit 0. Code is an engineering candidate, not an officially commissioned release.

Recommended next decision: authorize a fresh pristine matched pair and full commissioning of a newly frozen release. Recovery from checkpoint 14 requires a separately qualified policy/source transition, a narrow explicit learning-continuation authorization and a scientific lineage decision; the original guard is unchanged and must not be bypassed. No branch or pair was created. Do not automatically rerun the once-only attempt scripts or restart observation automations.
''')
    write(REPO/'agents/Codex/Session Summaries/HumanReport38.md',f'''# Session 38 — Workspace startup and cleanup repair

**Completed the authorized isolated engineering repair and independent qualification; no experiment was launched.** Pulled `main` to `7e444c5d`, read AgentPrompt/project authority and carried out Randy's October 9 10:04 PDT message.

The full result, timings, retained failures, code review and recommendation are in the [decision report](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-38/DECISION.md). [Recovery options](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-38/RECOVERY-OPTIONS.md) recommends a fresh pristine pair under later authority and full commissioning.

Reproduced a checkpoint-size restore exceeding the old deadline, the original constructor orphan, and the unmount/final-journal race. Added measurable progress with 20-second stall/120-second total admission limits, native Windows preparation with unchanged content format and Linux verification/directory durability, early process ownership, constructor/caller cleanup and a retirement path that never appends after finalization. Receipt-write and helper-deadline failures are covered.

Final qualification008 passed 14 startup/retirement cases, four construction/admission failures, original-failure reproductions, deadline checks and six isolation-canary gates. Audit002 passed all seven separately implemented groups, including adversarial namespace/cleanup and unchanged-reader verification. Five earlier qualifications remain failed with exact receipts. Qualification006/audit001 and qualification007 remain separately recorded earlier passes.

Repaired checkpoint-sized startup measured {min(cp):.2f}–{max(cp):.2f} seconds versus 19.91–21.46 seconds in the original host-clock measurements; the doubled state still took roughly half a minute. This is bounded descriptive evidence, not a statistical or worst-case speedup claim.

All 75,407 official v2/v3 files remained byte-identical. Checkpoint 14 and its prefix are intact; original `all_retired=false` and failed operator follow-up are unchanged. Final process/mount/log-handle checks passed. V3 Maps remains pristine/unlaunched. No model call, recovery, condition launch/comparison or monitoring restart occurred. Physics, scoring, robot, sensors, templates, control contract and recovery/checkpoint logic are unchanged.

Evidence and exact queue/source identities: [index](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-38/evidence-index.json). Close the five work claims, post/conclude the human subject, update continuity, check the final inbox and run exact-path closeout. A successful closeout ends this session.
''')
    write(REPO/'agents/Codex/Summary of Only Necessary Context.md','''# Codex continuity — after Session 38

**Workspace startup/cleanup repair is independently qualified; no official experiment is active or newly authorized.** Read [HumanReport38](Session%20Summaries/HumanReport38.md) and the [engineering decision](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-38/DECISION.md). Final qualification008 and audit002 succeeded with integer exit 0. Five prior qualifications remain failed; every frozen attempt is under `D:/Dandelion-Apartment-Experiment/engineering/workspace-session38` and indexed in the decision's evidence index.

The repair adds progress-aware readiness (20-second no-progress / 120-second total admission budget), native Windows content preparation with unchanged format and Linux hash/directory-flush verification, early process ownership, construction-safe cleanup, and retirement without a post-unmount journal append. Qualification covers 14 startup/retirement cases plus four admission/construction failures; the separate audit checks raw evidence, namespace semantics, corruption, actual retirement and official preservation. No model call was made. Current working-source commissioning certificates are stale; this is an engineering candidate, not an official release.

Randy's October 9 10:04 PDT instruction authorized this focused engineering session only. It ends at the decision-ready handoff. Recommend a **fresh pristine matched pair after later explicit authority and full commissioning**. Checkpoint-14 recovery would need a separately qualified source-migration/recovery policy and explicit scientific lineage/learning-continuation decision. Do not bypass the frozen guard, create any branch/pair, call Robot Codex, resume/start Baseline, launch Maps or restart monitoring on this authority. Check the fresh human inbox for later direction. Read [recovery options](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-38/RECOVERY-OPTIONS.md).

Official v3 root: `D:/Dandelion-Apartment-Experiment/official/apartment-v3`. Baseline remains failed/incomplete after 9/21 assignments and 14 normal sessions; session 15 failed before native/model execution. Checkpoint 14 manifest SHA-256 remains `5314dc656b39dd4254325a46c94bc56c028f5f526004f85ac983e1547ec44015`. The original execution's `all_retired=false` and failed operator follow-up remain immutable. Later independent retirement proof does not turn them into normal hibernation. The unchanged frozen recovery guard rejects that original flag. Maps v3 is pristine/unlaunched. Session37's [terminal decision](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-37/DECISION.md) contains historical operational details.

All 75,407 files across complete official v2/v3 roots were independently rehashed unchanged. Original v2 Baseline completed 21/21 at checkpoint 36; Maps is hibernated at checkpoint 22 with 2/21. Neither may be altered or resumed. Published v2 filesystems are operator-only; do not seed future guests with preserved learning. All monitoring remains paused by the prior instruction; this session started no automation.

Codex is the only standing agent. Use the project venv with `-X utf8 -B`, supported chat/work/map tools and shared queue. Attempt preparation scripts are once-only and must not be rerun against existing roots. Five Session38 claims close at normal closeout. Successful `closeout.py` is the final project action.
''')
    print(json.dumps(dict(report=str(HERE/'DECISION.md'),measurements=len(timings),attempts=len(attempts),source=sources)))

if __name__=='__main__':main()
