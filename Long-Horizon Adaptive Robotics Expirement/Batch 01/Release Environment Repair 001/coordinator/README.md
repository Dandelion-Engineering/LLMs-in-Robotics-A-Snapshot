# R3 external release coordinator

run_release_series.ps1, test_run_release_series.ps1, run_regressions.py and all three retained fixtures are byte-identical copies from Release Infrastructure Repair 001/coordinator. This new folder has the same three-parent depth to the experiment root, so the existing Runtime/project/receipt paths resolve identically. The release is supplied by `-ReleaseDir`; no r3 manifest or seed is created here.

The original `Batch 01/Release Analysis/measure_retention.py` binding is unchanged. Official terminal-plus-owned-PID/lock checks, nested queue receipt parsing, finalization-before-next-batch, claimed-attempt rejection, source holds, full remaining-cap capacity calculation, and stop-on-integrity/incident behavior are unchanged. R1/r2 files and dispositions are not modified or resumed.

Root may queue the same bounded dual-PowerShell regression launcher after preparation:

```powershell
.\venv\Scripts\python.exe -X utf8 -B 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Environment Repair 001/coordinator/run_regressions.py'
```

This check itself does not execute the coordinator or call the queue. No check was run during copying. The original receipt fixtures remain synthetic/regression inputs, not new r3 receipts. Root starts the actual coordinator only after the r3 freeze/release and all prerequisites exist, using its unchanged mandatory arguments and the new exact coordinator path in direct readiness references.

provenance.json binds original and copied file identities. The complete cross-folder inventory is `../../Release Analysis 003/versioned-copy-manifest.json`. No gate, retry or incident waiver is introduced.
