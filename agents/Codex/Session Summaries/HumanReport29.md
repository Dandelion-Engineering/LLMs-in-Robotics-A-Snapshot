# Codex session 29 — official apartment baseline launched

Randy explicitly said he was present and ready for launch. The official baseline was submitted once from the frozen D-drive repository at **21:58 PDT on October 6, 2026**. It was running at handoff; Maps remained pristine and unlaunched. Development Codex ends while the independent queue worker continues.

- Queue job: `20261007T045828061579Z-37c81eac`.
- Run/revision: `APARTMENT-v1-baseline` / `APARTMENT-v1-frozen`.
- Live observer: `http://127.0.0.1:51101` (opened visibly and retained in Codex). Reopen from `baseline/viewer.json` after a future restart because its port may change.
- [Operator launch, hibernate, resume and replay commands](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/README.md).
- [Exact launch authority and command](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-29/launch-authorization.json), [queue receipt](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-29/queue-submission.json), and [startup verification](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-29/startup-verification.json).

## What was verified

Pulled `main` (already current), read current authority/continuity, and checked claims/inbox. Before submission, the frozen source, certificate, installed runtime and calibrated configuration passed the read-only official launch gate. Both actual starting filesystem inventories were pristine, both schedules matched, neither condition had sessions, and no baseline process lock existed. Available capacity was C: 533.85 GiB / D: 521.81 GiB.

The native session started at `2026-10-07T04:58:47.237286+00:00`, with effective `gpt-6-astra` / `max` and existing ChatGPT authentication. Both namespace canaries qualified with integer exit zero. Native turn/tool events, sensors and physical commands were recorded. At the timestamped startup observation, session 1 was active at simulation time 168.024 seconds; the physical log contained eight sensor captures and seven admitted commands, the protected filesystem journal had 204 complete records, and replay contained 42 files. These are startup observations, not terminal scores.

The viewer visibly rendered the apartment, robot, battery, current assignment and journal activity. Simulation time advanced from the recorded session start. The observer was left open for Randy. Original event/replay/sensor/native/filesystem evidence remains in the official baseline root on D:.

## Boundaries and next action

Queue state was `running`, with null terminal exit. No completed-run outcome or checkpoint was claimed. A checkpoint is expected only after normal docking, filesystem closeout, native retirement and verification. Closing the viewer does not request hibernation or stop the experiment.

Use the handoff's exact hibernation command when desired. After a clean hibernation, authenticate queue `succeeded` with integer exit 0, the passed execution result, absent running lock and verified latest checkpoint before resuming with `--resume`. Preserve any abnormal stop and investigate; no automatic retry, schedule reset, task skip or frozen-source change is authorized by this launch. Maps stays unlaunched until the verified 21-assignment baseline endpoint.

Appended Architecture Map event `APARTMENT-v1-baseline-launch-001`; immutable prepared manifests and historical results were preserved. Map rebuild/validation passed. Only operator records, current handoff and Codex continuity changed; the frozen apparatus and robot starting templates were not edited.
