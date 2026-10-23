# Measure final qualified-restart CPU cost

`benchmark_qualified_restart.py` is queue-only and non-authorizing. It runs no Cell, native model, physics, renderer or inference. No real bundle or retained physical snapshot was read while preparing this helper. Seven synthetic tests pass; actual measurements remain unrun.

The current usual carry path with one mapped route calls `qualified_entry_identity` four times: grip, route, then both entries in the reported evidence. Each call hashes the entire bundle and repeats compatibility/identity checks. The route's `M` corridor boxes are validated once, then each other registered object's bounds is compared with the corridor union. Each `overlaps` call revalidates both boxes. For 12 registered objects in an n10 scene, a clear route can therefore reach `11M` overlap calls and `23M` box validations, besides fixed checks. Selection also JSON-copies the selected calibration; classification hashes it once; the two route identity calls compare its full envelope. `restart_begin` includes the selected calibration and serializes it both for the payload digest and the containing event before disk flush.

The current compact-cover implementation is `Engineering Investigation/compact_construction_corridors.py`, not the earlier exact-pruning helper. Its candidates group geometry/center bins and retain covering boxes with provenance; Runtime ultimately receives the chosen plain `min`/`max` dictionaries in `clearance_corridors_m`. The benchmark measures the actual final list. It assumes no compression ratio, cover selection or timing gain.

## Provisional rule: size and digest only

Submit this **child command through the shared queue**, with an actual completed provisional rule and fresh output directory:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/benchmark_qualified_restart.py' --provisional-rule '<actual provisional-rule.json>' --output 'D:\CodexEvidence\LLMs-in-Robotics\restart-provisional-size-001'
```

This mode reports file/canonical bytes, each cell's actual corridor count/canonical bytes and exactly five direct canonical rule digests (first plus four repeats). It never creates acceptance/context or calls the loader, selection, classifier or event encoder. It cannot measure the full qualified path; do not extrapolate an accepted-bundle timing result from it.

## Accepted bundle: actual protected API replay

After actual root acceptance and completed assembly, submit:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/benchmark_qualified_restart.py' --development-freeze '<accepted assembly directory>\development-freeze.json' --assembly-receipt '<retained official assembler succeeded-0 receipt.json>' --cut-states '<completed extraction directory>\<selected trial>\measured-states.json' --events '<original completed screen directory>\<selected trial>\events.jsonl' --output 'D:\CodexEvidence\LLMs-in-Robotics\restart-qualified-cpu-001'
```

`assembly.json` defaults to the freeze directory; `--assembly` can identify it explicitly. There is no acceptance override or synthesized context. The helper requires the completed accepted assembly, its exact script/output/job/timestamps and retained official receipt, and independently checks that receipt against installed queue state. It also requires the exact assessor receipt already referenced by the bundle and verifies its recorded job/output/source identities. It rehashes assembly inputs, bundle artifacts and implementation references. The actual Runtime loader then verifies the accepted freeze/bundle/artifacts and constructs the protected context.

`--cut-states` uses the extractor's existing `states.cut` shape. The original stream must be an exact verified bundle artifact. Its file hash, indexed line bytes, event ID/type, payload hash, snapshot digest and protected Python source identities must match. The event must be `protected_carry_state_before_cut`, with a `closed_grip_transfer` exposure. No modified or reconstructed cut is substituted. Choose retained source-matched cuts for the actual declared mapped cells; the helper does not choose a favorable cell or require the replay's assessment to pass.

Exactly five actual `select_restart_calibration`→`classify_restart` calls retain separate selection/classification costs, states, assessment digests and whether the qualified route path was reached. The first assessment is retained in full. Unknown/failed classifications remain visible; `status: complete` does not make them valid qualification or a measured full route path. First means first call in this process after verification/setup, not a cold OS cache experiment.

Event encoding executes the unchanged `canonical` function and `Evidence.emit` method extracted from current `Runtime/experiment.py`, without importing Cell. It uses a temporary `StringIO` sink and the actual protected snapshot/selection/calibration/report/identity payload. Capture landmarks are explicitly absent; the benchmark emits no real intervention event. This measures the two encodings, hash and in-memory write, excluding real disk/flush latency, contention and live capture. Loader/artifact verification, protected-input materialization and total setup are reported separately.

## Read the result within its scope

`summary.json` contains queue identity, all five call costs, exact inputs/source inventories before and after, `inputs_unchanged`, structural sizes, errors and explicit offline/nonphysical/no-readiness flags. Failed attempts retain a failed summary and exit 1; output must be fresh on another attempt. After natural completion, retain the helper's official receipt and inspect both the receipt and summary. CLI startup checks queue ownership before any evidence read; no queue submit/status/repair command is issued by the helper.

The existing fixture's approximately 0.4 ms `classify_restart(protected)` measurement used no qualified bundle/context. It is not evidence for the final qualified path. The native seal benchmark also does not measure this path.

Actual-host development remains the timing check: `experiment.py` and `development_batch.py` already accept `--development-restart-freeze`. The actual `restart_begin.capture_landmarks` separates capture from selection/classification; `restart_authority_revoked.before_cancel` additionally includes event serialization/flush before cancellation. The unchanged episode TimingMonitor includes all this wall cost. An offline CPU result neither replaces that measurement nor authorizes scored work.

The synthetic check command is:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/test_benchmark_qualified_restart.py'
```

It covers five-call bounds and provisional isolation, changed-input retention, actual loader/selection/classification with synthetic objects, the expected four identity calls per classification, unchanged event encoding, original-cut/source guards, strict receipt binding, draft refusal and queue ownership before reads. No real qualification or physics is constructed by these tests.
