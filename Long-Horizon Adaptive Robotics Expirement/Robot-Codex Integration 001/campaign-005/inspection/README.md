# Campaign 005: discoverable persistent work

Campaign 005 is complete. The sole frozen block had three valid C successes, each in its first fresh Astra/max session. All three placements, accepted handbacks, conventional resumptions and native retirements passed independent readback. Six allowed session opportunities were unused; no occurrence was unrun and no replacement block was launched.

The memory intervention produced observable reuse: all sessions read the semantic handoff; session 2 opened, adapted and executed session 1's helper; session 3 opened and executed the adapted helper unchanged. This demonstrates functional procedural reuse during successful later work. It does not establish that memory caused success, saved time, or improved a population success rate. These are three correlated occurrences in one persistent block, with no memory-withholding comparison.

## Review surfaces

- [Synchronized replay](D:/Dandelion-Campaign005-Exports/inspection/replay-001/index.html): public messages and tool results, recorded world images, exact file history, memory read/write jumps and fresh-session boundaries.
- [Observable analysis](evidence/observable-analysis.json) and [independent analysis verification](evidence/analysis-verification.json).
- [Independent experiment audit](evidence/audit-receipt.json), [final preservation/readback](evidence/final-readback-receipt.json), and [browser QA](qa/browser-qa.json).
- Exact final [semantic handoff](evidence/.continuity__Continuity.md), [helper](evidence/programs__bounded_step.py), and recovery notes for [order 1](evidence/notes__c1-recovery.md), [order 4](evidence/notes__c1-order4-recovery.md) and [order 7](evidence/notes__c1-order7-recovery.md). These are retained Robot-Codex artifacts, not developer recommendations or new authority. [Identities](evidence/public-file-identities.json) bind them to the closed journal.
- [Development and retained failures](development.md), [prospective manifest](../../../Architecture%20Map/releases/RCI001-C05/RCI001-C05-final-001/manifest.json), and [registered result](../../../Architecture%20Map/releases/RCI001-C05/RCI001-C05-final-001/result-record.json).

Browser QA used a temporary loopback preview. To reopen locally, run `python -m http.server 8765 --bind 127.0.0.1 --directory D:/Dandelion-Campaign005-Exports/inspection/replay-001` and visit `http://127.0.0.1:8765/`. Direct file-URL rendering was not tested. The replay is inert and makes no model or robot calls.

## Per-session observations

| C occurrence / public order | Session suffix | Continuity read | Inventory read | Physical requests: completed / rejected | Explicit captures | Actual image deliveries | Completed public tool items: command / image / edit | Model turn seconds |
|---|---|---|---|---|---|---|---|---|
| 1 / 1 | `e266dd3d57e04593` | Yes | Yes | 14 / 2 | 16 | 4 | 39 / 4 / 0 | 454.89 |
| 2 / 4 | `1b6d999793b246f6` | Yes | Yes | 14 / 0 | 15 | 3 | 31 / 3 / 2 | 385.94 |
| 3 / 7 | `bf71cbeefa0d4c6b` | Yes | No observed read | 14 / 0 | 15 | 2 | 36 / 2 / 0 | 348.60 |

Counts use original final command registries and completed public client items, independently reconciled. Physical requests include the native clear-view action; explicit capture requests are counted separately. Rejected commands are retained, not counted as dispatched successes. Each session used 14 of 120 admitted physical actions and ended normally with accepted handback and independently satisfied protected placement. At least 3,145 seconds of the 3,600-second model allowance remained; observation and wall/simulation limits were also far from exhaustion. The shorter later turns are descriptive, not an estimated speedup.

Session 1's clear-view requests `c1-clear-view-014` and `c1-clear-view-016` were rejected for stale observations. Later current evidence supported a new request, `c1-clear-view-017`, which completed. The rejection records and nonzero public tool exit remain visible. All three handbacks were accepted: `c1-handback-018`, `c1-o4-handback-015`, `c1-o7-handback-015`.

## What was transferred

The journal sequence numbers below can be entered in the replay's journal or memory controls. References to `client/events.jsonl:<line>` are completed public items under the named session's retained evidence directory. Real-model attribution requires the session, executor-2 PID namespace and native process start ticks together; framework inventory scans and executor-1 preflight reads are excluded.

1. **Session 1 created and indexed work.** It read the initially empty continuity at record 389 and the initial structural inventory at 392. It created `programs/bounded_step.py` at 1351–1352, then repaired its handling of terminal receipts/rejections at 1717 and 3485. The helper submits one caller-chosen command, queries the result and captures observations; it contains no automatic C placement route. The session executed it for its own task, wrote `notes/c1-recovery.md`, and indexed the helper and detailed evidence in continuity at 4897. The entry describes its purpose, evidence log, review requirement, lack of automatic retries, and need to reconcile unknown outcomes. It also records occlusion, stale-observation and image-publication limitations. There was no prior helper to reuse.

2. **Session 2 encountered the references and adapted the actual artifact.** At 5555 it read all 2,982 bytes of the handoff, including the helper path and limitations; at 5557 it read the 3,308-byte structural inventory. At 5613 and 5615 it opened the prior helper and recovery note (`client/events.jsonl:102,109`). Its first substantive code update, 6149, added epoch-specific evidence logs and a capture-only mode and scoped displayed historical unresolved receipts; 9274 added capture usage documentation. The mutation history preserves the intervening empty truncation states. Public executions at lines 171 and 218–412 ran that helper for a capture and all 14 physical requests, with terminal physical receipts. The session indexed the updated helper and new order-4 evidence at 9289/9682. The physical closing action also changed from session 1's gripper wrapper to a fixed Cartesian target, consistent with the prior note's sag warning; the code reuse and adaptation are directly evidenced, while the warning's causal influence cannot be isolated.

