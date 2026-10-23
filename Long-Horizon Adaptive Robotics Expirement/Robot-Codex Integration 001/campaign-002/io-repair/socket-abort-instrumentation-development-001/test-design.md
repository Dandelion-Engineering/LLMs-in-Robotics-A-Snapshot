# Prospective focused test design (source hold active)

Only `codehost_bridge_v3.py` and its test file will change after explicit release. Baselines are retained in this directory.

Exercise the existing upload/sink methods with exact injected OSError objects. Require one bounded metadata event per channel before existing fatal handling, exact same exception identity, no EOF/HALF_CLOSE/upload-drained fabrication, queue reservation release, genuine typed errno/winerror only, finite class fallback, detached counters/phase flags, and no exception text or arguments. Inject errors in writer.write and writer.drain separately. Confirm CancelledError and unrelated ValueError emit no socket metadata; retain cancellation failure semantics. Force ledger recording failure and ensure it cannot replace the socket exception.

Run paired actual Bridge/Relay fixture failures for upload abort and download write failure, retaining unsuccessful qualification and retirement. Existing success suite establishes no new socket event on healthy paths and unchanged acceptance. Retain red tests before production changes, then focused green output and exact AST/source reversal outside instrumentation. No native/model/OS query/empirical launch is part of these tests; the separate Windows loopback fixture has another owner.
