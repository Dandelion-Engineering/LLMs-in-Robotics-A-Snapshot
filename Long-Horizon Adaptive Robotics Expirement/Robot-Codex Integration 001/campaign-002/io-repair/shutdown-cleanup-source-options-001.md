# Native cleanup source options: bounded review 001

2026-09-28. Source inspection only. Smoke016 remains failed, unassessed, and task unknown; its rejected stream ID/RPC and 222-byte read contents were not retained. The separate dev055 diagnostic was running during this review, and none of its outputs were read. No source, launch, acceptance rule, or historical verdict was changed.

## Observed source behavior

All source identities below match their retained upstream receipts for `rust-v0.157.1`. This is not installed-binary build correspondence or a demonstrated explanation of Smoke016.

The proto (`60–64`, `185–195`) defines unary cleanup messages with only these string fields:

| RPC | Exact request shape | Retained host behavior |
| --- | --- | --- |
| CloseSession | session_id, field 1 | Existing UUID/session is removed, then shutdown is awaited (host session 157–181). |
| Terminate | session_id, field 1; cell_id, field 2 | Existing session lookup followed by runtime termination (host handlers 267–279; session 257–266). |
| CancelWait | session_id, field 1; wait_id, field 2 | Existing session lookup followed by cancel_wait (handlers 256–264); its internal waits implementation is not in the reviewed packet. |

None of those request messages accepts source code or tool arguments. Native operation Drop paths schedule Terminate (`operations` 38–64,311–322) and CancelWait (405–440). Native gRPC session Drop requests shutdown (241–243); drive_shutdown sends CloseSession, then closes local state and joins stream tasks (324–348). These are plausible fresh request-stream producers during interruption, not an identification of the historical request.

The OpenSession response is a lease (proto 9–11). Host event-stream loss triggers close_lease and session.shutdown (host session 131–181), which cancels waits, clears pending invocations/subscriptions, awaits runtime shutdown, closes events, and clears cells (237–254). No exposed native client API was established for selectively closing this lease.

## Lifecycle acknowledgment trace and gaps

`thread/unsubscribe` and `turn/interrupt` are exposed request names (protocol common 579–582,1050–1053). Their request-handler implementations are absent from this retained packet, so exposure is distinct from a fully traced implementation.

The retained thread listener unloads an unsubscribed thread only after its unloading-state predicate holds and agent status is not Running (thread_lifecycle 363–394). The unloading helper cancels pending callbacks, removes listener state, and awaits shutdown with a **10-second timeout** (408–435). It sends `thread/closed` only on Complete and only if the same runtime is successfully removed (436–456). Timeout logs a warning and leaves the thread loaded (463–465). This event is stronger lifecycle evidence than an unsubscribe reply, but its complete core cleanup dependency is not established here.

Core SessionIo.shutdown_and_wait submits Op::Shutdown and awaits session_loop_termination (core session 1048–1056). That future wraps the submission-loop task (932–943), but deliberately discards the join result (`let _ = handle.await`,1127–1134). Loop termination is therefore not proof of successful cleanup. The submission_loop/Shutdown handler and CodexThread forwarding are absent from the reviewed packet. CodeModeService.shutdown itself cancels new initialization, joins any existing initialization, and awaits session.shutdown (code-mode service 174–188); the missing link is whether core shutdown always joins this method before completion.

Pending `turn/interrupt` responses are sent on **either** TurnAborted or TurnComplete, before the corresponding turn/completed notification (event handling 185–200,1203–1219,1556–1568). These replies acknowledge a terminal turn event, not codehost closure. Core interrupt_task awaits abort_all_tasks (core session 4947–4953), but its implementation is absent. CodeModeService.interrupt_active_cells joins terminate calls while logging and swallowing each termination error (157–171); its call ordering relative to TurnAborted is not established here. Neither turn acknowledgment proves remote session/transport quiescence.

Native gRPC requests have a retained **60-second transport timeout**, added to runtime_timeout (deadline 7,55–66). This is a source-local bound, not a proposed change to the existing client or bridge bounds; it does not fit automatically within an outer 10-second shutdown wait.

## Options and limitations

1. Instrumentation-only diagnostic: retain fixed rejection-frame metadata while preserving rejection. This identifies structural new-ID versus reused-ID cases, but cannot establish RPC semantics.
2. Explicit pre-close lifecycle ordering: interruption followed by confirmed thread closure is a candidate to investigate. The missing shutdown joins, swallowed join errors, installed-binary correspondence, and actual transport behavior prevent treating it as an established safe repair.
3. Semantic cleanup-only gate: the request shapes are small, but HTTP/2 frame metadata cannot identify methods or existing IDs. This would require transient HPACK header and framed-protobuf interpretation plus existing-ID provenance; raw content need not be retained, but metadata/hash-only records cannot independently replay the semantic decision. Allowing opaque new HEADERS is unsupported. No expanded acceptance is designed or adopted here.