3. **Session 3 reused the adapted version.** It read all 5,667 handoff bytes at 10120, opened the helper at 10191, and opened the preceding recovery note and action list at 10193/10195 (`client/events.jsonl:99,109,111`). There is no positively attributed inventory read in this session. The helper's startup and final SHA256 are both `095d4e8a5a06b732e47601de1c88e87a0bff9e62cb045606e0630a8a4d9791f0`; it was not rewritten or copied to a replacement program. Public executions at lines 191 and 209–362 used its capture mode and performed all 14 physical requests. It created new epoch-9/order-7 evidence and recovery notes, then indexed them with the unchanged helper at 13268/13788. Its final note explicitly says it reused the helper after review.

| Evidence level | Supported conclusion |
|---|---|
| Existence | One model-created helper persisted; each session created its own evidence and recovery notes. |
| Discoverability | All authored handoffs included the helper path, purpose and limits; later complete handoff reads exposed those references. The structural index accurately published startup snapshots at 40, 5215 and 9786. |
| Read | Both later model executors read prior helper bytes and recovery material. Inventory reads occurred only in sessions 1 and 2. |
| Execution | Completed public Python commands, matching artifact reads and physical receipts establish execution in both later sessions. |
| Semantic reuse/adaptation | Session 2 edited and ran the prior helper; session 3 ran that exact adapted version. No replacement helper was created. |
| Useful transfer | Prior code performed functioning command/query/capture/logging work inside successful later tasks. Necessity or improvement over a fresh derivation is not identified. |
| Causal contribution | Unknown. There was no withholding/ablation, and the semantic handoff and inventory were introduced together. Campaign 004 is a historical comparator with a different seed/schedule, not a matched control. |

No hidden chain-of-thought is reconstructed. Unread historical paths remain available in the exact inventory; non-use is inferred only as absence of recorded model content reads/executions, not as a psychological claim. Reuse does not make the helper or its geometry a qualified general controller.

The handoff grew from 61 bytes initially to 2,982 bytes visible to session 2, 5,667 to session 3, and 8,044 at block close, including three framework terminal records. It retained older sections and pre-handback wording alongside authoritative terminal receipts. This block demonstrates discoverability over three occurrences, not long-horizon compaction quality. Future readers still must reconcile current authority and evidence.

## Qualification, freeze and preservation

The new lineage changes only the domain-general memory contract and a read-only structural inventory at fresh-session startup. Inventory versions count changed startup snapshots, not every write; exact intermediate versions remain in the journal. The index claims file identity/provenance, not semantic usefulness. Native write boundaries, current authority gates, same-world continuation rules, six-face public C perception and the absence of a scaffold-supplied C placement routine remain intact. Physical/perception/client/bootstrap sources and all resource limits carried forward unchanged from Campaign 004.

Deterministic qualification exercised two safe unresolved invocations followed by three successful witnesses, handoff/helper reads and updates/deletion, exact inventory reconstruction, invalid-stop rules and the hidden three-session ceiling. The initial dev001 worker failed because a fixture incorrectly demanded globally unique retired PID namespace numbers. That failed attempt is retained. Prospective dev002 used namespace plus native process start ticks and passed; independent dev003 passed without reader repair. No model was invoked during qualification. Actual-model within-occurrence continuation was never needed, so that path has deterministic evidence only.

The single block was frozen before invocation: revision `RCI001-C05-final-001`, manifest SHA256 `d71df07274627c8fdd8881d4b9533956f1c173f417996acc8d1d75aa1e9a1303`, snapshot `d617779c8818205cc3cdf12b6449274602bded51eaf26e604003033ceb39f8a2`. Scene 173, noise 550101, schedule 550103; C orders 1, 4 and 7, with four successful intervening A/B jobs. The coordinator requested exactly three model calls. Total coordinator wall time was 1,323.99 seconds.

All relevant workers succeeded with integer exit 0, and their output checks passed separately: actual `20261004T205806506972Z-5a753613`, experiment audit `20261004T210120284008Z-42099183`, analysis `20261004T212246149363Z-560e5ab3`, replay `20261004T212246575743Z-34e67ae2`, final preservation reader `20261004T213124966547Z-5d87cbb8`. Status receipts are adjacent to this report.

The independent audit reconciled 239 original evidence files, 71 frozen campaign files, 974 inherited files and all 45,007 historical files. The exact journal has 13,807 records (12,502 mutations and 1,289 reads), final state SHA256 `23939451112d0a7c8f169418655544b0331d44d3f274c7331a90d14339ea2a6e`. The replay includes 651 public events, 12,697 observations, 244 frames and 3,013 exported content objects. The largest public receipt bracket is 0.148 seconds; sparse Linux/Windows checkpoints do not locate every file operation at an exact world instant. Protected ending state is labeled analyst-only and gated by its recorded time. Endpoint/canary contents and hidden reasoning are withheld.

Campaigns 001–004 and their evidence remain byte-identical. Randy separately approved lossless NTFS compression of four exact historical r4 event logs; their hashes, logical lengths and modification times were preserved. Physical allocation fell 1,741,092,042 bytes, allowing the unchanged 111-GiB launch gate. Total free-space change is not wholly attributable to compression. Final readback measured C free 111.08 GiB and D free 457.29 GiB. Nothing was deleted or moved to obtain launch space.

Original actual evidence remains under `campaign-005/scored-evidence/RCI001-C05-final-001-block-001` (ignored and retained). Closed public archives, independent reconstruction and replay remain under `D:/Dandelion-Campaign005-Exports/`. No new model launch is authorized by this completion report.
