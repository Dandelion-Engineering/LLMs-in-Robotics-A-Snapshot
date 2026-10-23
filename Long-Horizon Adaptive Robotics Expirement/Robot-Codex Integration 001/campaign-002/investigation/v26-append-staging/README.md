# V26 history staging

This helper writes an exclusive candidate/QA batch beneath this directory. It has no canonical-history publication action, export builder, accounting action, registry call, or queue-submission command. Root must authorize the selected settled stages before invocation and authorize any later canonical append separately.

`baseline-row-spans.json` preserves identities for all 102 original raw JSON row spans and the 19 retained export bindings. Subsequent V26 batches also preserve every row already present when that batch starts. The baseline history SHA is `ad51bea18ad83aa5d38cdbe55fbeda60fe1116229cd41a419f0244b55b07a6e4`.

The fixed allocation is Raw016/Transport019/Host026 on dev079, Native025 on dev080, Boundary026 on dev081, and Smoke024/Pilot-stock023/Pilot-home023 on dev082, using `final-qualification-026` and coordinator V26. No seed, policy, admission or model configuration is supplied or changed here.

After authorization, supply a JSON plan with these fields:

```json
{
  "schema": "campaign002-v26-history-staging-plan-1",
  "coordinator": "run_final_qualification_v26.py",
  "ledger": "final-qualification-026",
  "expected_history_sha256": "caller-verified current history SHA256",
  "expected_rows_before": 102,
  "rows": [],
  "current_status": {}
}
```

The empty arrays/objects above are documentation placeholders, not a runnable plan. `rows` must contain only explicit original-evidence row drafts in the existing history schema, ordered by the fixed allocation. `current_status` is the existing closeout-status schema, retaining the correct generic qualifier basis and separate latest model qualifier. No-model prerequisites are not model qualifiers. The helper checks these with the existing report/QA readers and does not infer a task outcome from queue success.

Run with the project interpreter, after hashing the concrete plan:

```powershell
& .\venv\Scripts\python.exe -X utf8 -B "$I\v26-append-staging\stage_append.py" --plan "$plan" --plan-sha256 $planSha --batch prerequisites-001
```

The batch name must be fresh. Any partial batch remains retained and is not retried in place. Before hashing or reading attempt outputs, the helper obtains fresh official metadata for every indexed job, requires succeeded plus genuine integer exit0 for assessed rows, and matches stored official metadata. Failed queue rows must use the existing metadata-only `queue_failure_contract`; their raw outputs are blocked. Active/unselected V26 raw outputs and assessments are blocked independently. Separate cross-run diagnoses remain `diagnostic_analyses` hash-only links.

The existing original assessment/admission validators support native, boundary, smoke and pilot rows. Drafts must cite the original V26 ledger dispositions; the helper neither reruns an assessor nor creates a verdict. Successful pilot task outcome remains separate from apparatus admission under the original report contract.

Outputs are `intent.json`, an exact prior-history copy, fresh `official/*.json` receipts, `candidate-history.json`, `qa.json` and `staged-receipt.json`. Canonical history and all 19 exports are checked unchanged. The stage stops if scored launch metadata exists; it cannot declare campaign admission or completion.

`source-check-001.json` records AST compilation, import safety and existing report/QA interface checks. `prerequisites-drafts/` contains only separately authorized Raw016/Transport019 draft evidence and QA; no Host026 output was read for that draft packet. No three-row candidate or publication was performed during helper preparation.
