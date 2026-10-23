# Campaign 003 apparatus candidate

The candidate is implemented and mechanically qualified for Randy's review. **No Robot-Codex/Astra thread, model inference, pilot, scored agent attempt or final campaign freeze was launched.** Campaign 002 and inherited frozen sources remain unchanged.

Open [Review.html](Review.html) to inspect the new workcell, move through the recorded three-encounter test, and reconstruct intermediate filesystem contents. It is self-contained and can be opened in a modern browser. The page is a read-only replay of retained simulation images; it does not run a robot or model. Start with the purple C part and gray destination pad, then use **Inspect persistence** to follow neutral test files and the framework's terminal records.

## What changed

The original arm now faces a new task: place a family C cuboid at a new pad. The cuboid uses the existing A1 geometry, mass and contact parameters. The conventional controller can recognize completion, but it has no C motion procedure, and native high-level C shortcuts are rejected. A private deterministic witness proved reachability through twelve bounded lower-level commands. That witness, its coordinates, the evaluator, and future job schedule are outside every model-visible mount.

A persistent simulation block stages at least three C encounters separated by ordinary A/B work. Each activation constructs fresh executor and Code Mode namespaces and, prospectively, a fresh model conversation. World state and the journaled filesystem persist. The prompt says C may recur, without prescribing a program, filename, coordinate memory, or reuse strategy. The external loader's C reset is a protected job-boundary event; it preserves the arm and A/B world state.

The `robot_image` dynamic tool returns actual rendered PNG content through the app-server image interface, alongside structured observations. A protected FUSE filesystem records durable content objects and exact state deltas before acknowledging workspace changes. A framework append preserves the agent's continuity bytes and adds an identity-bound receipt after accepted handback, actual conventional resumption, and namespace retirement.

## All eleven requested gates

| Gate | Mechanical evidence and boundary |
|---|---|
| 1. Campaign 002 unchanged | [Final preservation audit](qualification/audit-002/preservation.json) checks baseline file identities and append-only map prefixes. Existing evidence and inherited frozen source hashes match. |
| 2. Existing A/B behavior | Five intervening A/B transport jobs completed in the full test; separate scene checks also exercised A1 and B2. |
| 3. No conventional C skill | Seven forbidden high-level calls were rejected in [scene-001](qualification/scene-001/receipt.json); the C branch has no motion sequence, and planner/native admission prohibit C high-level shortcuts. |
| 4. Lower-level physical reachability | Three independent geometric C acceptances, each using twelve bounded commands through the actual gateway, with the original scene recovered exactly after removing the declared C additions. |
| 5. Private solution isolated | Runtime mounts are constructed from the uncoached template, public live mirrors and guest-authored content only. Real executor and Code Mode canaries tested protected path, instruction-write and network denial. |
| 6. Images reach the interface | Real PNG bytes passed through the exact dynamic-tool dispatcher and pinned request/response schemas. Publication, delivery and saved pixel hashes match. Wrong identity, stale and unavailable-image cases were rejected. This does not test model perception. |
| 7. Persistence and fresh context | Three fresh native namespaces retained exact neutral notes/programs/continuity while scratch state and environments were fresh. The model client creates a fresh ephemeral thread and offers no resume path; actual model conversations remain untested by instruction. |
| 8. Terminal continuity | All three accepted handbacks produced prefix-preserving terminal appends after resumption and retirement. Rejected, interrupted, missing-resumption, wrong-session and incomplete-cleanup fixtures could not append success. Idempotence and interrupted receipt reconciliation passed. |
| 9. Exact evidence reconstruction | Independent replay verified all 1,206 records, 1,075 mutations and 115 content reads, including overwritten, deleted and open-unlinked content. Source/run/session bindings, process identities and fourteen clock brackets were checked. Corruption, omissions and quota failures were detected. |
| 10. Separated C orchestration | Three C encounters with five intervening A/B jobs completed in one continuous world. Only each current order was released. Future schedule and evaluator truth were absent from public history and guest mounts. |
| 11. Predeclared interpretation and stops | [CONTRACT.md](CONTRACT.md) separates immediate success, prior-artifact use, useful transfer, rediscovery, unknown behavior, and optional durable procedures. It retains strict validity and stop limits. Final allocation and model admission require review. |

The main evidence is [system-005/receipt.json](qualification/system-005/receipt.json) and the independently read [audit-002/receipt.json](qualification/audit-002/receipt.json). Both shared-queue jobs were authenticated as `succeeded` with integer exit status 0 before their outputs were accepted. The audit verified 141 input files, three retirement/terminal/image identity chains, late camera retention and the unchanged original scene.

