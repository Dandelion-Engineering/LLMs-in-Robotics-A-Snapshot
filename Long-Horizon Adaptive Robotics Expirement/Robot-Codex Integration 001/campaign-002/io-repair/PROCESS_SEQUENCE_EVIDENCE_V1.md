# Prospective process-sequence evidence correction

Declared after the retained smoke006/dev031 failure and before implementation, a new freeze or another model run. Smoke006 remains failed/invalid:61 of62 independent checks passed, with interrupt-stage live-source correspondence unproved by its frozen verifier. All previous sources, assessments and evidence remain unchanged in their archives. This correction concerns verification of an already captured process stream. It does not change model instructions, recovery behavior, command execution, output delivery, physics, timing thresholds, isolation, durable ordering or the twenty-slot experiment.

## Concrete retained evidence

The successful literal command `cat /workspace/live/activation.json /workspace/live/state.json` has one authenticated request/process identity and an integer exit0. Its capture arrival order contains native process sequences1(output),3(exited),2(output),4(output),5(closed). Every sequence1..5 is present exactly once; closure is last. The three stdout chunks retain ascending sequence order1,2,4. Their unchanged arrival-order concatenation is12524 bytes, SHA25600380aa7a891704f74afa0e9efd088011a188efe16d3db615e2496cae98fc596, exactly equal to the public app output. The two complete JSON values match the current activation and a unique protected episode/invocation/epoch/observation record. See the separate hash-bound smoke006 diagnosis for original input identities and limitations.

The capture producer reads and forwards native responses serially; it does not assign native process sequence fields. The native exec-server implementation is not present in the reviewed source archive. We therefore claim only the observed ordering: the exit notification arrived before a lower-sequence output notification. We do not attribute this to a specific native concurrency mechanism or claim that arbitrary response permutations are valid.

## Bounded prospective acceptance

Retain the exact capture ledger in its original arrival order and require all existing schema, hash-chain, unique request/process/tool identity, cwd/argv, one app completion, successful native/app exit, delivery receipt, unredacted original/retained bytes, blob identity, UTF-8, empty stderr and terminal capture checks.

For the process messages, require integer sequence values covering exactly1..N with no duplicate, gap, Boolean or extra member. There must be exactly one successful exit notification and exactly one closure; closure must remain the last received process message and carry sequenceN. Require every output notification's sequence to increase strictly in actual arrival order. Concatenate stdout and stderr only in that unchanged arrival order. The only permitted disagreement with globally increasing native sequence order is the sole exit notification appearing before or after output notifications. Never sort output chunks, repair missing bytes, substitute the app aggregate, combine connections, tolerate a failure, or allow output after closure.

A proof records the actual process sequence order, output sequence order, closure sequence and whether the exit notification was interleaved out of native sequence. It preserves the separate app-projection equality observation. Successful source delivery is not proof of model attention or an app acknowledgment. The existing finite literal-read grammar and protected live-identity matching are unchanged.

## Verification and adoption

Tests must preserve ordinary streams and exit-before-drain behavior, accept only the declared exit-notification interleaving, and reject reordered output, gaps, duplicate/Boolean sequences, nonterminal/duplicate/missing closure, duplicate or failed exit, missing delivery, altered/redacted blobs, nonempty stderr, wrong identities and malformed captures. Diagnostic replay may demonstrate the candidate proof on smoke006 without rerunning or overwriting its original assessor/verdict.

After code and tests settle, freeze a new source-bound anchor with this method. Retain the test receipt, run a fresh no-model host diagnostic and fresh no-model transport probe, then all five fresh final qualifiers: native references, isolated boundary/lifecycle, actual-model interruption/resume smoke and one pilot per family. Bind the method, original diagnosis and completed qualification lineage in the final certificate. No earlier passing revision substitutes for that complete lineage. No unchanged success-seeking retry is authorized.
