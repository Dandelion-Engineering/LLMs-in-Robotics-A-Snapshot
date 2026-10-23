# Smoke020: active cancellation during native cleanup

This is infrastructure diagnosis of **RCI001-C02-smoke-020**, frozen **dev066**, after fresh official authentication of job `20260928T221108244078Z-655651d6` as failed with integer exit 1 (2026-09-28 22:11:08.501882–22:15:53.893415 UTC). No task or timing assessment was performed. The original failure is preserved; no source, outcome, or launch was changed. The [machine-readable analysis](smoke-020-transport-failure-analysis.json) binds the original inputs and exact archived sources by bytes and SHA256.

## First failure and its scope

The planned interruption occurred after `smoke-open-001` was accepted and its authority was retired. The frozen [physical watcher](../harness/physical.py) then deliberately sets the same `abort_event` checked by [bootstrap receive](../harness/bootstrap_client_v4.py). Consequently, the client message “Qualified execution transport failed; stopping invocation” alone does not establish a transport failure preceding cleanup.

Native cleanup began at wall time `1790633751.769682`. The `turn/interrupt` request was sent at `.770691`; the first retained transport failure is parent ledger sequence **201**, `channel_ValueError`, at `.7716858`. The durable closing marker follows at `.780684`. These Windows event sequences and wall times establish the order; equal coarse monotonic values do not independently establish strict ordering.

Channel 2's original frontier, sequence **204**, retains an accepted active upload **RST_STREAM/CANCEL(8) on stream 15**, followed by active stream 17, with no parser error. The namespace's original frontier still has active stream 15, last stream 15, and no reset. Frozen [bridge feed_h2](../harness/codehost_bridge_v3.py) rejects an accepted active reset when no owner retirement frontier exists, before enqueueing the read. Thus `reset_before_owner_finish` is the source-supported first guard; that text was **not** retained as the exception message.

The parent read **36,851 bytes** on channel 2 but forwarded **36,791**, leaving **60 bytes unforwarded**. Its parsed stream state establishes active cancellation and a new upload HEADERS stream 17 in that withheld input. Neither the raw read nor a direct read hash was retained. Its exact contents, internal read/frame segmentation, RPC identity, and reason for opening stream 17 remain unknown. The rejected bytes must not be represented as delivered evidence.

At sequence **215**, the parent subsequently received a 10-byte namespace DATA payload (SHA256 `26c15ec938b7a6018c80a25ae1094b5a57f3f59f363b5e27fdd2034cddab9c3e`). Sequence **216** records `frame_read_ValueError`; the final parser error is “HTTP/2 headers on unavailable stream.” Its header stream ID and flags are unretained: **do not infer stream 15 or 17**. This is downstream of the initial active-reset guard. Channel 2 received 1,756 download bytes but wrote 1,746 to the client, preserving the later 10-byte discrepancy.

## Other retained lifecycle evidence

- Channel 1's two declared normal-closed CANCEL controls, streams **5 and 29**, retain matching normal-close wire proofs at both endpoints. Its upload and download meters match exactly. The normal-closed control path therefore ran in this failed invocation; this is not a transport qualification claim.
- Native cleanup retained successful interrupt response and terminal-turn acknowledgment, `unsubscribed`, matching `thread/closed`, a qualified handshake, native exit 0, and no forced close. Cleanup completed at wall `.798248`. These receipts do not override the full transport failure.
- The parent subsequently recorded invalid retirement frontier/drain, a downstream receiver failure, failed seal, namespace wrapper exit 1, and an unqualified namespace receipt. Namespace metadata retains two failed channel closures and failed final closure; the parent did not receive a complete qualified CLOSED/FINISHED lifecycle.
- Protected retirement, durable retention, and old-token denial were true. Stage success was false; `model_started` and `injected_interruption` were true. There was **one interrupt stage, no resume, and no pilot launch**.

## Bound evidence and limitations

The JSON links the [original stage directory](../../local-evidence/campaign002/qualification/RCI001-C02-smoke-020/orchestrator/interrupt), its parent ledger, namespace stderr metadata, bridge receipt, retirement receipt, client events/result/quiescence, sequence result, manifest, official queue record, and the [dev066 source snapshot](../../../Architecture%20Map/releases/RCI001-C02-dev-066/snapshot.json). All seven inspected production files matched the archived source bytes.

Parent and namespace clocks are separate and were not subtracted. No payload, RPC content, model reasoning, missing-byte reconstruction, task performance, or causal explanation for the downstream header identity is claimed. Smoke019's unknown historical reset and Diagnostic002's separately identified normal-closed reset remain unchanged. Any prospective correction needs its own declaration and validation; this diagnosis supplies no generic pre-retirement reset exception, counter suppression, new-stream permission, or longer deadline.
