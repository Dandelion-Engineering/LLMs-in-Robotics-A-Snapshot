# Source-matched implementation descriptions

`current-implementation-narrative.json` supplies A1, A2, A3 and the conventional C0 baseline's implemented mechanism, LLM role, motion/control and continuity descriptions, plus one shared description. C0 has no model; the shared model description applies only to A1–A3. It retains nine exact Runtime source hashes and line locators. The original proposed designs and canonical map records remain unchanged. [architecture-narrative-corrections.md](architecture-narrative-corrections.md) explains the source-reviewed differences.

The builder accepts optional `--implementation-narrative <JSON>`. `implementation_narrative.py` verifies the narrative shape and, for each implemented or frozen A1/A2/A3/C0 revision, hashes the named source members inside its hash-bound local ZIP attachment. All nine must match one unambiguous bundle. It does not import Runtime code or read live Runtime files. A historical mismatch leaves the original revision text visible; a broken immutable archive identity aborts the build. Proposed revisions never receive this description, even if they have matching attachments. Builds without the option retain the original behavior.

Archives must remain inside the canonical Map, including the registrar's retained frozen copy at `Architecture Map/releases/<release-id>/code-bundle.zip`. The original prepared-artifact ZIP outside Map is not substituted. This preserves the Map validator's attachment-containment rule; root is preparing the registrar copy fix separately. Matching ZIPs in live Runtime, raw evidence, candidate state or elsewhere outside Map are rejected.

The snapshot keeps the narrative's own path/hash/size, expected source identities, exact matching archive/member identities and unmatched revision IDs. The mechanism view identifies the description as source-matched, exposes its binding and preserves the original revision mechanism below it. The comparison table states the description basis. This establishes which implementation the prose describes, not that the prose is automatically proven, the system is qualified or a candidate performs well.

Add this argument to the existing final builder invocation:

```powershell
--implementation-narrative (Join-Path $runbookExperiment 'Engineering Investigation\current-implementation-narrative.json')
```

Retain the narrative JSON, reader, builder and template in the final external control index. If a relevant Runtime source changes, the old narrative must stop matching; review the changed mechanism and create a newly identified narrative artifact when needed. Do not silently refresh its hashes or substitute current files for a historical ZIP. Exact weights and nondefault model settings remain in the run's model manifest; the narrative identifies source defaults explicitly.

## Verification

Implementation and eleven focused synthetic tests were prepared during development003 physics, with execution deferred at that time. They have now passed within the **full Investigation suite: 164 tests in 27.477 seconds**, official job `20260923T115431720868Z-38d34027`, state `succeeded`, exit `0`. The [receipt](../Evidence/queue-receipts/20260923T115431720868Z-38d34027.json) and [validation 002 note](Interface%20validation%20002.md) retain the actual command and result. Tests cover matching implemented/frozen archives, the registrar-style frozen copy, rejected outside-Map archives, baseline-specific narrative, historical source mismatch despite matching live files, proposed/missing/absent narrative behavior, archive tampering, duplicate source members and bundles, missing source identity, builder immutability and UI fallback. Node.js supplies the small UI selection-function check.

The separate continuity display in `analysis.js` names independently verified context and held-cut absence coverage distinctly. It labels empty-cut admissibility as instantaneous and carry absence coverage as not applicable; it changes no counters or eligibility. Its reader/processor source change and tests are owned separately.

The focused commands remain available for a future relevant source change, from the project root; no repeat is required by this documentation update:

```powershell
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement\Engineering Investigation' -p 'test_implementation_narrative.py' -v
.\venv\Scripts\python.exe -X utf8 -B -m unittest discover -s 'Long-Horizon Adaptive Robotics Expirement\Engineering Investigation' -p 'test_workspace.py' -v
```

A later queued production build and browser inspection must confirm the selected revision's matching/unmatched state. The production HTML remains the earlier build; these checks have not yet been performed against the new source. The passing synthetic suite contains no actual scored data.