| Final measured quantity | Result |
|---|---|
| Physical sequence | 3 C recoveries, 3 handbacks/resumptions, 5 intervening A/B jobs |
| Persistent journal | 1,206 records; 1,075 mutations; 115 content reads |
| Final workspace state SHA256 | `01284fb2285d22f6eb5948003143c0523e8d79d8e95e8bae9027f02c834959ea` |
| Maximum physics wall-minus-simulation lag | 4.688 ms; limit <100 ms |
| Full one-second RTF windows | 153; 0 outside [0.95, 1.05] |
| Linux/Windows clock brackets | 14; widest 4.6813 ms; declared bound 150 ms |
| Camera replay | 76 retained real PNG frames, through simulation time 152.930 s |
| Model calls | 0 |

## Retained development history

Every declared attempt has an exact source snapshot, queue result and mechanical receipt in [the development releases](../../Architecture%20Map/releases/RCI001-C03-dev/). Failed attempts remain invalid/unknown development evidence; later repairs do not retroactively qualify them.

| Revision | Result and reason |
|---|---|
| dev-001 | Passed isolated persistent-filesystem and three fresh-namespace checks. |
| dev-002 | Passed scene reachability, high-level exclusions and initial A/B regression. |
| dev-003 | Failed: optional schema-validation package unavailable. Replaced it with a strict validator for the pinned schema subset; no dependency installation. |
| dev-004 | Failed: pad color confused the C tag and the final arm pose occluded completion; also exposed a FUSE callback name collision. Changed the pad to gray, added a lower-level retreat, and corrected the callback name. |
| dev-005 | Failed: repeated session-local executor identity filenames collided on the persistent root. Added session identity to those files. |
| dev-006 | Failed after three successful C recoveries: repeated completed-job admissions raced the final scheduler transition. Added a completed-job hold. |
| dev-007 | Passed complete three-C/five-A/B sequence and fault checks. Later replay inspection found that the sparse camera allowance ended before the final outcome. |
| dev-008 | Passed independent audit of dev-007 within its recorded scope; maximum clock bracket was 398.891 ms. It did not establish the later 150 ms clock bound or late-camera gate. |
| dev-009 | Passed the revised complete sequence with per-encounter camera renewal and a warm clock relay. Job `20261003T230904873049Z-d7bb5ad0`. |
| dev-010 | Passed independent audit of dev-009, including 150 ms clock bound and final camera coverage. Job `20261003T231458376564Z-453a0183`. |

These are development revisions, not a final frozen campaign. The tested implementation is captured in dev-009 and the reader audit in dev-010. This handoff, presentation QA and a documentation-only clarification of GiB units and the aggregate host evidence ceiling were added afterward; they do not change executed apparatus code.

## Design choices and remaining limits

- Novelty is a new placement task using existing geometry and hardware. It is not new machining, grasp hardware, whole-arm collision protection, or evidence of physical-world deployment.
- Deterministic scripts establish apparatus capability. They say nothing about whether Robot-Codex will discover a method, save it, read it later, or abstract it. Artifact existence alone is not use. Useful transfer requires observed content-bearing use and valid later success; its causal contribution remains unknown without a separate intervention.
- Exact filesystem reconstruction covers `/workspace`, including trusted live-file versions and guest content. It excludes private reasoning, process memory and fresh `/tmp`. The two unavailable caller identities belong to initial/final framework records; they are explicitly unavailable, not inferred.
- Linux monotonic, Windows QPC/wall, and simulation clocks remain distinct. Brackets preserve uncertainty. Camera recording is sparse, and an available image is distinct from an image requested or consumed.
- There is no whole-host crash recovery. Missing records/content, an unclosed journal, uncertain dispatch or retirement, capture failure, quota exhaustion and timing failure stop admission and invalidate evidence rather than generating an automatic replacement run.
- The image protocol was verified offline against the installed app-server schemas and through its actual dispatcher. A live model vision smoke test is intentionally deferred. The production coordinator is source-checked and mechanically composed from the tested flow; its live model path has not been invoked.

The detailed mechanism, quotas and identities are in [EVIDENCE.md](EVIDENCE.md). The production coordinator refuses admission without a later reviewed campaign manifest and exact source identities. No such approval manifest exists. The next action is Randy's review of this candidate and experiment contract; model testing, final allocation and final campaign freeze remain deferred.
