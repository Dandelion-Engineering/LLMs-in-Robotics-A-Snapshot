"""Render the operator handoff from the already verified hibernation receipts."""
from datetime import datetime, timezone
import json
from launch_maps import HERE, CODE, REPO, OP, PAIR
from common import read, sha


def write(path, text):
    path.write_text(text.strip() + '\n', encoding='utf-8', newline='\n')


def main():
    out = OP / 'terminal-hibernated-001'
    result = read(out / 'verified-terminal.json')
    audit = read(out / 'output/result.json')
    retirement = read(out / 'runtime-retirement.json')
    monitor = read(out / 'monitoring-paused.json')
    assert result['passed'] and result['status'] == 'hibernated'
    assert audit['passed'] and len(audit['checks']) == 5 and all(audit['checks'].values())
    assert retirement['passed'] and monitor['status'] == 'PAUSED'
    assert result['normal_closed_sessions'] == 22 and result['assignments_completed'] == 2
    manifest = result['checkpoint_manifest_sha256']
    state = result['checkpoint_state_sha256']
    official = result['official_queue']['id']
    audit_job = result['audit_queue']['id']
    table = '\n'.join(
        f"| {r['position'] + 1} | {r['task']} | {r['first_session']}–{r['last_session']} | {r['sessions']} | "
        + ('Advanced' if r['advancing_session'] else 'Incomplete at pause') + ' |'
        for r in result['assignment_table'])
    write(HERE / 'HIBERNATION.md', f'''
# Verified Maps hibernation — Session 35

Randy requested hibernation after identifying the cup phenomenon as significant. The frozen deferred command was issued at **15:11 PDT on October 8, 2026**. Robot session 22 finished normal docking and closeout, and the official worker exited successfully at **15:13:23 PDT**. The separate full-history audit finished at **15:14:14 PDT**, with all five gates passed.

**Checkpoint 22 is valid. Maps is paused after 22 normal sessions and 2/21 assignments advanced.** There are no abandoned starts, failed native turns or recovery branches. This is an incomplete experiment, not an all-assignment endpoint or a scientific condition result.

| Assignment (one-based) | Task | Robot sessions | Count | State |
| --- | --- | --- | --- | --- |
{table}

The completed throwing window is practice, not evidence of throwing mastery. The unfinished kitchen assignment remains exactly where the robot left it; the cup physics concern was not repaired or reset.

## Authentication

- Active root: `D:/Dandelion-Apartment-Experiment/official/apartment-v2/maps`; `maps-lineage.json` still has an empty continuation history.
- Checkpoint: `maps/checkpoints/session-00022`, reason `hibernation`, 101 manifest files.
- Manifest SHA-256: `{manifest}`.
- State SHA-256: `{state}`.
- Original queue `{official}`: succeeded, integer exit 0.
- Independent audit `{audit_job}`: succeeded, integer exit 0.
- Audit gates: queue execution; exact clean terminal boundary; native/inode/sensor/replay/transport evidence; complete started-session accounting; frozen pair and unchanged Baseline.

The audit authenticated world/RNG/task state, exact persistent files and inode namespace, chained events, original sensors and replay, all 22 distinct successful native turns, transport closeout, original frozen source/configuration/schedule identity and the preserved Baseline identity. A separate Windows/Linux process and queue check found no matching apartment runtime or active job. Native, filesystem, controller and viewer retirement passed, `running.lock` is absent and the former viewer port is closed.

Heartbeat `apartment-v2-maps-observations` is **PAUSED**. Its browser tab is closed. The original run, recordings, all eight periodic observations, checkpoint readbacks and cup diagnosis remain preserved. [resume-handoff.json](resume-handoff.json) binds the checkpoint, state, namespace, event/replay boundary, source receipts and terminal verification to their hashes; it records a potential resume command solely for use after new explicit authority.

## Open issue and authority

[CUP_DIAGNOSIS.md](CUP_DIAGNOSIS.md) records approximately two-metre oscillation, a roughly 50-second reversal interval and repeated energy gain during a later floor-only interval. The frozen cup lacks enabled rolling resistance. The evidence implicates a numerical cylinder/floor contact artifact; exact solver causation is unproven. Reconstructed forces are diagnostic and omit the original solver warmstart/actuator history. No repair, coaching, task skip, model-turn retry or new simulation was performed.

**Wait for Randy's next-session instructions.** Do not resume, relaunch, recover, reset, repair or restart monitoring from this handoff. The pause preserves the same anomalous physical state; checkpoint integrity does not resolve physics realism or establish the robot's ability to grasp a moving object. The scientific Baseline-versus-Maps comparison remains deferred.

Full operator evidence: `D:/Dandelion-Apartment-Experiment/official/apartment-v2/operator/maps-session35-001/terminal-hibernated-001/`. Compact receipts in this directory include `hibernation.json`, `runtime-retirement.json`, `monitoring-paused.json`, and `resume-handoff.json`.
''')
    write(HERE / 'STATUS.md', f'''
# Session 35 — verified Maps hibernation

**Maps is safely hibernated at Randy's request. Development Session 35 is closing; wait for his next-session instructions.** The official worker stopped at **15:13:23 PDT on October 8, 2026**, after session 22's normal docking and closeout. Checkpoint 22 passed independent readback, and the separate full-history audit passed all five gates at 15:14:14 PDT.

There were **22 fresh native sessions, all normally closed; 2/21 assignments advanced; zero abandoned starts, failed native turns or recovery branches**. One throwing-practice window and one bedroom assignment advanced. The first kitchen assignment remains incomplete after sessions 5–22. This is a verified resumable pause, not a completed scientific endpoint. See [HIBERNATION.md](HIBERNATION.md) and [hibernation.json](hibernation.json).

## Stopped state and evidence

- Active root: `D:/Dandelion-Apartment-Experiment/official/apartment-v2/maps` (original lineage; empty history).
- Checkpoint: `maps/checkpoints/session-00022`.
- Manifest SHA-256: `{manifest}`.
- State SHA-256: `{state}`.
- Original launch queue `{official}` succeeded with integer exit 0.
- Independent hibernation audit `{audit_job}` succeeded with integer exit 0 and all five gates.
- Native/filesystem/controller/viewer/transport retired; no running lock, active apartment queue job or matching Windows/Linux runtime remained. The former viewer port is closed.
- Heartbeat `apartment-v2-maps-observations` is **PAUSED**, and the live viewer tab is closed. **There is no next monitoring interval.**

`resume-handoff.json` authenticates checkpoint/state/filesystem-namespace/event/replay and evidence identities. Full receipts are under `D:/Dandelion-Apartment-Experiment/official/apartment-v2/operator/maps-session35-001/terminal-hibernated-001/`. The exact human request and frozen deferred command are in `hibernation-authority.json` and `hibernate-command-receipt.json`. Original source, schedule, recordings and learning were preserved.

## Open physics anomaly

Randy first directed read-only diagnosis with no fixes, then requested hibernation because the cup phenomenon is significant. `CUP_DIAGNOSIS.md` and `cup-diagnosis.json` preserve measured motion, full recorded-sample contact reconstruction and the limitations of the numerical-contact interpretation. No experiment repair, reset, coaching, retry or task skip occurred. Checkpoint validity does not clear the physics realism concern; moving-object grasp capability is unestablished. Preserve the original failed v1 histories and both v2 conditions.

## Authority for later work

**Wait for Randy's new explicit instruction.** This handoff does not authorize resume, another launch, recovery, repair, changed apparatus, fresh learning or renewed monitoring. If he later explicitly requests a clean resume, reauthenticate the frozen inputs, this checkpoint and its exact world/RNG/task/files/inode/event/replay boundary, plus retired runtime and queue state, before submitting the single preserved-state continuation. A new native turn would start from the existing learning and unfinished task. Do not silently clear the cup anomaly. No scientific Baseline-versus-Maps comparison was performed.

## Retained launch and observation record

Randy's October 8, 10:41 PDT project message authorized the initial official Maps launch without requiring his presence. A fresh Baseline endpoint audit passed all five gates; original Maps preparation, frozen inputs/runtime and duplicate absence passed. The original worker was submitted exactly once at 10:50 PDT, and startup passed eleven checks at 10:52 PDT. Eight periodic observations through 14:55 PDT and independently verified intermediate checkpoints are preserved in `periodic-01.json` through `periodic-08.json` and the external observations directory. The cup anomaly remained explicitly open in later records. `monitoring.json` is the historical creation receipt; `monitoring-paused.json` is the current schedule state.
''')
    write(CODE / 'README.md', f'''
# Apartment experiment — operator handoff

**Official apartment-v2 Maps is safely hibernated at Randy's request, after 22 normally closed Robot Codex sessions and 2/21 assignments advanced.** The worker exited 0 at **15:13:23 PDT on October 8, 2026**. Checkpoint 22 is valid; a separate full-history audit passed all five gates with exit 0. Native, filesystem, controller, viewer and transport retired, the live browser tab is closed, and Maps monitoring is PAUSED. **Wait for Randy's next-session instructions; no automatic resume or repair is authorized.**

Current handoff: [Session 35 status](operations/session-35/STATUS.md), [verified hibernation](operations/session-35/HIBERNATION.md), [authenticated resume handoff](operations/session-35/resume-handoff.json), and [HumanReport35](../../agents/Codex/Session%20Summaries/HumanReport35.md).

The **cup contact-physics anomaly remains unresolved**. Original recordings show roughly two-metre back-and-forth motion and repeated energy gain during a floor-only interval. The compiled cup has no enabled rolling resistance; a numerical cylinder/floor contact artifact is implicated, but exact solver causation is unproven. [The diagnosis](operations/session-35/CUP_DIAGNOSIS.md) preserves measurements and limitations. Nothing was fixed or reset. A valid checkpoint preserves the anomaly; it does not establish realistic physics or the robot's ability to grasp a moving object.

## Pair and condition state

Pair root: `D:/Dandelion-Apartment-Experiment/official/apartment-v2`. Use only its `frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment` source for an explicitly authorized official operation. `maps-lineage.json` identifies the original `maps` root with no recovery history.

Maps launched exactly once at 10:50 PDT on October 8 under Randy's 10:41 instruction. Independent Baseline endpoint verification and original pristine Maps readback preceded launch. Queue `{official}` succeeded with integer exit 0 after the later requested hibernation. The separate pause audit `{audit_job}` succeeded with all five gates. Evidence: `operator/maps-session35-001/`.

Maps checkpoint: `maps/checkpoints/session-00022`; manifest SHA-256 `{manifest}`; state SHA-256 `{state}`. All 22 starts closed normally with successful distinct native turns; no abandoned start, failed turn or recovery branch occurred. One throwing-practice window and one bedroom assignment advanced. The first kitchen assignment remains incomplete after 18 normal sessions. This is an incomplete condition history, not an all-21 endpoint or condition comparison.

Baseline previously completed all 21 assignments in 36 normal sessions. Its [verified result](operations/session-34/RESULT.md) and [Session 34 status](operations/session-34/STATUS.md) remain historical condition evidence. Its final checkpoint-36 manifest is `db3541829b8ec8bd78a8138bf4a3b0ab84c7d3e4bf29eb7aaf4f58ce767d7933`. Baseline monitoring is also paused; it is not awaiting resume. No scientific Baseline-versus-Maps comparison has been performed.

The v2 revision remains frozen: gpt-6-astra/max; 360-second bedroom/kitchen windows, 600-second throwing windows, 3,600-second return reserve and 7,200-second native wall limit. [RELIABILITY-REVISION.md](RELIABILITY-REVISION.md), [COMPARISON.md](COMPARISON.md) and [ANALYSIS.md](ANALYSIS.md) retain its protocol. Source manifest: `fb05ea19c8120ce18ae73bb59b02cb33445d2d851ec8e8f6ca52946b348e5e17`; hidden schedule: `6113dc0a9c70c3deaf6249a2faadb9de3b9c312514fa7534d41134eda102b8b4`. Frozen private geometry and task information must not be fed to Robot Codex.

## Later authorized work

Randy will decide what happens next. Do not resume Maps, submit another initial launch, modify frozen physics, retry a turn, reset learning, skip a task, create a recovery branch or restart monitoring from this document. The [authenticated handoff](operations/session-35/resume-handoff.json) includes the exact potential continuation argv solely for use after a new explicit instruction and fresh verification.

If a clean resume is later authorized, reauthenticate checkpoint 22 and the same source/configuration/model/runtime/schedule, persistent files/inodes, world/RNG/task state and event/replay boundary. Confirm no duplicate runtime/job. The unfinished household assignment and learning continue; never substitute a pristine template. The frozen launch mechanism uses `--official --resume`, once, through the shared queue. Read the newly written `viewer.json` after startup rather than reusing the retired port.

For a future running condition, the frozen `run.py hibernate --root <active-root>` requests deferred hibernation. Allow normal docking, model/filesystem closeout, verified checkpoint publication and runtime retirement. Require successful integer queue exit 0 and independent readback before calling it a safe pause. A docked robot, request file or closed browser alone is insufficient.

Genuine infrastructure failures must retain immutable failed evidence and use only the frozen verified-checkpoint recovery rules where authorized. An unsuccessful normal task session or the current physics anomaly is not infrastructure recovery authority. Failed v1 roots `official/apartment-v1` and `official/apartment-v1-restart001` remain unchanged engineering evidence and are ineligible resume sources; see [REPAIR.md](REPAIR.md) and [SECOND-FAILURE-INVESTIGATION.md](SECOND-FAILURE-INVESTIGATION.md).

## Evidence and read-only inspection

Both original condition roots and all recordings remain on D:. `events.jsonl` holds chained physical/task/session events; `sensors/` and `replay/` hold original sensor packets and hashed sampled states. `sessions/` holds native identity/retirement, immutable filesystem journals, content and timing brackets. `checkpoints/` binds docked world/RNG/task state, exact files/inodes, event prefix and replay index. `latest-execution.json` authenticates the terminal execution and component retirement.

The former Maps viewer URL `http://127.0.0.1:57429` is retired. Existing read-only replay can reconstruct original samples without new physics; no replay server is currently running. Use the project venv with `-X utf8 -B` and the shared compute queue for sustained rendering or bulk verification. Preserve simulation and monotonic timing; wall timestamps are descriptive. Do not expose operator/evaluator state or this repository to Robot Codex.

Architecture Map notes `APARTMENT-v2-maps-launch-001`, `APARTMENT-v2-maps-cup-contact-001` and `APARTMENT-v2-maps-hibernation-001` distinguish launch evidence, the physics interpretation and the verified pause. A successful operational audit does not establish physics realism, learning benefit, condition superiority, throwing mastery or real-robot transfer.
''')
    write(REPO / 'agents/Codex/Session Summaries/HumanReport35.md', f'''
# Session 35 — Maps launch, cup diagnosis and verified hibernation

**October 8, 2026. Official apartment-v2 Maps is safely hibernated at Randy's request.** Robot session 22 completed normal docking and closeout; the original worker exited 0 at **15:13:23 PDT**. Checkpoint 22 passed independent readback, and a separate queued audit passed all five gates at **15:14:14 PDT**. Monitoring is paused, the live viewer is closed and all runtime components retired. Randy will send instructions for the next Development session; no resume or repair is authorized now.

The preserved state contains **22 fresh Robot Codex sessions, all normally closed, and 2/21 assignments advanced**, with no abandoned starts, failed native turns or recovery branches. This is an incomplete experiment. The first kitchen assignment remains unfinished, and the cup contact-physics concern remains open.

## Factual accounting

| Assignment (one-based) | Task | Robot sessions | Count | State |
| --- | --- | --- | --- | --- |
{table}

Throwing-window completion records practice time, not throwing mastery. The eighteen normally closed kitchen sessions remain part of the original history. No unfavorable outcome was skipped or rerolled.

## Authorized work and observation

Pulled main first (`ac1b272c` → `642ce3a1`), then followed AgentPrompt and project authority. Randy's October 8, 10:41 PDT project message authorized the official Maps launch and same-session 30-minute monitoring without requiring his presence. A fresh independent Baseline audit passed all five gates and exit 0. Original pristine Maps files, the 266-file frozen source, hidden schedule/configuration/model/runtime, and absence of duplicate runtime/jobs passed prelaunch readback.

Maps was submitted exactly once at 10:50 PDT, queue `{official}`. Startup passed eleven gates covering native identity/isolation, simulator progress, sensors/images, tool activity, protected filesystem journal and original replay. The live viewer was opened for Randy. Eight periodic observations through 14:55 PDT and independent intermediate checkpoint readbacks were retained under `operator/maps-session35-001/observations/`. No infrastructure recovery, coaching, source change, learning reset, task skip or model-turn retry occurred.

## Cup phenomenon

Randy noticed a cup rolling between the same spots and directed diagnosis only, without fixes. Read-only inspection of 5,752 original samples over three simulated minutes confirmed roughly 1.97 m travel between endpoints, reversals around every 50 seconds, and maximum speed 8.8 cm/s. The viewer matched original recorded positions. No robot commands or robot contacts occurred in the retained window. One brief cabinet contact affects one reversal; a later 51-second interval had only floor contact but regained about 0.585 mJ of kinetic energy from near rest, compared with 0.00373 mJ gravitational-potential variation.

The frozen cup has contact dimension 3 and no enabled rolling resistance. Missing resistance explains persistent rolling, not repeated reacceleration. Contact reconstruction and energy behavior implicate a numerical cylinder/floor contact artifact; exact solver causation remains unproven. Reconstructed forces are diagnostic, not original force telemetry. No new simulation or counterfactual run was performed. This does not establish whether Robot Codex can grasp a moving object. [CUP_DIAGNOSIS.md](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-35/CUP_DIAGNOSIS.md) and its hash-bound evidence retain the details.

Randy then called the phenomenon significant and requested hibernation, checkpoint verification and the end of this session. The frozen deferred command succeeded at 15:11 PDT; the healthy native turn was allowed to finish normally. The operator records retain the exact direct-conversation instruction.

## Verification and handoff

Independent audit `{audit_job}` authenticated the exact terminal checkpoint and prefix, all native turns and inode continuity, sensors/replay/transport, full session accounting, frozen pair and unchanged Baseline. Separate Windows/Linux process and queue inspection found no apartment runtime/job; native/filesystem/controller/viewer retirement passed, no running lock remained, and the former viewer port was closed. Heartbeat `apartment-v2-maps-observations` is PAUSED and browser tab 1 was closed.

Checkpoint: `D:/Dandelion-Apartment-Experiment/official/apartment-v2/maps/checkpoints/session-00022`.

- Manifest SHA-256: `{manifest}`.
- State SHA-256: `{state}`.

The full audit and retirement evidence is in `D:/Dandelion-Apartment-Experiment/official/apartment-v2/operator/maps-session35-001/terminal-hibernated-001/`. [HIBERNATION.md](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-35/HIBERNATION.md) and [resume-handoff.json](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-35/resume-handoff.json) preserve the usable pause and reauthentication requirements. Original learned files, world/RNG/task state, hidden schedule and recordings remain intact. The operator README, continuity and Architecture Map now point to this paused state and unresolved physics note.

No scientific Baseline-versus-Maps comparison or secondary scientific outcome analysis was performed. This is one dependent Maps history with an unresolved physics realism issue. A valid checkpoint establishes faithful preservation, not scientific validity or task capability. **Wait for Randy's next-session instructions before any continuation, repair or further experiment.**
''')
    write(REPO / 'agents/Codex/Summary of Only Necessary Context.md', f'''
# Codex continuity — Session 35 verified Maps pause

**Stop and await Randy's next-session instructions.** He called the cup phenomenon significant and explicitly requested Maps hibernation, checkpoint validation and the end of Development Session 35. No resume, new launch, recovery, repair, reset or renewed monitoring is authorized by this handoff.

Official apartment-v2 Maps is safely paused after **22 fresh native sessions, all normally closed, and 2/21 assignments advanced**. One throwing-practice window and one bedroom assignment advanced; the first kitchen assignment remains incomplete after sessions 5–22. Zero abandoned starts, failed native turns or recovery branches. This is not a completed endpoint or a scientific condition result. [HumanReport35](Session%20Summaries/HumanReport35.md), the [operator README](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/README.md), and [Session 35 hibernation handoff](../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-35/HIBERNATION.md) contain the details.

Pair: `D:/Dandelion-Apartment-Experiment/official/apartment-v2`. `maps-lineage.json` identifies the original `<pair>/maps` with empty history. The exact frozen code is `<pair>/frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment`. Initial Maps queue `{official}` succeeded with integer exit 0 at `2026-10-08T22:13:23.423121Z`. Independent full-history audit `{audit_job}` succeeded with exit 0 and all five gates at `2026-10-08T22:14:14.152763Z`. Evidence: `<pair>/operator/maps-session35-001/terminal-hibernated-001/`.

Checkpoint: `maps/checkpoints/session-00022`; manifest SHA-256 `{manifest}`; state SHA-256 `{state}`. `operations/session-35/resume-handoff.json` binds exact world/RNG/task/files/inode/event/replay and terminal evidence identities. It includes a potential preserved-state resume argv only for a later explicitly authorized and reverified continuation. No runtime or active apartment queue job remained in independent Windows/Linux inspection. Native/filesystem/controller/viewer/transport retired; no running lock; old viewer port closed; browser tab closed. Heartbeat `apartment-v2-maps-observations` is PAUSED in this thread `01a11c9f-30b1-7b62-8892-bff6a2415a14`.

**Open physics anomaly:** Randy first requested read-only diagnosis and no fixes, then hibernation. Recorded cup motion travels approximately 1.97 m between endpoints, reverses about every 50 seconds, and regains kinetic energy in a later floor-only interval without robot commands/contact. The compiled cup lacks rolling resistance. Numerical cylinder/floor contact dynamics are implicated; exact solver causation is unproven. See `operations/session-35/CUP_DIAGNOSIS.md`, `cup-diagnosis.json`, and external `operator/maps-session35-001/cup-diagnosis-001/`. Preserve the evidence and the anomalous state. A checkpoint pass does not clear realism or establish moving-object grasp capability. No new physics steps, fix, coaching, retry, task skip or reset was performed.

Maps launched once at 10:50 PDT on October 8 under Randy's 10:41 project instruction after fresh independent Baseline endpoint and pristine Maps verification. Startup passed eleven gates. Eight periodic observations and checkpoint readbacks preceded the requested pause. Architecture Map notes: `APARTMENT-v2-maps-launch-001`, `APARTMENT-v2-maps-cup-contact-001`, `APARTMENT-v2-maps-hibernation-001`. No scientific Baseline-versus-Maps comparison has been performed.

Baseline remains complete at all 21 assignments/36 normal sessions; its checkpoint-36 manifest is `db3541829b8ec8bd78a8138bf4a3b0ab84c7d3e4bf29eb7aaf4f58ce767d7933`, and Session 35 reverified unchanged identity. Use HumanReport34 for historical detail. Both earlier failed v1 roots remain immutable excluded engineering evidence and are not resume sources.

Frozen v2 source manifest: `fb05ea19c8120ce18ae73bb59b02cb33445d2d851ec8e8f6ca52946b348e5e17`; certificate: `0bcf95559d1693c7cb7fd0f34dcbf150f4bd38c53f6871daf622a5450b99ba7b`; hidden schedule: `6113dc0a9c70c3deaf6249a2faadb9de3b9c312514fa7534d41134eda102b8b4`. gpt-6-astra/max, work windows 360/600 seconds, return reserve 3,600 and native wall limit 7,200 remain frozen. A later apparatus change requires a newly authorized scientific/engineering disposition; do not retrofit preserved histories.

Codex is the only standing AI agent. Use project venv `-X utf8 -B`, supported chat/work/Architecture Map tools, and the shared queue for heavy work. Session 35 initially pulled main `ac1b272c` to `642ce3a1`. Its launch/monitoring conversation is concluded with a summary. All session claims are closed at closeout. Read the human inbox and new explicit instructions before choosing later work.
''')
    report_index = REPO / 'agents/Codex/README.md'
    text = report_index.read_text(encoding='utf-8')
    old = '- [Session34 verified Baseline endpoint](Session%20Summaries/HumanReport34.md) — authenticated checkpoint resume, continued observation and all 21 assignments in 36 normal sessions; monitoring paused, Maps pristine and unlaunched.'
    assert text.count(old) == 1
    new = '- [Session35 verified Maps hibernation](Session%20Summaries/HumanReport35.md) — official launch and observation, unresolved cup contact-physics diagnosis, and verified pause after 22 normal sessions/2 assignments; await Randy\'s instructions.\n- [Session34 verified Baseline endpoint](Session%20Summaries/HumanReport34.md) — historical Baseline completion of all 21 assignments in 36 normal sessions.'
    write(report_index, text.replace(old, new))
    summary_index = REPO / 'agents/Codex/Session Summaries/README.md'
    text = summary_index.read_text(encoding='utf-8')
    start = text.index('Current report:')
    end = text.index('\n\n', start)
    replacement = 'Current report: [HumanReport35](HumanReport35.md), the official Maps launch, cup contact-physics diagnosis and verified human-requested hibernation after 22 normal sessions and 2/21 assignments. Monitoring is paused; await Randy\'s next-session instructions. [HumanReport34](HumanReport34.md) records the completed Baseline endpoint; [HumanReport33](HumanReport33.md) records v2 commissioning and its earlier pause. Older reports remain historical evidence.'
    write(summary_index, text[:start] + replacement + text[end:])
    def ref(path, label):
        return dict(label=label, uri=str(path), sha256=sha(path), state='available', access='operator', locator=None)
    note = dict(schema_version='architecture-map-1.0', id='APARTMENT-v2-maps-hibernation-001',
        recorded_at=datetime.now(timezone.utc).isoformat(), author='Codex',
        tags=['apartment', 'maps', 'official', 'hibernation', 'verified-checkpoint', 'incomplete-endpoint'],
        details=dict(assignments_completed=2, assignments_total=21, normal_sessions=22, abandoned_starts=0,
            checkpoint_session=22, endpoint_session_count=None, monitor_status='PAUSED', comparison_performed=False,
            unresolved_physics_note='APARTMENT-v2-maps-cup-contact-001'),
        target_ids=['APARTMENT-v2-maps', 'APARTMENT-v2-maps-cup-contact-001'], claim_type='observation',
        body='Randy called the cup phenomenon significant and requested hibernation, checkpoint verification and the end of Development Session 35. The frozen deferred command was issued at 15:11 PDT on October 8. Session 22 docked and closed normally; the original worker exited 0 at 15:13:23 PDT. Independent full-history audit exited 0 and passed all five gates, authenticating checkpoint 22, exact clean boundary, native/inode/sensor/replay/transport history, all 22 normal starts/closures, frozen pair and unchanged Baseline. Two of 21 assignments advanced; the first kitchen assignment remains incomplete. No abandoned starts, failed native turns or recovery branches occurred. Separate Windows/Linux process and queue checks found complete runtime retirement; the viewer port and browser tab closed. Monitoring is paused. Original recordings, learning and the unresolved cup physics state remain preserved. This is a resumable incomplete pause, not a scientific endpoint. No repair or condition comparison occurred; later work requires new explicit human instructions.',
        supersedes_note_id=None, evidence=[ref(OP/'hibernation-authority.json','Exact human hibernation instruction'),
            ref(out/'verified-terminal.json','Verified factual pause accounting'), ref(out/'output/result.json','Independent full-history audit'),
            ref(out/'official-queue.json','Official queue exit 0'), ref(out/'audit-terminal-queue.json','Audit queue exit 0'),
            ref(out/'runtime-retirement.json','Independent process and runtime retirement'),
            ref(out/'monitoring-paused.json','Paused monitoring and closed browser'),ref(out/'resume-handoff.json','Authenticated future handoff')])
    with (HERE / 'APARTMENT-v2-maps-hibernation-001.json').open('x', encoding='utf-8') as stream:
        json.dump(note, stream, sort_keys=True, indent=2)
    print(json.dumps(dict(written=['HIBERNATION.md', 'STATUS.md', 'operator README', 'HumanReport35.md', 'Codex continuity', 'two navigation indexes', note['id']], checkpoint_manifest_sha256=manifest)))


if __name__ == '__main__':
    main()
