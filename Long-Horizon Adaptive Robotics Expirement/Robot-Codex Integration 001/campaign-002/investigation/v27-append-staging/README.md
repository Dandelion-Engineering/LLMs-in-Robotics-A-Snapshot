# V27 prospective history staging

This directory contains a source-only adaptation of the V26 staging helper. It has no canonical publication, export rebuild, accounting, registry or queue-submission action. Import was checked with evidence reads and subprocesses forbidden.

`prerequisites-plan-template-001.json` is deliberately not executable: its rows are empty, current-status timestamp is unset, and it grants no execution authorization. It carries only root-provided queue identities. Do not run staging while a selected job is active or before root authorizes the settled batch. Retain this template unchanged; create a new concrete plan after the required terminal notice, fresh official authentication and original independent settlement.

The current baseline is 108 history rows, SHA `dd4dc9414c705c20d102544ebee6a1093f3bb1b390e6b3346124d287d9319576`. `baseline-row-spans.json` preserves all 108 raw row spans and 19 original exports. Later batches also preserve all rows present when they start. Raw017, Transport020 and Host027 use dev083; later allocations are Native026/dev084, Boundary027/dev085 and Smoke025/Pilot-stock024/Pilot-home024 on dev086. The immutable qualifier ledger is `final-qualification-027`.

After root authorizes a completed batch, populate only its explicit evidence-backed rows in a new concrete plan, retain current-status basis Smoke024 (the prerequisite-exclusion rule), fill the actual staging cutoff, then invoke once with a fresh batch name:

```powershell
$I = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/investigation'
$plan = "$I/v27-append-staging/prerequisites-plan-001.json"
$planSha = (Get-FileHash -LiteralPath $plan -Algorithm SHA256).Hash.ToLowerInvariant()
& .\venv\Scripts\python.exe -X utf8 -B "$I/v27-append-staging/stage_append.py" --plan $plan --plan-sha256 $planSha --batch prerequisites-001
```

The concrete plan above does not yet exist. Do not substitute the empty template. The helper authenticates every indexed official job before reading or hashing its outcomes, verifies exact retained official metadata and original report/QA evidence, and denies active/unselected/failed V27 raw outcomes. Failed stages require the existing metadata-only failed-queue schema; they must never masquerade as passing prerequisites. Cross-run diagnoses remain separate hash-only links. Host/transport/raw diagnostic passes do not imply model qualification or task success.

A successful authorized staging run would produce `intent.json`, `prior-history.json`, `official/*.json`, `candidate-history.json`, `qa.json` and `staged-receipt.json` inside an exclusive batch. It never publishes that candidate. Existing or ambiguous batches are retained and not retried in place. No actual staging or outcome read occurred during this preparation.
