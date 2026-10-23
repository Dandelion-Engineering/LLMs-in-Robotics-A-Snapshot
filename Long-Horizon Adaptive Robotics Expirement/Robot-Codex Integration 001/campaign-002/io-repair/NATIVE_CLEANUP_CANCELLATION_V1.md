# Authenticated native cleanup cancellation and original-byte drain

Prospective apparatus repair declared 2026-09-28 before implementation, after settled Smoke020/dev066. This amends the pre-retirement active-reset rejection in NORMAL_CLOSED_CANCEL_V1.md only inside the new authenticated cleanup phase. Neither earlier declaration nor failed evidence is rewritten. Smoke020 remains failed, unassessed and task outcome unknown; no resume, pilots or scored slots were launched.

Smoke020's first retained transport failure follows the existing turn/interrupt write. The next unchanged source-bound H2 snapshot retains upload CANCEL8 on stream15 and 60 original upload bytes not forwarded. The exact reset_before_owner_finish guard is source-inferred, not retained exception text. A later unavailable download HEADERS rejection has no retained stream identity. Native lifecycle acknowledgments and native exit0 do not repair this transport failure. The separate smoke-020-transport-failure-analysis.json and .md bind the evidence and limitations.

Pinned native source creates cancellation/termination work during interrupt and unsubscribe. No supported acknowledgment separates all new cleanup streams from cancellation. Moving the final no-new-stream frontier before those controls would recreate the earlier new-stream failure. RFC9113 sections5.1 and6.4 explain that frames already sent or queued can still arrive after a reset: https://www.rfc-editor.org/rfc/rfc9113.html#section-5.1 and https://www.rfc-editor.org/rfc/rfc9113.html#section-6.4. This method does not infer RPC identity, task success or remote application semantics from an opaque HTTP/2 stream.

## One authenticated phase barrier

Before writing the first existing native cleanup control, retain its exact existing request event, allocate one random32-hex nonce, then synchronously call the bridge-owned callback from the bootstrap worker. No additional native RPC, model turn, tool action or retry is introduced. The first control remains turn/interrupt for an active known turn, otherwise thread/unsubscribe for a known thread. No-thread cleanup has no barrier or invented control. Retained turn identity in the seed is distinct from an unsubscribe request event's legitimately null turn_id.

The callback schedules a coroutine on the captured parent event loop. Under the existing admission lock it validates the authenticated owner, freezes detached channel frontiers, activates the phase and queues CLEANUP_BEGIN without an intervening await. Parent DATA already enqueued remains before BEGIN. Namespace processes ordered BEGIN, activates the same phase, drains all earlier upload queues, then retains its immutable frontier record and sends CLEANUP_ACK. Parent validates and durably records that ACK before returning. The controller retains cleanup_barrier_complete before writing the unchanged request bytes. A missing callback, owner, ACK, mismatched identity/hash, duplicate phase, exception, late completion or exhausted deadline fails; the control is not sent. Callback timeout cancels its future and permanently latches transport failure. A late ACK never restores permission or qualification.

Parent callback and controller share the original close-entry +5-second absolute graceful deadline; +10-second hard cleanup and the later +25-second owner drain are unchanged. Namespace uses bounded local waits, never comparisons between Windows and namespace monotonic clocks. Existing queue/frame/metadata/receipt caps remain; an oversized snapshot/ACK fails explicitly without truncation or raising the cap. CLEANUP_BEGIN=12 and CLEANUP_ACK=13 are bounded canonical metadata on mux channel0. Final DRAIN_BEGIN/ACK/FINISH, genuine upload/download EOF, exact byte/hash equality and namespace retirement remain mandatory.

Existing same-owner channel admission remains possible until the original final retirement frontier. Such channels inherit the nonce on an empty witness before OPENED or DATA. Their admission, inherited phase and exact empty frontier are recorded; their OPEN appears after ordered BEGIN. No new owner, broader TCP authentication, stream bound, payload transformation or queue allowance is granted.

Prospective enrollment clarification after a deterministic paired reproduction and before its correction: an already completed channel's CLOSED receipt can still be in flight at BEGIN, making local closed-status observations differ. Existing channels therefore enter the cleanup phase only when genuine upload EOF has not occurred: parent parent_eof is absent and namespace half_closed is false. Ordered HALF_CLOSE before BEGIN provides the common direction-local boundary; both frontier rows add upload_eof, and the independent reader joins it to actual client EOF/HALF_CLOSE/namespace upload EOF order. Already-closed channels necessarily have upload EOF. Their original H2 witnesses remain unphased, with no nonce projection or relaxed canonical equality. Local already_closed remains a retained observation, not phase authority; its asynchronous channel_closed retention is not assumed simultaneous with the state transition. Channels without upload EOF and later newly admitted channels retain the phase rule above. No bytes can be accepted after genuine upload EOF, and all original idle, final closure and retirement checks remain.

