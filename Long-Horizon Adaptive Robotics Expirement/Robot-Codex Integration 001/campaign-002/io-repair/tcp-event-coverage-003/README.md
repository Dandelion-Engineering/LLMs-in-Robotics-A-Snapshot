# Six-event synthetic closure coverage — passed

Randy explicitly granted **Allow bounded host scope**; see [authorization](AUTHORIZATION.md).
The frozen helper ran once after UAC at 2026-09-30 04:04:28 UTC and exited
integer0. Its 0.0592714-second, 196608-byte trace passed all nine
[independent checks](assessment-001.json): all four synthetic controls, exact
endpoint/QPC correlation, declared event types, no loss and complete cleanup.
It contained24 synthetic and12 other closure records plus required trace-header
metadata. Raw/decoded traces remain local; only synthetic projections and
bounded metadata are in Git. The prior failed scope checks remain failed.

This folder contains the tested source, [test receipt](tests-001/receipt.json),
independent assessor, [frozen manifest](launch-source-manifest-001.json), and
one-shot UAC launcher. Thirteen lifecycle cases, eight guards and the terminal
raw-QPC reader check passed. The tests run real synthetic fixtures with
simulated ETW session APIs. They do not establish effective OS trace coverage.
The launcher's scope guard first refused a test invocation without authorization
before opening UAC. The subsequently authorized [launch record](elevation-attempt-001.json)
binds the one actual run.

Do not rerun this completed attempt. Adequate synthetic coverage is not native
qualification or a complete kernel-abort history. A fresh, separately declared
native diagnostic must bind this collector to the exact interruption window
and owned endpoint identities before supported repair and full requalification.

The source change from attempt002 explicitly selects mode0x400001, documented
by Microsoft in [logging modes](https://learn.microsoft.com/en-us/windows/win32/etw/logging-mode-constants),
and removes the ineffective payload-PID predicate. It retains the event-ID
allowlist and ignore-keyword-zero. No claim of process-limited collection is
made. No model, native qualifier, pilot or scored slot is included.
