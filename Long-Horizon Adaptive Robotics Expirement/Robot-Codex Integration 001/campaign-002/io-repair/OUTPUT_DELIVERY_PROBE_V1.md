# Bounded output-delivery diagnostic, version 1

Declared prospectively after smoke008's retained startup-read failure and before implementing or running this diagnostic. This is development infrastructure evidence under Randy's September 27 continuation. It does not repair, reinterpret, or replace smoke008, and it does not qualify a model path.

## Question and fixed scope

Does the installed native app server preserve complete stdout/stderr from the existing isolated remote executor through standalone `command/exec`, for immediate and deliberately separated output, in streaming and buffered modes? Smoke008 delivered 13,029 Tools.md bytes to the app server but retained only the last 4,837 bytes in the public projection. The unique cause is unknown; send completion is not application consumption or model attention.

Use the current Runtime namespace, capture bridge, immutable native executable, strict configuration and boundary canaries. A diagnostic child may set `CODEX_EXEC_SERVER_URL` to that fixture's private URL solely to select its default remote environment. Production bootstrap configuration remains unchanged. Prove the remote route by an exact captured process/start argv/cwd match, start response, native process identity and complete output/exit/closed lifecycle; no local fallback counts. No model thread/turn, ChatGPT inference, robot command, physical simulation or policy change is allowed. Reject any attempt to invoke thread/start or turn/start.

Exactly six serial cases are planned, once each, with unique fixed markers in producer argv: immediate streaming; separated streaming; immediate buffered; separated buffered; empty streaming; mixed stdout/stderr streaming. Each nonempty stdout is exactly 13,029 deterministic ASCII bytes, written as 8,192 and 4,837 bytes. Separated cases insert 100 ms between writes; this is a diagnostic contrast, never a production delay workaround. Mixed stderr is a separate fixed 257-byte payload. No success-seeking retries, variant search, or output substitution. Buffered and streaming are separate public protocol behaviors; streaming final replies need not repeat deltas.

## Bounds, parity and failure behavior

Use a 65,536-byte explicit command output cap, a 10-second command timeout and a 120-second whole diagnostic limit. Expected total stdout/stderr is below 80 KiB. Preserve existing 64 MiB invocation capture ceiling and capability redaction. Use an isolated `/usr/bin/python3 -I -B -c` producer with no filesystem/network access, stdin interaction, inherited shell or dynamic code from output. It is harmless if misrouted to the Windows host because the absolute POSIX interpreter is absent, but such a run still fails route admission.

For each case require expected bytes = authenticated executor bytes = decoded public bytes, exit integer zero, no output cap/truncation, matching exclusive request/process identity, no duplicate or missing native sequence, complete delivery and closed lifecycle. Keep stdout/stderr separate. Independently preserve the original response bytes, output deltas and response envelope. Bind the connection-scoped app process ID to the native PID through unique argv, request/response and serial case interval; do not assume these IDs equal. Exact source and binary bindings are required before launch. Disallow unexpected extra process/start calls after initialization and any thread/turn/model traffic.

Retain failures honestly. Missing fields, ambiguous identity, queue failure, drift, timeout, bridge failure, partial constructor or cleanup failures must not become pass. Run synchronous native Client work off the bridge event loop. Close the client inside its worker, retire the executor and close the Runtime even after exceptions. No reconnect or replay is part of this probe.

Implement deterministic negative tests for wrong route, missing first output, duplicate sequence/delta, stdout/stderr confusion, false/noninteger exit status, cap reached, unexpected model method, source drift and cleanup on failure. Freeze a new source-bound development revision and submit once through the shared compute queue. Read empirical output only after fresh official succeeded with integer exit zero. Preserve original failed attempts and all protected sources.

## Claims and next decision

A pass establishes only this standalone app-server remote output path for these six cases. It does not validate the model unified_exec/code-mode subscriber or identify smoke008's cause. A gap locates another observable boundary but is not causal attribution by itself. Any production repair requires a separately declared ordering, parity and failure contract, meaningful tests and a new complete final qualification. Never fill missing public bytes from executor capture, loosen the startup criterion, change instructions or infer a model read from send completion.
