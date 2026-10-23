# Engineering Investigation 005 — prepared; verification deferred

005 is a versioned copy of Engineering Investigation 004. It consumes Release Analysis 005 administrative-continuation selection and provenance while retaining Runtime 004 numerical analysis, diagnostic and restart interpretation bindings. Original 004 files and all canonical/evidence files are unchanged. `source-copy-manifest.json` records actual source/target SHA-256 values, copied/modified/added files and the unchanged twelve-slot trace declaration.

No tests, queue jobs, physics, real evidence extraction, production HTML builds or browser checks were run during this implementation. Source inspection and file hashing do not establish passing behavior. Root must queue verification and fresh derivation/build jobs, then perform browser QA before use.

The 005 processor and administrative analysis sidecar bind queue ownership to the exact `Runtime Recovery 001/recovery_runner.py` implementation. Its queue-state locking repair is separate from Runtime 004 numerical and diagnostic behavior. The processor records `queue_authorization_implementation` in its retained selection/index and method inventory; readers reject a different implementation or changed bytes. Legacy 004 analysis keeps its original ownership binding. The first validation attempt failed a Windows sharing fixture; this source preparation makes no passing-validation, adoption or physical claim.

## Evidence and accounting

- The processor accepts the adopted `--annex` and retains the collector's complete `selected-evaluation-results-administrative-1` artifact, including both collector implementations, exact canonical results/notes references, control sources, annex/source-index references and normal flat results unchanged.
- Counts separate original finalized terminals, annex-authorized finalized terminals, administrative interruptions and missing dispositions. `selected_terminal` counts only the first two; `missing_terminal` includes administrative rows. `complete_disposition_accounting` is not a claim that every run has a physical terminal. Existing 004 index/analysis schemas remain readable through their original implementation/receipt bindings.
- An administrative row is an explicit infrastructure-invalid, unknown-outcome projection with no physical end or original post-run integrity. Diagnostics and continuity are unavailable with null compact measurements, not zero-valued reports. Processing an accounted administrative row is not a derivation error. Missing dispositions, report failures and integrity errors remain separate.
- The analysis reader binds the source-bound administrative wrapper, canonical sources and supplemental authority without modifying protocol estimates. Annex, source index, disposition and official receipt links remain accessible. Paired-block exclusions follow the existing protocol.
- The twelve slots in `../Batch 01/evaluation-trace-selection-r4.json` remain fixed. Detailed playback keeps 2 Hz observations and 5 Hz motion. Administrative slots never parse partial streams into playback and are never replaced. Ordinary evaluation playback requires `manifest.json`, terminal `result.json`, events and a protected `../terminal.json` bound to the exact result. Missing, truncated and unavailable traces remain visible as such; identity/hash errors refuse the build.
- All planned rows remain in the compact evaluation index. Metadata can still include every immediate development run or release `attempts/<run>/evidence` directory. No raw evidence is fabricated or rewritten.

The copied implementation narrative remains bound to its existing Runtime 004 revision/source identities. 005 does not automatically relabel it for administrative-continuation revisions. The existing exact-match reader controls whether it is displayed.

## Deferred verification and production commands

From the repository root, submit the following verification command through the approved queue; do not treat the prepared tests as executed:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement/Engineering Investigation 005' -p 'test_*.py' -v
```

`test_administrative_projection.py` prepares counterexamples for invented timestamps/outcomes/counters/integrity, incorrect counts, forged terminals, substituted canonical notes, partial-stream playback, report dispatch, all-264 denominator preservation and actual 005 analysis-wrapper input binding. Existing suites retain ordinary outcomes, canonical corrections, fixed trace slots and legacy analysis checks. The Release Analysis 005 suite is a separate verification process.

For subsequent root-owned queue jobs, select fresh derived/analysis/site output directories and exact retained receipts. `$release`, `$annex`, `$derived`, `$analysis`, `$site`, `$derivationReceipt`, and `$analysisReceipt` below are operator-supplied absolute paths; the release remains the original r4 release. These are command templates, not executions:

```powershell
$project = 'Long-Horizon Adaptive Robotics Expirement'
& .\venv\Scripts\python.exe -X utf8 -B "$project/Engineering Investigation 005/process_evaluation.py" --release-dir $release --annex $annex --output-dir $derived
& .\venv\Scripts\python.exe -X utf8 -B "$project/Batch 01/Release Analysis 005/analyze_results.py" --release-dir $release --annex $annex --selected-results "$derived/selected-results.json" --output-dir $analysis
& .\venv\Scripts\python.exe -X utf8 -B "$project/Engineering Investigation 005/build_workspace.py" --output "$site/index.html" --metadata-root "$release/attempts" --trace-selection "$project/Batch 01/evaluation-trace-selection-r4.json" --observation-hz 2 --motion-hz 5 --evaluation-index "$derived/index.json" --evaluation-receipt $derivationReceipt --analysis-file "$analysis/analysis.json" --analysis-provenance "$analysis/analysis-provenance.json" --analysis-receipt $analysisReceipt --implementation-narrative "$project/Engineering Investigation 005/current-implementation-narrative.json"
```

The compressed embedded snapshot, decoded evidence hashes, XSS-safe rendering, source panels, keyboard interactions and browser decompression failure state are inherited unchanged. The source package contains no generated production page or synthetic score data.
