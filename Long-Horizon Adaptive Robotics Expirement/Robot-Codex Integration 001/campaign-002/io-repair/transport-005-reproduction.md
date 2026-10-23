# Prospective transport status and EOF correction

This is engineering evidence, not a retrospective qualification or a causal explanation of smoke005. Its official queue attempt failed; that failure and unknown task outcome remain unchanged.

## Reproduced original defects

`transport-005-reproduction.json` was created before the repair. It retains the exact original source hashes, the complete synthetic reproduction source and its hash, and both actual reproduction results.

1. Executing the original `inside.py` codehost AST branch with a synthetic child exit17 returned normally. That branch ignored the child return code, unlike the executor branch.
2. Running the original codehost bridge against a fake process and an actual local TCP client accepted a clean early EOF while `client_finishing` was false. Its callback returned, the abort flag remained unset, and its receipt reported no pump errors and exit0.

Neither reproduction used a model, WSL namespace, physics or robot action. The receipt does not identify which mechanism, if either, occurred in smoke005. That attempt's stderr text was not retained and its codehost receipt lacks closure chronology.

## Additive correction

The new entry reuses the original namespace validation, resource limits, identity handling and command. For codehost mode alone, it substitutes the source of the exact read-only `/inside.py` mount. The gateway handler/server class ASTs remain identical. Original executor/canary modes and all original files remain untouched.

The new bridge records a bounded, fsynced, hash-chained lifecycle ledger with timestamps, pump identity, close reason, contemporaneous owner-finishing state, per-connection source identities, namespace status and retirement bindings. It records the existing single-client policy's denied connections. Unexpected EOF/error/nonzero or incomplete status/drain/retirement fails closed. Later owner shutdown cannot legitimize an earlier unexpected EOF.

The wrapper separates the codehost child's stdout/stderr into private pipes. Child-controlled diagnostics become bounded byte counts and hashes, never raw lines on the wrapper status channel. Status-shaped child output cannot forge namespace records. Child exit status and deliberate termination are distinguished.

For graceful HTTP/2 shutdown that precedes TCP FIN, the wrapper exposes channel EOF and permits at most0.5 seconds for the trusted parent's stdin-close handshake. The parent still requires its durable finishing marker to precede the first EOF. This does not extend model/physics timeouts or make an unexpected disconnect successful.

## Validation and remaining gate

`test_codehost_transport_v2.py` includes the original reproductions and deterministic negative tests for early EOF, later finishing, nonzero/missing status, bounded metadata, concurrent-client denial, child-log spoofing, source-bind equivalence and unchanged gateway classes. It retains distinct proof of normal owner shutdown.

`codehost_probe.py` is prepared for a separately queued, source-bound no-model diagnostic. It will run two fresh actual isolated fixtures: normal FIN and intentional TCP RST, each following the original canaries and a two-second idle HTTP/2 PING. It independently verifies the new lifecycle receipts and namespace retirement. No real probe was launched by this implementation task.

The original boundary suite's legacy H2 bridge test exercises the final namespace entry but does not by itself validate the new Windows bridge. The mandatory new transport probe and subsequent complete fresh model qualification cover that new path. No scored admission follows from these synthetic tests alone.
