# Local socket closure: source-only review

Prepared 2026-09-29T05:42:37.763215+00:00. This review inspected current source only. It did not read or hash old run outputs, execute a fixture, invoke a model/native service, or reassess an attempt. The bridge source is the instrumented version identified below; the immutable Smoke026 verdict and unresolved OS cause are unchanged.

## Finding

The reviewed control flow does **not** provide an ordinary same-channel path that explicitly closes the bridge's accepted local socket while its upload read is still running, then produces that upload task's first error. The only explicit accepted-socket close is `writer.close()` in `Bridge.handle`'s `finally`; it follows cancellation of unfinished upload/sink tasks and an awaited `gather(..., return_exceptions=True)`. A task must have terminated before that close is reached. This is a source-order statement, not proof of the original runtime's kernel state or chronological cause.

Local socket closure without a preceding bridge failure is possible during normal completed-channel cleanup, and handler cancellation can also enter cleanup without logging `channel_CancelledError`. Neither route reverses that cancel/join-before-close ordering. Overlapped-operation cancellation is a distinct action from closing the socket handle.

## Ownership and close sites

| Owner/path | Resource affected | Ordering and qualification consequence |
|---|---|---|
| `SocketWriter.close`, bridge line51 | The accepted Python socket shared with `SocketReader` | Calls only `self.sock.close()`. `wait_closed` at52 is a no-op and supplies no kernel completion evidence. |
| `Bridge.handle`,635–695 | That channel's accepted local socket | The sole call site at692. For an admitted channel,687–691 cancels unfinished upload/sink tasks, awaits both, and retrieves completed futures first. Admission rejection also closes here, but no upload task exists in that branch. |
| `SocketServer.close`,77; `begin_finish`,373–398 | The listening socket and accept task | This is a different socket from each `sock_accept` result (67–73). It stops admission and does not call accepted writers. It does not itself manufacture client EOF. |
| `Bridge.run`,779–813 | Handler tasks, namespace subprocess stdin/process | Normal drain waits for genuine upload EOF; a caught drain error is recorded at798 before global handler cancellation at801. It then awaits the handlers, whose cleanup owns the accepted-socket close. Closing namespace stdin and namespace retirement affect separate resources. |
| Linux `Relay.close_channel`,315–359 | The Linux socket to the single native code host | Cancels/awaits its own tasks and closes its own writer, then sends a CLOSED frame. This is neither the Windows accepted socket nor the native app-server peer socket. |
| Bootstrap `Client`,112–120; `native_quiescence.Controller.run`,280–344 | Native app-server subprocess/job and stdin pipe | These paths can initiate native peer shutdown, but never receive the bridge's accepted Python socket object. A peer closure is not a bridge-local `SocketWriter.close`. |
| `Runtime.close`,409–431 | Mirror thread, broker stdin/process, synthetic gateway/owner and canary | No bridge-channel socket reference is supplied to this function. `Runtime.model`,394–407 awaits the bridge wrapping the native callback; outer cleanup runs later. |
| `codehost_owner.OwnerRegistry` | Process and TCP ownership metadata | It authenticates ownership; it contains no socket-close operation. |

## Normal and failure ordering

1. **First upload failure:** the actual reader await is at bridge580. The new diagnostic catches an `OSError` at581–583 and rethrows it. `handle` awaits an already-completed upload task at670–675, records a non-cancellation channel failure at684, and only then reaches its finally/cancel/join/close sequence. An explicit close at692 cannot be the preceding action on this route.
2. **Normal channel completion:** `sink` resolves `channel.closed` only after the namespace receipt and byte/H2 checks (601–629). A supported Linux clean-idle closure waits for authenticated upload HALF_CLOSE and the queued upload to drain before sending CLOSED (inside301–307). Qualified owner-finish closure likewise requires upload EOF/drain (inside337–350). The Windows owner-finish path independently waits for upload tasks and genuine EOF before seal (bridge413–439). Those normal source paths provide no permission to close an outstanding upload early.
3. **Other failures:** receive-loop failure records `frame_read_*` before setting channel futures exceptional (bridge540–547); sink failure records `channel_sink_*` before setting `channel.closed` exceptional (630–633). A drain timeout/error is latched before global handler cancellation (798–802). Their later closes are cleanup consequences, not evidence that local close preceded the first failure.
4. **Cancellation caveat:** direct handler cancellation is exempt from `channel_*` failure logging (677–684), so absence of a previous failure record alone does not prove absence of cancellation. It still cancels and awaits its child tasks before closing the local socket. If a second cancellation interrupts that awaited cleanup, source execution may leave cleanup incomplete; that is not a demonstrated close-before-read-error path. OS/process teardown and external socket/handle manipulation are outside this source-only enumeration.

