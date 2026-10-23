# Slot 1 validity and stopping disposition

Read-only follow-up after official queue job
`20260927T190904644691Z-6612356c` reported `succeeded`, integer exit status `0`.
The authenticated queue interval was September 27, 2026,
19:09:04.923939–19:13:27 UTC. No task outcomes were consumed before that gate.

**Finding:** `RCI001-C01-stock-01` is a valid, scorable success under the sealed
Campaign 001 protocol. No immediate campaign-stop condition is present, and the
consecutive ordinary infrastructure-invalid count remains zero. This is one
known-fixture attempt; it does not establish a general reliability rate.

## Evidence checked

- [Admitted assessment](../execution/RCI001-C01-stock-01/assessment.json), SHA256
  `724445763810d9b13d70ae3c37a7becb0e828ae1435558662025c19451c5f585`:
  `validity=valid`, `task_outcome=success`, `scorable=true`, no failed checks.
- [Protected host result](../../local-evidence/campaign001/RCI001-C01-stock-01/host/result.json):
  execution completed, no error, `terminal=task_success`, one invocation and one
  handback. The independent evaluator accepted A1 in tray1, reported no
  violations, and recorded 0.5000000000023874 seconds of settled placement against
  the unchanged 0.5-second requirement.
- [Protected event journal](../../local-evidence/campaign001/RCI001-C01-stock-01/host/public-history.jsonl):
  invocation start event 32; accepted handback/control transfer to conventional
  owner and epoch 4 at event 2107; task-success episode stop at event 2477. The
  orchestrator reports clean host exit code 0 and no forced exit.
- [Storage guard receipt](../execution/RCI001-C01-stock-01/storage/receipt.json):
  56 samples, complete queue coverage, no stop latch and no alerts. Minimum native
  free space was 418,513,186,816 bytes; minimum WSL free space was
  1,009,127,575,552 bytes. Sampled additional peak was 43,599,060 bytes, including
  conservatively included shared-service growth. Maximum scan-start gap was
  approximately 5.016 seconds. This is a sampled peak, not an exact continuous
  peak measurement.

## Timing and lifecycle interpretation

The current episode retained 120,768 original host timing samples and maximum
per-tick lag of approximately **0.038 seconds**, below the strict 0.1-second limit.
The frozen TimingMonitor reconstructed **241 complete one-second windows, zero
outside 0.95–1.05 RTF**, maximum reconstructed lag approximately **0.054 seconds**,
and maximum protected-journal sample gap approximately **0.140 seconds**. All
predeclared timing requirements pass. Reconstructed windows remain interpolated
journal evidence with their origin/sample-spacing limitations; they are not
unrecorded original per-tick windows.

Lifecycle validity uses the predeclared `successful_terminal_host_closure`
branch: task-success stop, clean protected host exit, accepted handback/ownership
transfer, durable evidence and observed namespace retirement. The explicit
retirement receipt and late stale-token HTTP403 receipt are both **missing**.
They remain missing and were not counted as passed checks. Their absence in this
qualified natural-closure branch is not unverified namespace retirement.

The older 010c restart-smoke timing failure and prior 010d pilot's measurement
limitations are unchanged. Neither was substituted for this episode's timing.
No new qualification, source change, timing relaxation or replacement attempt
was performed for this follow-up.

The behavioral investigation is separate. This note addresses evidence validity
and application of the original stop rules, not causal explanation of the model's
recovery choices.
