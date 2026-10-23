# Smoke026 socket-abort reference — diagnostic context only

Primary Microsoft documentation checked 2026-09-29UTC:

- [Windows Sockets error codes](https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-error-codes-2) distinguishes a software-caused connection abort from orderly completion.
- [Graceful shutdown, linger options and socket closure](https://learn.microsoft.com/en-us/windows/win32/winsock/graceful-shutdown-linger-options-and-socket-closure-2) distinguishes graceful from abortive shutdown and describes shutdown before final socket closure.
- [closesocket](https://learn.microsoft.com/en-us/windows/win32/api/winsock/nf-winsock-closesocket) documents that closure options affect shutdown behavior and that callers should arrange send/receive completion explicitly.

These sources explain general API semantics; they do not establish Smoke026's missing numeric OS error, exact call stack, unobserved bytes or native-client closure cause. The retained exception class alone must not be expanded into a fabricated errno or benign EOF. All observed byte equality is weaker than complete end-of-stream evidence. No assessor, protocol acceptance or original verdict changed from consulting these references. No endpoint or security settings were modified.
