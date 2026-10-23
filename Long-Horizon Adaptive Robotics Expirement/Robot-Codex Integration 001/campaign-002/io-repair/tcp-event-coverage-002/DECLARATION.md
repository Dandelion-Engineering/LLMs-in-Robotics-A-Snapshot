# Direct ETW closure metadata — prospective synthetic qualification

Randy explicitly selected **Allow bounded process scope** in the Session18
Codex task. The question specified socket-closure metadata from owned diagnostic
processes, potentially including their non-loopback IP addresses and ports,
excluded packet contents, and unchanged16MiB/30second limits. This scope change
does not authorize host-wide process metadata or an unrestricted trace.

This helper starts one uniquely named, source-bound direct ETW file session.
Enable only Microsoft-Windows-TCPIP IDs1038,1039,1040,1043,1044,1468 with
the installed [event versions and fields](schema.json). Before provider
enablement, construct every numeric payload ProcessId predicate for the owned
fixture process, aggregate them, and combine with the explicit event-ID
allowlist and EVENT_ENABLE_PROPERTY_IGNORE_KEYWORD_0. No system trace flags,
process rundown, additional provider, packet capture, stacks or application
buffers. Fail closed on any unsupported descriptor, predicate or API result.

Use a fresh GUID/session/output, sequential16MiB file,64KiB buffers and a
30second maximum. Verify the live session GUID and exact ETL path before
stopping the returned owned handle; never stop a foreign/replaced session.
Retain API results, session statistics, fixture identities and empty-job/signaled
handle retirement. Do not erase a failed attempt or repeat it unchanged.

Use the unchanged synthetic FIN/RST fixture for included and excluded processes.
Hold retained identity handles through trace retirement. Enable only the included
payload PID. Release both after filter installation. Require both controls in
the included process, no excluded or unrelated-process event, only allowed
event IDs and fields, known exact endpoint pairs, raw-QPC clock correlation,
zero loss, no overflow/wrap and complete cleanup. Collection success alone
does not qualify coverage. Every earlier failed attempt remains unchanged.

Before launch, raw decoding of the terminal001 synthetic trace established that
generic close/abort events1038/1039/1040 can carry payload ProcessId0. Do not
include PID0 or treat these as covered by a process predicate. This diagnostic
can qualify only owned-process disconnect/shutdown/system-abort metadata, not
packet-level FIN/RST coverage or a complete kernel abort history. The frozen
control expectations are graceful disconnect1043/status0 on both endpoint
directions and reset shutdown1044/status0xC000020D at the server endpoint, with
the exact synthetic endpoint pair and timestamps between its close-request and
fixture completion. Both endpoints' payload PIDs must be the included fixture.
Require zero excluded-process records and zero unexpected provider/event
descriptors. Necessary ETL file-header/partition metadata is counted separately;
host-wide process rundown is never accepted. No omission establishes absence
of an OS event. Raw trace stays local pending independent scope assessment.

First test filter construction and aggregation without enabling a provider,
mocked ETW lifecycle/ownership/error handling, real owned-fixture control flow,
and the bounded decoder against the already terminal local trace. Then freeze
sources and use a single RunAs/UAC launch. No persistent privilege broker,
alternate route, security change, spending, model, queue job, simulator, native
qualifier, pilot or scored attempt is included. Denied/timed-out UAC is retained
and ends that attempt. A later native diagnostic requires a separate question,
declaration and fresh identities; supported repair and full fresh qualification
remain prerequisites to Campaign002 scoring.