## Exact barrier evidence

Controller seed has exactly:

```
schema: campaign002-native-cleanup-request-1
nonce: 32 lowercase hex digits
thread_id: retained original thread identity
turn_id: retained original turn identity or null
control_event: exact fsynced native_quiescence request event
start_monotonic_s: original cleanup entry
graceful_deadline_monotonic_s: original entry +5
```

Bridge request adds exactly owner_receipt_sha256, binding the existing native-owner receipt. request_sha256 hashes canonical request bytes. Parent native_cleanup_begin ledger record binds the request, exact channel IDs, authentication hashes and full detached H2 frontiers. BEGIN payload has exactly schema=campaign002-native-cleanup-begin-1, request and parent_record_sha256. Namespace native_cleanup_begin record binds request_sha256, nonce, parent_record_sha256, complete local frontiers and the source-bound child identity; its retained sequence and local time are ordinary namespace metadata. ACK payload has exactly schema=campaign002-native-cleanup-ack-1, nonce, request_sha256, parent_record_sha256 and namespace_record. That full record must equal its actual retained namespace ledger row.

Returned completion has exactly:

```
schema: campaign002-native-cleanup-complete-1
request: complete authenticated request
request_sha256
parent_barrier_record_sha256
namespace_barrier_record_sha256
begin_payload_sha256
ack_payload_sha256
parent_ack_record_sha256
parent_ack_sequence
completed_monotonic_s
```

Parent native_cleanup_ack ledger record joins the exact BEGIN and ACK payload hashes and namespace record hash. Completion time is parent/controller local and precedes the exact first control write and original graceful deadline. Native quiescence receipt schema2 adds cleanup_barrier (the exact completion or null); one cleanup_barrier_complete event carries the completion. All prior lifecycle controls, original response correlation, terminal notification, thread/closed, finishing marker and native-exit checks remain. The independent verifier joins actual native, parent and namespace ledger records, source bindings, owner receipt and mux frame projections; merely asserting these hashes is insufficient.

## Bounded passive witness

H2Witness.begin_cleanup(nonce) returns its detached pre-phase summary and sets a once-only nonce. New empty channels call the same API. feed(direction,data) keeps its interface. begin_retirement() keeps the final no-new-stream gate and permits an earlier reset prefix only when exhaustively explained by the new cleanup records. The phase remains through genuine EOF. A cancellation after final retirement must still refer to a stream active in that original final frontier or an exact retained normal-close proof for an already admitted stream. It never extends that frontier or permits a new request.

An eligible cancellation is exactly upload RST_STREAM, flags0, payload length4, CANCEL8, whose first byte and completion are inside the cleanup phase. It identifies either a proven active stream in the local phase frontier, a valid upload opening begun and header-completed inside the phase before final retirement, or an exact cached normal-close proof. A partial opening that crosses BEGIN cannot newly gain active cancellation permission. A normal-close endpoint never grants permission to an otherwise ineligible active counterpart. The normal-close phase exception may also apply after final retirement: independent paired verification must still match the exact phase, original admitted opening, RST wire identity and final closure trace to an eligible active or proved-normal counterpart. This explicitly amends the old normal-control retirement restriction only for these phase records. Every stream ID may have at most one such cancellation; 64 cleanup records/tombstones per channel, the existing1,024 stream/proof bound and all existing byte/receipt bounds apply. Unknown, skipped, evicted, duplicate, wrong-direction, wrong-code, ambiguous phase-boundary and malformed frames fail.

Copy the canceled stream's structural state into a bounded tombstone. Preserve original reset_records/reset_streams or terminal_control_records/closed_streams exactly according to the endpoint's local classification. Do not reopen the stream or count a previously reset stream as a normal closure. Accept only valid trailing download HEADERS/DATA/CONTINUATION for that exact tombstone, including a previously begun frame/header block. Preserve continuation, padding, priority, frame-size, prior download-header and END_STREAM checks. No new upload work on the canceled ID is accepted. Existing validated stream control frames remain subject to their original syntax and are traced when the stream proof is retained. All original bytes are forwarded, counted and hashed; none is generated, dropped or replayed. Incomplete framing or headers still fail final EOF.

Each summary adds cleanup_phase_nonce and cleanup_cancel_records. Each cleanup record has exactly:

