# Prospective timing repair and its evidence boundary

Campaign 001 remains frozen. Its three blocked-home timing-invalid attempts stay
invalid, their scored outcomes stay unknown, and its remaining slots stay not run.
The changes below belong only to the new Campaign 002 harness and fresh
qualification evidence. They do not establish the historical cause of a delay.

## What the retained evidence establishes

| Campaign 001 attempt | Original loop maximum | Journal maximum | Bad full-second windows | Supported finding |
|---|---:|---:|---:|---|
| home02 | 0.099 s | 0.113 s | 0/315 | Journal fails; different origins cannot be exactly aligned from retained maxima |
| home03 | 0.327 s | 0.334 s | 3/322 | Both maxima fail; 0.375 s wall passes while simulation advances 0.068 s near the journal peak |
| home05 | 0.108 s | 0.115 s | 1/334 | Both maxima fail; largest journal sample precedes the model turn |

The exact values, neighborhoods and queue receipts are retained in
[home02](../campaign-001/investigation/home02-timing-investigation.md),
[home03](../campaign-001/investigation/home03-timing-investigation.md) and
[home05](../campaign-001/investigation/home05-timing-investigation.md).
Their current host result files also each report **zero atomic-replacement
retries, zero requested retry wait and zero exhausted retries**. The known
Windows sharing-retry sleep path therefore did not contribute retry sleep in
these attempts. This does not exclude ordinary file I/O or another scheduling
delay.

The original host emits `episode_started`, publishes state and starts the HTTP
gateway before assigning its loop clock (`host/run_host.py:353–361`). Journal
events use the journal's earlier clock (`host/supervisor.py:86–93`). The old
external assessor subtracts the episode-start event (`campaign-001/assessment/
admitted.py:72–105`). At success the original loop breaks before updating its
per-tick scalar, while the journal stop follows cancellation
(`host/run_host.py:396–419`). These are directly observed measurement-boundary
differences. The 7–14 ms differences between recorded maxima are **not** measured
clock offsets and cannot be subtracted to rescue a historical attempt.

The unchanged host also performs synchronous work on the physics thread:

- Each journal event writes and fsyncs protected and public copies
  (`host/supervisor.py:98–102`); state publication writes two atomic snapshots
  (`107–109`, `594–608`, `633–634`).
- Each delivered camera capture passes through PNG and depth compression and a
  SQLite commit (`host/run_host.py:292–310`; `Storage Retention Implementation
  001/future/runtime_adapter.py:69–81`; `future/recorder.py:332–355`).
- Requested images are encoded and hashed (`host/run_host.py:298–305`), and a
  recursive storage census runs every five simulation seconds (`403–407`).

These paths identify work worth measuring. The retained events do not establish
which one, if any, caused a particular Campaign 001 spike. Model inference,
other processes, OS scheduling and the external storage monitor are likewise
unassigned possible contributors. Capacity passing does not measure contention.

## Additive implementation

[harness/run_host.py](harness/run_host.py) copies the original host runner and
imports the original supervisor, fixture validator, workcell and recorder
unchanged. It modifies only prospective timing measurement and local scheduling.
Control ownership, command admission, physical steps, task evaluation, evidence
durability and the clock pacing equation retain their previous behavior.

[harness/timing.py](harness/timing.py) loads the exact `TimingMonitor` AST class
from `Runtime 004/experiment.py`; its source file and class hashes are retained.
The numerical rules remain conjunctive and unchanged:

- Maximum observed wall-minus-simulation lag **strictly below 0.1 seconds**.
- Each complete one-second window within **0.95–1.05** RTF, endpoints inclusive.
- Out-of-tolerance complete-window fraction **strictly below 0.01**.
- At least one complete window. Trailing partial time is reported explicitly.

Initialization finishes before the one common loop origin is assigned. Full
samples occur before each loop's gateway/physics processing and after its host
work, including the storage census. A separate final sample captures the terminal
condition before cancellation, publication and cleanup. Sampling before physics
catches delayed wakeups before subsequent simulated time can catch up. These
samples are prospective operational evidence; they do not reinterpret old
episode-start events. The original journal remains retained and independently
inspectable, including initialization and terminal event chronology.

The protected `timing-samples.bin` contains little-endian float64 wall/simulation
elapsed pairs, 16 bytes per sample, with an exact `(0, 0)` first pair. An
`array('d')` stores bounded samples in memory; the ledger is written and fsynced
after the measured interval. Capacity is `2 * int(sim_cap_s / 0.002) + 16` rows,
reserved within the existing per-run storage quota with 2 MB for metadata.
The capacity guard fails closed. It does not drop samples or allow an unbounded
list of Python dictionaries.

