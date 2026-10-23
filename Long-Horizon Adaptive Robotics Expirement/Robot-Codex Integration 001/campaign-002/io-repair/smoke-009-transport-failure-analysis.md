# Smoke 009 protected transport/lifecycle diagnosis

Smoke009's official queue job `20260928T070832475978Z-cc8a6cbd` failed with integer exit status 1. Fresh queue authentication and exact retained-receipt equality preceded this diagnostic read. This report does not evaluate task success, physics timing, recovery policy or empirical qualification, and no assessor or model was run for it.

The original accepted codehost TCP connection remained open until the trusted owner announced finishing. Four additional TCP connections were rejected by the existing single-active-client boundary. Three pre-shutdown denials align with actual raw code-mode tool errors. The records support a connection-cardinality mismatch, while the reason for the native client's additional connections remains unknown. They do not prove an early break in the original accepted byte stream.

## Bound evidence

The [machine-readable analysis](smoke-009-transport-failure-analysis.json) binds the official metadata, dev041 snapshot/archive, corresponding dev037 source archive, manifest, source identities, raw metadata and client-side companion analysis. Its SHA256 is `c81882511db9c705a0d547d208f3e1ec5d75f8e6270bed383bc3a3ff4a8ac0ed` (51,454 bytes). The [client-side diagnostic](smoke-009-client-failure-analysis.md) independently describes the actual tool-result errors and the absent interruption trigger.

Only new diagnostic JSON/Markdown files were written. Existing raw evidence, frozen sources, assessments and outcomes remain unchanged.

## Connection and shutdown chronology

Times below use the Windows parent/client wall clock. Native event timestamps have millisecond resolution; the bridge ledger has a finer representation. Temporal correspondence is not an authoritative raw-call-ID to TCP-connection-ID join.

| Denied connection | Bridge denial time (UTC) | Nearby raw tool-result metadata |
|---|---|---|
| 2 | 2026-09-28T07:12:36.298309+00:00 | BrokenPipe, raw event 364 |
| 3 | 2026-09-28T07:12:43.569524+00:00 | ConnectionReset, raw event 373 |
| 4 | 2026-09-28T07:13:04.103235+00:00 | BrokenPipe, raw event 419 |
| 5 | 2026-09-28T07:13:07.654343+00:00 | Shutdown phase; no tool-result claim |

Connection 1 was accepted at `2026-09-28T07:08:52.228644+00:00`. The last successful native command event cited by the client diagnostic is public line 351 at 07:11:04.843 UTC. The first denied new connection followed about 91.455 seconds later; this interval is an observation, not proof of an idle-timeout mechanism.

The owner-finishing record is client line 479 at `2026-09-28T07:13:07.652346+00:00`. The first pump end is upload EOF at `2026-09-28T07:13:07.655344+00:00`, approximately 2.997 milliseconds later, with `client_finishing=true`. The download pump was then cancelled during cleanup. There is no earlier retained pump-end record, and `pump_errors=[]` for connection 1. Client line 480 records integer exit code 0.

The four connection denials have exact reason `single_active_client`. The ledger ends with `accepted=1`, `denied=4`, `failures=[]`. No second codehost namespace was accepted. The bridge's close-on-denial branch is present at frozen `harness/codehost_bridge_v2.py:122–130`.

## Authenticated metadata and its limits

- The complete 13-record codehost ledger has contiguous sequence numbers and valid per-record/previous-record hashes. Its opening source identities match dev041 archive bytes and the accepted bridge receipt.
- Bound codehost stderr is complete, unredacted, untruncated and 2,109 bytes. All eight lines have the protected namespace-record prefix; the parsed records exactly equal the bridge receipt. The child was alive before cleanup; normal owner-input closure led to SIGTERM, child exit -15, no kill escalation and a qualified wrapper exit 0. Child diagnostic stdout/stderr retain only byte counts and hashes, so they cannot identify why a new native channel was attempted.
- All three namespace retirement receipts report qualified retirement, empty remaining namespace membership, no normal-wait timeout, no wrapper kill after retirement, and integer wrapper exit 0. These are retirement claims, not a whole-apparatus pass.
- Both executor capture ledgers authenticate. The first contains 11 responses and 11 unique delivery receipts; the second contains 190 of each. Every retained response has one later delivery receipt and its retained-message hash matches. This verifies the capture/delivery metadata only, without evaluating command or task output.
- Executor 2 records `ConnectionClosedError` at 07:13:07.904753 UTC, after owner finishing. That cleanup-era exception alone is not evidence of a preceding executor outage.
- Namespace `from_host=180910` and parent bridge `from_host=180893` are independent shutdown counters. The 17-byte difference does not identify a payload or establish complete H2 stream correspondence. Linux and Windows monotonic clocks are not compared.

## Why clean receipts are insufficient

Frozen `codehost_bridge_v2.py:233–235` computes the accepted connection's qualified flag from expected shutdown, its pump errors, namespace records, exit status and retirement. The rejection branch adds `connection_bound` to failures, but does not add `single_active_client`. Therefore `qualified=true` and `failures=[]` can coexist with these four recorded denials.

The separate frozen `assessment/transport_integrity.py:307–313` explicitly requires one accepted connection, **zero denied connections**, and an exact lifecycle sequence with no extra connections. The observed ledger does not meet that source clause. This is a static contract comparison; no empirical assessor was executed and no prior assessment is rewritten.

Likewise, `bootstrap_client_v3.py:359–363` sets client success after the native turn reports `completed`; it does not certify each tool's success. Sequence metadata retains `injected_interruption=false`, `watchdog_errors=[]`, and `Interruption stage failed its gate; restart not attempted`. No resume directory exists. Root's trigger diagnosis and the client companion report cover why that sequence gate was absent; this transport report makes no recovery-policy conclusion.

## Raw-event source comparison and next boundary

Dev041 bridge, namespace wrapper, executor capture and transport verifier bytes exactly equal dev037. The runtime differs only by loading bootstrap v3 instead of v2. The archived bootstrap difference consists of requesting `experimentalRawEvents=true` and recording that requested/accepted flag in launch and preflight metadata. Its bounded notification reader already logs emitted notifications. The exact source diff is retained in JSON. There is no evidence here that requesting raw events caused the additional TCP channels.

The supported next investigation is source inspection or a bounded no-model probe of native channel creation and ownership while an earlier connection remains open. Preserve the single protected namespace and capability/authority boundaries; do not make independent concurrent codehost namespaces acceptable or weaken the zero-denial requirement. A supported correction would need prospectively bound sources and fresh qualification. Smoke009 remains a failed attempt with no empirical assessor or pilots run.
