# Session 62 — Stale viewer and Maps closeout failure

The viewer retained session 2, but **the scientific run is now stopped**. Queue `20261010T163419885117Z-d580bba0` failed at **10:42:47 PDT on October 10, 2026**, during session 6 filesystem closeout. The native model finished normally and the robot docked. The frozen validator rejected a main report plus a separate Markdown correction addendum because it requires exactly one new report. Shutdown retired the live viewer server too.

Randy asked in this thread to investigate the stale display and `TypeError: Failed to fetch`. This Development session pulled main (already current), followed AgentPrompt/Codex-only instructions, checked continuity/inbox/claims, read the Session 59 storage route/protocol and retained an immutable observation. No scientific source, robot filesystem, setting, schedule or recording was changed.

## Viewer diagnosis

The existing tab at `http://127.0.0.1:59465/` visibly showed `official · maps · session 2`, `active · 100.0%` and `TypeError: Failed to fetch`. It was visible at inspection. Screenshot and accessibility text are retained in `Local Experiment Data/apartment-v4-maps/operator/session-62/`, referenced by [viewer-diagnosis.json](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-62/viewer-diagnosis.json).

The runner/native Windows owners and Linux run processes/mounts are retired; port 59465 refuses connections. Frozen `run.py` creates the viewer inside the runner and shuts it down during final cleanup. This explains the current fetch failure. Refresh cannot restore an exited server.

The frontend's error handler changes only the error text. It leaves the old scene, session and active/battery label visible without a freshness timestamp or disconnected status. Polling runs only while the document is visible, reschedules after ordinary fetch rejection, and has no explicit fetch timeout. An error therefore does not itself permanently cancel the loop, but the retained display can look live after disconnection.

**The earlier update gap remains unknown.** No retained browser request history establishes its onset. Hidden-tab polling suspension is plausible, not proven. Session 61 really observed session 6 through HTTP `/frame`, native ownership and events at 10:36–10:37; it did not recheck the rendered user tab. The handoff did not make that distinction clear enough. This investigation preserved the tab without reload or restart.

## Exact failure and retained progress

Read-only evaluation of the unchanged validator against the original initial/final exports reproduces `ValueError('Exactly one substantive new session report required')`:

| New file under `SessionReports/` | Bytes | Role |
|---|---:|---|
| `2026-10-10-session-006.md` | 13,539 | Main report |
| `2026-10-10-session-006-addendum.md` | 890 | Correction of two overly precise warning timestamps |

The addendum explicitly belongs to session 006. The template requires one report per invocation and makes written reports immutable; the validator counts every new top-level Markdown file as a report. Historical reports were unchanged and continuity was updated. No report was deleted, renamed, merged or rewritten to make this failed attempt pass.

Session 6 recorded a kitchen success latch (event 1400) and completed docking (event 1441; simulation time 3822.512 s). Its native turn and filesystem service closed normally, but **no checkpoint 6 was published**. Last accepted checkpoint **5** retains **2/21 closed advancements**: one timed throwing window and bedroom session 4. Normal nonadvancing sessions 2, 3 and 5 remain preserved. The kitchen latch is not a third closed advancement; there is no completed endpoint or new physical-scoring conclusion.

## Verification and disposition

Read-only audit `20261010T181100216252Z-42047900` succeeded with integer exit 0 and all nine diagnostic gates passed. The scientific queue remains failed/exit 1. Audit success does not alter that result.

- Checkpoint 5 content/manifest/event/replay prefix passed the Session 59 helper's `--checkpoint` readback. All 1,441 controller events also passed full chain and monotonic-order verification.
- All six native journals passed independent chain/content verification: 421, 358, 408, 386, 345 and 335 records. Distinct native threads, normal completion/cleanup receipts, exact Windows owner retirement and actual Linux process/mount absence passed.
- All 174 sensor images and 1,025 replay chunks match recorded hashes. All 266 frozen sources and run identity match. Original pristine D: Maps and Baseline endpoint anchors pass. Full Baseline inventory, full native transport and physical rescoring were not repeated.
- C: retained **515.730751 GiB**, D: **133.818359 GiB**; both full 50 GiB reserves pass. Storage shortage did not cause this failure.
- The Maps monitor is **PAUSED**, as required by the failed-runtime protocol. Only status/update timestamp changed; all four older monitors remain byte-unchanged and paused. No further runtime termination was needed.

The sole launched root remains `Local Experiment Data/apartment-v4-maps/run` under this project. Failed session-6 exports and raw evidence remain intact. D: Maps remains the pristine duplicate and must never be launched. The observation helper's generic `passed: true` covers preservation/reserve/checkpoint checks; that same observation explicitly records a failed queue and offline viewer.

Evidence: [observation-summary.json](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-62/observation-summary.json), [scientific terminal receipt](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-62/official-terminal.json), and [audit terminal receipt](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-62/audit-terminal.json). These bind the raw audit, checkpoint, original failure, browser capture and pause evidence. Harmless operator read/patch errors are recorded separately from the scientific failure.

Map result `APARTMENT-v4-maps-closeout-failure-result` records failed execution and an invalid/incomplete full-condition endpoint, with task outcome not assessed. Note `APARTMENT-v4-maps-viewer-and-closeout-failure-session62` preserves the viewer diagnosis and uncertainty. Earlier dated observations remain unchanged.

A future qualified viewer revision should visibly mark stale/disconnected data, show last successful update time and bound requests. A separate prospective lifecycle decision should reconcile immutable corrections with the single-report gate. These are proposals, not changes to the frozen attempt. **No retry, replacement, recovery, old-root launch or scientific comparison is authorized.** Preserve checkpoint 5 and failed session 6 pending Randy's next direction. After Git closeout, further project work belongs to Development Session 63.
