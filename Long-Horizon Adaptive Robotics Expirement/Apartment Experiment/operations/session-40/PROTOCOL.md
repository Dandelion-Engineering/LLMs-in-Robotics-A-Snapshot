# Session 40 storage audit and cleanup

Randy's October 9 19:08 PDT instruction authorizes project-owned C: and D: storage cleanup only. Main was pulled first to c8058506. No experiment preparation, model call, launch, recovery, comparison or monitoring is authorized in this session.

Measure the repository, its named external evidence/export roots and attributable temporary workspaces. Inspect project Linux storage separately; do not treat free blocks inside WSL as released Windows volume capacity. Exclude other projects and shared/system stores. Preserve Git history, installed dependencies, current and qualified sources, published robot filesystems, all original experiments and historical qualification evidence. Directory age, failure or supersession is never sufficient grounds for deletion.

Use the shared compute queue for sustained census, hashing and cleanup. Census every regular file's logical size and Windows FILE_STANDARD_INFO allocation; do not follow reparse points. Record hardlinks because pathname totals can overcount allocation. Establish project process/mount quiescence before deletion. Protect uncommitted work; the initial worktree is clean.

Select exact paths only after checking contents, provenance, references and retained manifests. A redundant copy requires complete readable byte-equivalent surviving content and evidence that retained consumers do not depend on the removed location. Regenerable bytecode requires surviving source and exclusion from frozen records/dependencies. Uncertain candidates remain untouched with a recorded reason. No broad temporary-directory or shared-cache purge, deduplication migration, compression of originals, or gate change.

Before deletion, freeze a path-level manifest with size/allocation, hashes where relevant, classification and justification; recheck the actual resolved paths, reparse ancestors, metadata and process state. Delete via one native PowerShell workflow using literal paths. Preserve every failed/partial cleanup result. Verify exact absences and retained protected identities, source/certificate bindings and entrypoints afterward. Report actual per-volume free-space deltas separately from removed logical/allocation totals, with accounting caveats and remaining D: shortfall against the unchanged 50 GiB gate.

Write the final report, append Architecture Map and human-chat records, update continuity, close the claim and use normal Git closeout. Stop even if sufficient capacity becomes available.
