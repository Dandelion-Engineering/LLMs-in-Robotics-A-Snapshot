# Socket-abort diagnostics without changing transport acceptance

Declared 2026-09-29 UTC after Smoke026 failed and before any implementation or new diagnostic execution. This is diagnostic development, not a repair qualification or authorization to repeat V28.

## Original evidence and unresolved question

Smoke026/dev090 job20260929T050327589414Z-e2cffb4f failed with integer exit1. Its immutable diagnostic packet is `smoke026-queue-failure-diagnosis-001/analysis.json`, SHA256 `2611904daa2ce67fef888e426f1d9af7fb1309d5bc8c9a4d087cf8858effe35b`. The original failure disposition is `../qualification/RCI001-C02-smoke-026/queue-failure.json`, SHA256 `f1c14d6d96782de145092bb9f3269655ef7bf407d8dabd56b1b4205506232050`. No assessment exists and task outcome remains unknown. Native027 and Boundary028 retain their separate original passes; no pilot or scored slot launched.

The first retained fault is `channel_ConnectionAbortedError`. Source/state evidence points to an upload read, but the actual operation, channel, errno and winerror were not retained with the exception. One channel has no genuine EOF or upload-drained receipt. Every observed byte meter matches and both H2 parsers report structurally complete streams; these observations do not prove EOF or absence of unobserved bytes. The first fault and actual durable finishing marker share the same recorded timestamp; their strict order is unknown. All three original retirement receipts report qualified retirement, independently of failed transport completion.

The immediate question is which exact socket operation raises the first error and how controlled Windows graceful/abortive/cancelled closures appear through the existing reader/writer. No new full qualification is justified by diagnostic metadata alone.

## Bounded implementation

Restrict production edits to `harness/codehost_bridge_v3.py`, with targeted regression additions in `harness/test_codehost_bridge_v3.py`. Before-state source SHA256 is `332bca286235715c241b36996a7c35c38f4bb966152395a32976eeebd1244263`; before-state test SHA256 is `2cdbc6689ac420c055dbcd5e2ffd9923dd4bdbee5d3b3e47f4600e5c3ee90ea1`. Preserve exact copies before editing. Both are bound by the retained dev090 snapshot `a72d7068856370b531a0b5e704ca6e8bf1f8091d5798a5c08fbd0f8c0cd476b9` and its archive.

Observe `OSError` only around the actual upload reader await or download writer/write-and-drain operation. Record the first fixed-schema socket failure per channel through the existing bounded ledger, then rethrow the same exception. Allowed metadata: operation enum `upload_read` or `download_write`, authenticated channel ID, a finite exception-class enum with an unknown fallback, bounded genuine integer errno/winerror or null, existing clock timestamps, cleanup/finishing/sealed booleans, and compact existing structural state/byte counters where useful. Missing numeric codes remain null; booleans are not integer error codes. Metadata must be detached from mutable objects.

Do not retain arbitrary exception messages, stringified arguments, traceback text, endpoint addresses, capabilities, credentials, headers or payload bytes. Recording failure must not mask the original exception or turn it into success. Preserve existing ledger limits and fail-closed behavior; no unbounded storage or new transport synchronization. Do not add normal-path network reads or writes.

No parser, assessor, model, prompt, task, native RPC, fixture, timing, resource or lifecycle acceptance rule changes. Genuine EOF remains only an actual empty socket read. Cancellation, reset and abort do not become EOF. Keep exact byte/hash equality, owner authentication, complete drain, deadline and retirement gates. Do not move the finishing marker, sleep longer, extend deadlines or infer native shutdown success from thread/closed.

## Development evidence

Add focused negatives proving error metadata is bounded/redacted, the original error still propagates, no EOF/drain success is created, and cancellation remains distinct. Retain pre-change failures and subsequent results. Verify unchanged protocol behavior with the existing bridge suite and source parity outside the small instrumentation region.

Prepare a separately retained no-model Windows loopback fixture under `io-repair/`. Exercise the actual `SocketReader`/`SocketWriter` on `127.0.0.1` using a fixed finite set: explicit graceful send shutdown after known payload, peer abortive closure, local closure with pending receive, and explicit task cancellation. Use short absolute deadlines, exact source bindings, actual observed exception class/numeric codes and byte hashes. Do not require a guessed OS code or silently rerun a case that produces a different result. All cases and failures are retained. Close only sockets/processes created by this fixture.

This fixture is development evidence, not a recreation of Smoke026's hidden native cause or a scientific qualification. It invokes no model, native app server, account, robot host or external network service. Any sustained extension must use the shared queue. Register/freeze a distinct diagnostic identity before any later empirical native investigation; do not modify the original attempt or launch a full unchanged qualification. A supported behavioral repair, its tests and a fresh complete qualification are still required before the twenty-slot campaign.

The existing history120 rows, original diagnostics, source archives, accounting and retained exports remain immutable inputs. Complete pending Smoke026 history bookkeeping and verify that no historical reader relies on a mutable bridge source before changing it.
