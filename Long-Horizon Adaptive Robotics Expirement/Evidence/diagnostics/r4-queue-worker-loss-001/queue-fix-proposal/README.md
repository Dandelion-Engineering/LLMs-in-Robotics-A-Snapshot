# Windows queue liveness fix — proposal only

The installed queue has not been changed. `compute_queue.original.py` is an exact byte snapshot; `proposal-manifest.json` records its installed path and SHA-256, all proposed files, and the narrowly scoped change. Do not import or execute the original snapshot on Windows. Do not run either queue copy as a CLI.

`compute_queue.proposed.py` changes only `pid_alive` on Windows. It opens the process with `SYNCHRONIZE` rights, performs a zero-time `WaitForSingleObject`, and closes the handle in `finally`. A signaled process is dead; `ERROR_INVALID_PARAMETER` (87) while opening a positive representable PID means absent. Timeout means alive. Access-denied, unknown failures and other wait results conservatively mean alive. An unrepresentable PID is never truncated. The function requests no termination rights; Unix behavior and the rest of the queue are unchanged.

This fixes the concrete non-destructive-query defect in the proposal. It is not proof that the identified concurrent submission caused every observed process disappearance, and is not a repair of GPU observation failures, queue file-sharing errors, PID-reuse identity ambiguity or interrupted robot-attempt metadata.

## Proposed isolated validation

No tests, workers or native probes were run by the proposal author. Root may review and run this lightweight standard-library suite independently of heavy compute admission. From the repository root:

```powershell
$proposal = Join-Path (Get-Location) 'Long-Horizon Adaptive Robotics Expirement/Evidence/diagnostics/r4-queue-worker-loss-001/queue-fix-proposal'
& '.\venv\Scripts\python.exe' -X utf8 -B (Join-Path $proposal 'test_queue_proposal.py')
```

The suite imports only the proposal copy. It replaces `production_paths`, `main` and the default detached launcher with refusal guards, and restricts every `QueueStore` to one explicitly identified disposable directory. Fixture subprocesses verify its token and proposed-source hash. No installed/shared state, other project, GPU, model, robot or policy episode is used. Native tests require Windows; skips elsewhere are not evidence for Windows correctness.

Coverage includes mocked native handle results and close behavior, unchanged Unix behavior, actual child survival with a normal-completion sentinel, a separate live lock/lease owner, two actual concurrent submitter processes during an active worker, single-slot/exactly-once completion, deliberate loss of an owned worker with interrupted/no-retry recovery, and queued/running process-tree cancellation. Exit code zero alone cannot prove survival because the original hazard can terminate a process with that code.

Successful cases should take seconds; handshake waits are bounded at eight seconds, lock-contention checks at 0.2 seconds, and benign fixture tasks self-expire after 30 seconds. Cleanup retains direct process handles and acknowledged native handles rather than terminating arbitrary reused PIDs. It attempts all known cleanup steps and records failures. A fixture that fails before its ownership handshake can remain unacknowledged until its 30-second self-expiry; such a failed test is not clean validation. The exact resolved temporary root, name and token are checked before recursive cleanup. Failed tests retain their scoped temporary directory and logs and print the path; no automatic retries occur.

## Adoption boundary

Inspect actual test output and the manifest before any decision. Applying this proposal to the installed shared queue requires the user's explicit override of the current no-shared-queue-edit instruction and the queue owner's applicable review workflow. No deployment, installation, readiness or successful-test claim is made here. Preserve all original interrupted jobs and episode evidence; this proposal does not authorize retries or scored continuation.
