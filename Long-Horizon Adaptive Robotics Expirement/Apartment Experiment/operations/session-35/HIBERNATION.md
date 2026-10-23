# Verified Maps hibernation — Session 35

Randy requested hibernation after identifying the cup phenomenon as significant. The frozen deferred command was issued at **15:11 PDT on October 8, 2026**. Robot session 22 finished normal docking and closeout, and the official worker exited successfully at **15:13:23 PDT**. The separate full-history audit finished at **15:14:14 PDT**, with all five gates passed.

**Checkpoint 22 is valid. Maps is paused after 22 normal sessions and 2/21 assignments advanced.** There are no abandoned starts, failed native turns or recovery branches. This is an incomplete experiment, not an all-assignment endpoint or a scientific condition result.

| Assignment (one-based) | Task | Robot sessions | Count | State |
| --- | --- | --- | --- | --- |
| 1 | throwing | 1–1 | 1 | Advanced |
| 2 | bedroom | 2–4 | 3 | Advanced |
| 3 | kitchen | 5–22 | 18 | Incomplete at pause |

The completed throwing window is practice, not evidence of throwing mastery. The unfinished kitchen assignment remains exactly where the robot left it; the cup physics concern was not repaired or reset.

## Authentication

- Active root: `D:/Dandelion-Apartment-Experiment/official/apartment-v2/maps`; `maps-lineage.json` still has an empty continuation history.
- Checkpoint: `maps/checkpoints/session-00022`, reason `hibernation`, 101 manifest files.
- Manifest SHA-256: `6a965290aa9abf6bc8a0bf8908f8f920c806d90d8e92e583e664b85c576493be`.
- State SHA-256: `1b06f7700efd1ead871853db3eb907735fd5e645c094110ed33b5de9282894a3`.
- Original queue `20261008T175026684677Z-eb210af9`: succeeded, integer exit 0.
- Independent audit `20261008T221352745327Z-f2b65b3d`: succeeded, integer exit 0.
- Audit gates: queue execution; exact clean terminal boundary; native/inode/sensor/replay/transport evidence; complete started-session accounting; frozen pair and unchanged Baseline.

The audit authenticated world/RNG/task state, exact persistent files and inode namespace, chained events, original sensors and replay, all 22 distinct successful native turns, transport closeout, original frozen source/configuration/schedule identity and the preserved Baseline identity. A separate Windows/Linux process and queue check found no matching apartment runtime or active job. Native, filesystem, controller and viewer retirement passed, `running.lock` is absent and the former viewer port is closed.

Heartbeat `apartment-v2-maps-observations` is **PAUSED**. Its browser tab is closed. The original run, recordings, all eight periodic observations, checkpoint readbacks and cup diagnosis remain preserved. [resume-handoff.json](resume-handoff.json) binds the checkpoint, state, namespace, event/replay boundary, source receipts and terminal verification to their hashes; it records a potential resume command solely for use after new explicit authority.

## Open issue and authority

[CUP_DIAGNOSIS.md](CUP_DIAGNOSIS.md) records approximately two-metre oscillation, a roughly 50-second reversal interval and repeated energy gain during a later floor-only interval. The frozen cup lacks enabled rolling resistance. The evidence implicates a numerical cylinder/floor contact artifact; exact solver causation is unproven. Reconstructed forces are diagnostic and omit the original solver warmstart/actuator history. No repair, coaching, task skip, model-turn retry or new simulation was performed.

**Wait for Randy's next-session instructions.** Do not resume, relaunch, recover, reset, repair or restart monitoring from this handoff. The pause preserves the same anomalous physical state; checkpoint integrity does not resolve physics realism or establish the robot's ability to grasp a moving object. The scientific Baseline-versus-Maps comparison remains deferred.

Full operator evidence: `D:/Dandelion-Apartment-Experiment/official/apartment-v2/operator/maps-session35-001/terminal-hibernated-001/`. Compact receipts in this directory include `hibernation.json`, `runtime-retirement.json`, `monitoring-paused.json`, and `resume-handoff.json`.
