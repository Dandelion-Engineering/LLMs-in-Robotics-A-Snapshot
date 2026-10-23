# R4 external coordinator — prepared, not accepted

Copied from the frozen Release Environment Repair001 coordinator at the same three-parent depth below the experiment root. Only `seriesRuntime` and its focused expected-path assertion change to sibling `Runtime 004`. The retained receipt fixtures and prior `provenance.json` are byte-identical historical regression inputs, not r4 evidence; current copy identities are in `../reader-copy-manifest-001.json`.

The original `Batch 01/Release Analysis/measure_retention.py` binding remains unchanged. Stored-order selection, zero retries, official terminal plus retained owned-PID/lock checks, receipt binding, finalization-before-next-batch, capacity/reserve, and strict incident stops remain unchanged. In particular this coordinator still stops at historical incident/unlaunched dispositions; it does not create or consume continuation reviews.

Deferred queue payload, from project root:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Lifecycle Repair 001/coordinator/run_regressions.py'
```

No coordinator/test/queue execution occurred during preparation. A later actual launch needs a fresh r4 release and output directory, root's actual frozen resource/retention refs, and the real preceding successful receipt. No release or readiness is created here.
