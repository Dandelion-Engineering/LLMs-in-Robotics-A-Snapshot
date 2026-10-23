# Historical fixed-target boundary pacing fragment

The fixture owner integrated this pattern directly into `run_screen.py` after root authorization (reported source SHA-256 `ee64f3805f09ddfc33d5529cd64f5401a724bd2f2f691aa3a3933eb8e740eab5`), adding actual HoldWindow tick counts under `details.recovery_boundary_pacing`. The owner reported 14 focused instrumentation/selector/integrated fake-clock tests passing. The standalone `boundary_catchup_fragment.py` remains an unimported historical proposal, and its tiny fake-clock tests do not provide physical evidence.

[Completed diagnostic 002](BOUNDARY-TIMING-PROFILES.md) established that this fixed-entry target is **insufficient**: 12 ordinary steps advanced simulation 24 ms but consumed 11.7746 ms and left 11.2081 ms of lag before the next atomic observation group. Physical checks passed, but two warm RTF windows still failed. Root then authorized a prospective feedback predicate requiring fresh public sensing and actual lag no greater than `loop.dt`, with the same ordinary steps, eight-second phase timeout, caps and unchanged timing monitors.

Completed diagnostic 003 used that bounded feedback rule and passed its single selected physical trial and host timing: 23 ordinary ticks advanced simulation 46 ms, leaving 1.5848 ms of lag; maximum lag was 47.4839 ms with zero failing RTF windows out of 18. The actual hold extended to 5.046 simulation seconds and 5.0456211 wall seconds. Its summary remains diagnostic-only, with 39 declarations deferred and qualification ineligible. [The profile note](BOUNDARY-TIMING-PROFILES.md) retains the exact receipt/hashes and both earlier failures. Fresh full construction and untouched independent validation are still separate required evidence; this local pass establishes neither.

The remaining text preserves the original fixed-target proposal and its reasoning. It is historical, not an instruction to replace the integrated feedback rule.

The narrow proposed insertion replaces the existing `loop.until(loop.public_ready, 8.)` in `trial_body` **after** `protected_held_state_after_absence` and its forced geometry record, **before** `protected_state_before_recovery_dispatch`. Keep the literal existing timeout of 8 seconds and every other observation/control call in place. Root/fixture owner may paste the function into the source-held fixture or explicitly add this helper to the complete source manifest; an unbound import is not an integration.

```python
details['stage'] = 'fresh_sensing_before_recovery'
details['boundary_catchup'] = wait_recovery_boundary_ready(loop, 8.)
# Existing pre-dispatch capture, forced geometry, admission, endpoint hold
# observation, post-admission capture and forced geometry follow unchanged.
```

At entry, record the actual accumulated lag with the same monitor, then freeze the target as `max(entry simulation elapsed, entry wall elapsed)`. Use only `loop.until` and ordinary `QualificationLoop.step` until that target and the unchanged public-ready predicate both hold. Keep the original at-least-one-step behavior. A moving `wall <= simulation` target can fail to terminate because every iteration adds real overhead; the frozen target closes existing debt without claiming new work takes zero time. Residual lag remains measured and can remain positive. No monitor history, deadline, tolerance or clock is reset.

Every catch-up step services the existing physics, sensors, authority renewal, events, trajectory, hold checks, dense geometry and monitor/cap logic. Never replace it with direct `cell.tick`, change the timestep, or defer/drop observations. Record the returned timing facts as part of existing details; final retention can occur with the existing result writer. Boundary profile observations remain on the actual clock.

**Meaningful protocol change:** the configured five-second after-absence landmark remains at the same point, but pre-dispatch and accepted recovery now occur after additional real physics ticks. Keep `HoldWindow` active through those ticks; its actual wall/simulation durations and `recover_held_admitted` endpoint must include them. Do not subtract catch-up time, reuse the prior physical snapshot, or assume old state/absence envelopes cover the later state. This prospective source change requires fresh construction/validation support before acceptance. Failed old runs remain failed.

Do not place catch-up between the at-cut snapshot and cancellation, or between pre-dispatch capture, admission and post-admission capture. Those observation/control groups remain atomic with respect to stepping. If an inseparable group itself exceeds the existing timing budget, this scheduler change cannot cure it; reduce its actual computational/serialization work instead. No expectation that B timing will pass is established here.

Source hypotheses awaiting the profile: warm rich capture plus forced-geometry/event writes can accumulate across several boundary groups before the next ordinary step; `Records.event` serializes the same payload for its hash and again in the containing event; `QualificationLoop.step` currently adds hold/geometry work after the base class's pacing sleep. These are concrete profiling targets, not measured causal attribution. A future single final pacing point or byte-equivalent single-pass event encoding would be separate reviewed changes, not part of this fragment.
