# Windows socket closure observations — prepared, not executed

This fixture implements the four development cases declared in `../SOCKET_ABORT_DIAGNOSTICS_V1.md`. Root must review both sources and wait for the bridge instrumentation to settle before the single execution. No model, app server, namespace, robot, queue job or external network service is invoked.

Each fresh TCP pair binds only `127.0.0.1`. The actual production `SocketWriter.write/drain` sends one fixed 4096-byte payload; the actual `SocketReader.read` receives and verifies it before starting a pending read. The single declared action is then peer `SHUT_WR`, peer confirmed abortive linger+close, local writer close, or explicit read-task cancellation. The fixture records the actual outcome without requiring an OS error number. Unanticipated results remain `unknown`. Only an actual empty read is recorded as EOF; later deadline-cleanup cancellation is a separate phase and cannot replace a timeout observation.

Cases have absolute five-second observation deadlines and two-second cleanup allowances. The hidden, owned child receives35seconds; the launcher reserves the remainder of its40-second outer acceptance bound to kill/reap only that child. The matrix executes once; `execution-001` is exclusive. Incomplete cleanup or an overrun remains recorded failure, never a successful observation.

All retained events use finite enums, booleans, clock values, genuine bounded integer error codes, byte lengths and hashes. No payload bytes, endpoint addresses, arbitrary exception text/arguments, traceback or dynamic exception-class names are retained. Child stdout/stderr are bounded, hashed and discarded; only digest summaries are saved. Event/result/receipt sizes are bounded. Source identities include the reviewed bridge and dependencies, both fixture sources, the declared method, interpreter executable/DLLs and installed asyncio source.

After root review and the stable bridge hash, run exactly once using the project Python:

```powershell
& .\venv\Scripts\python.exe -X utf8 -B '<absolute path to launch.py>' --reviewed-bridge-sha256 '<reviewed bridge hash>' --reviewed-fixture-sha256 '<reviewed fixture hash>' --reviewed-launcher-sha256 '<reviewed launcher hash>'
```

The launcher records its exact argv and source manifest before starting the child with `CREATE_NO_WINDOW`. Exit0 means the bounded collection completed and sources stayed unchanged. It does not mean every synthetic outcome was anticipated, that transport is qualified, or that Smoke026's cause was reproduced. Original evidence and verdicts remain unchanged.
