# Run the frozen release series

Prepared, unexecuted coordinator: [run_release_series.ps1](run_release_series.ps1). It supplements the [final freeze runbook](final-freeze-selection-runbook.md); it does not create a release or decide readiness.

Root reviewed the helper and ran all six [synthetic checks](test_run_release_series.ps1) successfully on 2026-09-23 at 10:44 UTC; the exact source hashes and limited scope are retained in [the test record](release-series-synthetic-validation-001.json). The tests extract only selected function definitions from its parsed AST and mock queue state, CIM, sleeps and terminal journals; they never execute its main body. Actual coordinator invocation remains pending final experiment readiness.

## Inputs and invocation

Before release creation, place the final coordinator itself, the actual Resource and Retention Policy, measured retention summary and its official receipt in the control index **and as individual direct final-readiness evidence_refs**. The script requires those exact direct hashes; merely indexing their index is insufficient. Also retain this runbook/test version in the control index. Freeze the final helper bytes before starting evaluation.

The retention input is the existing successful measure_retention.py summary (robot-retention-inventory-1.0) with measured maximum/planning MiB per task-second, 50 GiB reserve, exact measurement source and official job. Its actual source/receipt/output/time are checked. Supply the latest actual successful queue receipt separately as AfterQueueReceipt, so initial handoff can observe known worker/child PIDs without enumerating processes.

After qualification/development closeout, actual freeze/readiness and existing 264-manifest release creation, use full actual paths:

~~~powershell
$seriesScript = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Batch 01\Release Analysis\run_release_series.ps1'
& $seriesScript -ReleaseDir '<existing C release directory>' -ResourcePolicy '<directly frozen resource policy.md>' -RetentionSummary '<directly frozen retention summary.json>' -RetentionReceipt '<directly frozen official measurement receipt.json>' -AfterQueueReceipt '<latest completed official queue receipt.json>' -OutputRoot '<fresh C Evidence\release-series\directory>' -Limit 4
~~~

The OutputRoot parent must exist. Default limit is 4, permitted 1–16; limit16 reduces the number of batches without changing order, caps or the matrix. JobWaitSeconds defaults to 43,200 (12 hours) per queued operation; expiration stops observation and never kills or repairs a worker. If root launches an external PowerShell process, use WindowStyle Hidden. Do not launch another queue client concurrently.

## Each cycle

1. Require global queue inactivity, terminal owned-job state, every retained worker/child PID absent, and both worker/state locks absent. Read-only targeted CIM polling is every10seconds; progress every30seconds. An absent worker.json alone never permits a queue call; PID reuse also blocks.
2. Verify held small control/Runtime source identities and prior finalized terminal journals. Missing terminal evidence, unresolved claims, invalid/unknown validity, integrity flags, aborted execution or a prior incident stops the series.
3. Read current C available capacity. Required bytes are ceil(all remaining original task caps × frozen planning MiB/task-second ×1,048,576)+53,687,091,200. Preserve the complete calculation before each run submission. Public C01–C08/C09–C16/C17–C24 IDs imply300/600/900seconds; the full metadata must still contain264 attempts and156,600seconds. The coordinator never opens runs/*.json or reads seeds.
4. Queue unchanged release_runner.py run --release-dir ... --limit ..., with no --run-id override. Wait for natural exit and retain the exact official succeeded/integer-exit-0 receipt. Check that planned.json selected the expected original schedule slice.
5. Queue unchanged release_runner.py finalize --release-dir ... --verified-queue-job-id <original run job> --queue-status <original run receipt>. Finalization hashes terminal/result JSON and all immutable map revision attachments while rebuilding/validating the map; placing this work in the queue avoids growing external hashing. It executes no policy and does not bypass a run entrypoint guard.
6. Retain the finalizer's own official receipt and verify the original run batch's finalized.json. Recheck incident/terminal state before the next capacity calculation. An ordinary valid task failure, partial result or timeout remains a measured outcome and does not by itself stop the comparison.

Both official receipts are retained under Evidence/queue-receipts. The fresh series directory retains started.json, each capacity decision, submissions/stdout/stderr, per-batch receipt/finalization references, and complete.json or stopped.json. Complete means264 original valid terminal dispositions finalized, not264 task successes or a scientific result.

## Stops and limits

No retry, incident review, waiver, cancellation, overwrite, migration, source repair, release creation or readiness change is automated. An official failed/interrupted job stops without finalization. A successful run job containing an invalid result is finalized first where source integrity still permits the unchanged finalizer, then the series stops. It does not adopt even an existing continuation review automatically; root handles incidents under the existing explicit review procedure. A clean already-finalized partial release can resume in a fresh series-output directory; unresolved batches cannot.

The coordinator cannot replace the runner's complete artifact/model/isolation authorization: those checks stay inside every queued run. It checks only small control/source/terminal metadata externally (individual files capped at8MiB), no frames, model weights or bulk raw streams. It never chooses a policy/checkpoint or changes the schedule.

The frozen measured retention rate is a planning estimate, not a bound on future writing. Free space and remaining caps are recalculated each batch; rate fitting and bulk retention scans are not silently added. Keep actual capacity interpretation with root, preserve originals and full caps. All scored evidence remains on C. A stopped observer may leave an authorized child running naturally; inspect the retained identifiers without using queue CLI until the same natural-exit conditions are established.
