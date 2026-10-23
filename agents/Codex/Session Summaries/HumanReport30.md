# Session 30 — apartment storage and lifecycle repair

The repair is complete, validated, and frozen. Both official conditions are pristine and prepared at `D:/Dandelion-Apartment-Experiment/official/apartment-v1-restart001` for the next session with Randy present. No official relaunch occurred in session 30.

The session first pulled `main` from `563f6e9d` to `5c773ca2`, then followed AgentPrompt, the Codex-only project rules and Randy's October 6, 22:51 and 22:57 PDT instructions in the Apartment Simulation Commissioning chat. The authorized stopping state is a repaired, tested, pristine pair for a later launch with Randy present.

## What failed and what changed

The failed official launch wrote only 2,900,579 bytes through successful file writes, but its journal retained 3,211,381,062 bytes of whole-file versions: 1,107.15 bytes stored per input byte. One append-only log accounted for 99.98% of those content bytes. Each append copied the complete growing prefix. The separate 1 MiB transport ledger retained a row for every opaque frame and filled independently. Error reporting then hit the same limit during shutdown.

The repair stores immutable compressed chunks and bounded-depth deltas while retaining every full-file hash, intermediate version and journal mutation. Readers verify reconstruction; exports/checkpoints retain exact ordinary file bytes and Linux inode metadata. Transport endpoints now independently commit to every ordered frame descriptor using counts, byte totals and SHA256, retaining lifecycle events and all qualification barriers. Individual frame-descriptor rows are no longer recoverable from repaired runs; equality of terminal commitments is still required.

A first throwaway repaired run exposed another receive-queue failure. Its peak plus fixed framing headroom equaled the existing 1 MiB ceiling. The old receive path failed immediately at capacity; a separate test reproduced that exception. The adapter now waits for capacity and releases reservations on cancellation. Queue ceilings, drain deadlines, physics, tasks, sensors, battery configuration, native model and official templates were not relaxed.

A second live attempt reached the full work window and battery warning, then hit the inherited native client's 32 MiB cumulative output guard. Image-result echoes dominated that traffic. Forced client exit caused the later socket reset. The native adapter now bounds its queue and keeps only terminal notifications in memory while retaining observable events on D:. Its separate finite budgets are 32 MiB per message, 256 MiB cumulative input, 512 MiB retained events and 4 MiB additional cleanup input. The cumulative budget is about twice the conditional two-hour projection from measured traffic; arbitrary future output remains bounded and can fail explicitly.

The session also found the original failed FUSE service still mounted. Its exact identity and transient files were preserved before unmounting and retiring that service. Only the original console log grew with teardown diagnostics; the pre-cleanup bytes were retained. Failed evidence is never promoted to a valid closeout or checkpoint.

A third live attempt exposed a legal HTTP/2 client-cancellation race. The inherited observer discarded stream state before response headers already in flight arrived. The apartment adapter now retains bounded cancellation proofs and requires matching byte/structure evidence at both endpoints, while preserving raw reset counts and local ordering. Sixty fragmentation/order cases, ten negative cases, four paired relay tests and both native preflights passed. The original campaign source is unchanged.

## Evidence and interpretation

[REPAIR.md](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/REPAIR.md) contains the measured path-level diagnosis, conditional duration projections, storage design, changed evidence semantics and complete repair attempt ledger. [The operator handoff](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/README.md) contains the next-session launch, viewer, hibernation and resume procedures.

The original failed root remains `D:/Dandelion-Apartment-Experiment/official/apartment-v1`; never resume it. Its separate preservation package is `D:/Dandelion-Apartment-Experiment/failed-launches/APARTMENT-v1-baseline-launch-001`. Engineering attempts are under `D:/Dandelion-Apartment-Experiment/engineering`, with immutable declared source snapshots and queue records. Architecture Map result `APARTMENT-v1-baseline-failed-launch-result` marks the original launch invalid and excluded completely.

Completed storage tests reconstructed all 2,342 original content versions exactly in 2,898,705 bytes. A second fixture appended 8 MiB of incompressible data in 8,192 writes: 28,321,635 stored bytes versus 34,363,932,672 bytes for full copies. One million synthetic frame descriptors used 1,557 parent and 994 namespace metadata bytes, with equality and deliberate-mismatch checks. This represents metadata stress, not a measured 1 GB transfer. The separate flow test transferred 16 MiB of actual socket payload with an intentionally slow consumer and exact byte-digest equality.

