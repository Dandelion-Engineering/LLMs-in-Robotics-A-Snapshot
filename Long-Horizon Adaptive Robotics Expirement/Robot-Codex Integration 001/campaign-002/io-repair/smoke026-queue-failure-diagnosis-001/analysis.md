# Smoke026 queue failure: infrastructure diagnosis only

Run `RCI001-C02-smoke-026`; official job `20260929T050327589414Z-e2cffb4f` freshly authenticated **failed / integer 1**. No empirical assessment, retry or task-outcome claim. Task outcome remains unknown.

The planned interruption occurred after accepted `smoke-open-001`. Native cleanup completed: turn interrupt, terminal acknowledgement, unsubscribe, thread/closed, native exit 0, no forced job close. The first transport failure was `channel_ConnectionAbortedError` (ledger line/sequence 174). It was followed by `drain_invalid`, failed namespace terminal evidence and wrapper exit 1; resume was not attempted.

The source/state inference is a channel-1 native upload socket read exception: `SocketReader.read` delegates directly to `loop.sock_recv`; channel 1 has no `client_eof`, HALF_CLOSE or upload-drained receipt. The first failure does not retain its channel, stack, errno, winerror or message, so the exact OS cause and socket-close mechanism are unknown. Channel 2 retained genuine EOF and upload drain. Neither H2 parser retained an error or first rejection.

The first failure and the actual durable `client_finishing_before_close` marker have exactly equal wall and monotonic timestamps (1790658441.0409749 / 515920.5). Their strict cross-file order is unproved. `thread/closed` was recorded earlier at .0384662; the later controller `finishing`/`stdin_closed` records are .0424805. Those later records must not substitute for the marker.

All observed meter identities match across native read, parent forwarding, namespace receipt and native writes: channel 1 upload 229450 B/download 166743 B; channel 2 upload 32471 B/download 1303 B. Both parsers ended structurally complete with zero active streams. This does not prove an aborted read is EOF or that no unobserved data remained. Channel 2's protected cleanup CANCEL evidence was retained successfully.

The existing guard correctly requires genuine EOF. Parent `finish_owner` re-observes the upload exception and records `drain_invalid`; emergency FINISH has no channel-1 HALF_CLOSE. Linux's first applicable FINISH guard is `Owner finish before genuine upload EOF`. The namespace retained an unqualified terminal record, then retirement. All three original namespace-retirement receipts report qualified, retired, empty namespace membership and outer process absent; host exit is 0. No live-namespace leak is shown by these scoped historical receipts, but no present global OS census was performed.

A supported next step is prospective bounded socket-operation/typed-error instrumentation plus a separately declared no-model local lifecycle reproducer. Keep failure, owner authentication, genuine EOF, byte hashes and deadlines unchanged. The retained native tag source joins CloseSession/stream tasks and emits thread/closed after thread shutdown; it does not expose a proved socket FIN acknowledgment or attest this installed native socket-close cause. Moving the marker, treating abort as EOF, sleeping longer, or another unchanged full qualification is unsupported.

See [analysis.json](analysis.json) for exact source/archive identities, all original input bindings, metadata-only timelines, retirement observations and limits. Sources verified byte-equal to dev090 and its code.zip. No original evidence or source was changed.

Key source locations: `harness/codehost_bridge_v3.py:35,412,548,633,774`; `harness/codehost_inside_v3.py:418`; `harness/physical.py:55`; `harness/native_quiescence.py:260`. Native tag interpretation remains source evidence, not installed-binary attestation.
