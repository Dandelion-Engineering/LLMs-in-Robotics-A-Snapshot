# Revised-envelope mechanical qualification

`RCI001-C03-dev-011` completed as queue job `20261004T022323188785Z-3f50404f`, succeeded with integer exit 0. The registered result and immutable source archive are in Architecture Map/releases/RCI001-C03-dev/RCI001-C03-dev-011.

All 24 boundary and inherited-authority tests passed. The exact history index addressed 132,000 rows (146,957,790 retained JSONL bytes) using 10,828,056 index bytes. The physical sequence completed three C placements, handbacks and fresh namespaces, plus five A/B jobs. Strict timing passed with maximum lag 0.0057068 seconds and zero bad complete windows out of 157.

Independent reader job `20261004T022955849345Z-bb56770f` also succeeded with integer exit 0. All 16 checks passed: full filesystem reconstruction, clock brackets, source identities, unchanged historical evidence and physical scene, terminal/retirement chains, late camera evidence, and strict timing replay. See `independent-audit/receipt.json` and `independent-audit-official-status.json`. `mechanical_reader.py` selected a new derived viewer location without changing the reader logic; `independent-reader-readback.json` records its source hashes after completion.

These checks contain zero model invocations. The large history exercise is a synthetic retention check, and the approximately 157-second physical sequence is not a full-duration soak. Neither establishes live qualification or model performance.

The raw `system/`, `independent-audit/raw/`, `history-stress.jsonl` and derived `Review.html` remain local and ignored by Git. Their identities are bound by the compact receipts and reader input inventory. No evidence was deleted.
