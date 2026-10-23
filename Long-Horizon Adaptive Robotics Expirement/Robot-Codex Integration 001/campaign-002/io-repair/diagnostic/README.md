# Protected C: synchronous IO diagnostic

This prospectively fixed non-physics workload follows the retained native-003
shared durability failure. The parent must freeze/register its exact sources and
manifest, then submit one declared run through the shared compute queue. This
directory does not authorize a retry, production repair, model or physics run.

The measured schedule is 120 seconds, 12,000 ticks at 100 Hz. Every tick calls
the unchanged `InstrumentedFutureEvidence.motion.write` path. Every tenth tick
calls its exact recorder image method with a native-003 PNG/NPZ pair, then the
unchanged `InstrumentedJournal.event` and `registry` methods. Every fiftieth
tick also calls `Journal.state`. The original DELETE/FULL SQLite constructor,
1000-row motion flushes, 2-second sparse image policy, 12 MB image quota and
50 MB core quota are retained. All work is serial. There is no off-thread
writer, batching change, warmup exclusion, latency threshold or outlier removal.

All 588 native stock-1 observation payloads and 5912 motion payloads are cycled
in original order. Only motion timestamps and new event envelope identity/time
are generated; observation payloads retain their original contents. The 30
retained encoded image pairs cycle at the native sparse 2-second cadence;
each pair supplies its intervening 20 image submissions. Native stock-1 had
zero SQLite event rows, so this diagnostic does not invent extra SQL events.
State and registry use the exact terminal snapshots on every publication;
their authentic sizes are representative of the terminal state, not a replay
of historical growth. Sensor encoding, unavailable intermediate imagery,
observation-latest mirrors, non-observation events, trajectories and physics
are omitted. This is a specified shared-path reproduction, not host equivalence.

The binary ledger retains every nested measured operation with its sequence,
parent, tick, start/end wall, thread CPU and process CPU clocks, and failure
flag. Its 250,000-row bound fails closed. No ledger writes occur during the
120-second loop. Setup and complete recorder finalization have separate named
scopes. Inclusive phases overlap and must not be added across nesting levels.
Windows `GetProcessIoCounters` is sampled read-only once per second on the same
thread, in an explicitly measured diagnostic phase. This reveals process IO
counts/bytes, not device latency, filter attribution or scheduling events. No
privileges, services, power settings, security settings or tracing are changed.

The only accepted output path is a new child under the existing protected
`Robot-Codex Integration 001/local-evidence/campaign002/io-repair` root on C:.
Its public mirror is a separate subdirectory in that disposable diagnostic
output, also on C:. Existing episode evidence is read-only and hash-bound.
No output is written to D: or an existing episode.

Resource declaration: 120-second scheduled loop; 180-second cooperative total
cap; 128 MiB observed output cap with a 1 MB final receipt allowance; a maximum
22 MB full binary timing ledger; unchanged recorder quota guards; approximately
30 MB input/template memory plus bounded recorder ring and ledger. The ledger
is checked before every entered scope. Output ceilings are checked after the
bounded workload, not continuously measured transient peaks. The cooperative
cap cannot preempt an OS call blocked inside fsync; an external queue/process
timeout should be retained by the parent if available. Each fixed iteration is
still attempted if the schedule falls behind; lateness is retained, not dropped.

The run manifest starts from `plan.json` with a parent-assigned frozen revision
and run ID. The parent registry should include these four diagnostic sources,
the plan/manifest, `host/supervisor.py`, `harness/instrumented_journal.py`,
`harness/instrumented_recorder.py`, and the future `recorder.py` and
`runtime_adapter.py`. The run receipt binds those source files before/after and
binds every retained input file. Freeze/register provenance and official queue
success are independent parent gates before result use.

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/io-repair/diagnostic/benchmark.py" --manifest "<frozen-manifest.json>" --output "<new-protected-C-output>"
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/io-repair/diagnostic/assess.py" --manifest "<frozen-manifest.json>" --output "<new-protected-C-output>" --assessment "<outside-output-assessment.json>"
```

`assess.py` independently reopens finalized native evidence, checks every event
and motion payload, exact image bytes/availability, Journal/public parity,
atomic snapshots, complete operation counts and durability ordering, source
and output hashes, quotas and schedule completeness. Its assessment must live
outside the immutable run output. Focused unit tests check original-method
parity, source declaration drift, full-ledger bounds/corruption, commit failure
and public-fsync failure. Passing establishes diagnostic completion/integrity;
it never qualifies real-time physics, repairs storage, retroclassifies native003
or establishes power-loss durability.