## Native peer and asyncio limits

The bootstrap passes only native process identity and a cleanup-barrier callback into the bridge (bootstrap299–307; runtime401–405). `native_quiescence` sends `turn/interrupt` / `thread/unsubscribe` through native stdin after its source-bound barrier (193–214), records finishing, and closes native stdin before waiting for exit (288–303). A normally exited native process can therefore release its own peer sockets without a previous bridge failure. The fallback kill-on-close job is assigned to the native subprocess, not the parent Python bridge (launcher200–241; bootstrap112–119). None of these facts identifies how the native implementation or Windows released a particular connection.

Installed Python's `_OverlappedFuture.cancel` explicitly cancels the overlapped operation (`windows_events.py`,49–86). `finish_socket_func`,459–468 maps both `ERROR_NETNAME_DELETED` and `ERROR_OPERATION_ABORTED` to `ConnectionResetError(*exc.args)`. That source warns against identifying an OS cause from a high-level exception class alone; it does not say which case occurred in Smoke026. Explicit asyncio cancellation, peer shutdown, accepted-socket close, listener close, and process retirement must remain separate observations.

## Interpretation boundary

The original same-timestamp observations cited in the task do not establish cross-thread order. This review neither resolves their ordering nor infers a missing EOF, syscall error number, native RPC identity, packet loss or native bug. The source ordering narrows one hypothesis: ordinary bridge accepted-socket cleanup does not overtake its own upload task. The planned loopback matrix can characterize controlled adapter outcomes; it cannot recreate the hidden native cause. A later instrumented failure's operation/channel/error codes would provide additional evidence, but remain distinct from causal proof.

## Reviewed source identities

Hashes bind only files read in this source review; they are not a claim that all were executed in a historical attempt.

| File | SHA256 | Bytes |
|---|---|---:|
| `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/codehost_bridge_v3.py` | `419c13a6761fa23bed0a06b540ffba3f327a2d86ff94ad55e1c9b8ece16b0a75` | 56272 |
| `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/codehost_inside_v3.py` | `9032e9317bf9eb5eb878213dd3c902de93c46f4d67e965fc000a023bb328ffed` | 34005 |
| `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/runtime.py` | `80b393d8f539e91bb7c202478372aa212274cc3773307efbc5e5fe3faf378bd5` | 28853 |
| `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/bootstrap_client_v4.py` | `a08f0b820c5ce30c0a68bc8ea7fc19102b29834a6b9b0dd447157568060706ad` | 23326 |
| `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/native_quiescence.py` | `d51e7ead1c6a3101cc0233e142d1669927f7de26aca2c2f572ec17dbc6d7fd00` | 18764 |
| `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/transport_stderr.py` | `29920d4d46d147dbb9726b691dc729ce95de573e6e3e1e12065d04611efcb29f` | 2204 |
| `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/codehost_owner.py` | `fc26b1b4cd2a1f7de81445378cbb75493f14dca922f66bf2727d380fc8f8d23c` | 9410 |
| `Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/launch/robot_codex_launcher.py` | `a78ee81e797e4dd3f4f6fddf6192fde8aa220b37d865d89be0bacdfe1b3cb905` | 36093 |
| `C:\Users\cresp\AppData\Local\Programs\Python\Python312\Lib\asyncio\windows_events.py` | `0f94acdfd79706099961bb265a0e6431e744234cac3f572209a1653a5321fda7` | 33488 |
