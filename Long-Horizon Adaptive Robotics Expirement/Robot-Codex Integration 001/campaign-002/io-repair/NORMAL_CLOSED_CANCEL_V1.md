# Preserve cancellation controls after an observed normal stream completion

Prospective infrastructure correction declared on 2026-09-28 after the single Diagnostic002/dev062 and before implementing acceptance changes. Official job `20260928T212544481369Z-1e380c95` failed with integer 1. Its instrumented parent witness rejected upload RST_STREAM on stream 27, flags 0, payload length 4, code CANCEL(8), before retirement. This exact stream was recorded as normally closed, not previously reset, with no history eviction. The 13 rejected bytes were not forwarded. Subsequent native cleanup did not repair the transport failure. Diagnostic002 remains failed/unassessed/task unknown. Smoke019's unretained reset identity and code remain unknown.

RFC 9113 sections 5.1 and 6.4 distinguish a reset received after normal stream closure from an illegal reset on an idle stream: https://www.rfc-editor.org/rfc/rfc9113.html#section-5.1 and https://www.rfc-editor.org/rfc/rfc9113.html#section-6.4. This correction handles only the observed upload CANCEL after source-witnessed normal completion. It does not infer application/RPC success from transport closure or grant any new operation.

## Narrow runtime rule

Retain a bounded proof for the last 1,024 normally completed stream IDs. A proof is created only from a previously validated upload HEADERS opening, both END_STREAM observations and completion of all associated header blocks. Retain the opening and final completion positions as direction-local complete-frame ordinals and absolute wire end-byte positions (including the upload preface). A DATA read's total length is not a frame end position. Evict the smallest stream ID when the proof cache exceeds 1,024; an evicted or otherwise missing ID cannot qualify for this exception.

Before the original unavailable-stream reset rejection, admit only an upload RST_STREAM with exact code 8 and flags 0, for a retained normally completed ID, when both the frame start and completion are before retirement. Permit at most one such control per stream and at most 64 per channel. Unknown, skipped, evicted, previously reset, active, partially completed and duplicate streams remain outside this exception. Other directions and codes retain the prior behavior. Record each accepted terminal control separately and forward every original byte unchanged. Do not create, reopen or close a stream, change last_stream_id or closed_streams, or increment/decrement/erase the existing active-reset counters or records.

The original active-reset semantics remain: a pre-retirement active reset prevents clean qualification; retirement permits only the original bounded CANCEL8 rule on streams active in its original frontier. No terminal-control exception operates during retirement or across its boundary. No new request stream, payload transformation, RPC replay, source bypass, deadline change or weakened EOF/retirement proof is introduced. Existing frame, queue and receipt-size limits remain; exceeding any bound fails explicitly.

## Exact evidence schema

Every successful H2 summary adds exactly `terminal_control_records`, a list sorted by upload frame ordinal. Each row has exactly:

```
direction: "upload"
stream_id: the normally completed odd client stream ID
error_code: 8
frame: complete upload frame ordinal of the RST_STREAM
end_byte: absolute upload wire end-byte position of that frame
normal_close:
  opened_upload: {frame, end_byte}
  upload_closed: {frame, end_byte}
  download_closed: {frame, end_byte}
opposite_observed_frames: completed download frames observed locally before this control
```

The normal_close object is copied from that exact ID's immutable cache entry at control acceptance. Positions are positive exact integers; opening precedes or equals upload completion, which strictly precedes the control; its 13 bytes follow the upload completion. Download completion precedes or equals the source's recorded opposite_observed_frames. All positions fit the corresponding summary frame/byte totals. IDs are unique, no greater than last_stream_id, and disjoint from active IDs and active-reset records. The control count is at most 64 and no greater than closed_streams.

`opposite_observed_frames` is an endpoint-local causal observation, not a common wire order. Validate it independently at each endpoint and preserve it exactly through that endpoint's later snapshots. Only this field is projected away by final cross-endpoint h2_facts comparison; every canonical closure/control identity and position still matches exactly. Never compare timestamps across endpoints. All terminal records must already exist unchanged in each endpoint's original pre-retirement frontier; none can be added after it. Earlier/later snapshot validation preserves record prefixes and forbids changed or disappearing evidence. All existing source, failure, byte/hash, framing, real EOF, drain, native-quiescence and namespace-retirement checks remain mandatory.

## Implementation and validation

Add the producer proof and narrow rule to the current passive witness, plus an exact independent verifier for this schema. Preserve failed artifacts and frozen sources. Keep unrelated parser decisions unchanged. Deterministic tests must compare the unchanged parser's rejection with the new rule on actual source, include fragmented/coalesced controls and paired bridge/namespace forwarding, and show unchanged rejection for unknown/skipped/evicted/reset IDs, active resets, other codes/directions, duplicate/overflow, incomplete END_STREAM/header completion, boundary-crossing fragments, new streams, dropped bytes, missing EOF and retirement failure. Mutated or inconsistent proof records must fail independent verification, including endpoint-local causal bounds and canonical endpoint differences. No robot/controller/physics/evaluator/recovery-policy change is included.

Use an additive prepare_model_v14 inventory wrapper over v13 and preserve policy parity. Bind this declaration, producer/verifier/test sources and the retained diagnostic evidence in fresh source inventories. After development passes, declare new raw/transport/host prerequisites and the complete native/boundary/smoke/two-pilot sequence with new identities. No old failed job or old passing gate is substituted for the new lineage; no diagnostic becomes a scored outcome. Only a fully qualified final revision may enter the previously authorized fixed twenty-slot campaign.
