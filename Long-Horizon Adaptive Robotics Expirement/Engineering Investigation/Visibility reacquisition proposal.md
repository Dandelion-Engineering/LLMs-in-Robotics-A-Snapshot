# Visibility reacquisition: applied Runtime change and retained proposal

Status update, 2026-09-23: **root applied the patch to Runtime after the derivation source hold ended**. Applied `candidates.py` SHA256 is `4ba2aa0980ca36ae2748fc06c44b5fe5208f3fbf2666c650a54874e45874f8bc`. Root moved the 13 behavioral checks into [test_visibility_reacquisition.py](../Runtime/test_visibility_reacquisition.py), using the actual module; its SHA256 is `55d1ce496552475b79c047ba3cc165585d3806c41bc2865070a8f838a79be30e`. The complete 424-test Runtime suite then passed under [official receipt 20260923T074337863126Z-fa4ef51c](../Evidence/queue-receipts/20260923T074337863126Z-fa4ef51c.json), ending 07:44:19.996499 UTC. That receipt predates the subsequent raw-grid geometry update and does not validate later edits or physical performance.

The original [patch](visibility_reacquisition.patch), [generator](propose_visibility_reacquisition.py) and opt-in checks remain historical review evidence, unchanged after application. Their exact base was `fc101b3a79a4f647735f396d8938cb6156e180566d114eb5e46f8c8659e89c47`. **Do not regenerate or run the old source-bound proposal checks against applied Runtime.** Their guard correctly rejects the changed source. The implementation scope below is the applied visibility change; no original run was rewritten or reclassified.

The unchanged baseline/A3 scheduler reaches its existing visibility fallback only after its ordinary eligible-action branches. The proposal requests an observation, then charges the existing four-observation allowance only for delivered distinct fresh captures: increasing sequence **and** capture time within the same incarnation, using the existing 1.5-second freshness rule. Repeated, stale, missing-time or backwards captures wait without consuming that allowance. Ordinary machine waits and restart view-retreat actions do not spend it.

The first exhausted round issues the existing structured help action, retains its request ID and marks a visibility-specific pause. A first new answer correlated to that request permits one assisted round. Its failure pauses without another identical help request. Replayed answers, different answer IDs for the same request, unrelated advice, packet numbers and a changed order version alone cannot re-arm the visibility allowance. Successful existing public action reconciliation clears the episode; a completed receipt without supporting physical observation does not. The state is retained inside the existing candidate checkpoint and exposed through ordinary context-write events.

During only this visibility pause, a later distinct fresh capture may resume the unchanged scheduler if that scheduler already chooses a locally validated `transport`, `setup`, `cycle`, `inspect` or `done`. There is no new action ranking: A3 still requests its model objective before transport, and A1/A2 retain their own model/procedure selection. A changed order that creates a supported action can therefore resume work without manufacturing a new assistance loop. This resumption passes through the existing pending/recovery/model/failure checks. Other help reasons never acquire this automatic resumption behavior.

The existing human-answer bookkeeping still logs and consumes every new public answer and preserves pending actions, failure counts and process provenance. Correlation limits only the new visibility retry allowance. It does not change the assistance service, its 15-second delay, the answer text or original costs. No protected state, target-ID special case, extra clear-view motion, tipped-part recovery, or new scientific threshold is introduced. If no fresh capture arrives, the candidate remains passively waiting within the existing run cap; the patch adds no new camera-stall timeout.

Historical pre-application command, retained for provenance only:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/visibility_reacquisition_checks.py" --with-existing
```

Observed: **61 tests passed in 1.232 seconds**: 14 focused proposal tests plus 47 existing `test_candidates.py`/`test_candidate_loop_fix.py` tests. The tests load the proposed source in memory. Focused checks use synthetic public packets and mock persistence; existing tests create and clean their temporary candidate directories inside Engineering Investigation. No physics, model calls, queue calls, full evidence processing or Runtime writes occur. Source hashing confirms the exact base remains unchanged. The proposal checks deliberately are opt-in rather than normal `test_*.py` discovery because their source-hash guard becomes obsolete after integration.

The tests cover repeated frames; capture freshness/order; ordinary machine waits; one correlated assisted round; no repeated help; unrelated/replayed answers; supported resumption; A3 objective preservation; A1/A2 choice preservation; unresolved pending/recovery/other halts; model and physical failure limits; receipt-versus-public-reconciliation distinction; persisted state; and public order changes.

Historical generation command, retained for provenance only; do not rerun after application:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Engineering Investigation/propose_visibility_reacquisition.py"
```

The [actual C0-007 public chain](C0-007%20public%20visibility%20chain.md) contains distinct captures before help and persistent missing B6 detections. The patch handles the proven synthetic repeated-frame weakness and actual repeated-help symptom; it does not claim to resolve the physical visibility loss or improve the recorded 9/10 result.
