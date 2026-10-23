# Shutdown interpretation limits

Primary documentation checked September 29, 2026:

- Microsoft's [graceful shutdown description](https://learn.microsoft.com/en-us/windows/win32/winsock/graceful-shutdown-linger-options-and-socket-closure-2) distinguishes orderly shutdown from handle deallocation and describes explicit send shutdown followed by draining remaining peer data. A returned close call alone does not establish completed delivery.
- The [closesocket reference](https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-closesocket) explains that outstanding operations may complete after the call returns, and describes separate abortive and graceful linger behavior. These are operating-system semantics, not proof of which path the installed native client took.
- The current [OpenAI App Server documentation](https://learn.chatgpt.com/docs/app-server) describes thread unsubscribe/unload notifications. It does not promise an orderly TCP FIN at `thread/closed`. Its current inactivity default is not substituted for this project's pinned zero-delay unload configuration.

The retained native tag source describes session close and task joins but is not installed-binary build attestation. High-resolution observations can establish sampling order around the actual stdin-close call; a later socket error is not by itself proof that stdin closure caused it. Genuine EOF, exact forwarded bytes, protected cleanup, and independent qualification remain separate evidence requirements.
