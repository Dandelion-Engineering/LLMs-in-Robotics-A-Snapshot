# Initialize the protected static-model memo during sealing

Root **applied** this four-line behavior change to `Runtime/restart_physical_class.py` at 2026-09-23 09:20:11.154627 UTC after exact byte guards, as retained in [the integration record](seal-memo-initialization.integration.json). Original SHA-256: `9ce69d9df5b543b832cc52d7124e1d436a78e5ca377070a7bc12a7b069a4db91`; applied SHA-256: `18c6106b09729230a38878225ee1a654f13c93ae7e21d40271cc250c494d6553`. The original patch, stage sources, preparation validation and `unapplied` manifest remain unchanged historical preparation artifacts; the separate integration record establishes application. During preparation, no physical output was read, no Runtime/held source was edited, and no native model or physics was run.

Post-application Runtime checks completed under [official job 20260923T092033443549Z-ad7f1217](../../Evidence/queue-receipts/20260923T092033443549Z-ad7f1217.json), with root reporting 436 tests passing in 40.618 s. [Completed diagnostic 002](BOUNDARY-TIMING-PROFILES.md) measured first rich capture at 16.7445 ms versus 35.5871 ms in diagnostic 001, but still failed warm host timing after the separately integrated fixed-entry pacing change. This is observed boundary evidence, not qualification or a general performance guarantee. No separate native static benchmark was needed or run.

Immediately after the existing `seal_sha256` is calculated, call the existing `_model_surface_sha(model, result)` and require it to equal the just-sealed compiled-surface digest. This initializes exactly the current memo and refuses a model that changes during that extra construction-time read. No other function changes. For identical input source identities, returned seal and export evidence remain identical; installing the exporter naturally changes the actual exporter source identity, so prior qualifications remain historical unless the normal compatibility/evidence path supports the new source.

The memo stores raw native-model bytes, primitive descriptors and weak references. It does not store `MjData`, contacts, actual joint positions/velocities, action state, boundary snapshots, authority, or a time-based pass. Every export still enumerates all public model fields and reads every current array's bytes; exact equality only avoids rehashing/rebuilding unchanged descriptors. New/changed fields, nested solver changes, nonfinite values and illegal process-mark colors remain checked. The existing full-read fallback for providers without weak-reference support remains intact.

## Clock placement and cost

`Cell.__init__` calls `seal_model` immediately after `MjModel.from_xml_string`, before creating its controller adapter/MjData. Both `experiment.run_episode` and `physical_calibration.PhysicalLoop` instantiate Cell and perform their existing setup/settling before establishing the actual-host task/calibration clock. The change adds one complete native-model traversal and cold memo initialization to that already out-of-clock setup. It removes no observation from an actual intervention boundary and pauses no running physics clock.

Setup cost increases. First live export can reuse exact static bytes only after reading them again; any legal mark change or other model change still causes the existing recomputation/failure behavior. Later exporter and complete rich-snapshot costs remain on the actual clock. No measured native speedup is claimed by the synthetic tests. Parent-reported earlier cold/warm timings motivate this proposal but are not a causal diagnosis of the operational B-trial timing failure. Repeated physical timing still needs the completed official records and a prospective run after any applied change.

## Prepared artifacts and bounded checks

- `prepare_seal_memo_patch.py` refuses any changed original and writes only this folder's stage, manifest and patch. It never applies the patch.
- `seal-memo-initialization.patch` changes only the seal tail; `seal-memo-stage/{original,proposed}.py` retain the exact LF-normalized comparison sources. The manifest distinguishes original file-byte hash from normalized stage hashes.
- `test_seal_memo_initialization.py` uses synthetic native-like objects, never MuJoCo compilation: AST equivalence outside `seal_model`, identical seals/exports for 3/6/10 parts, full current array/property reads on every capture, first-capture fixed/nested/unsupported/nonfinite mutation rejection, allowed/illegal mark transitions, mutation during initialization refusal, tampered-seal refusal, weak-key retirement and original nonweak fallback.

After application, the tests load and hash-guard the retained original/proposed stage pair rather than rerunning the strict patch generator against the changed Runtime. When the application record exists, they also verify that installed Runtime bytes equal the reviewed proposal. All six synthetic checks passed again in 0.157 s; [the separate applied-test record](seal-memo-initialization.applied-test-validation.json) retains this result and source identities. The earlier preparation validation remains unchanged and historical.

Run source-only tests from the project root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/test_seal_memo_initialization.py'
```

The optional **queued child** below remains an unrun historical diagnostic option. Root chose actual boundary repeats after integration instead; do not launch it unless a new concrete gap requires it. If needed, use a fresh output directory under an existing operator parent:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/benchmark_seal_memo.py' --output '<fresh static benchmark directory>'
```

The helper enforces queue ownership before substantial work. It constructs the same three fixed development scenes separately for the original and proposed staged exporters, recording source binding, compile/seal setup, first post-seal export, two subsequent exports and fixed-solver mutation/restoration. It retains source/assets/runtime binary identities and before/after source hashes. It does not instantiate Cell/MjData, render, step physics or run inference. These are **descriptor export** timings, not actual rich boundary capture or physical timing-gate measurements. Fixed original→proposed order is disclosed; do not turn this small diagnostic into an inferential performance claim. Failures are retained with `expectations_met: false` even if the queue exits 0. Require the official successful receipt before using the report, then inspect its actual expectations/source stability.

Application is complete; do not regenerate or reapply the original guarded patch against the changed Runtime. No seal/predicate threshold, capture boundary, actual clock or cut definition was changed by this integration. Physical results and timing failures remain in their original evidence.
