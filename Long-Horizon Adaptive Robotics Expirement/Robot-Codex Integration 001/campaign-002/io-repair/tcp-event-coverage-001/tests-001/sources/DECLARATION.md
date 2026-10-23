# Prospective no-model TCP closure-event coverage

The authorized Session17 Packet Monitor helper completed on September30 UTC.
Its two socket controls passed, but its OS trace contained only three metadata
records and no packet events. That result is inadequate and remains unchanged.
This is a distinct measurement, not a retry of that capture or of Smoke027.

Use the installed Microsoft-Windows-TCPIP provider's documented **provider-side**
filters: exact `127.0.0.1` source and destination, the freshly owned fixture's
exact `TCP.AnyPort`, and its validated `ProcessId`. The installed
[provider filter help](provider-filter-help.txt) explicitly distinguishes these
from packet-capture filters. Generic TDH address predicates failed construction
(error87); numeric ProcessId predicates succeeded. Do not substitute either a
process-only or a host-wide capture for the exact provider scope.

Collect only `ut:ClosePath` (`0x1000000000`) at level5. The retained
[schema](closepath-schema.json) contains closure/status/address/process metadata,
not application buffers. Set `capture=no`, `report=disabled`,
`correlation=disabled`, `perfMerge=no`, `persistent=no`, `overwrite=no`,
`maxSize=16`, `fileMode=single`, and a64KiB buffer. Packet payload collection is
disabled; the earlier40-byte packet-prefix allowance is not enlarged.
Start a uniquely named session and stop only that same session after verifying
its exact fresh ETL path. Never stop or alter another trace, change settings,
install a broker, or use another privilege route. At most30seconds including
startup/stop, at most16MiB ETL; any loss, overflow, missed bound, failed cleanup,
unmatched endpoint or absent control invalidates coverage.

Launch the unchanged synthetic FIN/RST fixture twice in separately owned private
jobs before capture. One is the included control; the other has a distinct PID
and port and is an exclusion control. Verify both using the existing source-bound
identity/retirement helper. Release both only after scoped trace startup and
ownership verification. Retain source bindings, command records, clock pairs,
both results, original ETL and text/statistics. Independently require the included
graceful and abortive closures to be distinguishable at their exact endpoint/time
pairs, the excluded control to be absent, and all cleanup/bounds/loss checks.
Successful collection alone is never coverage qualification.

First exercise control flow with real owned fixtures and simulated netsh
commands, including start/stop failures, interruption and foreign-session refusal.
Freeze the helper and its imports before one RunAs/UAC launch. This is an ordinary
bounded diagnostic within Randy's existing continuation authorization. If consent
is denied or times out, preserve it and stop; do not retry or change privilege
routes. No model, simulation, native qualifier, pilot or scored slot is involved.
Any later native measurement requires its own prospective scope and new identity;
any supported repair still requires complete fresh qualification before scoring.

References: installed netsh help is the host-specific authority. Microsoft's
[ETW filter documentation](https://learn.microsoft.com/en-us/windows/win32/api/evntprov/ns-evntprov-event_filter_descriptor)
and [payload predicate limits](https://learn.microsoft.com/en-us/windows/win32/api/tdh/ns-tdh-payload_filter_predicate)
explain why generic payload filtering cannot compare these binary address fields.
