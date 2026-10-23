# Bounded administrator coverage automation

Session 17 continues the [administrator handoff](../admin-guidance-handoff-001/README.md).
The synthetic helper now accepts the actual Windows venv process topology using
authenticated private-job membership and retained process handles. It does not
remove the endpoint identity check. No model, native qualifier, pilot or scored
attempt is part of this packet.

The [prospective declaration](DECLARATION.md) gives the scope. The unchanged
fixture is launched through the project venv. Windows atomically assigns that
launch to a private job; the job has kill-on-close and no breakaway. The helper
records the venv redirector and its direct base-interpreter child separately,
then verifies image, creation time, ancestry, job membership and exact loopback
metadata. Cleanup requires an empty job and signaled retained process handles.

## Development evidence

| Retained attempt | Observed outcome |
|---|---|
| [launch-probe-001](launch-probe-001/receipt.json) | Normal synthetic FIN/RST control passed. Three forced-cleanup checks failed because the first implementation checked process signaling immediately after job membership emptied. The exact sources remain in its `sources/` directory. |
| [launch-probe-002](launch-probe-002/receipt.json) | All four controls passed after waiting for both independent retirement conditions within the original three-second bound. The ready PID is a different process from the venv redirector and has that redirector as its parent. |
| [helper-tests-001](helper-tests-001/receipt.json) | Nine of ten passed; the changed-filter test double indexed the command's `-p` token as the port and raised before applying the intended mutation. This is retained as a failed test, not a helper success. |
| [helper-tests-002](helper-tests-002/receipt.json) | All ten complete helper paths passed after correcting the test double's flag/port indexes. |
| [helper-tests-003](helper-tests-003/receipt.json) | Twelve passed, adding output-root and exact capture-path guards. It binds the final helper, process owner and original fixture. |
| [guard-tests-001](guard-tests-001/receipt.json) | All nine original preflight/filter/netsh guards passed against the repaired helper. |

The complete helper tests launch **real local fixture processes** and substitute
**simulated administrator command results**. They establish launch/control-flow
and owned cleanup behavior, not OS trace coverage. Cases include interruption
before/after simulated capture start, partial filter setup, uncertain startup,
foreign/changed capture or filters, and stop failure. A failed stop remains a
failure and prevents filter removal.

The full source snapshots and test logs are retained beside their receipts.
[Historical preservation](prior-attempt-preservation-check.json) verifies all
20 copied files from the two user-run attempts without changing them.

## Exact elevation action

[launch_elevated.ps1](launch_elevated.ps1) uses Windows `Start-Process -Verb RunAs
-WindowStyle Hidden` to launch only the project Python and this helper. Its
[manifest](launch-source-manifest-001.json) binds the three runtime source hashes
and the fresh output
`C:/Users/cresp/Documents/Campaign002 TCP Trace/coverage-managed-20260929-001`.
The PowerShell file was parsed successfully before execution. UAC consent is
handled by Windows; no administrator terminal is automated and no persistent
privileged command service is installed.

The [first elevation attempt](elevation-attempt-001.json) returned Windows
`The operation was canceled by the user.` The requesting command exited 1;
no launch receipt, helper output directory or remaining consent process was
present at the 20:18:43 UTC check. This establishes that this attempted RunAs
launch did not start the helper; it does not identify whether cancellation
came from a click or a consent timeout. No trace or filter was created in this
session. Do not repeat the elevation request without Randy's direction.

The next required action is Windows UAC consent for this specific helper.
The agent can manage the launch and read its output directly after consent;
Randy does not need to run commands or send screenshots. A canceled request
does not justify an alternate privilege route or security-setting change.

The helper retains exact command outputs, owned process identities, retirement,
fixture records, ETL/text if collection reaches them, and a terminal receipt.
Its receipt never grants coverage qualification. Collection must be followed
by independent evidence review. Campaign 002 remains closed to scoring until a
supported repair and complete fresh qualification; all earlier verdicts stand.