Native preflights, full inode/checkpoint continuation and explicit failed-service retirement passed. The native-stream test processed over 96 MiB, preserved all 769 observable records with redaction, and bounded its queue below 8 MiB while retaining one terminal notification. Both native preflights then retired normally.

`APARTMENT-repair-live001` failed before warning/docking; `APARTMENT-repair-live002` reached warning but failed before docking; `APARTMENT-repair-live003` failed at the cancellation race. Their continuation/Maps sessions were not run. `APARTMENT-repair-validation001` through `003` failed immediately at those prerequisites. Those attempts remain in the record. Validation 004 was canceled before start after an import-order dependency was found in its test fixture; it is explicitly not run.

`APARTMENT-repair-live004` passed all ten gates across four real native sessions. The first baseline session completed the full original 30-minute work window, warning, return, docking, closeout, retirement and verified checkpoint. Baseline resumed in a fresh thread; Maps completed its own warning/dock/checkpoint and fresh resume. Both 4,096-write stress files survived exactly, with two reports per condition. `APARTMENT-repair-validation005` then passed all eleven combined/readback gates with integer queue exit 0. It verified native retirement, every retained content version and inode continuation, checkpoint and transport commitments, actual resumed room-map reads, twelve viewer boundary queries, original inputs and failed-launch preservation. This is builder-owned independent readback, not external independent physics validation.

The full-window baseline warned at simulation time 1,800.40 and docked at 1,965.54 after seven return base commands. Its journal retained 8,665,261 content bytes plus 14,472,667 metadata bytes, under the unchanged 3 GiB cap. The four final transport ledgers were 116,240 / 36,648 / 70,615 / 47,772 bytes; each queue peak plus fixed headroom was 917,504 bytes under the unchanged 1 MiB cap. Nine ordinary runtime cancellations were reconciled. All 32 recorded session-30 FUSE identities were checked after completion: no matching service or mount remained. The original failed mount is also absent.

The [repair attempt index](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-30/repair-attempt-index.json) preserves fifteen distinct attempts: eight passed, six failed, one canceled before start. The original failed official baseline and the original unlaunched Maps preparation have separate terminal records; the new pair has no launch or terminal result.

## Ready state and next action

The [pristine-pair readback](../../../Long-Horizon%20Adaptive%20Robotics%20Expirement/Apartment%20Experiment/operations/session-30/pristine-pair-readback.json) was executed from the actual frozen source. Both initial filesystems exactly match the original prepared inventories (15 baseline files, 19 Maps files), with no sessions, checkpoints or consumed assignments. Original Maps remains pristine. Baseline launch checks pass; Maps correctly refuses to start before baseline's 21-assignment endpoint. Original evaluation text is byte-identical. No learned state, progress or checkpoint enters either new initial state.

- Revision: `APARTMENT-v1-storage2-frozen`; runs: `APARTMENT-v1-restart001-baseline` and `APARTMENT-v1-restart001-maps`; pair: `APARTMENT-pair-001-restart001`.
- Original matched schedule SHA256: `6113dc0a9c70c3deaf6249a2faadb9de3b9c312514fa7534d41134eda102b8b4`.
- New frozen source-manifest SHA256: `814a368c4895bdfc6272a080036bae821fa32e8cfbac7b8d518e3fdc8cacbce3` (254 files).
- New certificate SHA256: `598f83a35f450344c2579deb1043d762bd9ccb2ce98c9366f1238d19d5d4303a` (244 source/template identity entries).
- Configuration remains household 240 s, throwing 1,800 s, return reserve 3,600 s, native wall limit 7,200 s. Exact launch/status/viewer/hibernate/resume commands are in the operator handoff.

Stop here. The next Development Codex session can launch the fresh baseline with Randy present. Use its frozen D: source, and never resume the excluded original root. Maps follows only after the completed baseline endpoint.

Apparatus readiness is separate from learned task performance. Household recurrence is unbounded; finite limits and explicit failures remain. There is no guarantee of eventual task completion, throwing skill, Maps advantage or real-world transfer.
