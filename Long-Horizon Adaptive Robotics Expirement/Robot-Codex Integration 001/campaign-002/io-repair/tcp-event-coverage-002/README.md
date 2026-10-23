# Process-scoped ETW attempt — failed, preserved

Randy approved bounded process scope in the Codex task, including non-loopback
IP addresses and ports belonging to owned diagnostic processes. Packet contents
remained excluded, with the existing 16 MiB and 30-second limits.

The direct collector passed 13 local lifecycle cases, eight guards, real TDH
predicate construction for all 14 versions, and raw-QPC decoding of the prior
terminal synthetic control trace. Those checks did not establish OS coverage.
The frozen sources and tests are retained unchanged.

The one-shot UAC launch succeeded at 2026-09-30 03:56:53 UTC; the helper exited
integer 1. Windows selected LogFileMode 0x400001, adding its documented
stop-on-hybrid-shutdown behavior. The strict mode-1 guard refused before either
fixture was released. The owned session stopped after 0.0152256 seconds; both
private fixture jobs became empty and all retained handles signaled.

Independent terminal diagnosis found a second, more consequential failure:
the ETL contained eight allowed-type closure events, of which six had payload
PID 0 and two belonged to an unrelated process. The payload predicate was not
enforced despite successful TDH construction and EnableTraceEx2. This is a
failed process-scope check, not a reason to silently accept a broader trace.
The cause of the ineffective predicate is not established. Changing only the
shutdown-mode guard is insufficient; no unchanged retry was made.

The only other descriptors were the ETL header and partition metadata. No
process rundown appeared in this short direct session. This observation does
not guarantee a longer session's scope. Raw ETL and decoded endpoint values
remain outside the repository; the [failure assessment](failure-assessment-001.json)
contains counts, file hashes, bounds, and cleanup evidence only. Earlier
exact-port and netsh scope failures remain failed. No model, queue job, native
qualifier, pilot, scored slot, map or qualification-history record was changed.

Microsoft documents the automatic shutdown-mode selection in
[logging modes](https://learn.microsoft.com/en-us/windows/win32/etw/logging-mode-constants).
Its [filter reference](https://learn.microsoft.com/en-us/windows/win32/api/evntprov/ns-evntprov-event_filter_descriptor)
also distinguishes payload predicates from generic PID scope filters; the
latter do not enable kernel-driver registrations. Neither a successful API
return nor a constructed predicate proves this provider's effective scope.

The next prepared option is a separate, explicitly declared host-scope closure
metadata diagnostic. It requires a new privacy-scope decision; it is not
authorized by the existing owned-process approval.
