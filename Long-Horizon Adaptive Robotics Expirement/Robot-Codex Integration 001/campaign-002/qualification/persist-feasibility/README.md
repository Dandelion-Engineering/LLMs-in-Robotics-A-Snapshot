# Conditional PERSIST/FULL recorder feasibility

This prototype is isolated from the frozen robot harness. It is a prospective
apparatus comparison, not a repair adopted by Campaign 002. Probe 004 remains a
valid no-model diagnostic with a 95.148 ms maximum lag; it does not establish
that PERSIST improves latency or fixes probe 003's unresolved bridge stall.

The parent declares and freezes the manifest and submits the exact command:

```powershell
& .\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/qualification/persist-feasibility/benchmark.py' run --manifest '<absolute prospective manifest path>' --output '<new absolute evidence directory>'
```

Do not run the complete comparison outside its authorized shared-queue job.
Outputs may be assessed only after that official job succeeds with integer exit
status zero. The driver's zero exit means it retained its declared comparison;
the assessor must inspect every round and recovery check for actual success.

## Fixed workload and retained outcomes

The manifest fixes seed 173, eight rounds in order
`DELETE,PERSIST,PERSIST,DELETE,DELETE,PERSIST,PERSIST,DELETE`, 600 frames per
round, 64 by 48 RGB/depth inputs and ten motion records per frame. Synthetic
capture time advances by 0.1 seconds per frame; execution proceeds as quickly as
synchronous operations allow. This is not a wall-paced physics experiment.

All rounds receive identical arrays and motion/event/document inputs. The
original `LiveSensorBridge` performs its unchanged PNG/NPZ encoding, and the
candidate hashes every encoded pair, including pairs left in the retention
ring. The original sparse period, trigger mechanism, availability semantics,
ring bounds and quota implementation run with the same fixed fixture policy
in both conditions. One trigger occurs at the declared midpoint. No warmup,
outlier, failed round or losing condition is discarded, and there is no minimum
number of timing wins or performance threshold for adoption.

Each round retains its result and bounded `operations.bin`: little-endian six
float64 columns (`operation_code`, `wall_start_s`, `wall_end_s`, `thread_cpu_s`,
`process_cpu_s`, `success`). The metadata binds the complete ledger, fixed code
mapping, capacity and count. Parent image/motion calls include instrumentation
and space accounting. Nested SQL durations surround the native operation and
exclude its pre/post file census; inclusive parent/child rows must not be summed.
The aggregate result retains every round, descriptive distributions, input and
encoded-byte hashes, original Reader fingerprints, environment, and source
identities. Runtime input-file binding and official queue authentication are
the parent's frozen-release/assessment responsibilities.

## Candidate contract and failure handling

The original Recorder constructor still creates the database and selects FULL
durability. The candidate changes only the declared journal mode afterward,
reads back journal mode/FULL/one main database/no open transaction before work,
and delegates the original mutation and commit-before-return methods. Its
FutureEvidence constructor matches the original except for the explicit
recorder factory; inherited owner locking and all other methods are unchanged.

Before finalization, pending motion is flushed in the declared mode, configuration
is read back, and SQLite is asked to select DELETE mode. The original final-state
UPDATE/commit then forms a DELETE-mode transaction. A connection-close adapter
requires SQLite to have retired recovery sidecars before the original byte hash,
gzip verification, durable publication and working-database removal proceed.
No journal is manually deleted, truncated, renamed or zeroed. A failed operation
latches its first error; subsequent operations and finalization cannot turn it
into a successful container. The driver retains failed directory contents and
the first error, using SQLite itself for connection close/rollback without
retrying work or forcing complete publication.

## Space coverage

The declaration reserves 64 MiB for an active native fixture inside the unchanged
512 MiB host envelope: a 2 MiB database allowance, 32 MiB rollback-journal
allowance, 8 MiB overlapping-publication allowance, and 1 MiB metadata allowance.
Their sum is below the active reserve. Already completed outputs plus the active
reserve must fit the aggregate envelope before the next round. Fixed fixture
core/image quotas remain 1 MiB and 256 KiB respectively.

Pre/post SQL boundaries, mode transitions, SQLite close and finalization count
the database, journal, publication files and retained failure marker. Unexpected
files and observed component or total overages fail closed. Recorded maxima are
observations; they are not continuous transient peak measurements or an OS hard
quota. The deliberately generous journal/publication allowance is a declared
reservation, not evidence that every within-call peak was seen. No
`journal_size_limit` claim substitutes for that distinction. This small fixture
cannot qualify the production recorder's larger quotas/reserve without a
separate justified bound and actual-workload qualification.

## Recovery and validation boundary

Four disposable subprocess fixtures cover each mode immediately before and
after a native commit. The before-commit fixture uses a separately declared
eight-page cache to force an interrupted rollback journal; this cache setting
is not used by the benchmark rounds. Each child exits abruptly with code 23 at
its injection boundary. The parent preserves hashes of the original database
and journal, copies that pair, and permits SQLite recovery only on the copy.
The committed document set, retained committed payload and integrity check must
match expectation; interrupted evidence cannot carry a complete container
manifest. Process interruption tests do not certify power-loss behavior or the
storage device's durability.

Eight short tests cover original/candidate Reader and encoded parity, constructor
equivalence, journal accounting and SQLite-managed retirement before gzip,
latched space/commit failures, wrong durability and failed mode transition,
unexpected files, and actual disposable process-crash recovery. The complete
eight-round experiment still requires its separate official queue result.

The 300-second cap is checked before bounded workload iterations and fixtures;
a single blocked native operation may delay the next check. The driver retains
overrun/unrun status and cannot call such a result successful. This is a bounded
diagnostic, not a hard real-time scheduler or universal latency guarantee.
