# Engineering Investigation 004 — prepared, not accepted

These are versioned copies of the frozen003 reader/presentation sources. Production path changes select sibling `Runtime 004` and `Batch 01/Release Analysis 004`. Statistical formulas, qualification/context/absence checks, canonical corrections, receipt and hash checks, archive containment, and fixed twelve-trace semantics are unchanged. OriginalRuntime,003 and r3 artifacts remain untouched.

The implementation narrative preserves all candidate/baseline wording and nine member/line entries, but its Runtime004 SHA values are deliberately null and the scope marks it prepared/not accepted. The existing strict reader refuses it until root supplies actual final Runtime004 hashes and accepts the binding; no old hash is represented as current. Source labels and synthetic narrative fixtures now use `Runtime 004/`. Root should also confirm retained line locators when binding the final staged repair.

No HTML, derived data or tests were produced. The exact copy and transforms are recorded in `../Batch 01/Release Lifecycle Repair 001/reader-copy-manifest-001.json`. The new prospective trace declaration is `../Batch 01/evaluation-trace-selection-r4.json`.

After root completes Runtime004 and the narrative binding, queue these as separate processes from the project root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement/Engineering Investigation 004' -p 'test_*.py' -v
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Analysis 004' -p 'test_*.py' -v
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Lifecycle Repair 001/coordinator/run_regressions.py'
```

All checks are deferred. Later production jobs must use fresh outputs outside frozen source directories and explicit builder `--output`; use004 collector/analyzer/processor/builder with the unchanged r4 trace declaration. No readiness or physical claim is made here.
