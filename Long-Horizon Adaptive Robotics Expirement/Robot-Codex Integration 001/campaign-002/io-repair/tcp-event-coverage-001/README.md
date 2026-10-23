# TCP event coverage: useful control signals, failed collection scope

The [prospective declaration](DECLARATION.md) selected the installed TCPIP
provider's exact-address, exact-port and ProcessId filters, ClosePath keywords,
disabled packet capture/report/correlation/performance merge, a unique session,
16MiB and30seconds, and owned cleanup. This was a separate no-model diagnostic
after Packet Monitor returned no coverage, not an unchanged model retry.

[Ten control-flow cases and four guards](tests-001/receipt.json) passed using
real privately owned fixture processes and simulated administrator commands.
The original test sources remain in that directory. The [source-bound launch](launch-source-manifest-001.json)
received Windows consent and [ended integer0](elevation-attempt-001.json).

The actual trace lasted1.9512944seconds and used2,031,616bytes. The included
FIN and deliberate-RST controls produced distinct exact-endpoint events;
the [bounded projection](included-control-projection.txt) retains only those
twelve relevant records. The two negative-control connections have no matching
connection-level events. All fixture processes retired and the owned trace
stopped; Packet Monitor remained idle with no filters.

**The collector is inadequate.** The [independent assessment](assessment-001.json)
found unrelated endpoint-close records (including two excluded-control endpoint
closes), zero-keyword events, and system process rundown records despite the
explicit restrictions. The export also reported three formatting errors. The
12 selected records are observations from an invalid coverage attempt, not a
qualified measurement or an attribution of Smoke027. Exact raw-QPC event
correlation remains unestablished. Do not repeat this netsh collector or admit
a native/scored attempt from it.

The full ETL/text remain only in
`C:/Users/cresp/Documents/Campaign002 TCP Trace/event-coverage-20260930-001`.
They contain unintended process metadata, including command lines, and must not
be copied or published into the repository. The assessment retains hashes and
sizes of all originals; aggregate counts and the intended synthetic endpoints
are sufficient for the repository record. No historical evidence is deleted.

The [next scope proposal](NEXT-SCOPE.md) describes the narrowest currently
supported alternative and the actual new decision. No further elevation is
pending. No model, campaign runtime/assessor change, queue job, map registration,
qualifier, pilot or scored attempt occurred in Session18.
