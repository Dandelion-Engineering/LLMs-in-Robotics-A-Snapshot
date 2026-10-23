# Home 02: a short lag excursion invalidated an observed recovery

**The predeclared result remains infrastructure-invalid, with observed evaluator
success and scored task outcome unknown.** The only failed assessment check is
`current_episode_frozen_one_second_rtf_and_strict_per_tick_lag`. This investigation
describes retained measurements; it does not change the origin, threshold,
framework, scoring or attempt allocation.

Official queue job `20260927T192159944624Z-a05cc835` was independently queried and
confirmed `succeeded`, integer exit status `0`, before outcome inspection. Its
execution interval was 19:22:00.182614–19:27:34.447846 UTC on September 27, 2026.

## Observed measurements

The [admitted assessment](../execution/RCI001-C01-home-02/assessment.json) records:

| Measurement | Retained value | Predeclared disposition |
|---|---:|---|
| Original host per-tick maximum lag | 0.09900000003290188 s, 157,809 samples | Pass: strictly below 0.1 s |
| Reconstructed journal maximum lag | 0.11300000002975708 s | Fail: not strictly below 0.1 s |
| Complete reconstructed one-second windows | 315 | All within 0.95–1.05 RTF |
| Out-of-tolerance window fraction | 0 / 315 = 0 | Pass: below 1% |
| Maximum journal sample gap | 0.18800000002374873 s | Retained spacing limitation |

The protected host completed successfully, with valid natural terminal closure,
namespace retirement, source/evaluator/evidence checks and storage coverage. The
late explicit retirement and stale-token HTTP403 receipts remain absent under the
already declared successful-host-closure branch. There is no additional lifecycle
or integrity failure identified here.

The [protected journal](../../local-evidence/campaign001/RCI001-C01-home-02/host/public-history.jsonl)
contains the maximum directly at **observation event 716, sequence 701**. The
reconstruction's maximum is the maximum lag of its input samples; this particular
0.113-second value was not created by one-second boundary interpolation.

All following times are relative to the retained `episode_started` event 2, whose
wall elapsed time is 0 and simulation time is 1.0000000000000007 seconds:

| Event | Type / sequence | Relative wall (s) | Relative simulation (s) | Lag (s) |
|---|---|---:|---:|---:|
| 715 | observation / 700 | 70.547 | 70.526 | 0.021 |
| **716** | **observation / 701** | **70.735** | **70.622** | **0.113** |
| 717 | observation / 702 | 70.813 | 70.778 | 0.035 |
| 732 | observation / 717 | 72.360 | 72.260 | 0.10000000003357457 |
| 822 | observation / 807 | 81.469 | 81.430 | 0.039 |
| 823 | continuity committed | 81.532 | 81.430 | 0.102 |
| 824 | observation / 808 | 81.610 | 81.574 | 0.036 |

Between events 715 and 716, 0.188 seconds of recorded wall time elapsed while the
simulation advanced 0.096 seconds, increasing lag by approximately 0.092 seconds.
The next sample shows 0.078 seconds of wall time and 0.156 seconds of simulation
advance, bringing lag back to approximately 0.035 seconds. Event 716's separately
recorded UTC timestamp is 19:23:12.075170. UTC is supplied for finding the event;
the scoring calculation uses retained monotonic elapsed values.

There are three journal samples at or above the strict 0.1-second threshold:
716, 732 and 823. Event 732 lies extremely close to the numerical boundary, but
the overall failure does not depend on that near-boundary sample: event 716
exceeds the threshold by approximately 13 ms and event 823 by approximately 2 ms.
Sparse samples do not establish the exact duration or peak between samples.

The one-second rate criterion and maximum-lag criterion measure different things.
The retained 70–71-second window has RTF 1.0064623655757572, and the 81–82-second
window has RTF 1.0002800000020784. A brief delay followed by simulation catching up
can therefore pass the full-second rate check while failing the maximum sampled
lag check. No window was removed or recomputed using a more permissive origin.

## Clock-origin limitation and what remains unknown

The unchanged [host loop](../../host/run_host.py) emits `episode_started`, publishes
state and starts the HTTP gateway **before** assigning its loop `start` clock
(lines 353–361). It then records its original per-tick scalar as
`monotonic_now - loop_start - (simulation_now - initial_simulation)`
(lines 399–402). The
[journal](../../host/supervisor.py) records event wall time relative to its own
earlier start (lines 86–93); the external reconstruction subtracts event 2's wall
and simulation values.

Consequently, the reconstructed lag includes the interval from the episode-start
event to loop-clock initialization. The host scalar excludes that interval.
Journal events are also recorded at different points within host processing than
the per-tick scalar. The terminal journal event follows cancellation, whereas the
host scalar is not updated on the successful terminal break. Here the largest
journal lag occurs well before terminal closure, so terminal cancellation does
not explain the observed maximum.

**The observed 14 ms difference between the two maxima is not a measured clock
offset.** The retained host result contains a maximum and sample count, without
the timestamp or full sequence of per-tick lag samples. It therefore cannot show
whether that scalar maximum occurred at event 716 or at another instant. The
loop-start clock itself is not retained as a separately alignable receipt. The
origin difference is supported by source order; its exact value and contribution
to this episode's maximum difference remain unresolved. Subtracting 14 ms to
produce a passing counterfactual would not be justified.

Event 823 records 63 ms of wall advance at unchanged simulation time between the
preceding observation and continuity commit. That is an observed processing
interval associated with the commit, not proof of which operation caused all of
the delay. Similarly, event 716's neighboring records are observations. These
records contain no retained scheduler, CPU-contention or per-operation I/O trace
that attributes its excursion to model reasoning, the external monitor, sensor
work, filesystem work or another host process. Those causal explanations remain
unknown.

## Campaign implication and provenance

Under the frozen protocol, this timing-only failure is an **ordinary
infrastructure-invalid attempt**. It consumes slot 3, is not replaced and is not
a scored robot failure. Following valid preceding attempts, it sets the
consecutive ordinary-invalid count to one. It does not itself activate the
immediate source/isolation/evaluator/evidence-integrity, reserve-threat or
unverified-namespace stop conditions. The root operator applies the predeclared
two-consecutive-invalid rule to later attempts.

Inspected retained identities:

- Protected journal SHA256:
  `f35e1ae643406d23647481bd22b465f4f367a678868da8c812650747a84cf601`.
- Assessment binds unchanged admitted assessor SHA256:
  `af4919faa927150fc97ea35023483e85023ce974f30d3ed98423614c77b5a7be`.
- Admission certificate SHA256:
  `89140521f0025febf0c9cdb3ec40eadbe426bb6cee512f81e9a4964855103c86`.
- Official queue receipt SHA256:
  `e2bc98a1bb57bcd8ce455932a4b6a7baf2f48017f81126c7e7faa35d694f8fae`.

This was a bounded read of the existing assessment, compact event records and
unchanged source. No simulation, model invocation, benchmark, qualification rerun
or source/protocol amendment was performed.
