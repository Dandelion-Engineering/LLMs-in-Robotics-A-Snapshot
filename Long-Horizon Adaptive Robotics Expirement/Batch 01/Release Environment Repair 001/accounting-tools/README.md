# R3 development accounting snapshot — prepared, not executed

Run `snapshot_selection.py` through the installed compute queue **after** the actual A3-007/008 environment pair has finished and both canonical terminal results have been appended by the existing `record_attempt.finish` workflow. No successful task outcome is required: failures count and remain visible. Keep all inputs stable until the official queue completion receipt is saved.

The queue command payload, from the project root, is:

```powershell
venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Environment Repair 001/accounting-tools/snapshot_selection.py"
```

Default output is the fresh `Batch 01/selection-evidence-r3-001` folder. The helper verifies exact queue ownership using the current Runtime's `release_runner.queued_job`. It neither submits queue work nor changes canonical records. Any failure leaves a partial folder and a `snapshot-failure.json`; use a newly named direct child of `Batch 01` via `--output` for a separately authorized retry. Never delete, fill in, or overwrite a failed snapshot. A complete snapshot still needs root's saved successful official queue receipt; its `queue_job_id` binds that receipt.

The fixed expected development set is 31 attempts and 32 result records, including the retained C0-002 correction. Counts by C0/A1/A2/A3 are 13/6/4/8, leaving 47/54/56/52 of each unchanged 60-episode ceiling. Missing, unrun, additional, or ambiguous results cause a refusal. Selection uses the exact `current_result` function from `Release Analysis 003/collect_results.py`, loaded by AST with its complete source bytes retained. Superseded records remain in the full canonical copy. A3-007/008 are explicitly post-closure common environment checks; their outcomes do not reopen policy tuning.

The two registered retired evaluation attempts are a separate accounting group: `batch01-eval-r1-C24-rep2-A1-persistent` and `batch01-eval-r2-C24-rep2-A1-persistent`. They are excluded from development effort counts and r3 inference. Their original canonical assessments and reference metadata remain visible. Unlaunched schedule entries do not become failures or invented result records. The two retirement documents are copied as provenance. No concealed evaluation manifest, raw result/event/trajectory stream, model binary, or candidate-private state is opened or rehashed.

`accounting.json` contains actual all-stage canonical counts, development totals and per-entrant effort, exact current-result records and supersession chains, retired evaluation dispositions, canonical input identities, and current Runtime source hashes. Actual revision counts are computed from canonical records; no fixed all-stage revision total is assumed. Canonical raw-result references are copied as metadata only. Engineering hours remain unmeasured and original 12-hour compliance remains unknown; equal realized development effort is not claimed. Root binds the final opportunity ledger separately.

Full canonical JSONL bytes, schema/map/selection source provenance, the prior accounting/index, development registration manifests, and all current `Runtime/*.py` files are copied. Each historical `runtime.zip` stays at its original immutable path; the helper verifies the archive's canonical hash, exact member inventory, and every declared Python member hash. The old 29-attempt snapshot is read only. Its canonical files must remain an exact prefix of the new canonical files. Every read metadata/source/archive input and the Runtime inventory must remain unchanged before publication. Paths inside copied canonical records still resolve from the original Architecture Map root.

`snapshot-files.json` indexes all files produced before itself, including `accounting.json`; it excludes itself to avoid a circular hash. It includes `queue_job_id`. The sealer should require complete status, no failure marker, the official successful receipt for that exact job, exact 31/32 development totals, both retired evaluation IDs, and unchanged current Runtime hashes. Rehash the indexed copies before use. This accounting grants no physical validity, restart qualification, selection, freeze, or scored readiness.

Preparation validation is limited to source inspection and Python syntax compilation without importing or running the helper. The first actual snapshot is performed only by root's queued invocation after canonical finalization.
