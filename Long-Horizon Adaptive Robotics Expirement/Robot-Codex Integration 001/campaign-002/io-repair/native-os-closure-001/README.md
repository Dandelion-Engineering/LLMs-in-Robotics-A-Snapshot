# Native closure diagnostic005 — prepared, not launched

Session18 completed unattended preparation after Randy said he was leaving
the desktop. The next action that needs him is one Windows UAC consent. No
native observer, control key, queue job, model invocation or capture has been
created for this diagnostic. Campaign002 remains unfinished with zero scored
starts or registrations. Existing campaign continuation authority remains.

The [declaration](DECLARATION.md) asks whether six TCPIP closure-event types,
joined to exact diagnostic loopback endpoints and QPC timestamps, explain the
native shutdown/socket-abort order. It permits one interruption, no resume or
retry. The independently qualified [synthetic collector](../tcp-event-coverage-003/README.md)
provides bounded host-scope metadata under Randy's explicit scope decision.
Raw and decoded host traces stay outside Git. Synthetic coverage does not
establish native coverage, a runtime repair or qualification.

## Ready state

- Run: `RCI001-C02-shutdown-diagnostic-005`; revision: `RCI001-C02-dev-097`.
- [Manifest](../shutdown-diagnostic-005/manifest.json) SHA256:
  `c051edff9872b8e04046b8c8fdbc1496545ca08d6674cf63e4b89b3ba5ed4f27`.
- [Snapshot](../../../../Architecture%20Map/releases/RCI001-C02-dev-097/snapshot.json)
  SHA256: `9339cd26d36b21eafffd4016db2256480923a268755a20082aaf6eef03197de0`.
- 986 frozen inputs. All 958 dev096 inputs and the original624 are unchanged.
- [Readiness](readiness-001.json) verifies every source/archive, unchanged
  canonical prefixes and absent launch footprints. The map has155 revisions,
  472 declared runs and471 results; the extra run is unexecuted development,
  with no result yet. Do not settle it as permanently not-run simply because
  its launch is deferred to the next desktop session.
- [Control tests](control-tests-002/receipt.json): eleven lifecycle cases and
  six protocol guards passed, with real owned workers and simulated ETW.
  Earlier control-tests-001 remains retained separately.
- [Wrapper tests](wrapper-tests-001/receipt.json): nine execution/failure cases
  and eight launch/configuration checks passed. External processes, queue,
  WSL and models were mocked. Failed arming retained original cleanup; absent
  readiness prevented launch; observer retirement failure failed the wrapper.
- [Launcher checks](launcher-checks-001/receipt.json): PowerShell syntax and
  the desktop-unavailable guard passed without a UAC prompt.

The full production runner, fixture, bootstrap, isolation and cleanup policy
remain unchanged. The wrapper arms only at the first retirement call, records
the added latency, and always delegates the original call. Its helper waits
at most900seconds without tracing, then stops capture on authenticated worker
retirement, worker exit or a25second automatic deadline. More than30seconds,
16MiB, data loss, schema/scope departure or incomplete cleanup fails the
diagnostic. The live elevated/native integration remains untested.

## Next desktop session

Do not rerun `prepare.py` or `freeze.py`: their immutable outputs already
exist. Do not edit frozen sources or restart V29. First follow AgentPrompt,
read the current director messages, and confirm Randy is at the desktop.
His latest instruction explicitly deferred UAC while away.

From the repository root, create the one-use operational configuration. This
revalidates test bindings, all frozen inputs and fresh output paths. It creates
a random key only in the external control root, never in Git or the model
namespace. No trace, process or model is launched by this command:

```powershell
$taskPacket = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/io-repair/native-os-closure-001'
.\venv\Scripts\python.exe -X utf8 -B "$taskPacket/prepare_observer.py"
```

Then start the fixed observer using the tested PowerShell script. Run it in a
retained tool session so its real exit code remains available. It writes an
exclusive intent before requesting UAC, retains the process handle, and waits
for terminal exit. A denied/timed-out prompt is a preserved failed attempt;
never repeat it unchanged or use another elevation route.

```powershell
& "$taskPacket/launch_observer.ps1" -DesktopAvailable
```

Once its signed `helper-ready.json` exists, use a separate unelevated command
to submit the sole native worker through the existing storage guard and shared
queue. These are operational control records, not empirical output reads.
The launcher reauthenticates readiness immediately before queue submission:

```powershell
$taskIO = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/io-repair'
$taskBinding = Get-Content -LiteralPath "$taskIO/shutdown-diagnostic-005/observer-preparation.json" -Raw -Encoding UTF8 | ConvertFrom-Json
.\venv\Scripts\python.exe -X utf8 -B "$taskIO/single-interrupt-diagnostic-v5/launch.py" --manifest "$taskIO/shutdown-diagnostic-005/manifest.json" --snapshot 'Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-097/snapshot.json' --observer-config-sha256 $taskBinding.config_sha256
```

Do not print or copy the external `config.json`: it contains the temporary
authentication key. No manual PowerShell commands, screenshots or result
inspection are required from Randy; the agent runs these commands.

Authenticate a fresh official terminal queue receipt and the elevated process's
actual exit before reading/hashing empirical outputs. Succeeded/integer0 is
necessary for ordinary assessment. Failed/integer1 permits only the declared
bounded infrastructure projection, with task outcome unknown. Use the frozen
`tcp-event-coverage-003/read_etl.py` to decode terminal ETL outside Git; correlate
only exact accepted endpoint pairs and QPC time. Payload PID0 alone cannot
establish ownership. Keep trace completeness and native cleanup as separate
checks. Missing events or nonreproduction remain inconclusive.

Settle the development record honestly after execution. A supported material
repair still requires full fresh Raw/Transport/Host/native/boundary/smoke and
both pilots before any sealed Campaign002 slot. No historical failure changes.
