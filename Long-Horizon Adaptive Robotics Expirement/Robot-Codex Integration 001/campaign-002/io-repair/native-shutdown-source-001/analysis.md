# Targeted shutdown join source check

2026-09-28. Additive follow-up to [review 001](../shutdown-cleanup-source-options-001.md); the earlier review remains unchanged. Only the two concrete missing upstream files were fetched from OpenAI's `rust-v0.157.1` tag. [URL, tag, byte and SHA256 receipt](source-evidence.json). No installed-binary correspondence, execution, acceptance change, or diagnostic outcome claim.

The normal shutdown path **joins a code-mode cleanup attempt**, but does not require that attempt to succeed:

1. [CodexThread](codex-rs__core__src__codex_thread.rs),253–254 forwards shutdown_and_wait to SessionIo.
2. Retained [SessionIo](../native-output-source-002/codex-rs__core__src__session__mod.rs),1048–1056 submits Shutdown and waits for session-loop termination.
3. [submission_loop](codex-rs__core__src__session__handlers.rs),592 awaits shutdown;329–330 awaits shutdown_session_runtime.
4. That helper first aborts outstanding tasks and terminates unified-exec processes, then **awaits code_mode_service.shutdown** (286–305). On error it logs a warning and continues (304–306). Retained [CodeModeService](../native-output-source-002/codex-rs__core__src__tools__code_mode__mod.rs),174–188 joins session initialization and awaits remote-session shutdown.
5. The handler emits ShutdownComplete only after the cleanup helper and persistence shutdown (329–371), returns true, and the loop exits (604–610). The same cleanup helper is awaited when the submission channel closes without a Shutdown operation (612–621).
6. Retained [thread lifecycle](../native-output-source-002/codex-rs__app-server__src__request_processors__thread_lifecycle.rs),408–456 wraps shutdown_and_wait in a ten-second timeout, then sends thread/closed after Complete and removal of the matching runtime. Timeout leaves the thread loaded (463–465).

Two independent limitations remain: the cleanup helper discards a code-mode shutdown error; SessionIo's completion adapter discards the task JoinHandle result (core session1127–1134). Therefore thread/closed can acknowledge the normal attempted-cleanup barrier without proving successful remote session closure, and it does not distinguish a task-join failure. Ordinary successful control flow joins the method; universal successful transport retirement is not established.

This makes explicit lifecycle ordering a more concrete candidate than before, but not an adopted repair. The retained packet still lacks the exposed thread/unsubscribe request handler, precise turn-abort-to-cell-cleanup ordering, and installed-binary correspondence. Existing turn/interrupt replies are sent on either TurnComplete or TurnAborted before turn/completed; neither is a stronger closure acknowledgment. Any eventual use would still need the existing independently retained transport/EOF/authority/retirement gates, and no new streams could be excused after the declared closing frontier merely because a lifecycle reply arrived.

Exact newly retained identities:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| [codex_thread.rs](codex-rs__core__src__codex_thread.rs) | 40082 | `be366b68df12621ea52e742c217dfa596858e11b62e50067f198dbecd25b52b0` |
| [session/handlers.rs](codex-rs__core__src__session__handlers.rs) | 24394 | `bad0cef6441ccd2505400d5bd4b1c93285202c5aa4ca64c3e2a996c2a64e5bf3` |
