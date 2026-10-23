# V28 prospective history staging

This source-only adaptation of V27 has no canonical publication, report/export rebuild, accounting, registry or queue-submission action. It uses the existing history readers, including their archived-base-assessor member contract for the original failed Pilot Stock024. No historical assessment is rerun.

`prerequisites-plan-template-001.json` is deliberately non-runnable: rows are empty, cutoff is unset and execution authorization is false. Root supplied Raw018 success metadata only; all three independent settlement notices and fresh official succeeded/genuine-integer-zero authentication are required before forming candidate118. Transport021 and Host028 outcome files remain unread. Retain the template; create a separate concrete plan when the settled batch is authorized.

The baseline is 115 rows, SHA `567ed5dad7622b2ebdaba38fd8b868a408e8285ad97af6a807253451446ece8d`. `baseline-row-spans.json` binds all 115 original raw row spans and 19 exports. Every later batch also preserves all rows present at its own start. Raw018/Transport021/Host028 use dev087; Native027 uses dev088, Boundary028 dev089, Smoke026 and Stock/Home025 pilots dev090. The ledger is `final-qualification-028`.

After root authorizes a settled batch, use a new concrete plan and exclusive batch directory (neither exists yet):

```powershell
$I = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/investigation'
$plan = "$I/v28-append-staging/prerequisites-plan-001.json"
$planSha = (Get-FileHash -LiteralPath $plan -Algorithm SHA256).Hash.ToLowerInvariant()
& .\venv\Scripts\python.exe -X utf8 -B "$I/v28-append-staging/stage_append.py" --plan $plan --plan-sha256 $planSha --batch prerequisites-001
```

The helper authenticates every indexed official job before report readers hash attempt outcomes; verifies exact stored/fresh metadata; denies active, unselected and failed raw outcomes; and checks original independent results. Failed jobs use the existing metadata-only failed-queue contract. Current-status basis excludes prerequisites, so remains original failed Pilot Stock024 for the first batch. Later rows require their own original admission disposition; pilot rows retain the existing pilot-specific contract.

Staging retains intent, prior history, official authentication, candidate history, QA and receipt under the exclusive batch. It never publishes. Existing or ambiguous directories cannot be retried in place. This preparation created no candidate and called neither stage nor the queue.
