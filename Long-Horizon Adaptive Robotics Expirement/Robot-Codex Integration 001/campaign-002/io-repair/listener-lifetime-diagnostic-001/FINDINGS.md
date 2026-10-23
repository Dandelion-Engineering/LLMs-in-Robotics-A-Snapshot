# Listener lifetime observations

All four one-shot cases completed with source identities unchanged and owned sockets/tasks cleaned up. Closing the real production listener, or cancelling its pending accept while retaining the listener, left the accepted read pending. The peer's subsequent tail was received exactly and genuine EOF followed. An ordinary peer close with 4096 unread download bytes produced `ConnectionResetError(errno=22, winerror=64)`; explicit peer SHUT_WR followed by exact download drain produced genuine EOF. No listener error was recorded.

Protocol deviation: the declared tail was 17 bytes, but the literal `fixed-tail-0000001` is 18 bytes. The two tail cases actually transferred 4114 bytes (4096 + 18), as the retained observations correctly report. This is not a fully conforming execution of the declared byte count and is not promoted to a qualification. No retry occurred. The accepted-channel survival and typed-error observations remain exploratory local evidence; they do not prove Smoke026's unknown cause.

The earlier four-case fixture closed its listener before active accepted traffic; this matrix supplied the missing listener-lifetime observation. No supported listener-close repair was found. Next useful evidence is higher-resolution native lifecycle order around the original stdin-close call and the actual socket error, preserving the error and genuine-EOF gate. Native003 never reached the prescribed trigger because of the service limit; its failed verdict remains unchanged.

Sources and exact observations are in [execution-001/result.json](execution-001/result.json). No model, native client, namespace, physics, or scored attempt ran.
