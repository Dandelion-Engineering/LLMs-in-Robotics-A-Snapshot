# Sequential construction derivation coordinator

[derive_construction.ps1](derive_construction.ps1) is prepared for source review only; it has not been executed. It is an external PowerShell coordinator, **not another queued wrapper**. Both `extract_screen.py` and `compact_construction_corridors.py` call `queued_job(expected_script=__file__)`, which checks the actual Python entrypoint and installed queue argv. Nesting their calls in one queued Python script would fail that contract. No helper or queue authorization was changed.

After construction 004 naturally completes and root retains its official succeeded/0 receipt, launch from native PowerShell:

```powershell
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoLogo -NoProfile -File `
  'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Engineering Investigation\derive_construction.ps1' `
  -Screen 'D:\CodexEvidence\LLMs-in-Robotics\recovery-construction-004' `
  -ScreenReceipt 'C:\Users\cresp\Documents\Dandelion Engineering\LLMs in Robotics\Long-Horizon Adaptive Robotics Expirement\Evidence\queue-receipts\20260923T095814743094Z-085c91b4.json' `
  -Suffix '002'
```

This command is prospective: construction 004 is active when this handoff is authored. Do not launch until official success. The coordinator refuses an existing metadata/output directory, so it is not an automatic resume mechanism. Keep the helpers and their listed dependencies held through all five derivations.

It submits, in order, the unchanged extractor, compact parking1, compact parking2, dossier parking1 and dossier parking2. Each is a separate exact installed-queue command with its own official receipt. The dossier helper does not implement a queue guard itself; it still runs as a separate queued job here and retains its existing extracted-file hashes. The extractor retains raw/source/receipt verification and the compact helper independently rebinds the extraction. The coordinator does not replace those checks or reinterpret unknown/failed measurements.

The new D-drive outputs are:

- `recovery-final-construction-extraction-002`
- `recovery-final-compact-parking1-002` and `recovery-final-compact-parking2-002`
- `recovery-final-construction-dossier-parking1-002` and `recovery-final-construction-dossier-parking2-002`
- `recovery-final-derivation-002` for submission captures, stderr, source inventory and coordinator completion/stopped metadata.

Official terminal receipts go to the existing experiment `Evidence/queue-receipts/<actual-job-id>.json`, using exclusive file creation. The coordinator passes the extractor's actual official receipt to both compact jobs. Existing outputs and receipts are never overwritten. All paths are absolute local paths; output ancestors containing reparse points are refused.

While a job is active, the coordinator only reads queue state and uses targeted `Get-CimInstance Win32_Process -Filter 'ProcessId = …'` queries for retained screen/job/worker-lease PIDs. Polls wait 10 seconds; progress prints at most 30 seconds apart. It requires a terminal owned job, no other pending/active job, all observed PIDs absent, and both worker/state lock files absent before an official `status` command. Then it verifies receipt identity/argv/state against the observed job and requires succeeded/0 before submitting the next stage. PID reuse blocks progress conservatively. There are no kill, cancel, repair, broad process enumeration or direct queue-state writes. A per-stage observation timeout stops without touching processes.

Every helper, the queue CLI, this coordinator, and the supplied screen receipt are hashed before launch and checked between stages. A helper-source change stops further derivations after retaining the finished job's official receipt; a changed queue CLI stops without invoking it. Failures preserve available logs/receipts and write `coordinator-stopped.json`. A success marker means only that all five queue jobs succeeded with held source inputs; inspection of compact completeness, actual blockers, source identities and provisional rules remains required. It grants no qualification or scored readiness.

The [existing queue limitation](../Batch%2001/Queue%20Limitation.md) remains. This coordinator avoids additional queue calls while an observed worker is alive; it does not repair the installed queue's internal Windows liveness implementation or create a global lock against an uncoordinated other project's submission. An ambiguous submission must be reconciled from retained state/logs rather than blindly rerun. Source review and later controlled use are distinct from execution validation; no actual queue call, evidence processing or physics was performed to prepare this driver.