`timing-v2.json` binds the binary SHA256, byte and sample counts, common origin,
terminal clocks/reason, frozen monitor identity, reproduced monitor report and
maximum sample. `result.json` binds that metadata hash through `timing_v2` and
preserves its legacy `timing` scalar/count from the same complete sample stream.
Its older `wall_elapsed_s` remains total process-run accounting, including
initialization and cleanup; it is not the measured terminal wall clock.

Phase measurements retain aggregate wall/current-thread CPU time and the largest
64 phases of at least 5 ms. Categories include gateway, adapter step, housekeeping,
conventional decision, evaluator, storage census and pacing sleep. Wall time
exceeding thread CPU time can include blocked I/O, preemption or waiting; it does
not identify a competing process or prove scheduler causation. Suboperations
within `adapter_step` remain grouped at this revision.

The native process requests `ABOVE_NORMAL_PRIORITY_CLASS` and a 1 ms timer period,
then records and verifies original-priority restoration and a paired
`timeEndPeriod(1)`. Failures remain visible and block qualification. This is a
prospective scheduling intervention, not a finding that the previous scheduling
policy caused the invalids. Microsoft documents AboveNormal below High, and
priority affects CPU scheduling without eliminating disk/memory interference.
[SetPriorityClass documentation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setpriorityclass).
The timer request must be paired, does not improve the performance counter, and
may increase scheduling overhead.
[timeBeginPeriod documentation](https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod).
Python also documents that sleep can overshoot through scheduling activity;
a requested wait duration is not an execution deadline.
[Python time documentation](https://docs.python.org/3/library/time.html#time.sleep).

## Qualification and verification

Nine focused timing tests passed on the initial implementation: common origin
and final boundary, lag equality, fraction equality, inclusive RTF endpoints,
pre-catchup delay capture, bounded sample/diagnostic storage, nonfinite/regressing
samples, and corrupted or inconsistent artifacts. The new runner's CLI import
also passed. These tests establish the measurement contract, not real-time
performance.

Fresh native qualification must bind the exact new sources before running and
use the shared compute queue. Outputs become qualification inputs only after an
independently queried official receipt reports `succeeded` and integer exit
status `0`. Retained binary replay must verify exact length/hash/count, finite
nonnegative monotonic clocks, first/common origin, final terminal boundary,
unchanged monitor source, complete report equality and scheduling restoration.
The independent assessment must also preserve the original source, evaluator,
isolation, lifecycle and storage gates.

Use fixed known-fixture reference work before model requalification, retain every
failed qualification and diagnose the new bounded phase evidence before a further
infrastructure revision. A passing native run qualifies only that native path;
it does not cover concurrent WSL/runtime/model activity. Any model qualification
must use a fresh workspace/invocation, exact bootstrap and separately admitted
resources. Freeze final sources only after the required fresh qualification;
Campaign 002 scored admission must consume that final binding. No new revision
reuses or replaces a Campaign 001 slot.

## Prospective dev005 diagnostic revision

The preceding implementation and qualification description records the initial
Campaign 002 harness. Its frozen revisions and all earlier attempts remain
unchanged. The first model smoke attempt, `RCI001-C02-smoke-001`, completed under
official queue job `20260927T211402369736Z-6428c112` with `succeeded` and integer
exit status `0`, but failed the unchanged timing criterion. The retained maximum
lag was approximately 0.406 seconds. At loop wall 434.313–434.547 seconds,
`adapter_step` consumed 0.234 seconds wall time and 0.015625 seconds thread CPU;
`housekeeping` then consumed 0.187 seconds wall time and zero observed thread CPU
at 434.563–434.750 seconds. A further adapter interval took 0.140 seconds.
The observation UTC gap of 518.771 ms independently shows real slowdown. These
measurements establish a stall, without attributing it to the model, a specific
I/O operation, or a competing process. The atomic replacement retry counters
were zero, excluding the recorded replacement retry sleeps as this explanation.

The deployed Python's earlier `monotonic` clock reports `GetTickCount64()` with
0.015625-second resolution. The new prospective runner uses `perf_counter`
(`QueryPerformanceCounter()` on this Windows deployment) for both the pacing
equation and every retained timing/phase measurement. Clock implementation,
resolution, monotonic/adjustable properties and the native
`QueryPerformanceFrequency` integer are retained. An initialization bracket
records QPC-before, the auxiliary monotonic clock, Unix time and QPC-after;
the original journal's monotonic origin is also recorded. This bracket permits
bounded cross-log correlation without claiming simultaneous readings. The
legacy metadata key `loop_origin.monotonic_s` now holds the primary QPC origin;
`clock_name`, `clock` and `clock_context` identify that clock explicitly.
Original journal chronology remains on its original clock. There is no
retrospective clock conversion, and finer resolution is not claimed to repair
the observed half-second stall.

The additive [instrumented journal](harness/instrumented_journal.py) preserves
the original synchronous writes, flushes, fsyncs, protected/public order,
atomic replacements, bounded retry policy, quotas and error propagation. It
measures serialization, preparation, open, write/flush, fsync, close and replace
separately. Continuity retains its original implementation with one outer timing
scope. Adapter scopes measure physics, motion recording, sensor polling, setup
resumption, the existing combined image/depth encoding and SQLite bridge,
requested-image encoding/hash, public observation update, feedback/events,
sensor request and public-packet construction. The bridge remains one combined
scope; an interval there would require a further prospective probe to distinguish
compression, lock acquisition, SQLite commit and its storage guard. No recorder
internals are changed in this diagnostic revision.

All timing phase scopes retain wall, thread CPU and process CPU aggregates.
They retain at most 128 phase names, eight slow intervals per phase, and 64 slow
intervals globally, with a 5 ms minimum for retained interval rows. Nested
durations overlap and must not be added together. CPU deltas can be quantized;
zero observed thread CPU does not prove that a specific blocking syscall caused
the interval. Sample and phase capture add overhead, which is included in the
unchanged live timing gate. The before-physics sample and final-before-cleanup
sample remain mandatory, and no timing thresholds, task logic or evidence
durability requirements are relaxed.

The next declared apparatus diagnostic is a fresh fixed 720-simulation-second,
840-wall-second serve-mode episode using the blocked-home fixture and the same
background storage guard, with no model or recovery invocation. Root prepares,
freezes and queues this bounded diagnostic. It tests long-duration host behavior
and helps localize any stall; it does not replace the final native suite, model
smoke or campaign pilot requirements. Any further repair must follow retained
diagnostic evidence and a new source revision. The failed smoke remains invalid.

## Prospective dev007 collection diagnostics

The 720-second no-model probe `RCI001-C02-host-probe-001` completed under official
queue job `20260927T214502202347Z-90eb9b2d` with `succeeded` and integer exit
status `0`. Its strict timing assessment failed: maximum lag was
0.11345209997000438 s at wall 582.4414520999999 s, with 720 complete RTF windows
and zero outside tolerance. This failed attempt remains preserved.

The five retained evaluator intervals above 5 ms began at approximately 51.597,
185.158, 317.187, 448.657 and 582.348 seconds. Their respective wall durations
were 10.951, 35.900, 55.586, 74.590 and 93.264 ms. They recur 131.47–133.69 seconds
apart and their thread CPU deltas approximately match their wall durations.
The final spike contributes approximately 93.264 ms to the 113.452 ms peak lag.
The largest identified journal fsync intervals were 46.404 and 45.179 ms,
separate from this evaluator peak. This differs from the earlier smoke's
largely non-CPU stall and does not establish one cause for both episodes.

The unchanged `Cell.outcome` copies the current fixed order, then calls
`IndependentEvaluator.evaluate_cell`. That method snapshots the current
contacts, registered objects, regions and protected state, and evaluates that
snapshot. It never traverses `Journal.events`. The journal nevertheless retains
each nested observation packet in its growing in-memory event list. The
periodic growing evaluator CPU intervals are consistent with a whole-heap
collection triggered by allocation inside evaluator work, but no collection
callback evidence was retained in probe 001. This is a hypothesis, not a causal
finding or permission to change evaluator polling, predicates or thresholds.

The additive [GC observer](harness/gc_diagnostics.py) registers a bounded
`gc.callbacks` observer while leaving automatic collection, thresholds and
debug configuration unchanged. Python documents these callbacks specifically
for timing and counting collections; collection supplements reference counting.
[Python 3.12 garbage collector interface](https://docs.python.org/3.12/library/gc.html).
There are no calls to disable, enable, freeze, retune or explicitly collect.
The observer retains collector enabled state, thresholds, counts, per-generation
statistics and debug flags before/after, and removes only its own callback.

Each `gc-collections.bin` row contains twelve little-endian float64 values:
QPC elapsed start/end, thread/process CPU deltas, generation, collected and
uncollectable counts, collecting native thread ID, host-thread flag, host-phase
code, and simulation elapsed start/end. The QPC and simulation origins match
the existing timing ledger. `timing-v2.json.garbage_collection` binds its exact
SHA256, byte count, collection count, encoding, phase-name table, boundaries and
unchanged-policy receipt. The existing result-to-timing-metadata hash binds this
additional diagnostic file. The reader verifies those bindings before presenting
collection associations.

The observer preallocates at most 8,192 rows, reserving 786,432 bytes plus 16,384
bytes for its metadata within the unchanged run storage cap. It writes and
fsyncs after the measured interval. Overflow, malformed/unpaired callbacks,
external callback removal or collector-policy changes fail the diagnostic
closed. Its observer attaches just before the common loop origin and detaches
just after the final sample; any initialization/terminal-boundary collections
retain their actual relative clocks and are not silently counted as loop work.
All callback overhead that occurs inside the loop remains visible to its timing
gate. A phase label for collection on another thread is only temporal context;
the collecting-thread identity prevents attributing that CPU to the host thread.

The next separately frozen no-model probe is declared for 240 simulation seconds
and 300 wall seconds. It seeks direct generation/phase overlap around the first
two previously observed periodic spikes. Added observation can shift collection
cadence, and the absence of a spike in this shorter interval would not establish
that collection cannot cause one. Any collector-policy intervention requires a
further prospective revision, measured memory implications and fresh native/model
qualification. No evaluator or original runtime source is changed here.

## Prospective bounded collector deferral and memory ceiling

The completed 240-second probe `RCI001-C02-host-probe-002` passed its timing
check with maximum lag 0.0586962 s. Its authenticated callback ledger contains
247 collections: 225 generation 0, 20 generation 1, and two generation 2.
The generation-2 collections took 10.0691 and 37.0645 ms, wholly inside the
two slow evaluator intervals and accounting for 96.58% and 99.01% of their
wall durations. Both ran on the host thread and reclaimed zero objects.
[The hash-bound analysis](qualification/host-probe-002-gc-analysis.json) records
all provenance, same-run overlap, CPU quantization and comparison limitations.
This supports a collector intervention. It does not retrospectively prove the
collector caused probe 001's later pause or the earlier smoke's non-CPU stall.

The next revision defers automatic cyclic collection only across the bounded
measured physics interval. The observer attaches during initialization, saves
enabled state, thresholds, debug flags and freeze count, and records an explicit
disable operation immediately before the common QPC origin. Every loop checks
that automatic collection remains disabled; each memory sample also verifies
the saved thresholds, debug flags and freeze count. An unexpected collection
or configuration change fails the resource gate. Ordinary reference counting
continues. No evaluator/controller logic, polling rate, evidence durability or
validity threshold is changed.

The final memory read and collector verification occur before the final timing
sample. Original collector settings are restored immediately afterward and in
the exception/finally paths before cancellation and cleanup. Each setting is
attempted independently so a threshold restoration failure cannot skip restoring
the enabled state. A detected external configuration change remains an invalid
condition even if restoration succeeds. Callback diagnostics continue through
cleanup and retain any deferred collections with their actual outside-loop
timestamps; their cost is not relabeled as physics time. No explicit collection,
freezing, unfreezing or periodic task pause is introduced.

The [native memory guard](harness/memory_guard.py) uses an unnamed Windows Job
Object containing exactly the dedicated host process. Before simulator
initialization it applies `JOB_OBJECT_LIMIT_PROCESS_MEMORY` with a 2 GiB
commitment ceiling. Both initial and final native readbacks must show the exact
flag, ceiling, current-process membership, and a one-process job list containing
that host PID. The ceiling covers allocations between periodic reads. The
observer uses `K32GetProcessMemoryInfo` for private commitment, working set and
lifetime peaks. These are different quantities; the soft ceiling uses current
private committed bytes.
[Windows job commitment limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information),
[process memory counters](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex).

The declared limits are:

- Pre-loop baseline private commitment strictly below 1 GiB.
- Soft stop at `min(1.5 GiB, baseline + 512 MiB)`, with equality failing.
- Native process commitment ceiling of 2 GiB for the host's lifetime.
- Periodic memory reads targeting 100 ms, with fresh origin and terminal reads.
- Maximum observed sample-end gap of 200 ms, including origin/terminal coverage.

The 200 ms completeness limit is not a relaxation of timing: the original
strict 100 ms lag limit remains separately required. A missed memory interval,
query failure, soft breach, hard-limit allocation failure, setup/readback failure,
unexpected collector change, failed restoration or incomplete evidence marks
infrastructure invalid with unknown task outcome. The job handle is closed and
the success/failure retained. The host is not detached from its Job Object;
its commitment limit remains for its bounded process lifetime. No separate
watchdog or model-process memory architecture is added.

`memory-samples.bin` contains bounded seven-float64 little-endian rows: QPC read
start/end relative to the loop origin, current private commitment, working set,
lifetime peak commitment, lifetime peak working set, and sample kind (`1` origin,
`0` periodic, `2` terminal). Capacity is `ceil(wall_cap_s / 0.1) + 16`; its full
size plus 32 KiB metadata is reserved under the unchanged storage cap. The
ledger is written/fsynced after timing ends. `timing-v2.json.host_memory` binds
its hash, size, count, limits, baseline, native receipts and completeness.
`result.native_memory_job` repeats the same native receipt for early-failure
inspection. The result's existing metadata hash binds the full resource evidence.

GC metadata now uses `rci-gc-diagnostics-2`, retaining the previous compact
collection-row format but explicitly recording the declared policy and all
disable/restoration transitions. `policy_unchanged` is false, while the original
configuration must be restored. Any collection overlapping the measured interval
fails the new collector gate. The host's legacy timing pass remains the numerical
monitor plus Windows scheduling; independent assessment additionally requires
the resource gates and source identities. Historical attempts retain their
original schemas and outcomes.

Qualification must first use the separately declared 900-simulation-second,
1100-wall-second no-model episode covering the maximum scored duration, then
the required fresh native/model qualification against the exact final revision.
These memory constants are declared infrastructure limits, not a measured claim
that all model-loaded runs fit them. Any failure remains retained and requires
diagnosis before another prospective change.

## Prospective bridge and recorder localization after probe 003

The authenticated [probe 003 analysis](qualification/host-probe-003-analysis.json)
retains an invalid 694.73-simulation-second attempt. Automatic cyclic collection
did not overlap measured physics, and observed private commitment remained below
the declared soft and hard ceilings. The terminal sensor-recording bridge took
125.839 ms wall time with 15.625 ms host-thread/process CPU time. That interval
preceded a 206.475 ms memory sample gap and a 133.133 ms maximum timing lag. The
combined bridge boundary does not identify the delayed operation. Its terminal
image was ring-only, but that path still encodes both arrays and synchronously
commits availability metadata. Neither GC deferral nor the memory ceiling
qualified this failed attempt, and these findings do not explain the earlier
non-CPU smoke stall.

The next separately frozen diagnostic adds
[instrumented_recorder.py](harness/instrumented_recorder.py). The original
`Recorder` methods remain inherited. Fixed-name scopes distinguish RGB PNG
encoding, depth NPZ encoding, acquisition/release of the same `RLock`, the
recorder image call, persistence selection, logical quota checks, physical page
checks, and native SQLite execute/commit operations. The connection adapter
delegates to the existing native connection and returns native cursors. The
original constructor still establishes DELETE journal mode and FULL synchronous
durability before the adapter is installed. All SQL, encoded bytes, retention
selection, ring bounds, quotas, transaction order, error propagation and durable
finalization remain unchanged. No asynchronous writer or batching is introduced.

These 23 declared phase names share the existing bounded timing aggregate and
slow-sample stores. Nested durations are inclusive and must not be summed.
All measurement overhead occurs inside the same strict timing interval;
initialization and terminal cleanup receive null scopes as before. The GC,
memory and timing contracts remain unchanged. A long wait inside `execute` or
`commit` would localize its host call, but would still not distinguish disk,
filesystem contention, native synchronization or operating-system descheduling
without additional evidence.

The focused disposable-fixture tests compare functional bridge/constructor ASTs,
exact PNG/NPZ bytes, SQL and commit order, fsync operation sizes, finalized SQLite
and gzip bytes, ring/trigger/quota outcomes, native cursor and transaction
semantics, concurrent event serialization and lock release, encoding errors,
commit failure propagation, and representative-quota failure artifacts. An
injected 120 ms commit wait is retained in both the nested commit phase and the
complete timing interval while cleanup remains outside it. These apparatus
checks establish measurement parity, not physical timing qualification. The
next 900-second episode requires its own predeclared manifest, frozen source,
official successful queue receipt, and independent assessment; probe 003 remains
invalid regardless of that future result.
