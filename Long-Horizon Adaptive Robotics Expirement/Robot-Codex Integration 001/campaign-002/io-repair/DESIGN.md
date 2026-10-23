# Continuous physics during synchronous evidence persistence

Prospective infrastructure candidate, session 14. Not adopted or qualified by this document. Randy's September 27 18:10 PDT instruction authorizes the bounded shared-I/O reproduction, supported repair and fresh complete qualification. Native003/dev013 remains invalid/unknown, with six completed reference tasks but two failed timing criteria in stock1.

The retained phases locate long waits in several synchronous durability operations. Their device, filter, operating-system and scheduler causes remain unknown. The fixed source-bound reproduction in `diagnostic/` will retain the actual operation sequence, payload provenance, wall/CPU timings and mechanical parity. A diagnostic pass means the workload/evidence checks passed, not that its latency qualifies physics.

## Candidate placement and ordering

One protected owner thread constructs, advances, reads, commands and closes the unchanged Cell. The supervisory thread retains the existing Supervisor, baseline, Journal, atomic files, SQLite recorder, HTTP processing and their synchronous flush/commit order. There is no asynchronous acknowledgement of a journal operation. A dispatched command's protected and public events and command registry must return from their original synchronous durability operations before the supervisory adapter sends a worker RPC. The worker rechecks original referenced observation age, authority epoch, order and stable request identity immediately before native submission. A timed-out RPC has unknown receipt and stops the apparatus; it is never automatically retried.

The worker supplies detached sensor envelopes and ordered motion/feedback/event records through a bounded queue. Full RGB/depth and packet contents are copied at the ownership boundary. No drop-on-overflow is permitted. Recorder writes precede observation journaling and publication just as before; unpublished worker camera fields cannot enter public status through a latest-snapshot shortcut. Live kinematic telemetry retains its existing explicitly live meaning. Only protected host code can access the worker; model filesystem/network isolation and the loopback authority boundary are unchanged.

The complete physics clock is sampled before and after each owner tick against the common QPC origin, including delayed wakes. Synchronous supervisory I/O therefore occurs *during* measured physics, not in excluded pauses. The unchanged monitor still requires lag strictly below 100 ms, one-second RTF 0.95–1.05 and fewer than 1% bad windows. A separate supervisory phase ledger records persistence waits against the same origin; phase stacks are never shared across threads. Memory samples stay on the owner at the existing cadence and ceilings. Automatic cyclic GC remains deferred for the bounded interval and restored afterwards.

## Bounded failure behavior

RPC count, evidence count and evidence bytes have explicit bounds. Physics never waits for queue space or a recorder lock. A full queue, lost supervisory health (two seconds), source/evidence failure or worker exception cancels locally, stops new admission and marks infrastructure failure. The owner enforces simulation/wall caps and the existing ninety-second skill limit independently of supervisory progress; direct-command deadlines remain enforced by Cell. Terminal timing is frozen in an owner handshake, then cancellation feedback and remaining evidence are drained before reporting completed execution. Failed drain or finalization is incomplete evidence and cannot yield a qualified or scored success.

No original controller, physics, sensor, evaluator, model, robot instructions, SQLite durability mode, fsync requirement, security setting or timing threshold is changed. Python scheduling and GIL-held work can still delay the owner; thread placement is not a hard real-time guarantee.

## Prospective checks before adoption

- Inject delayed journal/fsync and SQLite commits; verify actual ticks continue while commit-before-visible and intent-before-dispatch ordering holds.
- Verify original observation expiry and epoch/order rejection at actual submission, duplicate identities, lost acknowledgements and no replay.
- Verify single-owner Cell access, detached message content, exact event/motion/image sequence retention and no publication of pending camera fields.
- Exercise queue count/byte overflow, failed protected/public/registry/recorder writes, owner failure, health timeout and terminal drain failure; all fail closed with honest unknown evidence.
- Validate timing entry/exit coverage, independent memory sampling, finite resources and terminal/cancellation handshake.
- Preserve all development dispositions. After a supported candidate passes its development checks, freeze new bytes and perform six fresh native references, isolated boundary/lifecycle suites, interruption/fresh-invocation smoke and both family pilots. Earlier revision passes do not substitute for this final lineage.

Campaign 002's twenty slots remain unstarted until those gates and the original admission seal are complete.
