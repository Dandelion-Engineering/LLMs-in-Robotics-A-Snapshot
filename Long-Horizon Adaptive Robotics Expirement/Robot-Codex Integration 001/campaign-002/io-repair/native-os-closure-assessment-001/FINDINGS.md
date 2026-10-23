# Diagnostic005: drain timeout precedes the observed reset

The sole source-frozen dev097 interruption, job
`20260930T165659123517Z-cab77873`, ended failed/integer1 at
2026-09-30T17:02:04.93631Z. No resume, qualification pilot or scored run occurred.
Task outcome remains unknown. This diagnostic did not reproduce Smoke027's
earlier upload-read10053: its socket error was ConnectionResetError/winerror64
after the native drain deadline and forced retirement.

The one-shot elevated observer exited integer0. All11 independent collection
checks passed:7.107536seconds, bounded sequential file, correct QPC, no loss,
only the six permitted TCPIP event types and required headers, and verified
owned stop/absence. It retained54 permitted events, of which6 matched the sole
authenticated native loopback pair. The other48 endpoint records and all raw
and decoded host trace data remain outside Git. Arming added47.7199ms before
the original retirement request; this diagnostic is not a timing qualifier.

## Measured order

Times below use the common high-resolution host counter. Zero is the observed
native thread-closed notification. The retained complete timeline and exact
input hashes are in [ordered-analysis.json](ordered-analysis.json).

| Observation | Milliseconds after thread closed |
| --- | ---: |
| Native cleanup handshake complete |0.8066|
| Finishing retained |2.0002|
| Forced owned-job retirement requested after pre-exit timeout |4953.8263|
| Native stdin closed notification |4955.8935|
| First matching TCPIP abort request1039 |4979.0608|
| Native-side shutdown1044, status0xc0000241 |4979.0616|
| Bridge-side shutdown1044, status0xc000020d |4979.0675|
| Upload-read ConnectionResetError/winerror64 |4979.3904|
| Observed native exit0 |4988.1796|

The first matching OS event follows the forced-job observation by25.2345ms
and the actual stdin-close completion by23.2162ms. The native-side event's
payload PID32960 matches the authenticated channel owner, whose exact pair is
127.0.0.1:63762 to127.0.0.1:55585. Generic PID0 events are joined by that exact
pair and time, not attributed from PID alone.

The first recorded bridge failure is `native_pre_exit_TimeoutError`. At terminal
inspection the one channel has complete HTTP/2 framing and headers, zero active
streams,46 closed streams and one retained cleanup cancellation. Observed
upload345236bytes and download243214bytes match at both relay endpoints.
Neither genuine parent EOF nor upload-drained evidence exists. These final
byte counts do not establish when application traffic became idle and do not
replace EOF. Native cleanup is unqualified and forced despite process exit0.
Owned namespace cleanup, durable retention and old-token denial have their
narrow successful receipts; they do not promote the overall failed attempt.

## Interpretation and remaining work

The reset is later than the first failure and forced retirement in this run;
it cannot explain the earlier five-second wait. Lack of matching events before
forced retirement is not proof of complete kernel visibility. The original
Smoke026/02710053 cause remains unresolved and its evidence is unchanged.

The new evidence supports investigating a circular lifetime dependency:
the harness waits for every native TCP channel to end before closing native
stdin, while a reusable native HTTP/2 pool may outlive the thread. Retained
rust-v0.157.1 sources create the remote provider at app-server scope, cache the
HTTP client in SharedTransport, and make session shutdown close the remote
session and join stream tasks without an explicit transport-pool close. This
is a source-supported hypothesis, not installed-binary attestation.

Compare bounded graceful process shutdown with the current pre-exit wait in
no-model fixtures before changing production. Any prospective replacement
must still require actual socket EOF, complete byte accounting, normal native
exit, finished namespace and joined handlers within the original deadlines.
A change must not suppress the earlier10053 path or relabel any old result.
Full fresh qualification remains mandatory before the fixed20 scored slots.

The current [official app-server documentation](https://learn.chatgpt.com/docs/app-server)
describes thread/unsubscribe and thread/closed as thread lifecycle operations;
it supplies no guarantee that these close a remote code-mode TCP pool. Current
documentation does not attest behavior of the retained0.157.1 binary.

[Initial bounded projection and trace checks](analysis.json),
[terminal authentication](authentication.json), [scope](DECLARATION.md), and
[projection boundary tests](projection-tests.json) preserve the evidence.
