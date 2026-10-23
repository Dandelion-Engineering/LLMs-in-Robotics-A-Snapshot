# Home06: a lost supervisory heartbeat stopped the campaign

Home06 was ordinal 11 and the first distinct infrastructure failure, selected
for diagnosis after the outcome. Its official queue job
`20260930T231138503466Z-c3a5f10f` ended with exit 1. The original coordinator
therefore recorded an invalid attempt with **unknown task outcome** and stopped
immediately. The nine remaining slots stayed unrun. No replacement assessment,
retry or task-performance interpretation is made from this failed execution.

## What the retained infrastructure records say

The orchestrator completed its sequence, but the physics host exited 1 after
reporting `PhysicsWorkerError: Supervisory heartbeat lease expired`. The
configured lease was 2.0 seconds. The owner reports itself finished.

The separate supervisory timing ledger retained an `adapter_step` spanning
wall-relative 140.266497–145.756612 seconds: **5.490115 seconds**. Its recorded
simulation endpoints are 140.266–142.266 seconds. This is consistent with a
long supervisory step spanning the expiry. The phase is inclusive and overlaps
its children; the wall duration is not a disk-latency measurement. It does not
identify a scheduler, storage device, garbage collector or outside process as
the cause. The bounded slow-row inventory is not a complete event trace.

The frozen adapter refreshes the heartbeat at the beginning of `step`, before
draining and synchronously persisting queued owner messages. It checks the
owner error after that drain. A long drain/persistence step is therefore a
plausible path to missing the lease. This is a **source-supported hypothesis**,
not an established root cause or authorization to relax the lease.

The cleanup record reports `clean: true`; the code-host retirement receipt
reports qualified retirement, no normal-wait timeout and Windows exit 0.
However, the stage's original retirement and old-token operator calls were
refused (`WinError 10061`), and the public mirror recorded reply-validation
failure without established authority revocation. Those diagnostics do not
replace the missing complete retirement/evidence assessment. The original
disposition remains unchanged and no scientific timing pass is claimed.

## What can be learned next

The ten earlier valid runs passed both strict physics timing and transport
assessment. Home06 shows that this frozen apparatus did not complete the whole
allocation reliably. A future authorized development investigation could
instrument supervisory batch size, progress and persistence waits around the
lease, retaining the present timeout and source revision as the historical
baseline. This campaign supplies no causal estimate of repair benefit and no
physical-robot deployment result.

Evidence: [original diagnostic settlement](../execution/RCI001-C02-home-06/diagnostic.json),
[original disposition](../execution/RCI001-C02-home-06/disposition.json),
[terminal stop](../execution/campaign-stop.json), and
[bounded infrastructure inspection](session19-results-001/home06-diagnostic-001/inspection.json).
That inspection binds the original infrastructure files and the frozen
[adapter source](../harness/continuous_adapter.py) and
[owner source](../harness/physics_worker.py). Its own diagnostic job
`20260930T232409086429Z-1ceed9ce` succeeded with integer exit 0; that authenticates
the diagnostic collection only, never the failed scored attempt.

No failed-attempt model transcript, evaluator result, world outcome or image
was used. The episode explorer deliberately presents no task trajectory for
this slot. The retained files remain available for a future bounded diagnostic.
