# Code-mode channel lifecycle: source-only investigation

The pinned upstream code supports multiple TCP connections to one code-mode host and one leased session. The current campaign bridge instead equates a TCP connection with an isolated host lifetime. Removing its `single_active_client` check alone would create multiple hosts and lose shared session identity. A bounded transport repair can retain one host/namespace and forward several independent byte streams to that same host, without replaying gRPC calls.

This is source inspection, not an empirical reproduction or installed-build attestation. No native executable, model, simulation, or test workload was launched. Smoke009 observations supplied by the parent were not independently read or analyzed here. Its cause and all original verdicts remain unchanged.

## Retained sources and identity

`source-evidence.json` through `source-evidence-003.json` bind official `openai/codex` files retrieved from tag `rust-v0.157.1`, plus the complete Git tree listing, Apache license and NOTICE. `source-evidence-004.json` binds official reqwest 0.12.28 and hyper-util 0.1.20 crate archives; both SHA-256 values were checked against the retained tag's Cargo.lock before selected sources and licenses were copied. No archive code was executed. `analysis.json` binds these receipts and all source files cited below, including the local bridge/relay inspected.

The native tag and dependency checksums identify source bytes. They do not establish that the installed Windows app-server or Linux code-mode-host was built from these exact bytes or with these features.

## Client lifecycle and a concrete connection-expiry candidate

1. `codex-rs/code-mode/src/grpc_session/transport.rs:49–69,94–122`: the HTTP URL path caches a `GrpcClient` backed by `RouteAwareClientPool`; its service clones the pool for each request. It selects HTTP/2 prior knowledge and disables redirects. The Unix URL path uses a lazy tonic channel instead; `with_channel` is a Rust API, not a demonstrated campaign configuration switch.
2. `codex-rs/http-client/src/route_aware_client_pool.rs:47–60,454–545`: pool clones share the route-to-client cache and serialize client construction. This supports reuse but does not promise a single TCP connection forever. A changed account-bound factory, changed route, or eviction can select a different transport client; those possibilities were not observed here.
3. `codex-rs/code-mode/src/grpc_session/mod.rs:119–174,247–263`: OpenSession retains a response stream carrying the session lease; SubscribeToToolCalls creates another long-lived stream. Later operations clone the shared client while retaining the same session ID.
4. `reqwest-0.12.28/src/async_impl/client.rs:301–302,353–357,975–976`: the default pool idle timeout is 90 seconds; HTTP/2 keepalive is disabled. Codex `http-client/src/client_builder.rs:357–391` does not override these defaults.
5. `hyper-util-0.1.20/src/client/legacy/pool.rs:223–242,299–337,483–507`: an HTTP/2 shared sender remains in the pool; checkout resets its `idle_at`, and an entry is evicted when that timestamp expires. `client.rs:348–359,850–881` releases a request's pooled sender immediately for HTTP/2 rather than tying it to response-body completion. Pool expiry is therefore different from proving that every active response stream or TCP connection has ended.

Inference: a period of more than 90 seconds without a new HTTP request can expire the reusable pooled sender while the lease/subscription response streams persist. A subsequent RPC can then require a new TCP connection. This is a supported explanation for why an additional connection need not mean a new namespace or a failed old session; it is **not** proof of the observed failure's cause. A diagnostic should compare the interval with the last new request, not the last received DATA frame. Other transport events and installed-build differences remain possible.

There is also explicit **session** reconnection, which is distinct from TCP reuse: `grpc_session/reconnect.rs:123–189` checks stopped state, serializes opening, awaits previous-session shutdown and allocates a new generation. `generation.rs` fences cell IDs across generations. It does not justify replaying uncertain tool calls.

## Supported configuration limits

The inspected code-mode config resolver (`core/src/config/mod.rs:2701–2730`) exposes yield time, overhead display, tool namespace choices and disabling in-process fallback. No single-TCP or HTTP/2 keepalive setting was found there or in Codex's HTTP client builder. Reqwest has library-level pool and keepalive setters, but the inspected URL provider does not expose them through code-mode configuration.

