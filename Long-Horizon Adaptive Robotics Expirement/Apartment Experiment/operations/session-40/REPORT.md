# Session 40 — Project storage audit and verified cleanup

**Storage assignment complete. Removed 4,042 disposable environment cache files and 26 empty project temporary trees on C:. No D: files were deleted. D: has 36.895508 GiB free and remains 13.104492 GiB below the unchanged 50 GiB admission gate. No experiment preparation, model call, launch, recovery, comparison or monitor was started.**

The deleted files contained **30,008,579 bytes (0.027948 GiB)**; Windows reported **38,682,552 bytes (0.036026 GiB)** of file allocation. Every removed bytecode file had readable, unchanged Python source and no content-bound package RECORD entry. All installed source/dependency files remain. Only demonstrably empty, project-named temporary directory trees were removed. No duplicate evidence copy was admitted for deletion; therefore no surviving-copy substitution is being claimed.

## Actual volume observations

These are measured free-space differences, not sums of nominal file sizes. The interval is 2026-10-09T19:16:59.586204-07:00 through 2026-10-09T20:11:27.857034-07:00, before final Git closeout.

| Volume | Before free bytes | After free bytes | Net free change bytes | Net change GiB | New free GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| C: | 559,165,861,888 | 558,846,578,688 | -319,283,200 | -0.297356 | 520.466434 |
| D: | 39,616,249,856 | 39,616,249,856 | +0 | 0.000000 | 36.895508 |

**Combined observed net change: -319,283,200 bytes (-0.297356 GiB).** During the narrower deletion interval, C: changed by +33,800,192 bytes and D: by +0 bytes. The full interval includes new audit evidence and other host writes; it cannot be attributed solely to cleanup. FILE_STANDARD_INFO allocation excludes directory/filesystem metadata, and resident data/hardlinks can differ from volume-level recovery. A negative net change means free space decreased despite deleting the safe candidates. Large local audit inventories are hash-bound in `local-artifacts.json` and retained outside Git.

## Why the large items remain

The census inspected **1,208,520 files across 31 explicit roots**, including hidden/ignored repository files, installed dependencies, four project-owned D: roots and 26 named C: temporary trees. It reported no traversal or allocation errors and no reparse points. Linux project namespace storage was accounted separately in `linux-inventory.json`; shared WSL infrastructure and other projects were outside deletion scope. There is one Git worktree. No unrelated drive contents or shared caches were selected.

| Measured root | Files | Logical GiB | File-allocation GiB, path sum |
| --- | ---: | ---: | ---: |
| C: repository | 553,503 | 216.117856 | 215.562812 |
| D: apartment experiment | 481,831 | 17.333554 | 475.212891 |
| D: CodexEvidence/LLMs-in-Robotics | 166,103 | 28.674179 | 175.622070 |
| D: Campaign 004 exports | 3,518 | 0.481115 | 3.807617 |
| D: Campaign 005 exports | 3,565 | 0.693838 | 3.964844 |

The C: path sum repeats 25,553,465,600 allocated bytes across identified hardlinks; adjusted regular-file allocation is 191.764292 GiB. Removing extra model paths would not release that repeated amount. Directory/filesystem metadata is outside these regular-file totals.

D: is exFAT with **1,048,576-byte allocation units**; C: is NTFS with 4,096-byte units. The apartment root contains **18,611,761,770 logical bytes (17.334 GiB)** but uses **510,255,955,968 file-allocation bytes (475.213 GiB)**. Session 39 alone uses 134.890 GiB of file allocation for 2.985 GiB of data. This overhead explains why deleting a few generic caches cannot solve the D: gate.

