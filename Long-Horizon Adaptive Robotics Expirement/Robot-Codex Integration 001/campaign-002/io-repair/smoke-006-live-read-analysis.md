# Smoke006: live-read rejection diagnosis

Smoke006/dev031 remains **failed: 61/62 checks passed**. Fresh official authentication matched queue `20260928T043505991564Z-793bbbaf`: succeeded, integer exit0, `2026-09-28T04:35:06.269363Z` to `04:48:53.459001Z`. The sole false criterion is `model_requested_live_source_reads_match_protected_episode_invocation_observations`. Both transport lifecycle checks passed. Original timing passed: maximum lag **4.6873 ms**, **0/824** bad complete windows.

Original evidence: [assessment](../qualification/smoke-006-assessment.json), [failed admission](../qualification/final-qualification-008/smoke-006/disposition.json), [official queue](../qualification/smoke-006-queue.json), [frozen snapshot](../../../Architecture%20Map/releases/RCI001-C02-dev-031/snapshot.json), [source archive](../../../Architecture%20Map/releases/RCI001-C02-dev-031/code.zip). The [analysis JSON](smoke-006-live-read-analysis.json) binds every input and original archive-member source.

Interrupt command `exec-4414c7f4-b6b6-41d5-9ed1-81f6feb2e1d4`, public client lines115-116, executed:

```sh
/usr/bin/bash -lc 'cat /workspace/live/activation.json /workspace/live/state.json'
```

Actual protected request260 has the same argv, cwd `file:///workspace`, ttyfalse, tool ID and process43176. Start acknowledgment267 and every process response have unique completed-send receipts. Native/app exit codes are0, all message/blob hashes agree and stderr is empty.

| Capture line | Process seq | Notification | Stdout bytes | Delivery line |
|---|---:|---|---:|---:|
| 269 | 1 | output | 412 | 270 |
| 271 | 3 | exited, exit0 | — | 272 |
| 273 | 2 | output | 8192 | 274 |
| 275 | 4 | output | 3920 | 276 |
| 277 | 5 | closed | — | 278 |

The original `assessment/retained_reads.py` compares process sequence with capture-arrival position at127-135. The exited notification carries3 where2 is expected, so it skips this candidate at148-151. Original `literal_read_segments.py:246` then reports `No authenticated successful complete process stream` before segmentation or protected identity checks. Original `assess_smoke_v2.py:423` sees empty interrupt state/activation evidence lists; resume joins are present. An in-memory load of the archived dev031 reader reproduces this exclusion. Current prospective source edits are not used as the historical method.

Inspect [capture lines260-278](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-006/orchestrator/interrupt/executor-2-capture.jsonl) and [public command lines115-116](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-006/orchestrator/interrupt/client/events.jsonl). Concatenating stdout in its existing arrival order gives **12524 bytes**, SHA256 `00380aa7a891704f74afa0e9efd088011a188efe16d3db615e2496cae98fc596`, exactly equal to the app aggregate. No capture row or output byte was reordered. The complete unique sequence set is1..5, stdout order is1,2,4, and closed is last at5.

The complete stdout separates into activation bytes0:412, SHA256 `0680192f990aebb83577a403d77d05fe737b5fe435622f65a81d2d7ad780adb1`, and state bytes412:12524, SHA256 `0464c9cfe5b402c57c1c962f337301a641fe8f5c8825c14acf8d5adce8ab93a7`. Both identify epoch3 and invocation `interrupt-b34bd3e72160`; activation is `activation-001`, order1. State identifies `episode-fd185481fa374c70`, observation342, capture time35.53399999999746. Those required identity/capture/order fields match unique protected observation event364; invocation start is event33. Exact readonly serialization, original environment/command checks and close chronology also pass this bounded diagnostic join.

The [protected public history](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-006/host/public-history.jsonl) retains those joins. Request time is1790570142.4011977, close1790570142.4182286, completed send1790570142.4192336 and app completion1790570142.420. This is an identity/capture/order match, not full-packet equivalence or model attention.

Original `harness/executor_capture.py:133-139` reads native stdout lines serially, records each response, sends it unchanged, then records send completion. Its capture sequence differs from native `params.seq`; it does not allocate that native sequence. Original boundary `inside.py:106` launches `/codex exec-server --listen stdio`. Runtime setup binds binary SHA256 `3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970`. The exact native sequence-allocation implementation is not retained in the examined snapshot: **the upstream mechanism remains unknown**. The evidence establishes exit-notice overtaking here, not a universal protocol ordering guarantee.

A supported prospective correction is limited to that interleaving. Keep capture order and stdout bytes unchanged; require unique complete integer sequences1..N, one successful exit and closed, closed last atmaxN, and strictly increasing output sequence order. Preserve every existing source, exact argv/path/environment, PID, hash/delivery, stderr, chronology and protected-identity gate. Negative tests must reject gaps, duplicates, output reordering, early close, unsuccessful exit, altered/undelivered bytes and wrong identity. Arbitrarily sorting output messages is unsupported.

This artifact changes no assessment/runtime and launches nothing. The original failed assessment/disposition remains unchanged. A correction requires a prospective source anchor and full fresh qualification. Send completion is not app acknowledgment; equal app bytes do not prove attention. Only public tools/output and protected evidence were examined, with no private model reasoning.
