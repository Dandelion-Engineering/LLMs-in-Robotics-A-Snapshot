# Validation extraction and assessment coordinator

[derive_validation.ps1](derive_validation.ps1) is prepared for root source review and has **not run**. The completed `derive_construction.ps1` is unchanged. Its queue/PID/receipt functions are retained verbatim; the new driver changes explicit inputs, output names and the four-job sequence. No actual screen, active output or evidence trace was read to prepare it.

Launch only after **both** original parking1 and parking2 physical validation screens have naturally completed and their official succeeded/0 receipts are retained. A first successful screen alone is insufficient. The driver requires six explicit input paths and rejects a missing/unsuccessful receipt, duplicate physical job IDs, an unexpected rule path, existing outputs, or another pending/active queue job. It never submits a physical validation or alters a rule.

The completed parking1 receipt is `20260923T101804870942Z-e21545c0`; root reports parking2 active as `20260923T102107481352Z-c4ee3b98`. After parking2 naturally completes and root retains its official succeeded/0 receipt, the following native PowerShell command reads each actual screen path from its official command arguments. It does not read an active screen or invoke queue status:

```powershell
$validationProject = 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics'
$validationExperiment = Join-Path $validationProject 'Long-Horizon Adaptive Robotics Expirement'
$validationRuleRoot = Join-Path $validationExperiment 'Evidence\derived\recovery-provisional-001'
$officialParking1Receipt = Join-Path $validationExperiment 'Evidence\queue-receipts\20260923T101804870942Z-e21545c0.json'
$officialParking2Receipt = Join-Path $validationExperiment 'Evidence\queue-receipts\20260923T102107481352Z-c4ee3b98.json'
function Completed-ValidationScreen([string]$ReceiptPath) {
  $receipt = Get-Content -Raw -LiteralPath $ReceiptPath | ConvertFrom-Json
  if ($receipt.state -ne 'succeeded' -or $null -eq $receipt.exit_status -or $receipt.exit_status -ne 0) {
    throw 'Both original validation receipts must establish succeeded/0'
  }
  $arguments = [string[]]$receipt.argv
  $position = [Array]::IndexOf($arguments, '--output')
  if ($position -lt 0 -or $position + 1 -ge $arguments.Count) { throw 'Physical screen output argument absent' }
  return $arguments[$position + 1]
}
$completedParking1Screen = Completed-ValidationScreen $officialParking1Receipt
$completedParking2Screen = Completed-ValidationScreen $officialParking2Receipt
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoLogo -NoProfile -File `
  (Join-Path $validationExperiment 'Engineering Investigation\derive_validation.ps1') `
  -Parking1Screen $completedParking1Screen -Parking1Receipt $officialParking1Receipt `
  -Parking1Rule (Join-Path $validationRuleRoot 'parking1\provisional-rule.json') `
  -Parking2Screen $completedParking2Screen -Parking2Receipt $officialParking2Receipt `
  -Parking2Rule (Join-Path $validationRuleRoot 'parking2\provisional-rule.json') `
  -Suffix '001'
```

The four separate installed-queue payloads are:

1. `extract_screen.py --screen <parking1 screen> --queue-receipt <parking1 official receipt> --output <parking1 extraction>`.
2. The same extractor with parking2's screen/receipt/output.
3. `assess_validation.py --rule <unchanged parking1 rule> --validation-extraction <parking1 extraction.json> --validation-receipt <parking1 physical receipt> --extraction-receipt <actual official parking1 extraction receipt> --output <parking1 assessment>`.
4. The same assessor with parking2's matching inputs.

Both helpers retain their own exact `queued_job(expected_script=__file__)` guards. The driver is an external coordinator, not a queued wrapper or an imported-helper bypass. The assessor independently binds the rule, original construction evidence, validation source/archive and both supplied receipts. Coordinator success cannot substitute for those checks.

Fresh outputs under `D:\CodexEvidence\LLMs-in-Robotics` are `recovery-validation-extraction-parking1-001`, `recovery-validation-extraction-parking2-001`, `recovery-validation-assessment-parking1-001`, `recovery-validation-assessment-parking2-001`, and `recovery-validation-derivation-001` for coordinator metadata. Official terminal receipts use exclusive creation in the existing experiment `Evidence/queue-receipts/<actual-id>.json`. There is no overwrite or automatic resume.

The driver first observes the retained worker/child PIDs from **both** physical receipts. While each derivation is active it uses only read-only state and targeted CIM queries for retained job/worker-lease PIDs, polling every 10 seconds and reporting progress within 30 seconds. A terminal own job, no other pending/active job, absent observed PIDs and absent worker/state lock files are required before an official status call. The official receipt must match the exact queued command and observed terminal identity before the next job is submitted. No broad process enumeration, kill, cancel, repair or queue-state write is added. PID reuse blocks conservatively, and a timeout stops without touching the processes.

The coordinator, queue CLI, extractor, assessor, bundle/compatibility helpers, release runner, both rules and both screen receipts are hashed before submission and checked between jobs. Source holds must continue until all four jobs finish. The [shared queue limitation](../Batch%2001/Queue%20Limitation.md) remains: this does not repair the queue's internal Windows liveness check or guarantee safety against an uncoordinated other project's concurrent submission.

A queue failure stops the sequence with available official receipts/logs preserved. An assessor's `fail` or `unknown` scientific disposition is retained unchanged even when its derivation exits successfully. `coordinator-complete.json` means only four successful derivation jobs with unchanged held inputs; it grants no qualification or scored readiness. Root must inspect both assessment reports before any later acceptance.

Prepared driver SHA-256: `54806bdf426c9a39afe420a8a45fdcb2ecea0c270833ca68a4d94813ac1f6377`. No syntax execution, synthetic test, queue call, native work or real evidence processing was performed during this preparation.

A second source-only reviewer found no concrete parameter, receipt or queue-contract delta issue. Parking1's completed official receipt was read to make the invocation concrete; parking2's active output was not read. This review is not an execution result.
