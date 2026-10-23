# Administrative execution recovery 001

This new authority can execute only the 131 originally unattempted manifests named by an adopted recovery annex, in their original schedule order. It retains the 132 original terminals and the one separately documented administrative interruption. It never synthesizes that interruption's terminal, retries it, or normally finalizes its unfinished historical batch.

`recovery_runner.py` invokes the original `Runtime 004/release_runner.py` release/artifact verification unchanged. Its separate context and supervisor retain the original physical, policy, model, sandbox, protocol and qualification modules at their original absolute locations. `experiment_recovery.py` changes only context admission and administrative provenance. The source-copy review and AST check bind that boundary. New normal records reference both the original freeze and the supplemental source index, source ZIP and adopted annex; their revision IDs and parents come from the annex. The supplemental bundle does not retroactively become part of the original freeze.

Before execution, the runner also requires the exact canonical administrative interruption note, the adopted source inventory and the original artifact gates. Every new attempt receives an exclusive claim. Other unfinished batches or attempts still block admission. An explicitly matched in-progress plan is admitted only inside its own already authorized batch. Post-run checks verify both original artifacts and the administrative supplement. New invalid attempts stop the batch for review; fixed-budget valid policy failures retain their measured status.

Only these CLI shapes are supported (absolute real paths supplied by the operator):

```text
<project-python> -X utf8 -B <recovery_runner.py> run --release-dir <original-r4-release> --annex <adopted-annex.json> --limit 4
<project-python> -X utf8 -B <recovery_runner.py> finalize --release-dir <original-r4-release> --annex <adopted-annex.json> --verified-queue-job-id <actual-run-job> --queue-status <saved-official-receipt.json>
```

Execution must be admitted by the installed queue. The runner checks the actual Python script and owned PID (or the original narrowly verified Windows venv parent relation). Exact production queue snapshots first verify the installed queue source SHA and module location, then acquire its existing `ExclusiveFileLock` on `state.lock`. The `CreateFileW` snapshot handle closes before that lock releases, before ownership/CIM checks or sleeps. This read performs no queue state save, service call or worker lease operation. Other paths use the raw close-before-return reader without acquiring the queue lock. Lock/read failures reject admission.

Read/write/delete sharing alone does **not** permit Python's `os.replace` to replace an already-open destination on this measured host. The retained diagnostic confirmed access-denied errors while both share3 and share7 handles were open, success after closure, and a serialized writer waiting before committing generation 1 to 2. The reader therefore relies on the queue's existing cooperative state lock, which every installed state mutation uses; it does not claim that sharing flags remove replacement conflicts.

Normal finalization requires the exact successful official run receipt, matching the installed record and actual command, plus the original manifest and retained terminal bytes. It is metadata-only and resumes exact partial canonical appends idempotently; the finalized marker is last. The historical interruption is excluded from this path.

`test_recovery_runner.py` contains synthetic tests only. It never reads production queue state or canonical stores, invokes a queue command, imports the native supervisor, or runs a robot/model. Its Windows tests retain the open-handle replacement limitation, use the real pinned lock with a temporary writer and generation checks, and verify handle closure under the lock on a forced read error. The supervisor comparison parses source AST without importing it. The prospective source index binds the exact candidate bytes; it remains provisional until these tests and the contract/preparation checks pass, before adoption or execution. No test pass, adoption, physical qualification or execution is claimed by this source handoff.
