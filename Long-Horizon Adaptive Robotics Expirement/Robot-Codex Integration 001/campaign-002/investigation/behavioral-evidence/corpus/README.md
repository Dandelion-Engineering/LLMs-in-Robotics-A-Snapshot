# Campaign 002 behavioral evidence corpus

All ten existing valid successes: five misplaced-stock and five blocked-insert-home. This is post-campaign evidence packaging for ChatGPT analysis; no behavioral interpretation or new experiment was performed. Campaign 002 remains 10 valid successes, 1 infrastructure-invalid/unknown task outcome, and 9 not run. Selection of successes must not be confused with the full campaign denominator.

Start with [the machine-readable index](index.json) and [format guide](FORMAT.md). Each run has the same events, background observations, clocks, sources, workspace and content/version representation. Complete original final file bytes are browsable per run. The ZIP contains only this derived public corpus, without original raw model envelopes.

| Run | Challenge family | Seed | Final regular files | Protected Continuity commits |
|---|---|---:|---:|---:|
| [RCI001-C02-stock-01](runs/RCI001-C02-stock-01/README.md) | misplaced-stock | 173 | 19 | 3 |
| [RCI001-C02-home-01](runs/RCI001-C02-home-01/README.md) | blocked-insert-home | 173 | 19 | 6 |
| [RCI001-C02-home-02](runs/RCI001-C02-home-02/README.md) | blocked-insert-home | 173 | 19 | 6 |
| [RCI001-C02-stock-02](runs/RCI001-C02-stock-02/README.md) | misplaced-stock | 173 | 24 | 3 |
| [RCI001-C02-stock-03](runs/RCI001-C02-stock-03/README.md) | misplaced-stock | 173 | 22 | 3 |
| [RCI001-C02-home-03](runs/RCI001-C02-home-03/README.md) | blocked-insert-home | 173 | 19 | 6 |
| [RCI001-C02-home-04](runs/RCI001-C02-home-04/README.md) | blocked-insert-home | 173 | 19 | 6 |
| [RCI001-C02-stock-04](runs/RCI001-C02-stock-04/README.md) | misplaced-stock | 173 | 23 | 2 |
| [RCI001-C02-stock-05](runs/RCI001-C02-stock-05/README.md) | misplaced-stock | 173 | 22 | 3 |
| [RCI001-C02-home-05](runs/RCI001-C02-home-05/README.md) | blocked-insert-home | 173 | 24 | 6 |

Intermediate content is last evidenced/requested content, never an exact reconstructed filesystem. Missing mutation journals, exact write times, intermediate unknown contents, directory metadata and unretained namespaces remain explicit. Public notes and messages are the agent’s claims. Background sensors do not establish a read. Final snapshots are untimed closure exports. Hidden reasoning and credentials are excluded; public agent-authored notes remain exact.

Use event IDs and source sequence for joins, and wall/simulation bounds for timing. Tool-call and executor layers refer to the same observable work but different receipts; do not double count them. `contents.jsonl` is keyed by SHA256 and supplies every retained file/version body. `workspace-final/` supplies exact original final bytes. See [independent verification](verification.json) for coverage and authenticity checks.