Project-venv distribution metadata inspection found no installed h2, hpack, hyperframe, protobuf, grpcio, or grpcio-tools. This is scoped to the current project interpreter; no installs or other-runtime searches occurred. Thread/start-only metadata preflight does not exercise an opened native code-mode session. Direct command/exec runs sandbox/pipe subprocesses (command_exec 203–205,270–285). The native logical session remains New until an operation obtains a connection; shutdown of New closes locally (remote_session 239–249,253–276,285–327,399–401). No supported exposed no-model path reproducing this native teardown was established.

## Exact retained input identities

Each link resolves to the original local file; line references above use its UTF-8 physical lines. Bytes and SHA256 below were verified in this review against the linked existing source receipt.

| Source | Bytes | SHA256 | Existing receipt |
| --- | ---: | --- | --- |
| [proto](native-output-source-001/codex-rs__code-mode-protocol__src__grpc__codex.code_mode.v1.proto) | 6699 | `406d8f47d8d0b95a9d4ae104890e5e52764c9597e9271f75ff434a4ce24748d0` | [source-evidence-003.json](native-output-source-001/source-evidence-003.json) |
| [native gRPC session](codehost-channel-source-001/codex-rs__code-mode__src__grpc_session__mod.rs) | 12284 | `28aa4d341828b886b24756008f2039e029511922213763555ed0b993fcc965d6` | [source-evidence.json](codehost-channel-source-001/source-evidence.json) |
| [native operation drops](native-output-source-002/codex-rs__code-mode__src__grpc_session__operations.rs) | 15648 | `5d3798e40862a9c536c1d1d3283423eafc812c88963e4c42d959841cf5dff26a` | [source-evidence-003.json](native-output-source-002/source-evidence-003.json) |
| [native process session](codehost-channel-source-001/codex-rs__code-mode__src__remote_session.rs) | 18751 | `987ff29ed4b3978c482cd2616aeeef75ac1cec561912a49a4220f63efba8d244` | [source-evidence.json](codehost-channel-source-001/source-evidence.json) |
| [host session](codehost-channel-source-001/codex-rs__code-mode-host__src__grpc__session.rs) | 15294 | `30be8c6b41293ebc787caaf281c8fabc2172c42b9974563bf0e53fdfa787962c` | [source-evidence-002.json](codehost-channel-source-001/source-evidence-002.json) |
| [host RPC handlers](codehost-channel-source-001/codex-rs__code-mode-host__src__grpc__mod.rs) | 15779 | `16d0f85d3f8c1100aa0c2f5232a940cee4e1dffe4f21d2cf504611b577f3107e` | [source-evidence-002.json](codehost-channel-source-001/source-evidence-002.json) |
| [core code-mode service](native-output-source-002/codex-rs__core__src__tools__code_mode__mod.rs) | 19667 | `13b5bda6e93a65fe999a3f07b3c5ee4a05850bfca57e4090876d70b310d8ba9e` | [source-evidence-002.json](native-output-source-002/source-evidence-002.json) |
| [core session loop endpoint](native-output-source-002/codex-rs__core__src__session__mod.rs) | 205816 | `52f7d89d8ec2861850b17c4c21fdde295bdf35473efe11821af86432b61e651b` | [source-evidence-009.json](native-output-source-002/source-evidence-009.json) |
| [app-server event handling](native-output-source-002/codex-rs__app-server__src__bespoke_event_handling.rs) | 154786 | `e379140cecf3812c9495d744c3a4a9e49a84fe1773b0f0979b7affe51f482239` | [source-evidence.json](native-output-source-002/source-evidence.json) |
| [thread lifecycle](native-output-source-002/codex-rs__app-server__src__request_processors__thread_lifecycle.rs) | 34305 | `204a9b470a4ee86fbc7cdbc6737291a8dea678c562220153df4ccd57f4545ea4` | [source-evidence-003.json](native-output-source-002/source-evidence-003.json) |
| [app-server protocol](native-output-source-002/codex-rs__app-server-protocol__src__protocol__common.rs) | 173236 | `27fe9ee0a155ee1e5f59860869277fd7179f22e151a38326738396b60d97ebea` | [source-evidence-011.json](native-output-source-002/source-evidence-011.json) |
| [direct command execution](native-output-source-001/codex-rs__app-server__src__command_exec.rs) | 38308 | `73015751277a57d978d44dc047ff365858b5db1992d7405e49531372ea781057` | [source-evidence.json](native-output-source-001/source-evidence.json) |
| [gRPC deadline](codehost-channel-source-001/codex-rs__code-mode__src__grpc_session__deadline.rs) | 2306 | `1109f941047ccd366d88877106b30a6427b790bf2da778aa40bc92a75a6cb504` | [source-evidence-002.json](codehost-channel-source-001/source-evidence-002.json) |
