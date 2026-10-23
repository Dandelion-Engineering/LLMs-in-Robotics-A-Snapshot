# Next step: bounded administrator TCP closure tracing

Campaign 002 is **not complete**. V29 stopped at Smoke027; zero of the twenty scored slots have started. This packet is a prepared diagnostic, not approval to retry V29 or run another model invocation.

## Specific access boundary

The retained [read-only preflight](read-only-preflight.json) shows an unelevated Windows token and `pktmon status` exit 5: “Failed to communicate with the PktMon driver: Access is denied.” No trace was active according to `netsh trace show status`. No capture, filter, security setting or privilege was changed. Randy's September 27 18:10 instruction explicitly says to stop at a genuine “physical/admin access” boundary and explain the needed decision. An elevated PowerShell session is needed for the next diagnostic.

## Why this measurement

[Smoke027's ordered diagnosis](../smoke027-queue-failure-diagnosis-001/FINDINGS.md) places the first upload abort 0.5954 ms after the observed thread-closed notification and 7.2268 ms before actual stdin closure. Waiting before stdin closure cannot prevent that earlier event. Error 10053 alone cannot distinguish a native peer close, protocol behavior, or a host network component.

The original five/ten-second native bounds and 25-second bridge bound stay unchanged. Increasing them cannot undo an already recorded abort. Suppressing the exception or accepting byte equality as EOF would violate the existing evidence gate. Closing the relay before `thread/unsubscribe` also lacks a supported ordering: retained `grpc_session/mod.rs` lines324–348 still sends `CloseSession` and joins stream tasks during native shutdown. A premature half-close could break a required cleanup RPC. A signal after `thread/closed` is too late for this observed case. These are reasons to acquire lower-level evidence, not proof that every possible repair is impossible.

## First elevated action: synthetic coverage only

Use the existing Python and [coverage_fixture.py](coverage_fixture.py). Its [development result](development-001/result.json) passed two controls using only known synthetic bytes: graceful FIN gave genuine EOF; deliberate RST gave `ConnectionResetError`/WinError64. That difference is not an attribution of Smoke027's WinError10053. The fixture never starts tracing, runs a model, changes an account, or changes a security setting.

1. In the elevated session, inspect `pktmon status`, `pktmon filter list`, and `netsh trace show status`. Save their outputs. Proceed only when no capture is active and the filter list is empty. Do not stop another session or remove someone else's filters.
2. Launch the fixture in a **new exclusive output directory** without `--run-immediately`. Use the project venv Python with `-X utf8 -B`. It binds only `127.0.0.1`, writes `ready.json` with the selected port/PID, and waits at most 60 seconds for `release.json`. It exits within 70 seconds overall. Never reuse `development-001`.
3. Let `P` be the actual port in that fresh `ready.json`. Add only these two filters, whose argument syntax was checked against the installed tool's help:

   ```text
   pktmon filter add C02CoverageFIN -i 127.0.0.1 -t TCP FIN -p P
   pktmon filter add C02CoverageRST -i 127.0.0.1 -t TCP RST -p P
   pktmon start --capture --comp all --pkt-size 40 --flags 0x032 --file-size 16 --log-mode circular --file-name <fresh absolute ETL path>
   ```

   Both filter predicates contain the loopback address and exact fixture port. Their OR combination does not admit general host traffic. No additional event provider is enabled. Forty bytes can contain only header prefix for the fixed IPv4/TCP controls; no application payload is needed. Header truncation may prevent sufficient decoding on a given component, which must be recorded as failed coverage, not worked around with unrestricted capture.
4. Write exactly `{"release": true}` to the fixture's fresh `release.json` after capture starts. Stop this owned trace as soon as the fixture finishes, and in all cases within 30 seconds. Keep the original ETL, command outputs and fixture records. Verify no loss or wrap; any loss, overflow, missing control, ambiguous endpoint or coverage failure invalidates the measurement. The 16 MiB circular ceiling is a safety cap, not permission to discard the beginning and call the trace complete.
5. Convert the retained ETL using `pktmon etl2txt <etl> --out <new txt> --timestamp --metadata`; never overwrite an existing output. Verify both controls by their recorded endpoint pairs and performance-counter ordering. Capture support for loopback and enough FIN/RST metadata is **not yet established** on this host.
6. After stopping, inspect the filter list again. `pktmon filter remove` removes **all** filters on this installed version; use it only if the full current list still consists exactly of the two filters this procedure created. Otherwise leave the unexpected state intact and report it. No driver unload, network reset or security exclusion is part of this packet.

Before a native diagnostic, review the synthetic trace coverage. If it is inadequate, report that result and design a separately scoped TCP/IP event trace; do not broaden capture automatically. If adequate, prospectively declare one fresh native diagnostic with fresh identities, unchanged model/bootstrap/isolation and resource limits, exact port/PID correlation, automatic trace bounds and cleanup. Its new evidence question is the socket endpoint/OS closure sequence. It is neither an unchanged retry nor a qualifier. Full fresh qualification still follows any supported material repair.

## Evidence and alternatives

Preferred next step: validate bounded OS trace coverage, then choose a repair from observed closure evidence. A source-level native HTTP transport change or a different host/runtime is a larger alternative and has not been implemented or qualified. An upstream report would be external contact and needs separate authorization. No cash, accounts, API billing, firewall/antivirus changes, evidence deletion, physical deployment or scoring-gate relaxation is proposed.

Microsoft documents the [Pktmon command surface](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/pktmon), [filter conjunction and TCP flags](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/pktmon-filter-add), and [elevated network-trace collection](https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/tcpip-performance-known-issues). The local help and actual access-denied result are the evidence for this host. The procedure has been prepared; OS tracing has not been executed.
