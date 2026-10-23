# Bounded graceful process-drain comparison

Diagnostic005 establishes a native pre-exit drain timeout before the observed
reset. It does not establish the cause of Smoke027's earlier10053. The retained
source creates a shared code-mode provider at app-server scope, caches its HTTP
client and provides session shutdown without an explicit pool-close operation.
These are source facts, not attestation of the installed executable.

Before touching production, use owned Python subprocesses and real Windows
loopback sockets to compare a held-open pooled-connection analogue under:

1. The current order: require socket EOF before closing process stdin.
2. A candidate order: retain application-completion/byte-frontier evidence,
   close process stdin normally, then join genuine socket EOF, exact terminal
   byte accounting and normal child exit inside the same five-second deadline.

The candidate does not claim drainage before process exit. Its alternative
proof must retain the exact source-bound application-completion frontier before
ordinary shutdown, plus genuine EOF and complete bytes afterward. A production
replacement therefore needs a new versioned contract and independent reader;
it cannot reuse the old pre-exit certificate or change any historical verdict.
No reset/error may become EOF; no timeout, missing byte or forced/nonzero exit
may qualify. Do not extend the original five/ten/25second limits.

Fixed cases: pooled baseline (expected timeout), pooled candidate, delayed
response tail, early genuine EOF, abortive reset, truncated upload, nonzero
child exit, and missing EOF (expected timeout). Each case is at most five
seconds of retirement plus the existing ten-second total cleanup allowance.
Synthetic bytes are fixed and hashed at both endpoints. No native app-server,
model, WSL, robot simulation, administrator launch or network peer outside
127.0.0.1 is used. These fixture results characterize only the ordering design.
They do not qualify an implementation or authorize a pass-seeking native retry.

The original code,986 dev097 inputs and prior evidence remain unchanged.
If the candidate preserves the required completion evidence in these controls,
declare a source-bound implementation and evaluate it prospectively. A genuine
evidence-contract weakness requires a director decision, not silent adoption.
