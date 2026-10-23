# Release Analysis 002

The r2 collector and analysis wrapper are byte-identical copies of their frozen originals; their Runtime import remains at the original `Runtime` directory. Root deliberately preserved that execution root to avoid changing native mesh-directory identity. The collector/analyzer's new file paths identify their r2 use, and the two copied synthetic test files are unchanged.

Use this folder's collector and analyzer with `Engineering Investigation 002`. Its processor and analysis-provenance reader require these exact versioned tool paths. Protocol estimates, resampling settings, result correction/selection, complete-denominator and before/after integrity semantics are unchanged. The original tool folders and r1 retained artifacts are untouched. Root separately owns the runner repair, r1 retirement and fresh r2 freeze; no r1 live-path replayability is implied.

No coordinator, retention helper, sealing helper, old decisions, drafts or generated outputs were copied. The separately repaired coordinator continues to use original measure_retention.py and the actual retained inventory/receipt. The r2 sealing step must bind this folder's collector/analyzer and the versioned Investigation sources/assets.

Tests have not been run for these copies. Deferred command, for root to dispatch through the owned compute queue in its own Python process:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Analysis 002' -p 'test_*.py' -v
```

Use unchanged `collect_results.py --release-dir ... --output ... --complete` and `analyze_results.py --release-dir ... --selected-results ... --output-dir ...` interfaces with fresh r2 outputs. Nothing here creates a release, changes seeds, grants readiness or upgrades r1's failed attempt.

`versioned-copy-manifest.json` records exact original/new identities, three path-only changed copies and new files. Its self-hash is excluded; retain its ordinary file SHA-256 in final controls.
