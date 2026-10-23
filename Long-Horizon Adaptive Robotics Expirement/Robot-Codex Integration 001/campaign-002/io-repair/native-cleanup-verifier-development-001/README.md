# Native cleanup verifier development

Prospective verification only. No native/model/physics run, qualification, retry, or historical verdict change occurred.

[Final focused check](check-004.json) passed 142 assessment tests and 13 raw-preflight tests with all 16 bound sources unchanged. [Receipt](receipt.json) binds every retained check and settled source. Initial failures remain in check-001, check-002, and actual-paired-003-check-001.

The independent proof joins the original first cleanup request, native schema2 event, authenticated owner, hash-chained parent barrier and ACK, namespace record and exact control frames. It preserves native 5/10-second bounds, final drain/EOF/retirement, and raw reset counters. Cleanup reconciliation removes only uniquely indexed phase entries; original and canonical observations are distinct. Per-stream trace hashes are source-witnessed structural evidence, not replay of unretained payload.

[Emitted fixture replay](actual-paired-check-002.json) and [endpoint H2 replay](paired-h2-check-001.json) cover zero channels, active cancellation, phase-born channels, mixed active/normal closure, and CLOSED in flight. These are fake OS/native fixtures. The schema2 client replay adds an explicitly synthetic setup identity prefix/config in temporary copies; it does not claim that setup evidence was emitted. Original fixture artifacts remain unchanged.

Full top-level synthetic tests cover zero and phase-born channels, no-thread cleanup, exact mixed counter reconciliation, wrong trace/hash/owner/source, missing ACK/frame, late completion, malformed phase identity, immutable prefixes, active reset boundary, and post-retirement normal-close counterpart. Raw tests run actual Client.close and Controller with fake pipes, validate all consumed endpoint files, and preserve unknown/duplicate/lifecycle/stderr negatives.
