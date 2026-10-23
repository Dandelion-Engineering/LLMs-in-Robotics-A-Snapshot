# Imported userland diagnosis

Prepared only; no execution or distro modification. The held builder/verifier remain unchanged. Their successful build003 versions are preserved in `userland-tools/source-version-004`.

Queue this separate read-only diagnostic after the completed import attempt:

```powershell
.\venv\Scripts\python.exe -X utf8 -B "Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Environment Repair 001/installation-tools/diagnose_import.py" --distribution LLMs-Robotics-Candidate-001 --manifest "Long-Horizon Adaptive Robotics Expirement/Evidence/runtime-environments/candidate-linux-003/manifest.json" --manifest-sha256 983117c1fac0cb04c188da5d947a6f8cf04b72ef694e48584374103d5650d8a6 --output-dir "Long-Horizon Adaptive Robotics Expirement/Evidence/runtime-environments/import-diagnostic-001"
```

The wrapper checks its installed queue ownership before reading the complete tree. It captures the actual default user's UID/GID/groups/name/home/shell, then runs read-only static inspection as project-distro root to read protected paths. Two complete inventories use the held userland helper's declared scopes and exact mode/owner/type/link/content semantics. The report retains every extra, missing and changed entry, required-absence violations, symlink targets and resolution results. Observed external links resolving to `/init` bind that file's exact bytes; other outside targets are reported without reading their contents. No WSL additions are excluded, accepted or removed.

Fresh output contains `started.json`, `default-user.json`, `tree-before.json`, `tree-after.json`, `diagnostic.json`, and `host-invocation.json`. Complete status means the metadata observation completed with unchanged tree/linked-init/source/manifest identities, not that the imported tree matches or a WSL integration overlay was accepted. The original manifest remains authoritative for reporting differences. Actual acceptance requires a separate root decision; this helper provides no waiver.

The static reads have a600s bound and external WSL process660s bound. Source/manifest refs are recorded before and after. Official queue receipt must establish successful completion before using the report. No tests, rootfs rebuild, additional distro import, Runtime edit, seed read or physics occurs here.
