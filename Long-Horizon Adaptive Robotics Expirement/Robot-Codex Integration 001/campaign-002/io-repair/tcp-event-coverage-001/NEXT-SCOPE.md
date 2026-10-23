# Proposed next measurement and collection-scope decision

**Decision received in the Codex task, Session18:** Randy selected
"Allow bounded process scope" in response to the explicit question covering
owned-process socket-closure metadata, non-loopback IP addresses/ports,
excluded packet contents, and the unchanged16MiB/30second limits.
The prospective [direct collector](../tcp-event-coverage-002/DECLARATION.md)
continues under that authorization. The proposal below is retained as the
reviewed decision basis; its former pending status is superseded by this note.

The exact-port Packet Monitor capture missed both synthetic closures. The
exact-port TCPIP/netsh collector observed them but also retained unrelated
endpoint and system process metadata. Its failed scope result is preserved.
Repeating it or simply ignoring the extra events is not the next step.

## Recommended bounded alternative

Implement a direct Windows ETW session, with no netsh orchestration or system
rundown, using only Microsoft-Windows-TCPIP event IDs1038,1039,1040,1043,1044
and1468: close, abort, disconnect, shutdown and system-abort metadata. Bind
every installed event version and its field schema. Combine an explicit
event-ID allowlist, the ignore-zero-keyword property, and event-payload
`ProcessId == <retained owned process identity>` filters before collection.
Fail before enabling the provider if any descriptor or predicate is unsupported.

Start with a new no-model synthetic qualification, including a separate
excluded process, before declaring any native diagnostic. Require absence of
all process rundown and unrelated-process events, correct endpoint/clock
correlation, both distinguishable controls, no loss or overflow, and verified
owned stop/retirement. Retain the16MiB/30second limits, disabled packet capture,
no application content, new exclusive output and session identities, and
source-bound one-shot UAC. No persistent broker, security changes, billing,
accounts or blanket trace shutdown. Denied or timed-out consent ends that
attempt without an alternate route.

The **scope change requiring Randy's decision** is replacing an exact
loopback-port restriction with closure metadata from one or two explicitly
owned diagnostic processes. In a later native test, these processes could
also close non-loopback connections. Such records could include remote IP
addresses, ports, status codes, process IDs and timing, but no packet/application
payload. Filter on the event's numeric ProcessId field, not merely the emitting
thread's process, because kernel events can be emitted in another context.
Keep raw trace files local; only reviewed task-relevant projections enter Git.

Why this decision is real: the retained TDH probe can construct numeric
ProcessId filters for all nine tested closure-event versions, but rejects all
nine binary LocalAddress predicates with error87. Microsoft's documented
generic payload-filter types do not support binary address fields. The
installed netsh provider offers address/port filters, but this host's actual
trace proves that those settings did not enforce the whole requested scope.
This is a collection/privacy boundary, not another general campaign approval.

## Alternative if exact-port scope must remain

Continue source-level investigation without further TCPIP capture. The local
Microsoft-Windows-Kernel-Network manifest has numeric IPv4 address/port fields
and a connection-close event, so it is a possible narrower collector. Its
closure schema does not directly distinguish a graceful close from an abort or
give the TCPIP system-abort reason. It is not an equivalent replacement for
the intended diagnosis without a separate coverage demonstration. Changing the
native transport/runtime itself is a larger alternative; it has not been
implemented or qualified.

No process-scoped trace has been launched or approved by this proposal. Once
scope is decided, implement and test the collector, qualify it with no models,
then declare one distinct native evidence question. A resulting supported
repair still requires every fresh Campaign002 qualification gate before its
twenty sealed scored slots. Earlier failures and Campaign001 remain unchanged.

Sources: [actual failed-scope assessment](assessment-001.json),
[TDH construction results](filter-construction-001.json), retained installed
provider schemas, Microsoft's [filter descriptor API](https://learn.microsoft.com/en-us/windows/win32/api/evntprov/ns-evntprov-event_filter_descriptor)
and [payload predicate restrictions](https://learn.microsoft.com/en-us/windows/win32/api/tdh/ns-tdh-payload_filter_predicate).
