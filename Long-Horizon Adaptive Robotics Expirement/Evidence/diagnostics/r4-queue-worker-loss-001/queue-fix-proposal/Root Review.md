# Shared queue liveness repair: ready for approval

The proposed repair passed all 12 isolated tests on Windows on 2026-09-24. It has **not** been installed. The installed source remains SHA-256 `ca13faf55645df4050d918a745b183bebb967ae8f5b1dd180ff8212c0ed1d4bf`.

The [patch](windows-pid-alive.patch) adds only the Windows branch of `pid_alive`. It opens a process handle with synchronization access and performs an immediate state query. It requests no termination access. Unknown access or query errors conservatively mean the owner may still be alive. Original Unix behavior and every source byte outside that insertion are unchanged.

Root read the source, fixtures and cleanup safeguards, verified every proposal file against the [author's manifest](proposal-manifest.json), and ran the suite once. All seven mocked/scope cases and five native Windows cases passed in 3.599 seconds, with no skips. The native cases covered normal child survival, an existing lease/lock owner, concurrent submissions with one worker and serial execution, actual loss of an owned test worker without retry, and queued/running process-tree cancellation. A normal-completion sentinel checked survival independently of exit code zero. Disposable stores and process handles were confined to test-owned fixtures. No production queue service, GPU, model or robot episode was invoked.

The [root verification record](root-verification-001/verification.json), SHA-256 `0bba2b2565e6b475f71d2b8785c3905ae1f14d5f1e5fcd61540d89ce1444dee3`, binds the source, command, output and post-test observations. No fixture process remained. At 20:52:14 UTC, a read-only shared-state observation found no active or queued jobs and no worker lease/state lock. An unrelated HTTP server was left untouched. Its current PID 3096 also illustrates why historical PIDs must never be treated as durable process identities.

## Exact approval scope

Approval would allow replacing only the installed shared `compute_queue.py` with the reviewed proposal SHA-256 `31997fc851494df62c2466cf189b5e945a6a933464f5cd43e69b3d877c029829`. Before writing, recheck the installed source hash, current process identities and queue inactivity. Preserve the exact original snapshot and verify the installed result. If the source has changed or a worker is live, do not overwrite it; inspect the new condition. Do not change runtime queue records, start another project's job, or retry an interrupted episode as part of applying this patch.

The user was asked through the task's approval question after testing. No answer had been received when this record was prepared. Approval is required because the latest heartbeat explicitly forbids shared-queue edits and [Project Details](../../../../../Project%20Details/Project%20Details.md) says, “Never bypass or modify the queue or another project's jobs.” This is a concrete scope exception, not an additional approval requirement inferred for routine project work.

## Limits

This repair addresses destructive Windows liveness probing. It does not resolve file-sharing races, PID reuse, GPU sampler delays or the missing terminal from batch036. It does not prove the full historical process-loss mechanism. The 132 finalized originals, one interrupted original and 131 unstarted originals remain unchanged. Completing that inventory requires a separately explicit recovery contract and compatible execution/reading implementation; applying this queue patch alone does not resume r4.

Primary API references: [Python 3.12 `os.kill`](https://docs.python.org/3.12/library/os.html#os.kill), [Microsoft `OpenProcess`](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess), and [Microsoft `WaitForSingleObject`](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject).
