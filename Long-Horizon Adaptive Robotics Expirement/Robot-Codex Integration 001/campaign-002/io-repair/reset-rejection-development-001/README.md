# Reset rejection instrumentation: bounded development evidence

The parser still raises `HTTP/2 reset on unavailable stream` at the same gate. Its first failed snapshot now records fixed protocol scalars, diagnostic-only normal-close/reset membership, and tombstone eviction. The last 1,024 normally closed IDs are bounded internal diagnostic state. Absent membership remains unknown. Success and prior post-retirement HEADERS rejection schemas are unchanged.

The first focused command passed **61 parser and mocked bridge tests**. Comparison with the actual frozen dev061 archive passed **108 synthetic workloads/chunkings**, including late reset, duplicate reset, unknown ID, eviction, fragmentation/coalescing, retirement and malformed frames. After every call, acceptance/errors/counters/non-diagnostic internal state matched. Removing exactly three additive instrumentation blocks restored the archived parser bytes exactly.

One additional actual mocked bridge test passed: a late reset is counted as 13 observed bytes, rejected before forwarding, serialized in the failed parent H2/seal snapshot and never becomes qualified. The namespace does not receive it and retirement still runs. Its retained receipt is synthetic; its fixed CANCEL value does not identify Smoke019's unknown reset.

The initial comparison helper failed because it assumed CRLF while the exact parser uses LF. `parity-001.json`, its output and original `check_parity.py` remain unchanged. `check_parity_002.py` handles source line endings and passed; production/test source was not changed after the 61-test pass.

Exact commands, outputs and hashes are in [receipt.json](receipt.json), [test-001.json](test-001.json), [parity.json](parity.json), [parity-002.json](parity-002.json), and [synthetic-failed-bridge-receipt.json](synthetic-failed-bridge-receipt.json). There was no OS ownership/native/model/queue launch, historical result replay, assessment or qualification claim.
