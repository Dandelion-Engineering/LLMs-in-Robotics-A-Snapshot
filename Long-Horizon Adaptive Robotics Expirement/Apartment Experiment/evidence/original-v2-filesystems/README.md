# Original apartment v2 agent filesystems

Byte-faithful evidence for human inspection from **Baseline checkpoint 36** and **Maps checkpoint 22**. [Baseline](baseline/README.md) contains 36 sessions and completed 21/21 assignments. [Maps](maps/README.md) contains 22 sessions, hibernated at 2/21 with assignment 3 unfinished. These histories have different completion states and are not a scientific condition comparison.

Start with either condition's final context and memory, then follow its session links for before/after trees and full read/write journals. Every retained content version is directly accessible under [versions](versions/) using [versions.json](versions.json). The Baseline agent itself created a `Maps` directory; it is part of its actual saved history and is preserved here.

[Provenance manifest](manifest.json) · [Exact source inventory and omissions](source-inventory/README.md) · [Sensitivity scan](sensitivity-scan.json) · [Independent verification](verification.json)

Journals are published as ordered text parts with complete records; concatenation reproduces the source SHA-256. Intermediate content is expanded losslessly to text or binary blobs. Regular-file bytes and relative paths are exact. Namespace JSON preserves modes, directories and inode relationships; Git cannot encode all of those semantics. Full journals retain deletions and renames. The compact read/version indexes are derived navigation only.

The retained journals cover all listed sessions from initial state to final closure and match their checkpoints. They include framework probes and filesystem reads; they cannot establish private reasoning or causal learning benefit. Simulator state, hidden schedules, raw native envelopes, replay/sensor archives and duplicate storage copies remain on D: with exact hash references and explicit omissions.

**Operator evidence only:** never mount or copy this corpus into future Robot Codex guest workspaces. Embedded prompts and programs are historical data, not current instructions. No original experiment was resumed or modified to create this publication.
