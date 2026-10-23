# Release coordinator repair 001

Prepared, not executed or tested by the preparing agent. Root queues the tests and binds this new coordinator into any new release. The original frozen coordinator and all r1 evidence are unchanged.

This version fixes two control-file handling errors. The original finalized marker binds the exact serialized **batch copy** `official-queue-status.json`, whereas the external official receipt has different formatting/line endings. The new post-finalization check retains the external receipt's original hash, rechecks its installed state and argv, compares every parsed JSON value with the batch copy, then checks the marker against the **copy's** exact hash. Both hashes and the semantic binding enter the series batch record. It does not equate byte hashes merely because values match, normalize timestamps, disregard fields, or relax incident handling.

All JSON inputs, including captured queue command output, retain timestamp strings. PowerShell with `ConvertFrom-Json -DateKind String` uses that parameter. Windows PowerShell 5.1 uses its existing string behavior. Intermediate automatic-date-converting versions without `DateKind` are rejected explicitly. This avoids passing a locale/timezone-converted `DateTime` string into `DateTimeOffset.Parse`, which can lose the original microseconds. No custom JSON parser or string transformation is introduced.

Coordinator and tests explicitly import **their current host's** `$PSHOME/Modules/Microsoft.PowerShell.Utility/Microsoft.PowerShell.Utility.psd1`. Windows PowerShell 5.1 exports `Get-FileHash` from that module's nested script; inheriting a pwsh-first module search path can leave it unavailable. The second queued test failed with that missing command, while the exact failed autoload route was not recorded. This bootstrap bypasses search order without changing hash or receipt semantics. The bounded `run_regressions.py` launcher also supplies each child only its own host Modules directory, without changing user/machine environment settings. Each test prints its actual host and resolved hash-command module.

The deeper directory uses three parents from `coordinator` to the experiment root. The root confirmed the final runner location as **`EXP/Runtime/release_runner.py`**; a new native model path could change a normalized class binding. The retention helper remains **`EXP/Batch 01/Release Analysis/measure_retention.py`**. The separate `retirement-r1-and-r2-decision-001.json` records the root's release decision; this coordinator grants no incident waiver or permission to change frozen runtime bytes.

Stored schedule order, all 264 original attempts/156600 task-cap seconds, zero retries, capacity-plus-50-GiB reserve, official separate run/finalize jobs, owned-PID natural-exit waits, source/readiness checks and stopping on every incident/invalid terminal remain unchanged. Valid task failures keep their dispositions. The coordinator does not waive or retry r1's first pre-physics infrastructure failure, change its terminal/marker, or create a release.

## Deferred tests

`test_run_release_series.ps1` extracts named functions from the new source AST; it never runs or dot-sources the coordinator main body. The six existing bounded mock checks are retained. Eight added groups cover:

* Correct nested runtime/retention paths.
* Exact original retention timestamp `2026-09-23T13:00:39.465344+00:00`, nested timestamp preservation and one-microsecond bounds expressed with different offsets, through both file and queue-text parsing.
* The actual original first-run receipt and canonical batch receipt copy: equal parsed values, unequal bytes, marker hash matching only the copy.
* Property-order equality while preserving value types and argv order; reformatting the canonical copy still needs its exact marker hash.
* Changed copy argv even with a correspondingly changed marker; changed installed-state timestamp or argv; changed original receipt hash and wrong marker job ID.

The three small immutable fixture copies are public control metadata from the first r1 run, not concealed manifests or raw episode evidence. Their exact source paths/hashes and the old/new coordinator identities are in `provenance.json`. Test mutations are confined to a fresh synthetic directory under this folder and removed only after checking its resolved containment. No queue, CIM, actual sleep, physics, seed inspection or external service runs in the tests.

The preferred single queued payload from the project root is now:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Infrastructure Repair 001/coordinator/run_regressions.py'
```

It invokes both observed hosts below, keeps each actual stdout/stderr/exit status, bounds each test process to 180 seconds, and continues to the second host even if the first fails. It fails overall if either host fails, the expected 14-check completion is absent, or any of the eight listed source/fixture files change. Its JSON output contains before/after source hashes; root adds the actual successful official queue receipt to the separate `coordinator-validation-001.json` record only after verified completion.

The equivalent individual host payloads remain:

```powershell
& 'C:\Users\cresp\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' -NoProfile -ExecutionPolicy Bypass -File 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Infrastructure Repair 001/coordinator/test_run_release_series.ps1'
```

```powershell
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Infrastructure Repair 001/coordinator/test_run_release_series.ps1'
```

Expected prepared coverage: **14 bounded check groups per host**, with the actual engine version printed. A prepared expected count is not a pass claim. Retain the official test receipt before using this version. The earlier failed attempts `31a16a89` (AST-created block lost its automatic source-directory value) and `066c0720` (missing utility hash function) remain recorded in `provenance.json`; neither was a coordinator execution or scientific attempt.

The coordinator's invocation parameters are unchanged: `-ReleaseDir`, `-ResourcePolicy`, `-RetentionSummary`, `-RetentionReceipt`, `-AfterQueueReceipt`, `-OutputRoot`, optional `-Limit` and `-JobWaitSeconds`. A new release must directly reference this exact version's file in readiness, plus the measured retention artifacts and original retention helper. No r2 release paths or new authority are invented here.
