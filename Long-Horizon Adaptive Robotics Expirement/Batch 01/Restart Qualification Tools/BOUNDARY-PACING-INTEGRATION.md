# Recovery boundary pacing integration

Current source: **`281e0e44d81af0258f5bad36f541432635319c016b757df5899038120b77cdd3`**. The original fixed-target implementation described below is retained as history and superseded by the one-tick feedback correction at the end of this note.

Root authorized this change after diagnostic `20260923T091820736439Z-183e9e54` officially succeeded/0 at 2026-09-23 09:18:45.986400 UTC and released the source hold. Root's completed-profile handoff reported a cluster of warm capture/forced-geometry operations around recovery dispatch and approximately 71.5 ms maximum lag. This implementation task did not independently reprocess that evidence or infer a new timing tolerance.

The prior fixture source is archived verbatim at [run_screen.7af9eb67b5b367b545682785069859cb9a7cb9a9f2f670d25ebd6894a70ade11.py](source-archive/run_screen.7af9eb67b5b367b545682785069859cb9a7cb9a9f2f670d25ebd6894a70ade11.py), matching that SHA-256. The integrated [run_screen.py](../Recovery%20Qualification/run_screen.py) SHA-256 is **`ee64f3805f09ddfc33d5529cd64f5401a724bd2f2f691aa3a3933eb8e740eab5`**.

`wait_recovery_boundary_ready` is defined directly in the fixture, so the normal full source archive binds it. It retains the semantics of [the reviewed fragment](boundary_catchup_fragment.py), SHA-256 `78cc9142418790c07aeee56e7f438649310a6d3595700dbfb423fdd5f1cc0c45`. The only extension reads the active HoldWindow's entry/exit physics-tick counters and records their difference. There is no runtime import of this proposal folder.

Only the existing public-ready wait after the after-absence rich snapshot and forced geometry sample is replaced:

```python
details['stage'] = 'fresh_sensing_before_recovery'
details['recovery_boundary_pacing'] = wait_recovery_boundary_ready(loop, 8.)
```

The helper first records actual entry wall/simulation elapsed times in the existing monitor, fixes its target to their maximum, then uses the unchanged `loop.until` with the original eight-second timeout until simulation reaches that fixed target and public sensing is ready. The original at-least-one-step behavior remains. It records exit clocks and residual lag in the same monitor. A positive residual remains possible; this is not a moving zero-lag target, a clock reset, a cleared timing history, or a new pass threshold.

The returned `recovery_boundary_pacing` details include entry/exit clocks, fixed target, advanced simulation time, elapsed wall time, residual lag, `entry_hold_tick_checks`, `exit_hold_tick_checks`, and `hold_tick_checks_added`. Normal terminal details retain this report. Ordinary steps continue the existing physics, sensing, authority renewal, events, trajectory, unchanged contact/height hold checks, dense geometry, monitor and caps at the native 2 ms timestep. HoldWindow remains active. Thus extra hold ticks and their actual wall/simulation duration belong to the full cut-to-accepted-dispatch interval; no elapsed time is subtracted. The configured five-second after-absence landmark itself stays at its original position.

There is no additional step between cut capture and cancellation, or within pre-dispatch capture → admission → post-admission capture. All existing boundary timing wrappers and operations remain. The initial public-pick sensing wait, child/parent authority, original trial selector, caps and physical predicates are unchanged. The later dispatch posture and absence duration require fresh measured support; earlier failures are retained, and this source change alone does not establish a timing or physical pass.

[Fourteen bounded tests](test_integrated_boundary_pacing.py) passed in **0.145 s** across the existing instrumentation/selector checks and six integrated pacing checks. Fake clocks verify fixed-target termination, preserved prior/entry/exit timing observations, unchanged freshness requirement, at least one ordinary step, original timeout/cap exception propagation, and exact added hold-tick reporting. Stub trial execution and AST checks show the scheduler replacement is the only trial-body difference and all other functions/classes are unchanged. No Runtime imports, native model, actual physics, queue call or heavy test was used.

## One-tick feedback correction

After diagnostic002 officially completed successfully at 09:22:46 UTC with receipt `20260923T092209931696Z-474527be`, root reported that physical predicates passed but two timing windows still failed. Root's completed-profile handoff measured 12 additional ticks / 24 ms of simulation while the fixed-target wait itself cost 11.775 ms wall time, leaving 11.208 ms residual lag. The fixed target therefore did not account for the work needed to service its own ticks. These are root-provided profile observations; this implementation task did not reprocess the raw evidence. Earlier failed windows remain failed.

Root authorized feedback readiness using exactly the native timestep, `loop.dt`, as scheduling resolution. Before changing the fixture, the exact prior source was archived at [run_screen.ee64f3805f09ddfc33d5529cd64f5401a724bd2f2f691aa3a3933eb8e740eab5.py](source-archive/run_screen.ee64f3805f09ddfc33d5529cd64f5401a724bd2f2f691aa3a3933eb8e740eab5.py), matching that SHA-256. The new fixture source is `281e0e44d81af0258f5bad36f541432635319c016b757df5899038120b77cdd3`.

Each readiness predicate first calls the unchanged `public_ready()`, then reads fresh wall/simulation elapsed time, observes that pair in the same TimingMonitor, and requires both fresh sensing and `wall_elapsed - simulation_elapsed <= loop.dt`. Reading the clock after `public_ready()` includes its work in the lag decision. This uses the exact native 2 ms tick; there is no CLI tuning parameter or changed TimingMonitor threshold, and it does not chase zero lag. The old fixed entry target remains in `fixed_entry_target_reference_sim_s` as descriptive metadata only.

The helper still uses ordinary `loop.until(..., 8.)`; the original simulation timeout and ordinary loop wall/simulation caps terminate persistent overload. No fallback admission occurs when readiness cannot be reached. Entry and exit monitor observations remain, including failed attempts. The report now also retains predicate observation count and last predicate clocks/lag, exact `readiness_lag_limit_s`, timeout, success and error. A details dictionary is attached before calling the helper so partial timing/tick/error facts survive an exception. The original exception is propagated without replacement. Exit lag is observed separately and is not represented as a guaranteed margin after subsequent work.

Actual additional hold-tick counts, full wall/simulation absence duration, every ordinary native hold/geometry sample, and the protected cut/cancel and dispatch/admission groups remain as described above. The scheduling change still requires fresh measured construction/validation support and does not by itself establish a timing pass.

All **14 focused tests passed in 0.146 s** after this correction. Updated fake-clock cases verify convergence with nonzero tick work to at most one tick of measured lag; sensing work is included; current simulation still executes at least one ordinary tick; unchanged monitor history and hold/geometry frequency; and persistent overload propagates the original timeout/cap error with partial report. Stub call-order and AST checks retain every boundary operation and permit only the explicitly recorded scheduler insertion in the trial body. No Runtime change, native work, physics or queue call was performed.
