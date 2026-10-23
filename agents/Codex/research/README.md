# Initial map research provenance

The current source of truth is [literature/papers.jsonl](../../../literature/papers.jsonl) and [literature/searches.jsonl](../../../literature/searches.jsonl). These neighboring files preserve inputs and bounded checks from Codex session 1, dated 2026-09-18. They are historical provenance, not a second maintained corpus. Do not regenerate current records from them.

- [Tool reference notes](tool-reference-notes.md): read-only Vision and LC locations, revisions, sampled structure and file hashes.
- `planning_tools.papers.jsonl` / `planning_tools.searches.jsonl`: planning, executable code, architectural alternatives and root source/resource checks.
- [Memory/grounding handoff](memory_grounding.handoff.md) and neighboring `.papers.jsonl` / `.searches.jsonl`: memory, sensing, cognition and lab assistance.
- [Learning/transfer handoff](learning_transfer.handoff.md) and neighboring `.papers.jsonl` / `.searches.jsonl`: policies, embodiment, prediction and evaluation.
- [Retrieval checks](retrieval-checks.json): actual CLI arguments and bounded results against the canonical corpus.

Integration retains real search events, normalizes `retained_paper_ids` to the validator's `selected_paper_ids`, clarifies author-completeness metadata, and adds actual overview/use-check events. The integration event records input hashes. No corpus import is counted as reading.
