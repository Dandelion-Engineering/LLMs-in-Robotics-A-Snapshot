# Session 35 — Maps launch, cup diagnosis and verified hibernation

**October 8, 2026. Official apartment-v2 Maps is safely hibernated at Randy's request.** Robot session 22 completed normal docking and closeout; the original worker exited 0 at **15:13:23 PDT**. Checkpoint 22 passed independent readback, and a separate queued audit passed all five gates at **15:14:14 PDT**. Monitoring is paused, the live viewer is closed and all runtime components retired. Randy will send instructions for the next Development session; no resume or repair is authorized now.

The preserved state contains **22 fresh Robot Codex sessions, all normally closed, and 2/21 assignments advanced**, with no abandoned starts, failed native turns or recovery branches. This is an incomplete experiment. The first kitchen assignment remains unfinished, and the cup contact-physics concern remains open.

## Factual accounting

| Assignment (one-based) | Task | Robot sessions | Count | State |
| --- | --- | --- | --- | --- |
| 1 | throwing | 1–1 | 1 | Advanced |
| 2 | bedroom | 2–4 | 3 | Advanced |
| 3 | kitchen | 5–22 | 18 | Incomplete at pause |

Throwing-window completion records practice time, not throwing mastery. The eighteen normally closed kitchen sessions remain part of the original history. No unfavorable outcome was skipped or rerolled.

## Authorized work and observation

Pulled main first (`ac1b272c` → `642ce3a1`), then followed AgentPrompt and project authority. Randy's October 8, 10:41 PDT project message authorized the official Maps launch and same-session 30-minute monitoring without requiring his presence. A fresh independent Baseline audit passed all five gates and exit 0. Original pristine Maps files, the 266-file frozen source, hidden schedule/configuration/model/runtime, and absence of duplicate runtime/jobs passed prelaunch readback.

Maps was submitted exactly once at 10:50 PDT, queue `20261008T175026684677Z-eb210af9`. Startup passed eleven gates covering native identity/isolation, simulator progress, sensors/images, tool activity, protected filesystem journal and original replay. The live viewer was opened for Randy. Eight periodic observations through 14:55 PDT and independent intermediate checkpoint readbacks were retained under `operator/maps-session35-001/observations/`. No infrastructure recovery, coaching, source change, learning reset, task skip or model-turn retry occurred.

## Cup phenomenon

Randy noticed a cup rolling between the same spots and directed diagnosis only, without fixes. Read-only inspection of 5,752 original samples over three simulated minutes confirmed roughly 1.97 m travel between endpoints, reversals around every 50 seconds, and maximum speed 8.8 cm/s. The viewer matched original recorded positions. No robot commands or robot contacts occurred in the retained window. One brief cabinet contact affects one reversal; a later 51-second interval had only floor contact but regained about 0.585 mJ of kinetic energy from near rest, compared with 0.00373 mJ gravitational-potential variation.

The frozen cup has contact dimension 3 and no enabled rolling resistance. Missing resistance explains persistent rolling, not repeated reacceleration. Contact reconstruction and energy behavior implicate a numerical cylinder/floor contact artifact; exact solver causation remains unproven. Reconstructed forces are diagnostic, not original force telemetry. No new simulation or counterfactual run was performed. This does not establish whether Robot Codex can grasp a moving object. [CUP_DIAGNOSIS.md](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-35/CUP_DIAGNOSIS.md) and its hash-bound evidence retain the details.

Randy then called the phenomenon significant and requested hibernation, checkpoint verification and the end of this session. The frozen deferred command succeeded at 15:11 PDT; the healthy native turn was allowed to finish normally. The operator records retain the exact direct-conversation instruction.

## Verification and handoff

Independent audit `20261008T221352745327Z-f2b65b3d` authenticated the exact terminal checkpoint and prefix, all native turns and inode continuity, sensors/replay/transport, full session accounting, frozen pair and unchanged Baseline. Separate Windows/Linux process and queue inspection found no apartment runtime/job; native/filesystem/controller/viewer retirement passed, no running lock remained, and the former viewer port was closed. Heartbeat `apartment-v2-maps-observations` is PAUSED and browser tab 1 was closed.

Checkpoint: `D:/Dandelion-Apartment-Experiment/official/apartment-v2/maps/checkpoints/session-00022`.

- Manifest SHA-256: `6a965290aa9abf6bc8a0bf8908f8f920c806d90d8e92e583e664b85c576493be`.
- State SHA-256: `1b06f7700efd1ead871853db3eb907735fd5e645c094110ed33b5de9282894a3`.

The full audit and retirement evidence is in `D:/Dandelion-Apartment-Experiment/official/apartment-v2/operator/maps-session35-001/terminal-hibernated-001/`. [HIBERNATION.md](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-35/HIBERNATION.md) and [resume-handoff.json](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-35/resume-handoff.json) preserve the usable pause and reauthentication requirements. Original learned files, world/RNG/task state, hidden schedule and recordings remain intact. The operator README, continuity and Architecture Map now point to this paused state and unresolved physics note.

No scientific Baseline-versus-Maps comparison or secondary scientific outcome analysis was performed. This is one dependent Maps history with an unresolved physics realism issue. A valid checkpoint establishes faithful preservation, not scientific validity or task capability. **Wait for Randy's next-session instructions before any continuation, repair or further experiment.**
