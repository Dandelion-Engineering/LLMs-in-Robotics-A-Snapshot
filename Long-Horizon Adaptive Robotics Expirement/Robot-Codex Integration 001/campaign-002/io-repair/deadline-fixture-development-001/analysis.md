# Deterministic shared deadline regression fixture

The original checks018 harness failure is preserved untouched. It occurred in `DRAIN_BEGIN` at `codehost_inside_v3.py` queue-join, before ACK or FINISH. The old test patched the entire owner-drain allowance to 0.02 seconds, then slept 0.03 seconds after BEGIN. That made setup depend on Windows event-loop scheduling; the retained failure does not establish a restarted production deadline.

Only `harness/test_codehost_inside_v3.py` changed. It now completes ordinary BEGIN/ACK with the unchanged 25-second production allowance, establishes genuine upload EOF and a joined upload queue, then substitutes the isolated event-loop clock with original deadline + 1 only around the actual FINISH call. The test requires TimeoutError, the same original deadline, and no successful seal. No wall-clock sleep or allowance extension is used.

The focused inside suite passed all 30 tests (0.974 seconds reported by unittest; 1.185 seconds measured by its parent process). An in-memory mutation that renews the deadline immediately before FINISH failed the same regression with `TimeoutError not raised` (one expected assertion failure, exit 1). This is the required red check; production files were never mutated on disk. Both commands, stdout/stderr, source identities and the original checks018 stderr binding are retained in [receipt.json](receipt.json).

Advancing the mocked event-loop clock also produces an asyncio debug message saying one synthetic task took 26.000 seconds. This is the deliberate clock offset, not wall-clock runtime; both parent-process durations are recorded independently in the receipt.

Production identities before and after are exactly equal:

- `codehost_inside_v3.py`: 30797 bytes, SHA-256 `44906afa4691cf52c7aa9f2e12dea7233827f6a2b75bb0960de6d80ff09123f2`.
- `codehost_mux_protocol.py`: 18689 bytes, SHA-256 `b9d61b200e3bb698d06eed3a5a16bf047278be5f7cba2109659e9b261f0ec7cd`.

Changed test: 19645 bytes, SHA-256 `6a12da59e43eabdf4c570889b536706b467f2b238ef452112228abdaf4981131`.

Original checks018 failure SHA-256 `91cf94f234878dab0657ee904e4af3f376e87e793a03eace22e15349bccaae71`.

No native process, model, namespace, queue job, full-suite retry, runtime change, or empirical outcome assessment occurred.
