# Proposed six-event closure trace — human scope decision required

This packet is preparation only. The existing approval covers owned diagnostic
processes. It does not authorize this broader collection. Do not run the
launcher unless Randy explicitly permits bounded host scope.

Question: can the direct ETW collector record both synthetic closure controls
with exact endpoint and raw-QPC correlation while enforcing the six-event
allowlist and excluding every unrelated provider or event type? This is a
synthetic coverage diagnostic, not a native model test or campaign qualifier.

Collect only Microsoft-Windows-TCPIP IDs 1038, 1039, 1040, 1043, 1044 and 1468
at their installed, frozen versions. These events contain socket addresses and
ports, PIDs, TCP state/status or reason values, timestamps, connection pointers
and process sequence keys. Collection spans all processes, including PID 0,
and may reveal other applications' network endpoints. No packet contents,
application buffers, command lines, stacks, process rundown, other provider or
system trace flags are requested. Explicit event IDs and ignore-keyword-zero
remain required. Generic payload/PID filters are not claimed to limit this run.

Use a fresh session name, GUID and output; sequential 16 MiB ETL, 64 KiB buffers,
30-second maximum; explicitly request stop-on-hybrid-shutdown (mode 0x400001).
This documented flag does not enable another event or expand the file bound.
Retain live GUID/path/name checks before stopping the returned owned handle.
Never stop a foreign/replaced trace. Require complete retirement, zero event
or buffer loss, no wrap/overflow, and API plus actual helper-exit evidence.

Release two unchanged synthetic FIN/RST fixtures after provider enablement.
Both are included controls under this scope. Require graceful disconnect
1043/status 0 in both directions, abort request1039 and abort completion1040
for reset, and server shutdown1044/status0xC000020D. Match each exact endpoint
pair and its close-request-to-completion QPC interval. Never infer that an
omitted event did not occur. Unknown schema, extra event/provider, payload
extensions, lost records, incomplete cleanup, or missed bounds invalidate
coverage. Necessary ETL header and partition descriptors are counted separately.

Raw and fully decoded traces stay local outside Git, including on success.
Repository evidence contains hashes, counts, cleanup receipts, and projections
of the synthetic controls only. Do not publish other applications' endpoints
or process identifiers. No previous failed attempt may be relabeled or reused.

First complete simulated ETW lifecycle tests with real owned fixtures and
source-bound reader/guard checks. Freeze helper, declaration, tests, assessor
and one-shot launcher. After an explicit scope decision, use one RunAs/UAC
launch; denied or timed-out consent ends the attempt without an alternate
privilege path. No persistent broker, security setting, spending, model,
queue job, native diagnostic, pilot or scored slot is included. A native
evidence question and bounded capture integration must be declared separately
after synthetic coverage passes. Supported repair and full fresh qualification
remain prerequisites to Campaign002 scoring.
