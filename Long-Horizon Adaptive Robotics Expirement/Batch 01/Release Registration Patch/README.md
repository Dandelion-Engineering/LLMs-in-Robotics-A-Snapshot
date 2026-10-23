# Release registration attachment fix

Applied after the original development003 physics job ended. Seven focused tests passed in 0.878 seconds under official successful job `20260923T115600352214Z-8e78d523`; the same job passed the eight retention-inventory tests. Root verified the exact base and candidate hashes before copying the candidate bytes into `Runtime/release_runner.py`. [applied-001.json](applied-001.json) retains the application time and identities. Full Runtime regression verification remains pending until the remaining common restart prerequisites are settled. No scored release has been created. The staging account below describes preparation before application.

The current registrar uses an external prepared code ZIP and freeze JSON as revision attachments. `Architecture Map/map.py:177–183` correctly requires revision attachment files to exist inside the Map. This candidate preserves that boundary and copies the exact bytes into `Architecture Map/releases/<release_id>/code-bundle.zip` and `freeze.json` before the first revision append. All four architecture revisions reference the same verified files. Existing revision attachments must match before reuse.

The code ZIP hash comes from the freeze-pinned code index; the freeze hash remains the run's original `freeze_sha256`. The helper validates original bytes, uses exclusive binary creation, flushes the copies, verifies exact final bytes, and rechecks the original. Existing copies are reusable only when exact. Pre-existing partial/tampered targets and symlink/reparse components fail closed. An exclusive-create race is accepted only if the competing file contains the exact expected bytes. No overwrite, cleanup, retry, new run, seed change or evidence move is introduced; failed or partial copies remain for inspection. Run, protocol, scenario, seed and artifact-index authority references still point to their original locations.

Files are **staged only**; Runtime and the actual Map have not been edited. The stage script only transforms guarded source text and writes into a fresh direct subfolder here. It does not import the candidate, register anything, or execute tests.

- Exact base Runtime SHA-256: `8473087dfba3551fcc742dd6a45b8f0d6c0690a1cb5e804dc8acd30f99748ac6`.
- Unapplied candidate SHA-256: `aa0a5b897d236e24f1640cea6c7cf39870ce4457ee12027c4314dcb0a4c0af8c`.
- Original bytes, candidate bytes and source-stage record: `staged-001/`.
- Candidate-building specification: `stage_registration_patch.py` plus `registration_fragment.py.txt`.

Seven focused synthetic tests are prepared in `test_release_registration_patch.py`. They exercise the real Map validator against externally prepared source/freeze files, reproduce the original outside-Map refusal, check four-architecture and same-revision reuse, preserve original authority bytes/references, reject tampered/partial copies and changed source, simulate exact/partial competing creators, reject unsafe/reparse targets, and verify the exact staging guard. **Execution is deferred until physical timing work ends.**

Deferred test command from the project root, using the installed queue:

```text
venv\Scripts\python.exe -X utf8 -B -m unittest discover -s "Long-Horizon Adaptive Robotics Expirement/Batch 01/Release Registration Patch" -p "test_release_registration_patch.py" -v
```

After root review and authorization to integrate, require the current Runtime byte hash to equal the base above, require the candidate hash above, and copy only `staged-001/release_runner.candidate.py` bytes onto `Runtime/release_runner.py`. Retained base bytes provide the exact integration audit. Then run the appropriate queued Runtime checks before preparing fresh release artifacts; the code index must identify the resulting Runtime bytes. This note does not authorize integration or a scored attempt.