A native patch to disable pool expiry for this transport could address this particular candidate mechanism. It would require building and attesting a changed binary and would still not make one-TCP-only a general gRPC guarantee. HTTP/2 PINGs do not, by this inspected pool implementation, establish a new request checkout or prove that an entry will remain cached. Switching endpoint/backend or adding application requests solely to prevent expiry is not a demonstrated supported production fix and could change the experiment's configuration or traffic.

## One host can serve multiple channels without namespace duplication

`code-mode-host/src/grpc_transport.rs:35–57` constructs one `GrpcCodeModeHost` before serving the incoming TCP listener. `grpc/mod.rs:46–57` puts shared host state in an Arc. `grpc/session.rs:39–54,105–154` stores sessions in a host-wide UUID map and resolves later requests by session ID; it does not create a new runtime merely because a new TCP connection arrives.

The lease is meaningful: `grpc/session.rs:131–142,168–182` shuts a session down when its OpenSession stream disappears. `grpc/routing.rs:53–84` closes a session if a lost subscription has unresolved callbacks, explicitly avoiding replay. `grpc/mod.rs:130–152` resolves Execute by session ID and reserves execution identity before running it. `grpc/session.rs:269–287` rejects reused execution IDs within its bounded history; `grpc/routing.rs:214–234` resolves a callback once and handles a remembered duplicate completion without redispatch. These bounded guards are not an unlimited exactly-once guarantee and do not authorize bridge retries.

Current campaign mismatch: `harness/codehost_bridge_v2.py:116–150` denies another active connection and otherwise starts a namespace child per accepted connection. `codehost_inside_v2.py:217–232` starts one host and opens one socket to it. A permissive connection check alone would produce separate host state; calls using the original session ID would not reach its runtime.

## Bounded repair path and validation

Preferred apparatus candidate: start one isolated namespace and one code-mode-host for the invocation. Retain the unchanged private gateway and authority/canary boundary. Attach a bounded number of independent outer TCP channels to separate sockets on that **same** host. A trusted framed relay can carry channel-open, bytes, directional EOF and errors over the existing private owner transport. Do not concatenate independent HTTP/2 connections into one raw stream, rewrite H2/gRPC payloads, retry operations, or create new sessions on behalf of the native client.

The relay needs explicit channel identity, strict frame/byte/queue/concurrency bounds, per-channel backpressure, no channel-ID reuse, correct half-close semantics, and an owner-control lifetime independent of any one socket. Namespace child failure, malformed framing and bound overflow remain fail-closed. Owner shutdown closes all channels, joins all relay tasks, records actual child status and retires the one namespace. Per-channel transport receipts and the host-wide owner receipt must remain distinct. Existing rules that interpret any pre-owner channel EOF as whole-host failure need an explicitly declared replacement contract; their old evidence must remain unchanged.

Required bounded no-model checks before use:

- Open one native session on channel A; subscribe on A; invoke/complete/wait using B while A stays open. Verify session identity and one host/namespace, and preserve exact callback/response identities without replay.
- Keep lease/subscription streams open through a declared idle interval beyond 90 seconds, then make a fixed harmless request through the real URL provider if a supported no-inference driver exists. Record actual connection count; a generic second-socket test alone does not reproduce the native pool path.
- Close an auxiliary channel without terminating the host or inventing an RPC result; separately lose the lease/subscription with an outstanding operation and require honest failure/unknown handling without retries.
- Verify duplicate IDs, concurrent opens, foreign/unknown session IDs, truncated/oversized frames, slow channels, global and per-channel bounds, partial startup, child exit and owner cancellation/cleanup. Re-run all isolation canaries and lifecycle/evidence checks under a fresh source anchor.

No production repair has been implemented or qualified by this packet.
