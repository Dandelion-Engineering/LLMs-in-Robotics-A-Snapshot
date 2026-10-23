# Diagnostic002: CANCEL on a witnessed normally closed stream

Job `20260928T212544481369Z-1e380c95` was freshly authenticated as **failed, integer exit 1**, 21:25:44.752356Z–21:26:26.298879Z on 2026-09-28. This single-invocation infrastructure diagnostic remains unassessed with unknown task outcome. The planned interruption was not injected and resume was not attempted.

The first parent failure is ledger **sequence 69**, `channel_ValueError`, at wall **1790630783.547947**, monotonic **488263.0**. The unchanged parser raised **`HTTP/2 reset on unavailable stream`**. Its declared metadata identifies upload **RST_STREAM (type 3), flags 0, stream 27, payload 4 bytes, code 8 (CANCEL)**. Stream 27 was absent from the active map but present in diagnostic normal-close history: `observed_normal_close=true`, `observed_reset=false`, `normal_close_history_evicted=false`. Retirement was false; last stream ID 33, active IDs 1/3, 15 normally closed streams, zero accepted resets.

Frozen dev062 source inserts this diagnostic tombstone only after both directional END_STREAM states and complete header continuation boundaries. It does not affect admission. Thus this run establishes a CANCEL on a stream that the passive witness had normally closed. It does not identify the RPC or explain why native sent it.

The parent observed **81,416 upload bytes** and forwarded **81,403**; the namespace recorded the same 81,403. The rejected **13 bytes** were withheld before enqueue. Both download/client-written meters equal 47,788. No exact reset-read hash or raw frame bytes were retained; identification comes from source-bound structural metadata rather than digest reconstruction.

Cleanup began later (client line 145, wall **1790630784.5621727**). The interrupted-turn and unsubscribe/thread-closed handshake completed, then the marker at line 155/wall 1790630784.5691721. Native exit was 0; quiescence was qualified and no forced job close occurred. The transport failure remained. Parent retirement-frontier/drain qualification consequently failed; stage cleanup clean and durable retention are true, while bridge/stage success remain false.

This supports prospectively investigating a narrow known-normal-closed CANCEL path, preserving unknown-ID/active-reset/new-work/retirement rules, exact forwarded-byte proofs, resource bounds and fresh testing/qualification. [RFC 9113 sections 5.1 and 6.4](https://www.rfc-editor.org/rfc/rfc9113.html#section-5.1) distinguish closed-stream control races from prohibited idle-stream resets. No such repair is implemented or adopted by this analysis.

**Smoke019 remains separate:** its reset ID/code/state are still unknown. No historical verdict is changed. Namespace clocks are not subtracted from Windows clocks. No application payloads, model reasoning, credentials, robot outcome or timing result were inspected or retained here.

The [hash-bound JSON](shutdown-diagnostic-002-failure-analysis.json) binds the parent ledger/receipt, stage and sequence failure, native cleanup, manifest/queue receipt, and dev062 snapshot/archive. All five inspected source files matched their exact archived members and snapshot hashes. Paths resolve from the explicit JSON binding base; artifact paths additionally use its artifact base.
