# Release Analysis 003

The collector, analyzer and their two test files are byte-identical copies from Release Analysis 002. They retain the original Runtime root, unchanged statistical estimates/settings, canonical correction selection and exact source/input lineage. Engineering Investigation 003 explicitly expects these new tool paths. No frozen 002 file changed.

The r3 coordinator is separately retained at `../Release Environment Repair 001/coordinator`. It uses the original Release Analysis/measure_retention.py path and preserved receipt/capacity/queue/claim guards; no new retention measurement is claimed. No sealer, generated outputs or previous decisions were copied into this folder.

Tests are deferred to root's owned queue:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Analysis 003' -p 'test_*.py' -v
```

Interfaces remain `collect_results.py --release-dir ... --output ... --complete` and `analyze_results.py --release-dir ... --selected-results ... --output-dir ...`. Use fresh r3 outputs. `versioned-copy-manifest.json` lists exact prior/new byte identities and new-file hashes; its self-hash is excluded. This folder launches no job, creates no release or seed and grants no gate.