The official v2/v3 roots, failed launches, Sessions 36–39 qualifications, original journal/replay/sensor records, checkpoint and schedule histories, published v2 robot filesystems and qualified release remain intact. Apparent restoration/staging copies are retained when referenced by source manifests, certificates, historical preservation inventories or analysis. The large `D:/CodexEvidence/LLMs-in-Robotics` development/recovery trees hold distinct original attempts; the Campaign 004/005 exports support audit/replay readers. C: raw evidence, historical viewer packages, models and Git history remain. Model hardlinks were identified separately in `census001/hardlinks.json`; repeated path sizes are not reclaimable duplicate bytes. See `retained-candidates.json` for 19 high-value retained groups and their dependency evidence.

## Verification and continuation

The first deletion submission failed before changing files because Windows PowerShell could not load Get-FileHash. All 4,068 targets were independently confirmed present, and the unchanged script/manifest succeeded under the installed PowerShell 7 executable. The failed receipt/log and successful receipt remain separate.

The initial serial hash audit was canceled for I/O execution cost, and its queued cleanup-plan job was canceled before starting. Both terminal records and the incomplete log are retained. A fresh eight-worker read-only pass restarted from the beginning with the same comparison gates; the canceled output was not accepted as completed evidence.

The first final process observation (`quiescence-after.json`) flagged this audit's parent Python stdin wrapper as unexpected. Its failed guard is retained. Running the same checker directly after that wrapper exited produced `quiescence-after002.json`; the process filter was not relaxed. No experiment process was observed in either check.

Before deletion, full SHA-256 comparison matched **75 historical apartment roots, 344,286 files and 15,390,037,785 bytes** against the authenticated Session 39 inventory. A fresh full inventory also hashed **137,516 Session 39 files / 3,205,562,693 bytes**, plus the published robot filesystems. After the strictly C-cache-only deletion, retained census files were checked for unchanged size and modification time; only routine tool/chat state and Git index/fetch metadata were excluded, with their exact paths recorded in the verification receipt. All expected absences and cache-source hashes passed. The postcheck is a metadata comparison plus critical rehashes, not a second whole-history byte rehash.

Both copies of all 263 qualified source files, the certificate, v2 checkpoint 36, v2 Maps checkpoint 22, v3 checkpoint 14 and hidden-schedule/preparation identities were rehashed after cleanup. Certificate SHA-256 remains `49ac8e59a7af7b0e7b14c9c66eb3a5007984762c33e9382761cd44346d64054f`. Installed NumPy/MuJoCo/websockets imports, source syntax and Git connectivity passed. Process/queue/mount readbacks found no project experiment or orphaned runtime. `apartment-v4` remains absent. Shared-queue terminal receipts, exact deletion plan/status and verification are retained beside this report.

| Evidence | Contents |
| --- | --- |
| [Final volume measurements](final-measurements.json) | Exact before/after capacities, observed changes and remaining D: shortfall |
| [Deletion plan](cleanup-plan.json), [actual status](deletion-status.jsonl), [result](cleanup-result.json) | Every exact target, classification, justification, source proof, sizes and deletion outcome |
| [Surviving sources](cache-source-proof.json) | Per-source hashes for all removed bytecode |
| [Retained candidates](retained-candidates.json) | Large protected or uncertain groups and reference/dependency reasons |
| [Full protected hash baseline](parallel002/preservation-before/result.json), [postcheck](verification.json) | Preservation scope, source/certificate/checkpoint identities and environment checks |
| [Final runtime readback](quiescence-after002.json), [monitor state](monitor-status.json) | Process, queue, mount and paused-monitor observations |
| [Census](census001/result.json), [Linux inventory](linux-inventory.json), [local inventory identities](local-artifacts.json) | Measured scope, volume allocation and retained external-to-Git inventories |
| [Reader change](reader-change.json), [failed deletion disposition](cleanup-attempt001-disposition.json) | Explicit canceled/failed maintenance attempts and why their output was not accepted |

This session stops at the storage handoff. No further disposable D: data was demonstrated, and no gate was relaxed. Any future evidence-storage migration or new preparation attempt requires later direct human direction; old once-only helpers remain used and must not be rerun. The Session 39 commissioning result and all prior failed attempts retain their original status.