```
schema: campaign002-h2-cleanup-cancel-1
phase_nonce
stream_id
cancel: {direction:upload,type:3,flags:0,payload_length:4,error_code:8,
         frame,start_byte,end_byte,sha256}
opened_upload: {frame,start_byte,end_byte}
opening_headers_complete: {frame,end_byte}
upload_end_stream: {frame,end_byte} or null
upload_headers_complete: {frame,end_byte} or null
download_end_stream: {frame,end_byte} or null
download_headers_complete: {frame,end_byte} or null
wire: {upload:{frames,bytes,sha256},download:{frames,bytes,sha256}}
local: {classification:active or normal_closed,
        reset_record_index:int or null,terminal_control_index:int or null,
        eligibility:frontier_active or opened_during_phase or proved_normal_close,
        opposite_observed:{frames,wire_bytes,partial_frame:bool,pending_headers_stream:int or null},
        phase_frontier:{upload_frames,upload_wire_bytes,download_frames,download_wire_bytes,last_stream_id}}
```

Indices are zero-based. Positions are exact positive direction-local complete-frame ordinals and consumed wire offsets, never a read buffer's eventual total. start_byte is the inclusive first byte offset from zero; end_byte is exclusive. Each fixed RST occupies exactly13 original bytes. The direction's headers_complete anchor completes the header block associated with its END_STREAM (the END frame itself for DATA or END_HEADERS, otherwise its final CONTINUATION). opening_headers_complete instead completes the initial upload opening block. Directional per-stream wire traces begin at the observed opening and hash newline-delimited canonical structural descriptors containing the original full-frame hash; no application payload is retained. Only final genuine observations can fill previously null completion fields or advance a trace. Immutable reset identity, authorization, indices and local frontier never change; evidence cannot disappear or shrink. Full-frame digests and bounded structural observations are source-witnessed evidence, not independent replay of unretained payloads.

## Independent reconciliation

Validate every local row against its exact unique raw reset or normal terminal-control index, local phase frontier, opening/closure positions, opposite-direction causal prefix, final frontier and source-bound phase. Validate the original terminal normal-close proofs even when they are also referenced by a cleanup record. No unreferenced counter or row is exempted.

For cross-endpoint comparison retain every non-local cleanup field exactly, including final directional wire traces and actual closure positions. Compare closed_streams minus the number of locally normal cleanup records and reset_streams minus the number of locally active cleanup records. Remove only the uniquely referenced phase rows from the legacy reset and terminal lists before comparing those remaining lists under their existing rules. Preserve raw values in all artifacts and verify the arithmetic explicitly. This accounts one-for-one for a stream seen as active at one endpoint and already normally closed at the other. Any other difference fails. Snapshot progression permits only monotone observed tail completion/trace growth; original cancellation and authorization prefixes remain immutable.

All unrelated source, ownership, raw read evidence, failure, framing, real EOF, final no-new-stream, native quiescence, duration and namespace-retirement gates remain. Unsupported interleavings and exceeded bounds fail explicitly; this is not a claim of general HTTP/2 implementation or remote task success.

Implementation clarification, declared before changing idle_eof: a genuine channel EOF can precede final DRAIN_BEGIN during cleanup. Its idle proof still requires zero active streams, complete framing and headers, prior settings/preface and no error. Its formerly blanket reset-zero test accepts only a reset list exhaustively and uniquely indexed by valid cleanup records. An RST never stands in for EOF. No-phase idle behavior, both genuine endpoint EOF observations, original byte/hash equality, native lifecycle completion and complete owner/namespace retirement remain mandatory.

## Development and fresh qualification

Implement producer, barrier and independent reader together. Deterministic tests cover fragmented/coalesced frames, late DATA/HEADERS/CONTINUATION, active/normal endpoint races in both directions, phase-born streams and same-owner channels, boundary fragments, partial opens, callback/ACK failure and timeout, exact existing request bytes, raw counter preservation, absent EOF, dropped bytes, new streams after final retirement, mutated indices/proofs/ledger joins and resource bounds. Existing unaffected rejection cases remain tests. Keep original deadlines and event cap24.

Add a v15 inventory over preserved v14 and fresh v23 orchestration over preserved v22. Preserve model/task/physics/controller/recovery/evaluator policy exactly. Bind this method, the settled Smoke020 diagnosis, all implementation/test/independent-reader dependencies and exact source snapshots. Allocate fresh identifiers only after development passes and prospective lineage declaration. Run fresh raw, transport, host, native, boundary, interruption smoke and both pilot gates. Do not substitute any older pass or failed diagnostic. Only a fully qualified final revision can enter the already authorized fixed twenty-slot campaign and actual-results investigation.
